#!/usr/bin/env python
# prototype/verify_facility8.py — Facility=8 验证矩阵
# 运行: python -m prototype.verify_facility8
#
# 测试新规则 CONSTRUCTION_REQUIRE_FACILITIES=8 下的 AI 表现。
# 全矩阵 36,000 局数据均来自修复前规则（C5 研究完即获胜）。
# 本脚本产出新规则下的第一条可靠基线。

import json, os, sys, time, math, random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

# ─── 配置 ──────────────────────────────────────────
SIZE = 15
GEN = "balanced"
GAMES_PER_PAIR = 200  # paired mode: 200 seeds × 2 games = 400 games per pair
MAX_TURNS = 100
WORKERS = 30

# 核心验证对局: 4-AI 全交叉
MATRIX_AIS = ["evo", "greedy", "dqn_trained", "flatmc"]

OUTPUT_DIR = "experiments/v0.5.0/facility-8-verify"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _run_one_game(args):
    """Run a single game. args: (seed, ai0_name, ai1_name, size, gen, max_turns, tag).
    tag = "forward" (ai0=P0) or "backward" (ai0=P1), used for paired analysis.
    Returns result dict with _ai0, _ai1, _tag fields added.
    """
    seed, ai0_name, ai1_name, size, gen, max_turns, tag = args

    from prototype.game import init_game, step_game
    from prototype.eval import load_ai

    gs = init_game(seed=seed, size=size, generator_id=gen)
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)

    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))

    # Count facilities per player
    from prototype.mapgen import get_facility
    facility_count = {0: 0, 1: 0}
    for y in range(gs.size):
        for x in range(gs.size):
            f = get_facility(gs.grid, x, y)
            if f is not None:
                facility_count[f.player_id] += 1

    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
        "p0_facilities": facility_count[0],
        "p1_facilities": facility_count[1],
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_resources": {"food": gs.economies[0].food, "wood": gs.economies[0].wood,
                         "gold": gs.economies[0].gold},
        "p1_resources": {"food": gs.economies[1].food, "wood": gs.economies[1].wood,
                         "gold": gs.economies[1].gold},
        "_ai0": ai0_name,
        "_ai1": ai1_name,
        "_tag": tag,
    }


def run_paired_pair(ai_a, ai_b, n_seeds):
    """Run paired games. For each seed, run two games with swapped P0/P1."""
    tasks = []
    for seed in range(n_seeds):
        # Forward: ai_a = P0, ai_b = P1
        tasks.append((seed, ai_a, ai_b, SIZE, GEN, MAX_TURNS, "forward"))
        # Backward: ai_b = P0, ai_a = P1
        tasks.append((seed, ai_b, ai_a, SIZE, GEN, MAX_TURNS, "backward"))

    results = []
    start = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(_run_one_game, t): t for t in tasks}
        for i, f in enumerate(as_completed(futures)):
            results.append(f.result())
            if (i + 1) % 80 == 0 or (i + 1) == len(tasks):
                elapsed = time.time() - start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - i - 1) / rate if rate > 0 else 0
                print(f"  [{ai_a} vs {ai_b}] {i+1}/{len(tasks)} games "
                      f"({rate:.1f}/s, ETA {eta:.0f}s)")
    return results


def summarize_pair(ai_a, ai_b, results):
    """Compute paired summary. Each result has _ai0, _ai1, _tag fields."""
    forward = [r for r in results if r["_tag"] == "forward"]
    back = [r for r in results if r["_tag"] == "backward"]
    n = len(results)

    # ai_a winrate (paired): ai_a wins = (P0 wins in forward) + (P1 wins in backward)
    ai_a_wins = sum(1 for r in forward if r["winner"] == 0) + \
                sum(1 for r in back if r["winner"] == 1)
    ai_b_wins = sum(1 for r in forward if r["winner"] == 1) + \
                sum(1 for r in back if r["winner"] == 0)
    ai_a_wr = ai_a_wins / n if n > 0 else 0
    ai_b_wr = ai_b_wins / n if n > 0 else 0

    # P0 winrate (across all games)
    p0_wins = sum(1 for r in results if r["winner"] == 0)
    p0_wr = p0_wins / n if n > 0 else 0

    # Victory type distribution
    vtypes = [r["victory_type"] for r in results]
    conquest = sum(1 for v in vtypes if v == "conquest")
    construction = sum(1 for v in vtypes if v == "construction")
    tiebreak = sum(1 for v in vtypes if v and v.startswith("tiebreak"))

    # Average stats
    avg_turns = sum(r["turns"] for r in results) / n if n > 0 else 0
    avg_dead = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n if n > 0 else 0

    # Construction stats per AI (ai_a's construction across all games where it played)
    ai_a_cons = []
    ai_b_cons = []
    ai_a_facs = []
    ai_b_facs = []
    for r in forward:
        ai_a_cons.append(r["p0_construction"])
        ai_b_cons.append(r["p1_construction"])
        ai_a_facs.append(r["p0_facilities"])
        ai_b_facs.append(r["p1_facilities"])
    for r in back:
        ai_a_cons.append(r["p1_construction"])
        ai_b_cons.append(r["p0_construction"])
        ai_a_facs.append(r["p1_facilities"])
        ai_b_facs.append(r["p0_facilities"])

    return {
        "ai_a": ai_a, "ai_b": ai_b,
        "n_games": n,
        "ai_a_winrate": round(ai_a_wr, 4),
        "ai_b_winrate": round(ai_b_wr, 4),
        "p0_winrate": round(p0_wr, 4),
        "conquest_rate": round(conquest / n, 4) if n else 0,
        "construction_rate": round(construction / n, 4) if n else 0,
        "tiebreak_rate": round(tiebreak / n, 4) if n else 0,
        "avg_turns": round(avg_turns, 1),
        "avg_dead": round(avg_dead, 1),
        "ai_a_construction_mean": round(sum(ai_a_cons) / len(ai_a_cons), 2) if ai_a_cons else 0,
        "ai_b_construction_mean": round(sum(ai_b_cons) / len(ai_b_cons), 2) if ai_b_cons else 0,
        "ai_a_facilities_mean": round(sum(ai_a_facs) / len(ai_a_facs), 2) if ai_a_facs else 0,
        "ai_b_facilities_mean": round(sum(ai_b_facs) / len(ai_b_facs), 2) if ai_b_facs else 0,
    }


def generate_pairs(ais):
    """生成所有唯一 AI 对"""
    pairs = []
    seen = set()
    for i, a in enumerate(ais):
        for j in range(i, len(ais)):
            b = ais[j]
            key = (a, b) if a <= b else (b, a)
            if key not in seen:
                seen.add(key)
                pairs.append((a, b))
    return pairs


def main():
    # Verify constant
    from prototype.constants import CONSTRUCTION_VICTORY_REQUIRE_FACILITIES as FREQ

    print("=" * 60)
    print("Facility=8 Verification Matrix")
    print(f"CONSTRUCTION_REQUIRE_FACILITIES = {FREQ}")
    print(f"Map: {SIZE}x{SIZE} {GEN}, {GAMES_PER_PAIR} paired seeds/pair")
    print(f"Workers: {WORKERS}")
    print("=" * 60)

    if FREQ != 8:
        print(f"\n⚠️  WARNING: Facility requirement is {FREQ}, expected 8!")
        print("Check prototype/constants.py")
        return

    # Generate pairs
    matrix_pairs = generate_pairs(MATRIX_AIS)
    all_pairs = matrix_pairs + [("greedy", "greedy")]  # Mirror baseline

    print(f"\nPairs to run: {len(all_pairs)}")
    for a, b in all_pairs:
        label = " (mirror)" if a == b else ""
        print(f"  {a} vs {b}{label}")

    all_summaries = []
    total_start = time.time()

    for i, (ai_a, ai_b) in enumerate(all_pairs):
        print(f"\n{'─'*40}")
        label = " [MIRROR]" if ai_a == ai_b else ""
        print(f"[{i+1}/{len(all_pairs)}] {ai_a} vs {ai_b}{label}")

        results = run_paired_pair(ai_a, ai_b, GAMES_PER_PAIR)

        # Save raw
        raw_file = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")
        with open(raw_file, 'w') as f:
            json.dump(results, f, indent=2)

        summary = summarize_pair(ai_a, ai_b, results)
        all_summaries.append(summary)

        elapsed = time.time() - total_start
        print(f"  {ai_a} WR: {summary['ai_a_winrate']:.1%}, "
              f"{ai_b} WR: {summary['ai_b_winrate']:.1%}, "
              f"P0: {summary['p0_winrate']:.1%}")
        print(f"  Conquest: {summary['conquest_rate']:.1%}, "
              f"Construction: {summary['construction_rate']:.1%}, "
              f"Tiebreak: {summary['tiebreak_rate']:.1%}")
        print(f"  Avg turns: {summary['avg_turns']}, Avg dead: {summary['avg_dead']}")
        print(f"  Facilities — {ai_a}: {summary['ai_a_facilities_mean']}, "
              f"{ai_b}: {summary['ai_b_facilities_mean']}")
        print(f"  Session elapsed: {elapsed:.0f}s")

    total_elapsed = time.time() - total_start

    # ─── Save summary ──────────────────────────────────
    summary_file = os.path.join(OUTPUT_DIR, "summary.json")
    summary_data = {
        "config": {
            "facility_requirement": FREQ,
            "size": SIZE,
            "gen": GEN,
            "games_per_pair": GAMES_PER_PAIR,
            "paired": True,
            "date": "2026-07-03",
            "git_commit": "see git log -1",
            "description": "Facility=8 verification — first baseline under new construction victory rules"
        },
        "pairs": all_summaries,
        "total_games": sum(s["n_games"] for s in all_summaries),
        "total_elapsed_s": round(total_elapsed, 0),
        "total_elapsed_h": round(total_elapsed / 3600, 2),
    }
    with open(summary_file, 'w') as f:
        json.dump(summary_data, f, indent=2)

    # ─── Print results ─────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE: {summary_data['total_games']} games in {total_elapsed:.0f}s "
          f"({total_elapsed/3600:.1f}h)")
    print(f"Summary → {summary_file}")
    print(f"{'='*60}")

    # Win rate matrix
    print(f"\n📊 Win Rate Matrix (facility=8):")
    print(f"{'':>12}", end="")
    for ai in MATRIX_AIS:
        print(f"{ai:>10}", end="")
    print()

    wr = defaultdict(dict)
    for s in all_summaries:
        wr[s["ai_a"]][s["ai_b"]] = s["ai_a_winrate"]
        wr[s["ai_b"]][s["ai_a"]] = s["ai_b_winrate"]

    for ai_a in MATRIX_AIS:
        print(f"{ai_a:>12}", end="")
        for ai_b in MATRIX_AIS:
            if ai_a == ai_b:
                print(f"{'  ─':>10}", end="")
            else:
                val = wr.get(ai_a, {}).get(ai_b, None)
                if val is not None:
                    print(f"{val:>10.1%}", end="")
                else:
                    print(f"{'?':>10}", end="")
        print()

    # Construction rate analysis
    print(f"\n🏗️  Construction Victory Rates:")
    for s in all_summaries:
        print(f"  {s['ai_a']} vs {s['ai_b']}: "
              f"construction={s['construction_rate']:.1%}, "
              f"avg_facs {s['ai_a']}={s['ai_a_facilities_mean']}, "
              f"{s['ai_b']}={s['ai_b_facilities_mean']}")

    # Greedy mirror focus
    greedy_mirror = [s for s in all_summaries if s["ai_a"] == "greedy" and s["ai_b"] == "greedy"]
    if greedy_mirror:
        gm = greedy_mirror[0]
        print(f"\n🔬 Greedy Mirror Analysis:")
        print(f"  Construction rate: {gm['construction_rate']:.1%}")
        print(f"  Conquest rate: {gm['conquest_rate']:.1%}")
        print(f"  Tiebreak rate: {gm['tiebreak_rate']:.1%}")
        print(f"  Avg facilities: {gm['ai_a_facilities_mean']}")
        print(f"  Avg construction techs: {gm['ai_a_construction_mean']}")
        if gm['construction_rate'] < 0.01:
            print(f"  ⚠️  WARNING: Greedy almost never wins via construction!")
            print(f"  → Facility requirement may be too high, or Greedy doesn't build facilities")

    # Evo dominance check
    print(f"\n🎯 Evo Dominance Check (old rules: 75% avg winrate):")
    evo_pairs = [s for s in all_summaries if "evo" in (s["ai_a"], s["ai_b"])]
    evo_wrs = []
    for s in evo_pairs:
        wr_val = s["ai_a_winrate"] if s["ai_a"] == "evo" else s["ai_b_winrate"]
        opp = s["ai_b"] if s["ai_a"] == "evo" else s["ai_a"]
        evo_wrs.append(wr_val)
        print(f"  Evo vs {opp}: {wr_val:.1%} "
              f"(construction={s['construction_rate']:.1%})")
    if evo_wrs:
        avg_evo = sum(evo_wrs) / len(evo_wrs)
        print(f"  Average Evo winrate: {avg_evo:.1%}")
        if avg_evo > 0.65:
            print(f"  ⚠️  Evo STILL dominant (>65%). Facility requirement insufficient.")
        elif avg_evo > 0.50:
            print(f"  ✅ Evo balanced (50-65%). Facility requirement is in the right range.")
        else:
            print(f"  ⚠️  Evo collapsed (<50%). Facility requirement may be too harsh.")


if __name__ == "__main__":
    main()
