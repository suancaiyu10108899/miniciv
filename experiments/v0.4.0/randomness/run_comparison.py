"""eval_randomness/run_comparison.py
Run deterministic vs random combat comparison for E1.

Usage:
    python eval_randomness/run_comparison.py

Compares Greedy vs Greedy and Random vs Greedy with both combat modes.
Outputs JSON data and summary to eval_randomness/
"""

import sys, os, json, math, time, random as _random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from concurrent.futures import ProcessPoolExecutor, as_completed

from prototype.game import init_game, step_game
from prototype.eval import load_ai
from prototype import combat


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


def _run_one_game(args):
    seed, ai0_name, ai1_name, size, gen, max_turns, use_random = args
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    gs = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))
    return {
        "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
        "mode": "random" if use_random else "deterministic",
        "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_city_hp": gs.cities[0].hp, "p1_city_hp": gs.cities[1].hp,
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
    }


def _run_batch(args):
    """Run a batch of games with a specific combat mode."""
    mode_name, use_random, seed_offset, ai0, ai1, n_games, size, gen, max_turns, workers = args
    combat.RANDOM_COMBAT = use_random

    tasks = []
    for i in range(n_games):
        seed = seed_offset + i * 1000 + hash((mode_name, ai0, ai1)) % 100000
        tasks.append((seed, ai0, ai1, size, gen, max_turns, use_random))

    results = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one_game, t): t for t in tasks}
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.perf_counter() - t0
    print(f"  {mode_name} {ai0} vs {ai1}: {n_games} games in {elapsed:.0f}s ({n_games/elapsed:.0f} g/s)")
    return results


def analyze_pair(ai0, ai1, det_results, rnd_results):
    """Compare deterministic vs random for an AI pair."""
    def stats(results, label):
        n = len(results)
        p0w = sum(1 for r in results if r["winner"] == 0)
        p1w = sum(1 for r in results if r["winner"] == 1)
        p0r = p0w / n if n else 0
        p1r = p1w / n if n else 0
        cq = sum(1 for r in results if r["victory_type"] == "conquest")
        cs = sum(1 for r in results if r["victory_type"] == "construction")
        tie = n - cq - cs
        avg_t = sum(r["turns"] for r in results) / n if n else 0
        avg_d = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n if n else 0
        p0r_std = math.sqrt(p0r * (1 - p0r) / n) if n else 0
        return {
            "label": label, "n": n,
            "p0_wins": p0w, "p1_wins": p1w,
            "p0_winrate": round(p0r, 4),
            "p1_winrate": round(p1r, 4),
            "p0_stddev": round(p0r_std, 4),
            "p0_ci95": round(_ci(p0r, n), 4),
            "conquests": cq, "constructions": cs, "tiebreaks": tie,
            "conquest_rate": round(cq / n, 4) if n else 0,
            "construction_rate": round(cs / n, 4) if n else 0,
            "tiebreak_rate": round(tie / n, 4) if n else 0,
            "avg_turns": round(avg_t, 2),
            "avg_dead": round(avg_d, 2),
            "turns_std": round(_mean_std([r["turns"] for r in results])[1], 2),
            "dead_std": round(_mean_std([r["p0_dead"] + r["p1_dead"] for r in results])[1], 2),
        }

    det_s = stats(det_results, "deterministic")
    rnd_s = stats(rnd_results, "random")

    return {"ai0": ai0, "ai1": ai1, "deterministic": det_s, "random": rnd_s}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run deterministic vs random combat comparison")
    parser.add_argument("--games", type=int, default=500, help="Games per mode per pair")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=100)
    args = parser.parse_args()

    workers = args.workers or min(24, os.cpu_count() or 4)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    base_seed = args.seed

    # --- Step 1: Greedy vs Greedy (mirror) ---
    print("=" * 60)
    print("E1.1: Greedy vs Greedy - deterministic vs random combat")
    print("=" * 60)
    det_gvg = _run_batch(("deterministic", False, base_seed,
                          "greedy", "greedy", args.games, args.size, args.gen, args.max_turns, workers))
    rnd_gvg = _run_batch(("random", True, base_seed + 1_000_000,
                          "greedy", "greedy", args.games, args.size, args.gen, args.max_turns, workers))

    gvg_analysis = analyze_pair("greedy", "greedy", det_gvg, rnd_gvg)

    # Variance rule: if P0 winrate stddev > 4%, increase games
    for mode_name in ["deterministic", "random"]:
        s = gvg_analysis[mode_name]
        if s["p0_stddev"] > 0.04:
            print(f"  Variance rule triggered: {mode_name} P0 stddev={s['p0_stddev']:.4f} > 4%")
            print(f"  Running additional {args.games} games to reach 1000...")
            extra = _run_batch((f"{mode_name}_extra", mode_name == "random", base_seed + 2_000_000,
                               "greedy", "greedy", args.games, args.size, args.gen, args.max_turns, workers))
            if mode_name == "deterministic":
                det_gvg.extend(extra)
            else:
                rnd_gvg.extend(extra)
    gvg_analysis = analyze_pair("greedy", "greedy", det_gvg, rnd_gvg)
    print(f"  Deterministic: P0={gvg_analysis['deterministic']['p0_winrate']*100:.1f}% "
          f"CI={gvg_analysis['deterministic']['p0_ci95']*100:.1f}% "
          f"Build={gvg_analysis['deterministic']['construction_rate']*100:.1f}% "
          f"Turns={gvg_analysis['deterministic']['avg_turns']:.1f} "
          f"Dead={gvg_analysis['deterministic']['avg_dead']:.1f}")
    print(f"  Random:       P0={gvg_analysis['random']['p0_winrate']*100:.1f}% "
          f"CI={gvg_analysis['random']['p0_ci95']*100:.1f}% "
          f"Build={gvg_analysis['random']['construction_rate']*100:.1f}% "
          f"Turns={gvg_analysis['random']['avg_turns']:.1f} "
          f"Dead={gvg_analysis['random']['avg_dead']:.1f}")

    # --- Step 2: Random vs Greedy (underdog effect) ---
    print("\n" + "=" * 60)
    print("E1.2: Random vs Greedy - deterministic vs random combat")
    print("(Does randomness help the underdog?)")
    print("=" * 60)
    det_rvg = _run_batch(("deterministic", False, base_seed + 3_000_000,
                          "random", "greedy", args.games, args.size, args.gen, args.max_turns, workers))
    rnd_rvg = _run_batch(("random", True, base_seed + 4_000_000,
                          "random", "greedy", args.games, args.size, args.gen, args.max_turns, workers))

    rvg_analysis = analyze_pair("random", "greedy", det_rvg, rnd_rvg)

    # Also check variance rule
    for mode_name in ["deterministic", "random"]:
        s = rvg_analysis[mode_name]
        if s["p0_stddev"] > 0.04:
            extra = _run_batch((f"{mode_name}_extra", mode_name == "random", base_seed + 5_000_000,
                               "random", "greedy", args.games, args.size, args.gen, args.max_turns, workers))
            if mode_name == "deterministic":
                det_rvg.extend(extra)
            else:
                rnd_rvg.extend(extra)
    rvg_analysis = analyze_pair("random", "greedy", det_rvg, rnd_rvg)
    greedy_det = 1 - rvg_analysis['deterministic']['p0_winrate']
    greedy_rnd = 1 - rvg_analysis['random']['p0_winrate']
    print(f"  Deterministic: Greedy winrate={greedy_det*100:.1f}% "
          f"CI={rvg_analysis['deterministic']['p1_winrate'] and _ci(rvg_analysis['deterministic']['p1_winrate'], rvg_analysis['deterministic']['n'])*100:.1f}%")
    print(f"  Random:       Greedy winrate={greedy_rnd*100:.1f}% "
          f"CI={rvg_analysis['random']['p1_winrate'] and _ci(rvg_analysis['random']['p1_winrate'], rvg_analysis['random']['n'])*100:.1f}%")
    if greedy_det > greedy_rnd:
        print(f"  -> Randomness DECREASES Greedy winrate by {(greedy_det - greedy_rnd)*100:.1f}% — helping underdog")
    else:
        print(f"  -> Randomness INCREASES Greedy winrate by {(greedy_rnd - greedy_det)*100:.1f}% — helping favorite")

    # Save raw data
    for label, data in [("greedy_vs_greedy_det", det_gvg), ("greedy_vs_greedy_rnd", rnd_gvg),
                         ("random_vs_greedy_det", det_rvg), ("random_vs_greedy_rnd", rnd_rvg)]:
        path = os.path.join(out_dir, f"{label}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # Save analysis
    analysis = {
        "greedy_vs_greedy": gvg_analysis,
        "random_vs_greedy": rvg_analysis,
        "config": {"games_per_mode": args.games, "size": args.size, "gen": args.gen},
    }
    with open(os.path.join(out_dir, "analysis.json"), "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\nSaved raw data and analysis to {out_dir}/")

    # Generate textual summary
    summary_lines = [
        "# Randomness Impact Analysis",
        "",
        f"## Configuration",
        f"- Games per mode: {args.games}",
        f"- Map: {args.size}x{args.size} {args.gen}",
        f"- Max turns: {args.max_turns}",
        "",
        "## Greedy vs Greedy (Mirror Matchup)",
        "",
        "| Metric | Deterministic | Random (±3) | Difference |",
        "|--------|--------------|-------------|------------|",
    ]
    det = gvg_analysis["deterministic"]
    rnd = gvg_analysis["random"]
    for metric, key, fmt in [
        ("P0 Winrate", "p0_winrate", "{:.1f}%"),
        ("P0 95% CI", "p0_ci95", "±{:.1f}%"),
        ("P0 StdDev", "p0_stddev", "{:.4f}"),
        ("Conquest Rate", "conquest_rate", "{:.1f}%"),
        ("Construction Rate", "construction_rate", "{:.1f}%"),
        ("Tiebreak Rate", "tiebreak_rate", "{:.1f}%"),
        ("Avg Turns", "avg_turns", "{:.1f}"),
        ("Turns StdDev", "turns_std", "{:.2f}"),
        ("Avg Dead Units", "avg_dead", "{:.1f}"),
        ("Dead StdDev", "dead_std", "{:.2f}"),
    ]:
        if "Rate" in metric or "Winrate" in metric:
            dv = det[key] * 100
            rv = rnd[key] * 100
        else:
            dv = det[key]
            rv = rnd[key]

        if "CI" in metric:
            diff_str = ""
        else:
            diff = rv - dv
            diff_str = f"{diff:+.2f}" if isinstance(diff, float) else ""

        dv_str = fmt.format(dv)
        rv_str = fmt.format(rv)
        summary_lines.append(f"| {metric} | {dv_str} | {rv_str} | {diff_str} |")

    summary_lines.extend([
        "",
        "## Random vs Greedy (Underdog Effect)",
        "",
        "| Metric | Deterministic | Random (±3) | Difference |",
        "|--------|--------------|-------------|------------|",
    ])
    det = rvg_analysis["deterministic"]
    rnd = rvg_analysis["random"]
    # Greedy is P1 in this matchup
    greedy_det = det["p1_winrate"]
    greedy_rnd = rnd["p1_winrate"]
    summary_lines.append(f"| Greedy Winrate | {greedy_det*100:.1f}% | {greedy_rnd*100:.1f}% | {(greedy_rnd-greedy_det)*100:+.1f}% |")
    summary_lines.append(f"| Greedy 95% CI | ±{_ci(greedy_det, det['n'])*100:.1f}% | ±{_ci(greedy_rnd, rnd['n'])*100:.1f}% | |")
    summary_lines.append(f"| Random Winrate | {det['p0_winrate']*100:.1f}% | {rnd['p0_winrate']*100:.1f}% | {(rnd['p0_winrate']-det['p0_winrate'])*100:+.1f}% |")
    for metric, key, fmt in [
        ("Conquest Rate", "conquest_rate", "{:.1f}%"),
        ("Construction Rate", "construction_rate", "{:.1f}%"),
        ("Tiebreak Rate", "tiebreak_rate", "{:.1f}%"),
        ("Avg Turns", "avg_turns", "{:.1f}"),
        ("Turns StdDev", "turns_std", "{:.2f}"),
        ("Avg Dead Units", "avg_dead", "{:.1f}"),
        ("Dead StdDev", "dead_std", "{:.2f}"),
    ]:
        if "Rate" in metric:
            dv = det[key] * 100
            rv = rnd[key] * 100
        else:
            dv = det[key]
            rv = rnd[key]
        diff = rv - dv
        summary_lines.append(f"| {metric} | {fmt.format(dv)} | {fmt.format(rv)} | {diff:+.2f} |")

    summary_lines.extend([
        "",
        "## Summary",
        "",
    ])
    if greedy_det > greedy_rnd:
        summary_lines.append(f"- Randomness reduces Greedy winrate from {greedy_det*100:.1f}% to {greedy_rnd*100:.1f}%")
        summary_lines.append("- RECOMMENDATION: Randomness helps underdogs. Enable as default for fairer play.")
    else:
        summary_lines.append(f"- Randomness increases Greedy winrate from {greedy_det*100:.1f}% to {greedy_rnd*100:.1f}%")
        summary_lines.append("- RECOMMENDATION: Randomness does NOT help underdogs in this setting. Further investigation needed.")

    gap_det = greedy_det - 0.5  # How far from 50%
    gap_rnd = greedy_rnd - 0.5
    if abs(gap_rnd) < abs(gap_det):
        summary_lines.append(f"- Randomness narrows the winrate gap from {gap_det*100:.1f}% to {gap_rnd*100:.1f}% (more balanced)")
    else:
        summary_lines.append(f"- Randomness widens the winrate gap from {gap_det*100:.1f}% to {gap_rnd*100:.1f}% (less balanced)")

    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(summary_lines))

    print(f"Report saved to {os.path.join(out_dir, 'report.md')}")
    return analysis


if __name__ == "__main__":
    main()
