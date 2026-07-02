"""eval_full_matrix/run_matrix.py
Run the full 7x7 (or NxN) comparison matrix for E2.

Usage:
    python eval_full_matrix/run_matrix.py

Runs all AI pair matchups using paired mode (when available) or standard mode.
Produces raw JSON data and summary.
"""

import sys, os, json, math, time, subprocess, shlex

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from prototype.eval import AI_MODULES


def _ci(p, n):
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


# AI list - check what's available
AVAILABLE_AIS = []
for name in ["random", "greedy", "aggressive", "flatmc", "evo"]:
    if name in AI_MODULES:
        AVAILABLE_AIS.append(name)

# Check for BC and DQN weights
BC_EXISTS = os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'prototype', 'bc_weights.json'))
DQN_EXISTS = os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'prototype', 'dqn_weights.json'))

if BC_EXISTS:
    AVAILABLE_AIS.append("bc")
if DQN_EXISTS:
    AVAILABLE_AIS.append("dqn")

PENDING = []
if not BC_EXISTS:
    PENDING.append("bc")
if not DQN_EXISTS:
    PENDING.append("dqn")


def run_paired_eval(ai_a, ai_b, games, size, gen, workers, max_turns, out_dir):
    """Run paired evaluation using eval_matrix.py --paired."""
    cmd = [
        sys.executable, "-m", "prototype.eval_matrix",
        "--paired",
        "--ais", f"{ai_a},{ai_b}",
        "--games", str(games),
        "--size", str(size),
        "--gen", gen,
        "--max-turns", str(max_turns),
        "--workers", str(workers),
        "--output", out_dir,
    ]
    print(f"  Running: {' '.join(shlex.quote(str(c)) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return None
    # Parse the summary file
    summary_path = os.path.join(out_dir, "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            return json.load(f)
    return None


def run_standard_eval(ai0, ai1, games, size, gen, workers, max_turns, out_dir):
    """Run standard (non-paired) evaluation."""
    cmd = [
        sys.executable, "-m", "prototype.eval_matrix",
        "--ais", f"{ai0},{ai1}",
        "--games", str(games),
        "--size", str(size),
        "--gen", gen,
        "--max-turns", str(max_turns),
        "--workers", str(workers),
        "--output", out_dir,
    ]
    print(f"  Running: {' '.join(shlex.quote(str(c)) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return None
    summary_path = os.path.join(out_dir, "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            return json.load(f)
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run full comparison matrix")
    parser.add_argument("--games", type=int, default=300,
                        help="Games per paired seed (300 = 600 games per pair)")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--paired", action="store_true", default=True,
                        help="Use paired mode (default: True)")
    parser.add_argument("--no-paired", action="store_false", dest="paired")
    args = parser.parse_args()

    workers = args.workers or min(24, os.cpu_count() or 4)
    out_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("E2: Full Comparison Matrix")
    print("=" * 60)
    print(f"Available AIs: {AVAILABLE_AIS}")
    if PENDING:
        print(f"Pending (no weights): {PENDING}")
    print(f"Matrix size: {len(AVAILABLE_AIS)}x{len(AVAILABLE_AIS)}")
    print(f"Games per pair: {args.games} {'seeds (2 games each)' if args.paired else 'games'}")
    print(f"Map: {args.size}x{args.size} {args.gen} Workers: {workers}")
    print()

    pairs = [(a0, a1) for a0 in AVAILABLE_AIS for a1 in AVAILABLE_AIS if a0 != a1]
    total_pairs = len(pairs)
    pair_results = {}

    for idx, (a0, a1) in enumerate(pairs):
        print(f"\nPair {idx+1}/{total_pairs}: {a0} vs {a1}")
        pair_dir = os.path.join(out_dir, f"{a0}_vs_{a1}")
        os.makedirs(pair_dir, exist_ok=True)

        if args.paired:
            result = run_paired_eval(a0, a1, args.games, args.size, args.gen,
                                     workers, args.max_turns, pair_dir)
        else:
            result = run_standard_eval(a0, a1, args.games * 2, args.size, args.gen,
                                       workers, args.max_turns, pair_dir)
            # Standard mode uses 2x games for fairness

        if result:
            pair_results[(a0, a1)] = result
            # Check CI width variance rule
            if result["pairs"]:
                p = result["pairs"][0]
                ci95 = p.get("p0_ci95") or p.get("ai_a_ci95", 0)
                if ci95 and ci95 > 0.06:
                    print(f"  CI width ({ci95*100:.1f}%) > 6% — doubling games to {args.games * 2}")
                    if args.paired:
                        result2 = run_paired_eval(a0, a1, args.games * 2, args.size, args.gen,
                                                   workers, args.max_turns, pair_dir + "_x2")
                    else:
                        result2 = run_standard_eval(a0, a1, args.games * 4, args.size, args.gen,
                                                     workers, args.max_turns, pair_dir + "_x2")
                    if result2:
                        pair_results[(a0, a1) + ("x2",)] = result2

    # Collect all results for summary
    print(f"\n{'='*60}")
    print("All pairs complete. Compiling summary...")
    print(f"{'='*60}")

    # Save master list of what was run
    master = {
        "available_ais": AVAILABLE_AIS,
        "pending_ais": PENDING,
        "config": {
            "games_per_seed": args.games,
            "paired": args.paired,
            "size": args.size,
            "gen": args.gen,
            "max_turns": args.max_turns,
        },
        "pairs_run": list(pair_results.keys()),
    }
    with open(os.path.join(out_dir, "master.json"), "w") as f:
        json.dump(master, f, indent=2)

    # Build winrate matrix for report
    WINRATE_MATRIX = {}
    for a0 in AVAILABLE_AIS:
        for a1 in AVAILABLE_AIS:
            if a0 == a1:
                continue
            key = (a0, a1)
            if key in pair_results:
                summary = pair_results[key]
                if summary["pairs"]:
                    p = summary["pairs"][0]
                    WINRATE_MATRIX[(a0, a1)] = {
                        "ai_a_winrate": p.get("ai_a_winrate", p.get("p0_winrate", 0)),
                        "ai_b_winrate": p.get("ai_b_winrate", 1 - p.get("p0_winrate", 0)),
                        "p0_winrate": p.get("p0_winrate", 0),
                        "p0_ci95": p.get("p0_ci95", 0),
                        "ai_a_ci95": p.get("ai_a_ci95", 0),
                        "n": p.get("n_seeds", p.get("n", 0)),
                        "conquest_rate": p.get("conquest_rate", 0),
                        "construction_rate": p.get("construction_rate", 0),
                        "tiebreak_rate": p.get("tiebreak_rate", 0),
                        "avg_turns": p.get("avg_turns", 0),
                        "avg_dead": p.get("avg_dead", 0),
                    }

    # Save winrate matrix
    with open(os.path.join(out_dir, "winrate_matrix.json"), "w") as f:
        # Convert tuple keys to strings for JSON
        serializable = {f"{k[0]}_vs_{k[1]}": v for k, v in WINRATE_MATRIX.items()}
        json.dump(serializable, f, indent=2)

    print("\nWinrate matrix saved.")
    for a0 in AVAILABLE_AIS:
        row = []
        for a1 in AVAILABLE_AIS:
            if a0 == a1:
                row.append("  X    ")
            else:
                key = (a0, a1)
                if key in WINRATE_MATRIX:
                    wr = WINRATE_MATRIX[key]["ai_a_winrate"]
                    row.append(f"{wr*100:5.1f}% ")
                else:
                    row.append("  ?   ")
        print(f"  {a0:12s}: " + " ".join(row))

    return WINRATE_MATRIX


if __name__ == "__main__":
    WINRATE_MATRIX = main()
