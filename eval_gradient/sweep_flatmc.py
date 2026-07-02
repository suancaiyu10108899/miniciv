# eval_gradient/sweep_flatmc.py — B1: FlatMC rollout gradient
#
# For each rollout count in [3, 5, 10, 25, 50, 100]:
#   - Patch prototype.ai_flatmc.ROLLOUTS
#   - Run eval_matrix vs random and vs greedy
#
# Usage: python eval_gradient/sweep_flatmc.py

import sys, os, json, subprocess, math, time, random
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROLLOUT_COUNTS = [3, 5, 10, 25, 50, 100]
BASE_GAMES = 200
HIGH_GAMES = 500
WORKERS = 24
SIZE = 15
OUTPUT_DIR = Path(__file__).parent

def patch_rollouts(n):
    """Patch the flatmc module rollout count."""
    import prototype.ai_flatmc
    prototype.ai_flatmc.ROLLOUTS = n

def run_eval(rollouts, opponent, games):
    """Run eval_matrix and return results dict."""
    patch_rollouts(rollouts)
    output = OUTPUT_DIR / f"flatmc_rollout{rollouts}"
    if opponent == "greedy":
        output = OUTPUT_DIR / f"flatmc_vs_greedy_{rollouts}"

    output_str = str(output)
    cmd = [
        sys.executable, "-m", "prototype.eval_matrix",
        "--ais", f"flatmc,{opponent}",
        "--games", str(games),
        "--size", str(SIZE),
        "--workers", str(WORKERS),
        "--output", output_str,
    ]
    print(f"\n{'='*60}")
    print(f"FlatMC rollout={rollouts} vs {opponent} ({games} games)")
    print(f"{'='*60}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    elapsed = time.time() - t0
    if proc.returncode != 0:
        print(f"ERROR: eval_matrix returned {proc.returncode}")
        return None

    # Read summary
    summary_path = output / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: summary not found at {summary_path}")
        return None

    with open(summary_path) as f:
        summary = json.load(f)

    # Extract flatmc vs opponent result
    pairs = summary["pairs"]
    for p in pairs:
        if p["ai0"] == "flatmc" and p["ai1"] == opponent:
            return {
                "rollouts": rollouts,
                "opponent": opponent,
                "games": games,
                "flatmc_p0_winrate": p["p0_winrate"],
                "flatmc_p1_winrate": p["p1_winrate"],
                "flatmc_as_p0_wins": p["p0_winrate"],
                "opponent_as_p0_wins": p["p1_winrate"],
                "n": p["n"],
                "conquests": p["conquests"],
                "constructions": p["constructions"],
                "tiebreaks": p["tiebreaks"],
                "avg_turns": p["avg_turns"],
                "avg_dead": p["avg_dead"],
                "elapsed_s": summary.get("elapsed_s", 0),
            }

    # If flatmc was P1, swap
    for p in pairs:
        if p["ai0"] == opponent and p["ai1"] == "flatmc":
            return {
                "rollouts": rollouts,
                "opponent": opponent,
                "games": games,
                "flatmc_p0_winrate": p["p1_winrate"],
                "flatmc_p1_winrate": p["p0_winrate"],
                "flatmc_as_p0_wins": p["p1_winrate"],
                "opponent_as_p0_wins": p["p0_winrate"],
                "n": p["n"],
                "conquests": p["conquests"],
                "constructions": p["constructions"],
                "tiebreaks": p["tiebreaks"],
                "avg_turns": p["avg_turns"],
                "avg_dead": p["avg_dead"],
                "elapsed_s": summary.get("elapsed_s", 0),
            }

    print(f"ERROR: could not find flatmc vs {opponent} in summary")
    return None


def compute_stddev(rollouts, opponent, games):
    """Estimate winrate stddev from raw game data."""
    output = OUTPUT_DIR / f"flatmc_rollout{rollouts}"
    if opponent == "greedy":
        output = OUTPUT_DIR / f"flatmc_vs_greedy_{rollouts}"

    # Find the match file
    fname = f"flatmc_vs_{opponent}.json"
    fpath = output / fname
    if not fpath.exists():
        # try reverse
        fname = f"{opponent}_vs_flatmc.json"
        fpath = output / fname

    if not fpath.exists():
        return None

    with open(fpath) as f:
        results = json.load(f)

    wins = [1 if r["winner"] == 0 else 0 for r in results]
    n = len(wins)
    if n == 0:
        return None
    p = sum(wins) / n
    # Bernoulli stddev estimate
    return math.sqrt(p * (1 - p) / n) * 100  # as percentage points


def main():
    print("=" * 60)
    print("B1: FlatMC Rollout Gradient Sweep")
    print("=" * 60)

    results = []

    for r in ROLLOUT_COUNTS:
        # vs Random
        res = run_eval(r, "random", BASE_GAMES)
        if res:
            stddev = compute_stddev(r, "random", BASE_GAMES)
            res["stddev_pct"] = stddev
            print(f"  -> FlatMC vs Random: winrate={res['flatmc_as_p0_wins']*100:.1f}% (vs opp as P0={res['opponent_as_p0_wins']*100:.1f}%) stddev~{stddev:.2f}% turns={res['avg_turns']:.1f}")
            # Variance check
            if stddev and stddev > 5.0:
                print(f"  -> Stddev {stddev:.1f}% > 5%, re-running with {HIGH_GAMES} games")
                res2 = run_eval(r, "random", HIGH_GAMES)
                if res2:
                    stddev2 = compute_stddev(r, "random", HIGH_GAMES)
                    res2["stddev_pct"] = stddev2
                    res = res2
                    print(f"  (rerun) FlatMC vs Random: winrate={res['flatmc_as_p0_wins']*100:.1f}% stddev~{stddev2:.2f}%")
            results.append(res)

        # vs Greedy
        res = run_eval(r, "greedy", BASE_GAMES)
        if res:
            stddev = compute_stddev(r, "greedy", BASE_GAMES)
            res["stddev_pct"] = stddev
            print(f"  -> FlatMC vs Greedy: winrate={res['flatmc_as_p0_wins']*100:.1f}% (vs opp as P0={res['opponent_as_p0_wins']*100:.1f}%) stddev~{stddev:.2f}% turns={res['avg_turns']:.1f}")
            if stddev and stddev > 5.0:
                print(f"  -> Stddev {stddev:.1f}% > 5%, re-running with {HIGH_GAMES} games")
                res2 = run_eval(r, "greedy", HIGH_GAMES)
                if res2:
                    stddev2 = compute_stddev(r, "greedy", HIGH_GAMES)
                    res2["stddev_pct"] = stddev2
                    res = res2
                    print(f"  (rerun) FlatMC vs Greedy: winrate={res['flatmc_as_p0_wins']*100:.1f}% stddev~{stddev2:.2f}%")
            results.append(res)

    # Save aggregate results
    agg = {"b1_flatmc_gradient": results}
    with open(OUTPUT_DIR / "b1_flatmc_results.json", "w") as f:
        json.dump(agg, f, indent=2)

    print(f"\n{'='*60}")
    print("B1 Complete! Results saved to eval_gradient/b1_flatmc_results.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
