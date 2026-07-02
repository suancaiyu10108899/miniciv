"""eval_full_matrix/statistical_quality.py
Statistical quality check (E4) — deep dive on Greedy vs Greedy mirror matchup.

Usage:
    python eval_full_matrix/statistical_quality.py

Runs 2000 games of Greedy vs Greedy (paired mode) and analyzes:
- Precise P0 winrate with CI
- Is P0 winrate significantly different from 50%?
- Batch stability (10 batches of 200)
- Variance across batches
"""

import sys, os, json, math, time, random as _random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from concurrent.futures import ProcessPoolExecutor, as_completed

from prototype.game import init_game, step_game
from prototype.eval import load_ai


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
    seed, ai0_name, ai1_name, size, gen, max_turns = args
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    gs = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))
    return {
        "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
        "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
    }


def _run_one_paired(args):
    """Paired run for Greedy mirror: two games per seed swapping P0/P1."""
    seed, ai_name, size, gen, max_turns = args
    ai = load_ai(ai_name)

    # Game 1: P0=ai, P1=ai (same AI, just P0/P1 labels)
    gs1 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs1.winner is None and gs1.turn < max_turns:
        step_game(gs1, ai(gs1, 0, rng0), ai(gs1, 1, rng1))

    # Game 2: swapped roles (same seed base)
    gs2 = init_game(seed=seed + 1_000_000, size=size, generator_id=gen)
    rng0 = _random.Random(seed + 1_000_000)
    rng1 = _random.Random(seed + 1_000_001)
    while gs2.winner is None and gs2.turn < max_turns:
        step_game(gs2, ai(gs2, 0, rng0), ai(gs2, 1, rng1))

    g1 = {
        "seed": seed, "winner": gs1.winner, "victory_type": gs1.victory_type or "tiebreak",
        "turns": gs1.turn,
        "p0_dead": sum(1 for u in gs1.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs1.dead_units if u.player_id == 1),
    }
    g2 = {
        "seed": seed + 1_000_000, "winner": gs2.winner, "victory_type": gs2.victory_type or "tiebreak",
        "turns": gs2.turn,
        "p0_dead": sum(1 for u in gs2.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs2.dead_units if u.player_id == 1),
    }

    return {
        "seed": seed,
        "game1": g1, "game2": g2,
        "p0_wins": (1 if g1["winner"] == 0 else 0) + (1 if g2["winner"] == 0 else 0),
        "p1_wins": (1 if g1["winner"] == 1 else 0) + (1 if g2["winner"] == 1 else 0),
        "both_p0": g1["winner"] == 0 and g2["winner"] == 0,
        "both_p1": g1["winner"] == 1 and g2["winner"] == 1,
        "split": g1["winner"] != g2["winner"],
        "tot_conquest": (1 if "conquest" in str(g1["victory_type"]) else 0) +
                         (1 if "conquest" in str(g2["victory_type"]) else 0),
        "tot_construction": (1 if "construction" in str(g1["victory_type"]) else 0) +
                             (1 if "construction" in str(g2["victory_type"]) else 0),
        "tot_tiebreak": (1 if "tiebreak" in str(g1["victory_type"]) else 0) +
                         (1 if "tiebreak" in str(g2["victory_type"]) else 0),
        "tot_turns": g1["turns"] + g2["turns"],
        "tot_dead": g1["p0_dead"] + g1["p1_dead"] + g2["p0_dead"] + g2["p1_dead"],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Statistical quality check for Greedy mirror")
    parser.add_argument("--games", type=int, default=2000,
                        help="Total number of games (default 2000 = 1000 paired seeds)")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=100)
    args = parser.parse_args()

    workers = args.workers or min(24, os.cpu_count() or 4)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    n_seeds = args.games // 2  # paired mode: 2 games per seed

    print("=" * 60)
    print("E4: Statistical Quality Check — Greedy vs Greedy Mirror")
    print("=" * 60)
    print(f"Total games: {args.games} ({n_seeds} paired seeds)")
    print(f"Map: {args.size}x{args.size} {args.gen} Workers: {workers}")
    print()

    # Build tasks (split into batches of 200 games = 100 seeds)
    batch_size = 100  # seeds per batch (200 games)
    n_batches = (n_seeds + batch_size - 1) // batch_size
    print(f"Split into {n_batches} batches of {batch_size*2} games each")

    all_seeds = [args.seed + i * 1000 for i in range(n_seeds)]
    batches = [all_seeds[i:i+batch_size] for i in range(0, n_seeds, batch_size)]

    all_results = []
    batch_stats = []

    for batch_idx, batch_seeds in enumerate(batches):
        print(f"\nBatch {batch_idx+1}/{n_batches} ({len(batch_seeds)*2} games)...")
        tasks = [(s, "greedy", args.size, args.gen, args.max_turns) for s in batch_seeds]

        t0 = time.perf_counter()
        batch_results = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_run_one_paired, t): t for t in tasks}
            for fut in as_completed(futures):
                batch_results.append(fut.result())
        elapsed = time.perf_counter() - t0

        # Per-batch stats
        n_g = len(batch_results) * 2
        p0w = sum(r["p0_wins"] for r in batch_results)
        p0r = p0w / n_g if n_g else 0
        cq = sum(r["tot_conquest"] for r in batch_results)
        cs = sum(r["tot_construction"] for r in batch_results)
        tie = n_g - cq - cs
        avg_t = sum(r["tot_turns"] for r in batch_results) / n_g if n_g else 0
        avg_d = sum(r["tot_dead"] for r in batch_results) / n_g if n_g else 0

        batch_stats.append({
            "batch": batch_idx + 1,
            "games": n_g,
            "p0_winrate": round(p0r, 4),
            "conquests": cq,
            "constructions": cs,
            "tiebreaks": tie,
            "avg_turns": round(avg_t, 2),
            "avg_dead": round(avg_d, 2),
        })
        all_results.extend(batch_results)
        print(f"  P0 winrate: {p0r*100:.1f}% ({n_g} games, {elapsed:.0f}s)")
        print(f"  Conq={cq} Cons={cs} Tie={tie} AvgT={avg_t:.1f} AvgDead={avg_d:.1f}")

    # === Overall stats ===
    total_games = len(all_results) * 2
    overall_p0w = sum(r["p0_wins"] for r in all_results)
    overall_p0r = overall_p0w / total_games
    overall_cq = sum(r["tot_conquest"] for r in all_results)
    overall_cs = sum(r["tot_construction"] for r in all_results)
    overall_tie = total_games - overall_cq - overall_cs
    overall_avg_t = sum(r["tot_turns"] for r in all_results) / total_games
    overall_avg_d = sum(r["tot_dead"] for r in all_results) / total_games
    overall_ci = _ci(overall_p0r, total_games)
    overall_std = math.sqrt(overall_p0r * (1 - overall_p0r) / total_games)

    # === Significance test (binomial test) ===
    from scipy import stats as scipy_stats
    try:
        p_value = 2 * scipy_stats.binom_test(overall_p0w, n=total_games, p=0.5, alternative='two-sided')
    except Exception:
        # Manual computation using normal approximation
        z = (overall_p0w - total_games * 0.5) / math.sqrt(total_games * 0.5 * 0.5)
        p_value = 2 * (1 - _norm_cdf(abs(z)))  # two-sided

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total paired seeds: {len(all_results)}")
    print(f"Total games: {total_games}")
    print(f"P0 wins: {overall_p0w}/{total_games}")
    print(f"P0 winrate: {overall_p0r*100:.2f}%")
    print(f"P0 stddev: {overall_std*100:.2f}%")
    print(f"P0 95% CI: ±{overall_ci*100:.2f}%")
    print(f"Significantly different from 50%? {'YES' if p_value < 0.05 else 'NO'} (p={p_value:.4f})")
    print(f"Victory: Conquest={overall_cq} Construction={overall_cs} Tiebreak={overall_tie}")
    print(f"Avg turns: {overall_avg_t:.1f}")
    print(f"Avg dead: {overall_avg_d:.1f}")

    # === Batch stability ===
    print("\n" + "=" * 60)
    print("BATCH STABILITY (10 batches of ~200 games each)")
    print("=" * 60)
    batch_wrs = [s["p0_winrate"] for s in batch_stats]
    batch_mean, batch_std = _mean_std(batch_wrs)
    print(f"{'Batch':>7s} {'Games':>7s} {'P0 Win%':>10s} {'Conq':>5s} {'Cons':>5s} {'Tie':>5s} {'Turns':>7s} {'Dead':>6s}")
    print("-" * 60)
    for s in batch_stats:
        print(f"{s['batch']:7d} {s['games']:7d} {s['p0_winrate']*100:8.2f}% "
              f"{s['conquests']:5d} {s['constructions']:5d} {s['tiebreaks']:5d} "
              f"{s['avg_turns']:7.2f} {s['avg_dead']:6.2f}")

    print(f"\nBatch winrates: mean={batch_mean*100:.2f}% std={batch_std*100:.2f}%")
    print(f"Batch winrate range: {min(batch_wrs)*100:.2f}% — {max(batch_wrs)*100:.2f}%")
    print(f"Are results stable? {'YES' if batch_std < 0.04 else 'MARGINAL' if batch_std < 0.06 else 'NO'} "
          f"(std={batch_std*100:.2f}%, threshold=4%)")

    # Save
    output = {
        "config": {"total_games": total_games, "n_seeds": len(all_results), "n_batches": n_batches},
        "overall": {
            "p0_wins": overall_p0w,
            "p1_wins": total_games - overall_p0w,
            "p0_winrate": round(overall_p0r, 4),
            "p0_stddev": round(overall_std, 4),
            "p0_ci95": round(overall_ci, 4),
            "p_value": round(p_value, 4),
            "significantly_different_from_50pct": p_value < 0.05,
            "conquests": overall_cq,
            "constructions": overall_cs,
            "tiebreaks": overall_tie,
            "avg_turns": round(overall_avg_t, 2),
            "avg_dead": round(overall_avg_d, 2),
        },
        "batches": batch_stats,
        "batch_analysis": {
            "mean_winrate": round(batch_mean, 4),
            "std_winrate": round(batch_std, 4),
            "min_winrate": round(min(batch_wrs), 4),
            "max_winrate": round(max(batch_wrs), 4),
        },
    }

    with open(os.path.join(out_dir, "statistical_quality.json"), "w") as f:
        json.dump(output, f, indent=2)

    with open(os.path.join(out_dir, "statistical_quality_raw.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nSaved to {out_dir}/")
    return output


def _norm_cdf(x):
    """Standard normal CDF (approximation)."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


if __name__ == "__main__":
    main()
