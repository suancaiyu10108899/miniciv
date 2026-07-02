"""
Run econ-only decomposition experiment for P0 calibration.

econ_only patch needs careful handling because importlib.reload + multiprocessing
interactions can fail. This wrapper patches in each worker process initializer.
"""
import sys, os, json, math, random, time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _worker_init_econ_only(_=None):
    """Patch combat to no-op in each worker process."""
    import importlib
    import prototype.combat as combat_mod

    def _noop_melee(attacker, defender, terrain_att, terrain_def,
                    attacker_just_charged=False):
        return {"att_damage": 0, "def_damage": 0,
                "attacker_alive": True, "defender_alive": True}

    def _noop_ranged(archer, target, terrain_target):
        return {"damage": 0, "target_alive": True}

    def _noop_occupy(unit, city):
        return 0

    combat_mod.resolve_melee = _noop_melee
    combat_mod.resolve_ranged = _noop_ranged
    combat_mod.city_occupation_damage = _noop_occupy

    # Reload game.py so its imports pick up the patched combat functions
    import prototype.game as game_mod
    importlib.reload(game_mod)

    # Re-patch combat after reload
    import prototype.combat as combat_mod2
    combat_mod2.resolve_melee = _noop_melee
    combat_mod2.resolve_ranged = _noop_ranged
    combat_mod2.city_occupation_damage = _noop_occupy


def _verify_patch():
    """Verify the econ_only patch is active in current process."""
    from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
    melee = resolve_melee(None, None, None, None)
    assert melee["att_damage"] == 0, f"melee not patched: {melee}"
    ranged = resolve_ranged(None, None, None)
    assert ranged["damage"] == 0, f"ranged not patched: {ranged}"
    occ = city_occupation_damage(None, None)
    assert occ == 0, f"occupy not patched: {occ}"
    # Also verify game.py uses patched versions
    from prototype.game import _do_move
    # Can't easily check game's internal state, but verify game module's combat refs
    import prototype.game as game_mod
    melee2 = game_mod.resolve_melee(None, None, None, None)
    assert melee2["att_damage"] == 0, f"game.resolve_melee not patched: {melee2}"


def _do_paired(args):
    """Run one paired seed with econ_only."""
    seed, ai_a_name, ai_b_name, size, gen, max_turns, mode = args[:7]
    _verify_patch()

    from prototype.eval import load_ai
    from prototype.game import init_game, step_game

    ai_a = load_ai(ai_a_name)
    ai_b = load_ai(ai_b_name)

    gs1 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    while gs1.winner is None and gs1.turn < max_turns:
        step_game(gs1, ai_a(gs1, 0, rng0), ai_b(gs1, 1, rng1))

    gs2 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = random.Random(seed + 2_000_000)
    rng1 = random.Random(seed + 2_000_001)
    while gs2.winner is None and gs2.turn < max_turns:
        step_game(gs2, ai_b(gs2, 0, rng0), ai_a(gs2, 1, rng1))

    g1 = {
        "seed": seed, "ai0": ai_a_name, "ai1": ai_b_name,
        "winner": gs1.winner, "victory_type": gs1.victory_type or "tiebreak",
        "turns": gs1.turn,
        "p0_hp": gs1.cities[0].hp, "p1_hp": gs1.cities[1].hp,
        "p0_alive": sum(1 for u in gs1.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs1.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs1.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs1.dead_units if u.player_id == 1),
        "p0_techs": len(gs1.techs[0].completed),
        "p1_techs": len(gs1.techs[1].completed),
        "ai_a_p0": True, "ai_b_p1": True,
    }
    g2 = {
        "seed": seed + 1_000_000, "ai0": ai_b_name, "ai1": ai_a_name,
        "winner": gs2.winner, "victory_type": gs2.victory_type or "tiebreak",
        "turns": gs2.turn,
        "p0_hp": gs2.cities[0].hp, "p1_hp": gs2.cities[1].hp,
        "p0_alive": sum(1 for u in gs2.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs2.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs2.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs2.dead_units if u.player_id == 1),
        "p0_techs": len(gs2.techs[0].completed),
        "p1_techs": len(gs2.techs[1].completed),
        "ai_a_p1": True, "ai_b_p0": True,
    }

    g1ai_a_won = (g1["winner"] == 0)
    g2ai_a_won = (g2["winner"] == 1)

    return {
        "seed": seed,
        "ai_a": ai_a_name, "ai_b": ai_b_name,
        "game1": g1, "game2": g2,
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
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def _mean_std(values):
    n = len(values)
    if n < 2:
        return (sum(values) / n if n else 0.0, 0.0)
    m = sum(values) / n
    v = sum((x - m) ** 2 for x in values) / (n - 1)
    return (m, math.sqrt(v))


def get_commit_hash():
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", "..")
        ).decode().strip()
    except:
        return "unknown"


if __name__ == "__main__":
    commit = get_commit_hash()
    base_dir = os.path.join(os.path.dirname(__file__), "econ_only")
    os.makedirs(base_dir, exist_ok=True)

    n_seeds = 300
    size = 15
    gen = "balanced"
    ai_a = "greedy"
    ai_b = "greedy"
    max_turns = 100
    seed = 42
    workers = min(24, os.cpu_count() or 4)

    # Build tasks
    tasks = []
    for i in range(n_seeds):
        s = seed + i * 1000 + hash((ai_a, ai_b, "econ_only")) % 100000
        tasks.append((s, ai_a, ai_b, size, gen, max_turns, "econ_only"))

    print(f"=== Econ-Only P0 Calibration: {n_seeds} seeds, {n_seeds * 2} games ===")
    print(f"Map: {size}x{size} {gen}  Workers: {workers}")
    print()

    t0 = time.perf_counter()
    results = []
    completed = 0
    total = len(tasks)

    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init_econ_only) as ex:
        futures = {ex.submit(_do_paired, task): task for task in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            completed += 1
            if completed % max(1, total // 10) == 0:
                elapsed = time.perf_counter() - t0
                rate = completed / elapsed
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  {completed}/{total} ({completed * 100 // total}%) {rate:.0f}g/s ETA {eta:.0f}s")

    elapsed = time.perf_counter() - t0
    total_games = total * 2
    print(f"\nDone: {total} seeds ({total_games} games) in {elapsed:.0f}s ({total_games / elapsed:.0f} games/s)")

    # Statistics
    n = len(results)
    ai_a_wins = sum(r["ai_a_wins"] for r in results)
    ai_b_wins = sum(r["ai_b_wins"] for r in results)
    p0_wins = sum(r["p0_wins"] for r in results)
    p1_wins = sum(r["p1_wins"] for r in results)

    ai_a_wr = ai_a_wins / total_games
    ai_b_wr = ai_b_wins / total_games
    p0_wr = p0_wins / total_games

    p0_std = _mean_std([r["p0_wins"] / 2 for r in results])[1]
    p0_ci = _ci(p0_wr, total_games)
    ai_a_ci = _ci(ai_a_wr, total_games)

    seed_rates = [r["ai_a_wins"] / 2 for r in results]
    ai_a_mean, ai_a_std = _mean_std(seed_rates)

    cq_rates = [r["tot_conquest"] / 2 for r in results]
    cs_rates = [r["tot_construction"] / 2 for r in results]
    tie_rates = [r["tot_tiebreak"] / 2 for r in results]
    cq_mean, _ = _mean_std(cq_rates)
    cs_mean, _ = _mean_std(cs_rates)
    tie_mean, _ = _mean_std(tie_rates)

    all_turns = []
    all_dead = []
    for r in results:
        all_turns.append(r["game1"]["turns"])
        all_turns.append(r["game2"]["turns"])
        all_dead.append(r["game1"]["p0_dead"] + r["game1"]["p1_dead"])
        all_dead.append(r["game2"]["p0_dead"] + r["game2"]["p1_dead"])
    avg_t = sum(all_turns) / total_games if total_games else 0
    avg_d = sum(all_dead) / total_games if total_games else 0

    header = (f"{'AI_A':12s} {'AI_B':12s} {'A_win%':>7s} {'CI':>5s} {'B_win%':>7s} {'CI':>5s} "
              f"{'P0win%':>7s} {'CI':>5s} {'Conq':>5s} {'Cons':>5s} {'Tie':>5s} {'AvgT':>6s} {'Dead':>5s}")
    print(header)
    print("-" * len(header))
    print(f"{ai_a:12s} {ai_b:12s} {ai_a_wr * 100:6.1f}% {ai_a_ci * 100:4.1f}% "
          f"{ai_b_wr * 100:6.1f}% {ai_a_ci * 100:4.1f}% "
          f"{p0_wr * 100:6.1f}% {p0_ci * 100:4.1f}% "
          f"{cq_mean * 100:4.1f}% {cs_mean * 100:4.1f}% {tie_mean * 100:4.1f}% "
          f"{avg_t:6.1f} {avg_d:5.1f}")

    # Save raw data
    raw_data = {
        "mode": "paired",
        "ai_a": ai_a, "ai_b": ai_b,
        "n_seeds": n, "n_games": total_games,
        "city_hp": 100, "city_damage": 15,
        "size": size, "gen": gen,
        "commit_hash": commit,
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
        "seeds": [{
            "seed": r["seed"],
            "ai_a_wins": r["ai_a_wins"],
            "ai_b_wins": r["ai_b_wins"],
            "p0_wins": r["p0_wins"],
            "p1_wins": r["p1_wins"],
            "g1": r["game1"],
            "g2": r["game2"],
        } for r in results],
    }

    with open(os.path.join(base_dir, "paired_greedy_vs_greedy.json"), "w") as f:
        json.dump(raw_data, f, indent=2)

    summary = {
        "commit_hash": commit,
        "config": {
            "games_per_pair": n_seeds,
            "size": size,
            "gen": gen,
            "paired": True,
            "mode": "econ_only",
            "city_hp": 100,
            "city_damage": 15,
        },
        "pairs": [{
            "mode": "paired",
            "ai_a": ai_a, "ai_b": ai_b,
            "n_seeds": n, "n_games": total_games,
            "city_hp": 100, "city_damage": 15,
            "size": size, "gen": gen,
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
        }],
        "total_seeds": total,
        "total_games": total_games,
        "elapsed_s": round(elapsed, 1),
    }
    with open(os.path.join(base_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved to {base_dir}/")
