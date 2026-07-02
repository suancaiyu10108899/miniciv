"""
experiments/v0.5.0/run_batched_matrix.py — Batched 7x7 full matrix runner

Processes one AI pair at a time to avoid ProcessPoolExecutor queue saturation.
Each pair is run as a separate subprocess call to eval_matrix.

Usage:
  cd D:/Dev/miniciv
  python experiments/v0.5.0/run_batched_matrix.py
"""

import json, math, os, subprocess, sys, time

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(OUTPUT_DIR, "..", "..")

AI_NAMES = ["random", "greedy", "aggressive", "flatmc", "evo", "bc", "dqn"]
GAMES = 200
WORKERS = 8

def run_batched():
    """Run all 49 pairs sequentially, each as a separate subprocess."""
    print("=" * 70)
    print("  MINICIV v0.5.0 — BATCHED 7x7 EVAL MATRIX")
    print(f"  AIs: {', '.join(AI_NAMES)}")
    print(f"  Games per pair: {GAMES} (x2 swapped = {GAMES*2} games/pair)")
    print(f"  Workers per subprocess: {WORKERS}")
    print(f"  Total subprocesses: {len(AI_NAMES) * len(AI_NAMES)}")
    print("=" * 70)
    print()

    t_start = time.perf_counter()
    completed = 0
    total = len(AI_NAMES) * len(AI_NAMES)

    for ai_a in AI_NAMES:
        for ai_b in AI_NAMES:
            pair_key = f"paired_{ai_a}_vs_{ai_b}.json"
            pair_path = os.path.join(OUTPUT_DIR, pair_key)
            # Skip if this pair already exists
            if os.path.exists(pair_path):
                completed += 1
                print(f"  [{completed}/{total}] {ai_a} vs {ai_b} — already exists, skipping")
                continue

            out_dir = os.path.join(OUTPUT_DIR, "tmp", f"{ai_a}_vs_{ai_b}")
            os.makedirs(out_dir, exist_ok=True)

            print(f"  [{completed+1}/{total}] {ai_a} vs {ai_b} — running {GAMES*2} games...")
            sys.stdout.flush()

            cmd = [
                sys.executable, "-u", "-m", "prototype.eval_matrix",
                "--paired",
                "--ais", f"{ai_a},{ai_b}",
                "--games", str(GAMES),
                "--size", "15",
                "--gen", "balanced",
                "--workers", str(WORKERS),
                "--output", out_dir,
            ]

            t0 = time.perf_counter()
            result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
            elapsed = time.perf_counter() - t0

            if result.returncode != 0:
                print(f"    FAILED (code {result.returncode}) after {elapsed:.0f}s")
                if result.stderr:
                    print(f"    stderr: {result.stderr[:500]}")
                # Copy whatever was produced
            else:
                print(f"    OK ({elapsed:.0f}s)")

            # Copy output files to main directory
            for fname in os.listdir(out_dir):
                src = os.path.join(out_dir, fname)
                dst = os.path.join(OUTPUT_DIR, fname)
                if not os.path.exists(dst) or os.path.getsize(src) > os.path.getsize(dst):
                    try:
                        import shutil
                        shutil.copy2(src, dst)
                    except Exception as e:
                        print(f"    Warning: could not copy {fname}: {e}")

            completed += 1

            # Small delay between runs to let system breathe
            time.sleep(0.5)

    elapsed = time.perf_counter() - t_start
    print(f"\n  All {total} pairs completed in {elapsed:.0f}s")
    print()

    # Step 2: Build summary.json
    print("=" * 70)
    print("  BUILDING SUMMARY")
    print("=" * 70)
    build_summary()

    # Step 3: Compute Elo
    print("=" * 70)
    print("  COMPUTING ELO")
    print("=" * 70)
    compute_elo_and_report()


def build_summary():
    """Build summary.json from individual pair files."""
    pairs_data = []
    total_seeds = 0
    total_games = 0

    for ai_a in AI_NAMES:
        for ai_b in AI_NAMES:
            pair_path = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")
            if not os.path.exists(pair_path):
                print(f"  WARNING: {pair_path} not found, skipping")
                continue

            with open(pair_path) as f:
                data = json.load(f)

            if "ai_a" not in data:
                # It might be in key format
                pass

            pairs_data.append(data)
            total_seeds += data.get("n_seeds", 0)
            total_games += data.get("n_games", 0)

    # Also look for any regular pair files
    for ai_a in AI_NAMES:
        for ai_b in AI_NAMES:
            pair_path = os.path.join(OUTPUT_DIR, f"{ai_a}_vs_{ai_b}.json")
            if os.path.exists(pair_path):
                # Non-paired format
                pass

    summary = {
        "config": {
            "games_per_pair": GAMES,
            "size": 15,
            "gen": "balanced",
            "paired": True,
            "mode": "normal",
        },
        "pairs": pairs_data,
        "total_seeds": total_seeds,
        "total_games": total_games,
        "elapsed_s": 0,
    }

    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved summary: {summary_path} ({len(pairs_data)} pairs)")


def _ci95(p, n):
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def compute_elo(pairs, ai_names, start_elo=1500, K=32, iterations=100):
    """Compute Elo ratings from paired evaluation results."""
    elo = {name: start_elo for name in ai_names}

    for it in range(iterations):
        for p in pairs:
            ai_a = p.get("ai_a", p.get("ai0"))
            ai_b = p.get("ai_b", p.get("ai1"))
            if ai_a not in elo or ai_b not in elo:
                continue
            n_games = p.get("n_games", p.get("n", 0))
            a_winrate = p.get("ai_a_winrate", p.get("p0_winrate", 0.5))
            a_wins = int(a_winrate * n_games)
            b_wins = n_games - a_wins

            ea = 1.0 / (1.0 + 10.0 ** ((elo[ai_b] - elo[ai_a]) / 400.0))
            eb = 1.0 / (1.0 + 10.0 ** ((elo[ai_a] - elo[ai_b]) / 400.0))

            elo[ai_a] += K * (a_wins / max(1, n_games) - ea)
            elo[ai_b] += K * (b_wins / max(1, n_games) - eb)

    # 95% CI via bootstrap
    n_bootstrap = 1000
    import random as _rnd
    boot = {name: [] for name in ai_names}
    for _ in range(n_bootstrap):
        boot_elo = {name: start_elo for name in ai_names}
        for _ in range(len(pairs)):
            p = _rnd.choice(pairs)
            ai_a = p.get("ai_a", p.get("ai0"))
            ai_b = p.get("ai_b", p.get("ai1"))
            if ai_a not in boot_elo or ai_b not in boot_elo:
                continue
            n_games = p.get("n_games", p.get("n", 0))
            a_winrate = p.get("ai_a_winrate", p.get("p0_winrate", 0.5))
            a_wins = int(a_winrate * n_games)
            for _ in range(iterations):
                ea = 1.0 / (1.0 + 10.0 ** ((boot_elo[ai_b] - boot_elo[ai_a]) / 400.0))
                eb = 1.0 / (1.0 + 10.0 ** ((boot_elo[ai_a] - boot_elo[ai_b]) / 400.0))
                noise_a = _rnd.gauss(0, math.sqrt(ea * (1 - ea) / max(1, n_games)))
                noise_b = _rnd.gauss(0, math.sqrt(eb * (1 - eb) / max(1, n_games)))
                boot_elo[ai_a] += K * (a_wins / max(1, n_games) - ea + noise_a)
                boot_elo[ai_b] += K * (b_wins / max(1, n_games) - eb + noise_b)
        for name in ai_names:
            boot[name].append(boot_elo[name])

    ci = {}
    for name in ai_names:
        bvals = sorted(boot[name])
        ci[name] = {
            "elo": round(elo[name], 1),
            "ci_low": round(bvals[25], 1),
            "ci_high": round(bvals[975], 1),
        }
    return ci


def generate_report(summary, elo, ai_names):
    """Generate markdown report."""
    pairs = summary["pairs"]
    config = summary["config"]
    lines = []
    lines.append("# MiniCiv v0.5.0 — AI Comparison Matrix (7x7)")
    lines.append("")
    lines.append(f"- **Date**: July 2026")
    lines.append(f"- **AIs**: {', '.join(ai_names)}")
    lines.append(f"- **Games per pair**: {config['games_per_pair']} (x2 swapped = {config['games_per_pair']*2} games/pair)")
    lines.append(f"- **Total**: {len(ai_names)}x{len(ai_names)} x {config['games_per_pair']*2} = {len(ai_names)*len(ai_names)*config['games_per_pair']*2} games")
    lines.append(f"- **Map**: {config['size']}x{config['size']} {config['gen']}")
    lines.append(f"- **Protocol**: Paired (P0/P1 swap per seed)")
    lines.append(f"- **Total seeds**: {summary['total_seeds']}")
    lines.append(f"- **Total games**: {summary['total_games']}")
    lines.append("")

    # Winrate matrix
    lines.append("## Winrate Matrix (Row AI vs Column AI)")
    lines.append("")
    lines.append("Values are Row AI's winrate as percentage (with 95% CI).")
    lines.append("")
    wr = {}
    ci_lookup = {}
    for p in pairs:
        ai_a = p.get("ai_a", p.get("ai0"))
        ai_b = p.get("ai_b", p.get("ai1"))
        wr[(ai_a, ai_b)] = p.get("ai_a_winrate", p.get("p0_winrate", 0.5))
        ci_lookup[(ai_a, ai_b)] = p.get("ai_a_ci95", p.get("p0_ci95", 0))

    header = f"| {'AI':>8s} |"
    for name in ai_names:
        header += f" {name:>12s} |"
    lines.append(header)
    sep = "|:" + "-" * 7 + ":|"
    for name in ai_names:
        sep += ":" + "-" * 11 + ":|"
    lines.append(sep)

    for row_name in ai_names:
        row = f"| **{row_name:>6s}** |"
        for col_name in ai_names:
            key = (row_name, col_name)
            if key in wr:
                pct = wr[key] * 100
                the_ci = ci_lookup[key] * 100
                row += f" {pct:>5.1f}%+-{the_ci:>3.1f}% |"
            else:
                row += f" {'N/A':>12s} |"
        lines.append(row)
    lines.append("")

    # Elo ranking
    lines.append("## Elo Rankings")
    lines.append("")
    lines.append(f"- Starting Elo: 1500")
    lines.append(f"- K = 32")
    lines.append(f"- Iterations: 100")
    lines.append(f"- 95% CI via bootstrap (n=1000)")
    lines.append("")
    ranked = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    lines.append(f"| {'Rank':>4s} | {'AI':>12s} | {'Elo':>7s} | {'95% CI':>12s} |")
    lines.append(f"|{'':-<5s}|{'':-<13s}|{'':-<8s}|{'':-<13s}|")
    for rank, (name, e) in enumerate(ranked, 1):
        lines.append(f"| {rank:>3d}. | {name:>12s} | {e['elo']:>6.1f} | {e['ci_low']:>5.1f}-{e['ci_high']:>5.1f} |")
    lines.append("")

    # Compare with v0.4.0
    lines.append("## Comparison with v0.4.0 (4x4 Matrix)")
    lines.append("")
    v4_path = os.path.join(PROJECT_ROOT, "eval_final", "summary.json")
    if os.path.exists(v4_path):
        with open(v4_path) as f:
            v4 = json.load(f)
        v4_pairs = v4["pairs"]
        v4_wr = {}
        for p in v4_pairs:
            v4_wr[(p["ai0"], p["ai1"])] = p["p0_winrate"]

        lines.append("| Matchup | v0.4.0 P0% | v0.5.0 Paired% (AI_A) | Delta |")
        lines.append("|---|---|---:|---:|")
        matchups = [
            ("random", "random"),
            ("random", "greedy"),
            ("random", "aggressive"),
            ("random", "flatmc"),
            ("greedy", "greedy"),
            ("greedy", "aggressive"),
            ("greedy", "flatmc"),
            ("aggressive", "aggressive"),
            ("aggressive", "flatmc"),
            ("flatmc", "flatmc"),
        ]
        seen = set()
        for a0, a1 in matchups:
            key = (a0, a1)
            if key in seen:
                continue
            seen.add(key)
            v4_val = v4_wr.get((a0, a1))
            v5_val = None
            for p in pairs:
                p_a = p.get("ai_a", p.get("ai0"))
                p_b = p.get("ai_b", p.get("ai1"))
                if p_a == a0 and p_b == a1:
                    if a0 == a1:
                        v5_val = p.get("p0_winrate")
                    else:
                        v5_val = p.get("ai_a_winrate")
                    break
            if v4_val is not None and v5_val is not None:
                delta = (v5_val - v4_val) * 100
                lines.append(f"| {a0} vs {a1} | {v4_val*100:.1f}% | {v5_val*100:.1f}% | {delta:+.1f}% |")
        lines.append("")

    # Analysis
    lines.append("## Analysis")
    lines.append("")

    graded = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    top_elo = graded[0][1]["elo"]
    bottom_elo = graded[-1][1]["elo"]
    spread = top_elo - bottom_elo

    lines.append(f"### Overall spread: {spread:.0f} Elo points ({bottom_elo:.0f} to {top_elo:.0f})")
    lines.append("")

    tiers = {"S": [], "A": [], "B": [], "C": []}
    for i, (name, e) in enumerate(graded):
        pct_of_top = (e["elo"] - bottom_elo) / max(1, spread)
        if pct_of_top >= 0.8:
            tiers["S"].append(name)
        elif pct_of_top >= 0.5:
            tiers["A"].append(name)
        elif pct_of_top >= 0.2:
            tiers["B"].append(name)
        else:
            tiers["C"].append(name)

    for tier in ["S", "A", "B", "C"]:
        if tiers[tier]:
            lines.append(f"- **Tier {tier}**: {', '.join(tiers[tier])}")
    lines.append("")

    lines.append("### Paradigm Analysis")
    lines.append("")
    lines.append("The 7 AIs represent 4 different paradigms:")
    lines.append("")
    lines.append("1. **Rule-based (hardcoded)**: random, greedy, aggressive, flatmc")
    lines.append("2. **Weight-parameterized (evolvable)**: evo (pre-trained weights)")
    lines.append("3. **Behavior Cloning (supervised NN)**: bc (trained on Greedy demonstrations)")
    lines.append("4. **Reinforcement Learning (DQN)**: dqn (trained via self-play)")
    lines.append("")

    rule_names = ["random", "greedy", "aggressive", "flatmc"]
    ml_names = ["evo", "bc", "dqn"]
    rule_ranked = [(n, e) for n, e in graded if n in rule_names]
    ml_ranked = [(n, e) for n, e in graded if n in ml_names]

    if rule_ranked:
        lines.append(f"- Best rule-based: {rule_ranked[0][0]} ({rule_ranked[0][1]['elo']:.1f} Elo)")
    if ml_ranked:
        lines.append(f"- Best ML-based: {ml_ranked[0][0]} ({ml_ranked[0][1]['elo']:.1f} Elo)")
    if rule_ranked and ml_ranked:
        gap = rule_ranked[0][1]["elo"] - ml_ranked[0][1]["elo"]
        if gap > 0:
            lines.append(f"- Rule-based still leads ML by {gap:.0f} Elo points")
        else:
            lines.append(f"- ML-based leads rule-based by {-gap:.0f} Elo points")

    lines.append("")
    lines.append("### First-Player Advantage (Mirror Matches)")
    lines.append("")
    lines.append("| AI | P0 Winrate in Mirror | 95% CI | P0 Advantage |")
    lines.append("|---|---:|---:|---:|")
    for name in ai_names:
        for p in pairs:
            p_a = p.get("ai_a", p.get("ai0"))
            p_b = p.get("ai_b", p.get("ai1"))
            if p_a == name and p_b == name:
                p0_wr = p.get("p0_winrate", 0.5)
                p0_ci = p.get("p0_ci95", 0)
                adv = (p0_wr - 0.5) * 100
                lines.append(f"| {name} | {p0_wr*100:.1f}% | +-{p0_ci*100:.1f}% | {adv:+.1f}% |")
                break
    lines.append("")

    lines.append("### Victory Type Distribution (overall)")
    lines.append("")
    avg_conq = sum(p.get("conquest_rate", 0) for p in pairs) / len(pairs) * 100
    avg_cons = sum(p.get("construction_rate", 0) for p in pairs) / len(pairs) * 100
    avg_tie = 100 - avg_conq - avg_cons
    lines.append(f"- Conquest: {avg_conq:.1f}%")
    lines.append(f"- Construction: {avg_cons:.1f}%")
    lines.append(f"- Tiebreak (max turns): {avg_tie:.1f}%")
    lines.append("")

    return "\n".join(lines)


def compute_elo_and_report():
    """Compute Elo and generate report from existing pair files."""
    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    if not os.path.exists(summary_path):
        print(f"  ERROR: {summary_path} not found.")
        return

    with open(summary_path) as f:
        summary = json.load(f)

    pairs = summary["pairs"]
    ai_names = sorted(set(
        p.get("ai_a", p.get("ai0")) for p in pairs
    ))

    elo = compute_elo(pairs, ai_names)
    elo_path = os.path.join(OUTPUT_DIR, "elo_rankings.json")
    with open(elo_path, "w") as f:
        json.dump(elo, f, indent=2)
    print(f"  Saved Elo: {elo_path}")
    print()

    # Print Elo table
    ranked = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    print(f"  {'Rank':>4s} {'AI':>12s} {'Elo':>7s} {'95% CI':>12s}")
    print(f"  {'':->4s} {'':->12s} {'':->7s} {'':->12s}")
    for rank, (name, e) in enumerate(ranked, 1):
        print(f"  {rank:>3d}. {name:>12s} {e['elo']:>7.1f} {e['ci_low']:>5.1f}-{e['ci_high']:5.1f}")

    report = generate_report(summary, elo, ai_names)
    report_path = os.path.join(OUTPUT_DIR, "report.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\n  Saved report: {report_path}")


if __name__ == "__main__":
    run_batched()
