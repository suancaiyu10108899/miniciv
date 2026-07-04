# prototype/eval_matrix.py — 并行全矩阵评估, ProcessPoolExecutor
# 用法:
#   python -m prototype.eval_matrix --games 500 --size 15 --workers 24
#   python -m prototype.eval_matrix --paired --ais greedy,greedy --games 500 --size 15 --output eval_paired/rush
#
# Paired mode: for each seed, run TWO games swapping P0/P1 roles.
# Reports AI_A winrate (paired), AI_B winrate (paired), P0 winrate, stddev, 95% CI.

import argparse, json, os, random, sys, time, math
from concurrent.futures import ProcessPoolExecutor, as_completed
from prototype.game import init_game, step_game
from prototype.eval import load_ai, AI_MODULES
import prototype.cleanup  # atexit handler for orphan process cleanup
from prototype.constants import CITY_HP, CITY_DAMAGE


def _apply_city_overrides(city_hp, city_damage):
    """Apply city HP/damage overrides in the worker process. Idempotent after first call."""
    if not hasattr(_apply_city_overrides, "_applied"):
        _apply_city_overrides._applied = False
    if _apply_city_overrides._applied:
        return
    if city_hp is not None or city_damage is not None:
        import importlib as _il
        import prototype.constants as _c
        if city_hp is not None:
            _c.CITY_HP = city_hp
        if city_damage is not None:
            _c.CITY_DAMAGE = city_damage
        import prototype.game as _g
        _il.reload(_g)
    _apply_city_overrides._applied = True


def _run_one(args):
    """单局运行(独立函数, 用于进程池)"""
    # args: (seed, ai0_name, ai1_name, size, gen, max_turns, [mode, [city_hp, city_damage]])
    seed, ai0_name, ai1_name, size, gen, max_turns = args[:6]
    mode = args[6] if len(args) >= 7 else "normal"
    city_hp = args[7] if len(args) >= 8 else None
    city_damage = args[8] if len(args) >= 9 else None
    _apply_city_overrides(city_hp, city_damage)
    # Apply mode patches before game init
    gs = _make_game(seed, size, gen, mode)
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))
    return _extract_result(gs, seed, ai0_name, ai1_name)


def _make_game(seed, size, gen, mode="normal"):
    """Create a game state, applying mode-specific patches."""
    gs = init_game(seed=seed, size=size, generator_id=gen)

    if mode == "combat_only":
        _apply_combat_only_patch(gs)
    elif mode == "econ_only":
        _apply_econ_only_patch()
    # normal mode: no changes

    return gs


def _apply_combat_only_patch(gs):
    """Combat-only: no research, no unit production. Start with 5 infantry + 3 cavalry."""
    # Remove all starting units
    gs.units = []
    gs.dead_units = []

    # Disable research by patching tick_research to a no-op
    for pid in (0, 1):
        def _noop_tick():
            return None
        gs.techs[pid].tick_research = _noop_tick
        # Also clear researching so AI available_to_research returns options
        # (doesn't matter since research action won't be processed -- no econ for afford check)
        gs.techs[pid].researching = None

    # Add combat units for P0
    _add_starting_army(gs, 0, gs.cities[0].x, gs.cities[0].y)
    # Add combat units for P1
    _add_starting_army(gs, 1, gs.cities[1].x, gs.cities[1].y)


def _add_starting_army(gs, pid, cx, cy):
    """Add 5 infantry + 3 cavalry for a player."""
    from prototype.unit import Unit
    unit_types = ["infantry"] * 5 + ["cavalry"] * 3
    for utype in unit_types:
        placed = False
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = (cx + dx) % gs.size, (cy + dy) % gs.size
            from prototype.mapgen import get_terrain
            from prototype.terrain import Terrain
            t = get_terrain(gs.grid, nx, ny)
            if t == Terrain.WATER:
                continue
            occupied = any(u.x == nx and u.y == ny for u in gs.units)
            if not occupied:
                gs.units.append(Unit.create(utype, pid, nx, ny))
                placed = True
                break
        if not placed:
            # Fallback: place near city on any passable terrain
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = (cx + dx) % gs.size, (cy + dy) % gs.size
                    from prototype.mapgen import get_terrain
                    from prototype.terrain import Terrain
                    t = get_terrain(gs.grid, nx, ny)
                    if t == Terrain.WATER:
                        continue
                    occupied = any(u.x == nx and u.y == ny for u in gs.units)
                    if not occupied:
                        gs.units.append(Unit.create(utype, pid, nx, ny))
                        placed = True
                        break
                if placed:
                    break


def _apply_econ_only_patch():
    """Econ-only: disable all combat by patching module-level references."""
    # Patch combat module (sets attributes on the module object)
    import prototype.combat as combat_mod
    import prototype.game as game_mod
    import importlib as _il

    def _noop_melee(attacker, defender, terrain_att, terrain_def,
                    attacker_just_charged=False):
        return {"att_damage": 0, "def_damage": 0,
                "attacker_alive": True, "defender_alive": True}

    def _noop_ranged(archer, target, terrain_target):
        return {"damage": 0, "target_alive": True}

    def _noop_occupy(unit, city):
        return 0

    # First, patch the combat module
    combat_mod.resolve_melee = _noop_melee
    combat_mod.resolve_ranged = _noop_ranged
    combat_mod.city_occupation_damage = _noop_occupy

    # Then reload game.py so its `from prototype.combat import ...` gets the patched versions
    _il.reload(game_mod)

    # After reload, game.py has fresh imports from combat_mod (now patched).
    # But reload also resets combat_mod to its original state.
    # Re-patch combat_mod so future imports see the patches.
    combat_mod.resolve_melee = _noop_melee
    combat_mod.resolve_ranged = _noop_ranged
    combat_mod.city_occupation_damage = _noop_occupy


def _count_units_by_type(units, pid, unit_type, alive_only=True):
    """统计指定类型单位数量。"""
    if alive_only:
        return sum(1 for u in units if u.player_id == pid and u.alive and u.unit_type == unit_type)
    return sum(1 for u in units if u.player_id == pid and u.unit_type == unit_type)


def _count_facilities(gs, pid):
    """统计某方设施数。"""
    from prototype.mapgen import get_facility
    count = 0
    for y in range(gs.size):
        for x in range(gs.size):
            f = get_facility(gs.grid, x, y)
            if f is not None and f.player_id == pid:
                count += 1
    return count


def _extract_result(gs, seed, ai0_name, ai1_name):
    """Extract result dict from a finished game state (with per-unit-type stats)."""
    e0, e1 = gs.economies
    unit_types = ["infantry", "cavalry", "archer", "scout", "worker"]
    result = {
        "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
        "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_hp": gs.cities[0].hp, "p1_hp": gs.cities[1].hp,
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
        # Economic metrics
        "p0_food": e0.food, "p0_wood": e0.wood, "p0_gold": e0.gold,
        "p1_food": e1.food, "p1_wood": e1.wood, "p1_gold": e1.gold,
        "p0_total_resources": e0.food + e0.wood + e0.gold,
        "p1_total_resources": e1.food + e1.wood + e1.gold,
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
        "p0_units_produced": sum(1 for u in gs.units if u.player_id == 0 and u.alive) + sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_units_produced": sum(1 for u in gs.units if u.player_id == 1 and u.alive) + sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_facilities": _count_facilities(gs, 0),
        "p1_facilities": _count_facilities(gs, 1),
    }
    # Per-unit-type stats
    for ut in unit_types:
        result[f"p0_{ut}_alive"] = _count_units_by_type(gs.units, 0, ut, alive_only=True)
        result[f"p1_{ut}_alive"] = _count_units_by_type(gs.units, 1, ut, alive_only=True)
        result[f"p0_{ut}_dead"] = _count_units_by_type(gs.dead_units, 0, ut, alive_only=False)
        result[f"p1_{ut}_dead"] = _count_units_by_type(gs.dead_units, 1, ut, alive_only=False)
    return result


def _run_one_paired(args):
    """Paired run: two games per seed, swapping P0/P1 roles.
    Returns dict with both games' results and paired stats.
    Optional extra elements: mode, city_hp, city_damage."""
    seed, ai_a_name, ai_b_name, size, gen, max_turns = args[:6]
    mode = args[6] if len(args) >= 7 else "normal"
    city_hp = args[7] if len(args) >= 8 else None
    city_damage = args[8] if len(args) >= 9 else None
    _apply_city_overrides(city_hp, city_damage)

    ai_a = load_ai(ai_a_name)
    ai_b = load_ai(ai_b_name)

    # Game 1: AI_A=P0, AI_B=P1
    gs1 = _make_game(seed, size, gen, mode)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    while gs1.winner is None and gs1.turn < max_turns:
        step_game(gs1, ai_a(gs1, 0, rng0), ai_b(gs1, 1, rng1))
    e1_0, e1_1 = gs1.economies

    # Game 2: AI_A=P1, AI_B=P0 (swapped roles, same map via same seed)
    gs2 = _make_game(seed, size, gen, mode)
    rng0 = random.Random(seed + 2_000_000)
    rng1 = random.Random(seed + 2_000_001)
    while gs2.winner is None and gs2.turn < max_turns:
        step_game(gs2, ai_b(gs2, 0, rng0), ai_a(gs2, 1, rng1))
    e2_0, e2_1 = gs2.economies

    def _game_dict(gs, econ0, econ1, ai0_name, ai1_name, seed, ai_a_p0):
        """Build per-game dict with full economic metrics."""
        p0_alive = sum(1 for u in gs.units if u.player_id == 0 and u.alive)
        p1_alive = sum(1 for u in gs.units if u.player_id == 1 and u.alive)
        p0_dead = sum(1 for u in gs.dead_units if u.player_id == 0)
        p1_dead = sum(1 for u in gs.dead_units if u.player_id == 1)
        result = {
            "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
            "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
            "turns": gs.turn,
            "p0_hp": gs.cities[0].hp, "p1_hp": gs.cities[1].hp,
            "p0_alive": p0_alive, "p1_alive": p1_alive,
            "p0_dead": p0_dead, "p1_dead": p1_dead,
            "p0_techs": len(gs.techs[0].completed), "p1_techs": len(gs.techs[1].completed),
            "p0_food": econ0.food, "p0_wood": econ0.wood, "p0_gold": econ0.gold,
            "p1_food": econ1.food, "p1_wood": econ1.wood, "p1_gold": econ1.gold,
            "p0_total_resources": econ0.food + econ0.wood + econ0.gold,
            "p1_total_resources": econ1.food + econ1.wood + econ1.gold,
            "p0_construction": gs.techs[0].construction_count(),
            "p1_construction": gs.techs[1].construction_count(),
            "p0_units_produced": p0_alive + p0_dead,
            "p1_units_produced": p1_alive + p1_dead,
            "p0_facilities": _count_facilities(gs, 0),
            "p1_facilities": _count_facilities(gs, 1),
            "ai_a_p0": ai_a_p0, "ai_b_p1": not ai_a_p0,
        }
        # Per-unit-type stats
        for ut in ["infantry", "cavalry", "archer", "scout", "worker"]:
            result[f"p0_{ut}_alive"] = _count_units_by_type(gs.units, 0, ut, True)
            result[f"p1_{ut}_alive"] = _count_units_by_type(gs.units, 1, ut, True)
            result[f"p0_{ut}_dead"] = _count_units_by_type(gs.dead_units, 0, ut, False)
            result[f"p1_{ut}_dead"] = _count_units_by_type(gs.dead_units, 1, ut, False)
        return result

    g1 = _game_dict(gs1, e1_0, e1_1, ai_a_name, ai_b_name, seed, True)
    g2 = _game_dict(gs2, e2_0, e2_1, ai_b_name, ai_a_name, seed + 1_000_000, False)

    # Paired stats: per-seed, does AI_A win both, split, or AI_B win both
    g1ai_a_won = (g1["winner"] == 0)   # game1: AI_A=P0
    g2ai_a_won = (g2["winner"] == 1)   # game2: AI_A=P1

    return {
        "seed": seed,
        "ai_a": ai_a_name, "ai_b": ai_b_name,
        "game1": g1,
        "game2": g2,
        "g1_winner": g1["winner"], "g2_winner": g2["winner"],
        "g1_vtype": g1["victory_type"], "g2_vtype": g2["victory_type"],
        "ai_a_wins": (1 if g1ai_a_won else 0) + (1 if g2ai_a_won else 0),
        "ai_b_wins": (1 if not g1ai_a_won else 0) + (1 if not g2ai_a_won else 0),
        "p0_wins": (1 if g1["winner"] == 0 else 0) + (1 if g2["winner"] == 0 else 0),
        "p1_wins": (1 if g1["winner"] == 1 else 0) + (1 if g2["winner"] == 1 else 0),
        "both_won_by_ai_a": g1ai_a_won and g2ai_a_won,
        "both_won_by_ai_b": (not g1ai_a_won) and (not g2ai_a_won),
        "split": g1ai_a_won != g2ai_a_won,
        "tot_turns": g1["turns"] + g2["turns"],
        "tot_p0_dead": g1["p0_dead"] + g2["p0_dead"],
        "tot_p1_dead": g1["p1_dead"] + g2["p1_dead"],
        "tot_conquest": (1 if str(g1["victory_type"]) == "conquest" else 0) +
                         (1 if str(g2["victory_type"]) == "conquest" else 0),
        "tot_construction": (1 if str(g1["victory_type"]) == "construction" else 0) +
                             (1 if str(g2["victory_type"]) == "construction" else 0),
        "tot_tiebreak": (1 if "tiebreak" in str(g1["victory_type"]) else 0) +
                         (1 if "tiebreak" in str(g2["victory_type"]) else 0),
    }


def _ci(p, n):
    """95% CI width for a proportion"""
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def _mean_std(values):
    """Return (mean, stddev) for a list of numbers."""
    n = len(values)
    if n < 2:
        return (sum(values) / n if n else 0.0, 0.0)
    m = sum(values) / n
    v = sum((x - m) ** 2 for x in values) / (n - 1)
    return (m, math.sqrt(v))


def _save_checkpoint(results_by_pair, output_dir, completed, total):
    """Save intermediate results to checkpoint file. Thread-safe enough for single-writer."""
    import json as _json
    ckpt_path = os.path.join(output_dir, "_checkpoint.json")
    # Compact format: just per-pair result counts, no raw game data
    summary = {
        "completed": completed,
        "total": total,
        "pairs": {}
    }
    for (ai_a, ai_b), results in results_by_pair.items():
        n = len(results)
        if n == 0:
            continue
        # Quick winrate summary
        if "ai_a_wins" in results[0]:
            # paired mode
            ai_a_w = sum(r["ai_a_wins"] for r in results)
            summary["pairs"][f"{ai_a}_vs_{ai_b}"] = {"n": n, "ai_a_wins": ai_a_w, "total_games": n * 2}
        else:
            p0w = sum(1 for r in results if r["winner"] == 0)
            summary["pairs"][f"{ai_a}_vs_{ai_b}"] = {"n": n, "p0_wins": p0w}
    with open(ckpt_path, "w") as f:
        _json.dump(summary, f, indent=2)
    # Also print checkpoint confirmation
    pct = completed / total * 100
    print(f"  [checkpoint] {completed}/{total} ({pct:.1f}%) saved to {ckpt_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ais", default="random,greedy,aggressive")
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--output", default="eval_results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--paired", action="store_true", help="Paired eval: swap P0/P1 per seed")
    parser.add_argument("--mode", default="normal",
                        choices=["normal", "combat_only", "econ_only"],
                        help="Game mode for patches (default: normal)")
    parser.add_argument("--save-raw", action="store_true",
                        help="Save per-seed raw game data (paired mode only)")
    parser.add_argument("--city-hp", type=int, default=None,
                        help="Override CITY_HP constant")
    parser.add_argument("--city-damage", type=int, default=None,
                        help="Override CITY_DAMAGE constant")
    args = parser.parse_args()

    ai_names = [a.strip() for a in args.ais.split(",")]
    workers = args.workers or min(30, os.cpu_count() or 4)
    pairs = [(a0, a1) for a0 in ai_names for a1 in ai_names]
    os.makedirs(args.output, exist_ok=True)

    paired = args.paired
    mode_str = "Paired" if paired else "Standard"
    game_plural = "seeds (2 games each)" if paired else "games"
    print(f"=== Eval Matrix ({mode_str}): {len(ai_names)}x{len(ai_names)} x {args.games} {game_plural} ===")
    print(f"Map: {args.size}x{args.size} {args.gen}  Workers: {workers}")
    print()

    # Build task list: use unique pairs (dedup identical names)
    mode = args.mode
    seen_pairs = set()
    unique_pairs = []
    for a0, a1 in pairs:
        key = (a0, a1)
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_pairs.append(key)

    city_hp_ov = args.city_hp
    city_dmg_ov = args.city_damage
    all_tasks = []
    for pair_idx, (a0, a1) in enumerate(unique_pairs):
        for i in range(args.games):
            seed = args.seed + i * 1000 + pair_idx * 100000  # deterministic, no hash()
            task = (seed, a0, a1, args.size, args.gen, args.max_turns)
            extras = []
            if mode != "normal":
                extras.append(mode)
            if city_hp_ov is not None:
                extras.append(city_hp_ov)
            if city_dmg_ov is not None:
                extras.append(city_dmg_ov)
            if extras:
                task = task + tuple(extras)
            all_tasks.append(task)

    run_fn = _run_one_paired if paired else _run_one

    total = len(all_tasks)
    t0 = time.perf_counter()
    results_by_pair = {}
    completed = 0

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_fn, task): task for task in all_tasks}
        for fut in as_completed(futures):
            r = fut.result()
            key = (r["ai0"], r["ai1"]) if not paired else (r["ai_a"], r["ai_b"])
            results_by_pair.setdefault(key, []).append(r)
            completed += 1
            if completed % max(1, total // 10) == 0:
                elapsed = time.perf_counter() - t0
                rate = completed / elapsed
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  {completed}/{total} ({completed/total*100:.0f}%) {rate:.0f}g/s ETA {eta:.0f}s")
            # ── Checkpoint save every 500 completions ──
            if completed % 500 == 0:
                _save_checkpoint(results_by_pair, args.output, completed, total)

    elapsed = time.perf_counter() - t0
    actual_games = total * 2 if paired else total
    print(f"\nDone: {total} seeds ({actual_games} games) in {elapsed:.0f}s ({actual_games/elapsed:.0f} games/s)")

    # Summary
    from prototype.constants import CITY_HP, CITY_DAMAGE
    print(f"\n=== {mode_str} Summary (CITY_HP={CITY_HP} CITY_DAMAGE={CITY_DAMAGE}) ===")

    if paired:
        header = (f"{'AI_A':12s} {'AI_B':12s} {'A_win%':>7s} {'CI':>5s} {'B_win%':>7s} {'CI':>5s} "
                  f"{'P0win%':>7s} {'CI':>5s} {'Conq':>5s} {'Cons':>5s} {'Tie':>5s} {'AvgT':>6s} {'Dead':>5s}")
        print(header)
        print("-" * len(header))
    else:
        header = f"{'P0':12s} {'P1':12s} {'P0win':>7s} {'P1win':>7s} {'Conq':>5s} {'Cons':>5s} {'Tie':>5s} {'AvgT':>6s} {'Dead':>5s}"
        print(header)
        print("-" * len(header))

    all_summaries = []
    # In paired mode, we iterate over all pairs (including same-AI) because
    # the key insight is measuring P0 advantage when both sides use the same agent.
    display_pairs = unique_pairs if paired else pairs
    for key in display_pairs:
        if not paired:
            a0, a1 = key
            results = results_by_pair.get((a0, a1), [])
            n = len(results)
            p0w = sum(1 for r in results if r["winner"] == 0)
            p1w = sum(1 for r in results if r["winner"] == 1)
            cq = sum(1 for r in results if str(r["victory_type"]) == "conquest")
            cs = sum(1 for r in results if str(r["victory_type"]) == "construction")
            tie = n - cq - cs
            avg_t = sum(r["turns"] for r in results) / n if n else 0
            avg_d = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n if n else 0
            p0r = p0w / n if n else 0
            print(f"{a0:12s} {a1:12s} {p0r*100:6.1f}% {p1w/n*100:6.1f}% {cq:5d} {cs:5d} {tie:5d} {avg_t:6.1f} {avg_d:5.1f}")

            fname = f"{a0}_vs_{a1}.json"
            with open(os.path.join(args.output, fname), "w") as f:
                json.dump(results, f, indent=2)

            all_summaries.append({
                "ai0": a0, "ai1": a1, "n": n,
                "p0_winrate": p0r,
                "p1_winrate": p1w / n if n else 0,
                "conquests": cq, "constructions": cs, "tiebreaks": tie,
                "avg_turns": avg_t, "avg_dead": avg_d,
            })
        else:
            ai_a, ai_b = key
            results = results_by_pair.get((ai_a, ai_b), [])
            n = len(results)  # number of paired seeds (each has 2 games)
            if n == 0:
                continue

            # Per-seed stats already computed in _run_one_paired
            ai_a_wins = sum(r["ai_a_wins"] for r in results)
            ai_b_wins = sum(r["ai_b_wins"] for r in results)
            p0_wins = sum(r["p0_wins"] for r in results)
            p1_wins = sum(r["p1_wins"] for r in results)

            total_games = n * 2
            ai_a_wr = ai_a_wins / total_games
            ai_b_wr = ai_b_wins / total_games
            p0_wr = p0_wins / total_games

            # Stddev across seeds of per-seed AI_A winrate
            # Per-seed AI_A wins is 0, 1, or 2. Per-seed rate = wins/2
            seed_rates = [r["ai_a_wins"] / 2 for r in results]
            _, p0_std = _mean_std([r["p0_wins"] / 2 for r in results])
            ai_a_mean, ai_a_std = _mean_std(seed_rates)

            # Victory type rates with stddev
            cq_rates = [r["tot_conquest"] / 2 for r in results]
            cs_rates = [r["tot_construction"] / 2 for r in results]
            tie_rates = [r["tot_tiebreak"] / 2 for r in results]
            cq_mean, cq_std = _mean_std(cq_rates)
            cs_mean, cs_std = _mean_std(cs_rates)
            tie_mean, tie_std = _mean_std(tie_rates)

            # Average turns per game
            all_turns = []
            all_dead = []
            for r in results:
                all_turns.append(r["game1"]["turns"])
                all_turns.append(r["game2"]["turns"])
                all_dead.append(r["game1"]["p0_dead"] + r["game1"]["p1_dead"])
                all_dead.append(r["game2"]["p0_dead"] + r["game2"]["p1_dead"])
            avg_t = sum(all_turns) / total_games if total_games else 0
            avg_d = sum(all_dead) / total_games if total_games else 0

            p0_ci = _ci(p0_wr, total_games)
            ai_a_ci = _ci(ai_a_wr, total_games)
            ai_b_ci = _ci(ai_b_wr, total_games)

            # ── Economic metrics ──
            # AI_A is P0 in g1, P1 in g2. Aggregate across both roles.
            ai_a_units = []
            ai_b_units = []
            ai_a_resources = []
            ai_b_resources = []
            ai_a_construction = []
            ai_b_construction = []
            for r in results:
                g1, g2 = r["game1"], r["game2"]
                # g1: AI_A=P0, AI_B=P1
                ai_a_units.append(g1["p0_units_produced"])
                ai_b_units.append(g1["p1_units_produced"])
                ai_a_resources.append(g1["p0_total_resources"])
                ai_b_resources.append(g1["p1_total_resources"])
                ai_a_construction.append(g1["p0_construction"])
                ai_b_construction.append(g1["p1_construction"])
                # g2: AI_A=P1, AI_B=P0
                ai_a_units.append(g2["p1_units_produced"])
                ai_b_units.append(g2["p0_units_produced"])
                ai_a_resources.append(g2["p1_total_resources"])
                ai_b_resources.append(g2["p0_total_resources"])
                ai_a_construction.append(g2["p1_construction"])
                ai_b_construction.append(g2["p0_construction"])

            au_mean, au_std = _mean_std(ai_a_units)
            bu_mean, bu_std = _mean_std(ai_b_units)
            ar_mean, ar_std = _mean_std(ai_a_resources)
            br_mean, br_std = _mean_std(ai_b_resources)
            ac_mean, ac_std = _mean_std(ai_a_construction)
            bc_mean, bc_std = _mean_std(ai_b_construction)

            # Resource efficiency: winrate per 100 resources (higher = better allocation)
            ai_a_efficiency = round(ai_a_wr / (ar_mean + 1) * 1000, 2) if ar_mean > 0 else 0
            ai_b_efficiency = round(ai_b_wr / (br_mean + 1) * 1000, 2) if br_mean > 0 else 0

            # Per-unit-type aggregation
            unit_types = ["infantry", "cavalry", "archer", "scout", "worker"]
            ai_a_ut_alive = {ut: [] for ut in unit_types}
            ai_a_ut_dead = {ut: [] for ut in unit_types}
            ai_b_ut_alive = {ut: [] for ut in unit_types}
            ai_b_ut_dead = {ut: [] for ut in unit_types}
            for r in results:
                g1, g2 = r["game1"], r["game2"]
                for ut in unit_types:
                    ai_a_ut_alive[ut].append(g1.get(f"p0_{ut}_alive", 0))
                    ai_a_ut_alive[ut].append(g2.get(f"p1_{ut}_alive", 0))
                    ai_a_ut_dead[ut].append(g1.get(f"p0_{ut}_dead", 0))
                    ai_a_ut_dead[ut].append(g2.get(f"p1_{ut}_dead", 0))
                    ai_b_ut_alive[ut].append(g1.get(f"p1_{ut}_alive", 0))
                    ai_b_ut_alive[ut].append(g2.get(f"p0_{ut}_alive", 0))
                    ai_b_ut_dead[ut].append(g1.get(f"p1_{ut}_dead", 0))
                    ai_b_ut_dead[ut].append(g2.get(f"p0_{ut}_dead", 0))

            ai_a_ut_summary = {}
            ai_b_ut_summary = {}
            for ut in unit_types:
                ai_a_ut_summary[ut] = {
                    "alive_mean": round(sum(ai_a_ut_alive[ut]) / len(ai_a_ut_alive[ut]), 2) if ai_a_ut_alive[ut] else 0,
                    "dead_mean": round(sum(ai_a_ut_dead[ut]) / len(ai_a_ut_dead[ut]), 2) if ai_a_ut_dead[ut] else 0,
                }
                ai_b_ut_summary[ut] = {
                    "alive_mean": round(sum(ai_b_ut_alive[ut]) / len(ai_b_ut_alive[ut]), 2) if ai_b_ut_alive[ut] else 0,
                    "dead_mean": round(sum(ai_b_ut_dead[ut]) / len(ai_b_ut_dead[ut]), 2) if ai_b_ut_dead[ut] else 0,
                }

            # Per-victory-type P0
            p0_by_vtype = {"conquest": {"p0": 0, "total": 0},
                          "construction": {"p0": 0, "total": 0},
                          "tiebreak": {"p0": 0, "total": 0}}
            for r in results:
                for gkey in ["game1", "game2"]:
                    g = r[gkey]
                    vt = str(g.get("victory_type", "") or "")
                    if vt == "conquest":
                        cat = "conquest"
                    elif vt == "construction":
                        cat = "construction"
                    else:
                        cat = "tiebreak"
                    p0_by_vtype[cat]["total"] += 1
                    if g["winner"] == 0:
                        p0_by_vtype[cat]["p0"] += 1

            p0_vtype_summary = {}
            for cat in p0_by_vtype:
                t = p0_by_vtype[cat]["total"]
                p0_vtype_summary[cat] = {
                    "p0_winrate": round(p0_by_vtype[cat]["p0"] / t, 4) if t > 0 else 0,
                    "n_games": t,
                }

            print(f"{ai_a:12s} {ai_b:12s} {ai_a_wr*100:6.1f}% {ai_a_ci*100:4.1f}% "
                  f"{ai_b_wr*100:6.1f}% {ai_b_ci*100:4.1f}% "
                  f"{p0_wr*100:6.1f}% {p0_ci*100:4.1f}% "
                  f"{cq_mean*100:4.1f}% {cs_mean*100:4.1f}% {tie_mean*100:4.1f}% "
                  f"{avg_t:6.1f} {avg_d:5.1f}")
            # Print unit composition line
            for ut in unit_types:
                a_alive = ai_a_ut_summary[ut]["alive_mean"]
                a_dead = ai_a_ut_summary[ut]["dead_mean"]
                b_alive = ai_b_ut_summary[ut]["alive_mean"]
                b_dead = ai_b_ut_summary[ut]["dead_mean"]
                if a_alive + a_dead + b_alive + b_dead > 0.1:
                    print(f"  {' ' * 12} {' ' * 12} {ut:>10}: "
                          f"A={a_alive:.1f}/{a_dead:.1f} B={b_alive:.1f}/{b_dead:.1f}")
            print(f"  {' ' * 12} {' ' * 12} P0_by_vtype: "
                  f"Conq={p0_vtype_summary['conquest']['p0_winrate']:.1%} "
                  f"Const={p0_vtype_summary['construction']['p0_winrate']:.1%} "
                  f"Tie={p0_vtype_summary['tiebreak']['p0_winrate']:.1%}")
            print(f"  {' ' * 12} {' ' * 12} Econ: "
                  f"A_res={ar_mean:.0f} B_res={br_mean:.0f} "
                  f"A_con={ac_mean:.1f} B_con={bc_mean:.1f} "
                  f"eff_A={ai_a_efficiency:.1f} eff_B={ai_b_efficiency:.1f}")

            # Save raw paired data (only if --save-raw is set, otherwise save light summary)
            raw_data = {
                "mode": "paired",
                "ai_a": ai_a, "ai_b": ai_b,
                "n_seeds": n, "n_games": total_games,
                "city_hp": CITY_HP, "city_damage": CITY_DAMAGE,
                "size": args.size, "gen": args.gen,
                "ai_a_winrate": round(ai_a_wr, 4),
                "ai_b_winrate": round(ai_b_wr, 4),
                "p0_winrate": round(p0_wr, 4),
                "p0_std": round(p0_std, 4),
                "p0_ci95": round(p0_ci, 4),
                "ai_a_std": round(ai_a_std, 4),
                "ai_a_ci95": round(ai_a_ci, 4),
                "conquest_rate": round(cq_mean, 4),
                "construction_rate": round(cs_mean, 4),
                "tiebreak_rate": round(tie_mean, 4),
                "avg_turns": round(avg_t, 2),
                "avg_dead": round(avg_d, 2),
                # Economic metrics
                "ai_a_units_mean": round(au_mean, 2), "ai_a_units_std": round(au_std, 2),
                "ai_b_units_mean": round(bu_mean, 2), "ai_b_units_std": round(bu_std, 2),
                "ai_a_resources_mean": round(ar_mean, 1), "ai_a_resources_std": round(ar_std, 1),
                "ai_b_resources_mean": round(br_mean, 1), "ai_b_resources_std": round(br_std, 1),
                "ai_a_construction_mean": round(ac_mean, 2), "ai_a_construction_std": round(ac_std, 2),
                "ai_b_construction_mean": round(bc_mean, 2), "ai_b_construction_std": round(bc_std, 2),
                "ai_a_resource_efficiency": ai_a_efficiency,
                "ai_b_resource_efficiency": ai_b_efficiency,
                # Per-unit-type composition
                "ai_a_unit_composition": ai_a_ut_summary,
                "ai_b_unit_composition": ai_b_ut_summary,
                # Per-victory-type P0
                "p0_by_victory_type": p0_vtype_summary,
            }
            if args.save_raw:
                raw_data["seeds"] = [{
                    "seed": r["seed"],
                    "ai_a_wins": r["ai_a_wins"],
                    "ai_b_wins": r["ai_b_wins"],
                    "p0_wins": r["p0_wins"],
                    "p1_wins": r["p1_wins"],
                    "g1": r["game1"],
                    "g2": r["game2"],
                } for r in results]

            fname = f"paired_{ai_a}_vs_{ai_b}.json"
            with open(os.path.join(args.output, fname), "w") as f:
                json.dump(raw_data, f, indent=2)

            all_summaries.append({
                "mode": "paired",
                "ai_a": ai_a, "ai_b": ai_b,
                "n_seeds": n, "n_games": total_games,
                "ai_a_winrate": round(ai_a_wr, 4),
                "ai_b_winrate": round(ai_b_wr, 4),
                "p0_winrate": round(p0_wr, 4),
                "p0_std": round(p0_std, 4),
                "p0_ci95": round(p0_ci, 4),
                "ai_a_std": round(ai_a_std, 4),
                "ai_a_ci95": round(ai_a_ci, 4),
                "conquest_rate": round(cq_mean, 4),
                "construction_rate": round(cs_mean, 4),
                "tiebreak_rate": round(tie_mean, 4),
                "avg_turns": round(avg_t, 2),
                "avg_dead": round(avg_d, 2),
                "ai_a_units_mean": round(au_mean, 2), "ai_a_units_std": round(au_std, 2),
                "ai_b_units_mean": round(bu_mean, 2), "ai_b_units_std": round(bu_std, 2),
                "ai_a_resources_mean": round(ar_mean, 1), "ai_a_resources_std": round(ar_std, 1),
                "ai_b_resources_mean": round(br_mean, 1), "ai_b_resources_std": round(br_std, 1),
                "ai_a_construction_mean": round(ac_mean, 2), "ai_a_construction_std": round(ac_std, 2),
                "ai_b_construction_mean": round(bc_mean, 2), "ai_b_construction_std": round(bc_std, 2),
                "ai_a_resource_efficiency": ai_a_efficiency,
                "ai_b_resource_efficiency": ai_b_efficiency,
            })

    config = {"games_per_pair": args.games, "size": args.size, "gen": args.gen,
              "paired": paired, "mode": mode}
    summary = {"config": config, "pairs": all_summaries,
               "total_seeds": total, "total_games": actual_games,
               "elapsed_s": round(elapsed, 1)}
    with open(os.path.join(args.output, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {args.output}/")


if __name__ == "__main__":
    main()
