"""
experiments/v0.5.0/run_full_matrix.py — 7x7 full matrix runner + Elo + report

This script:
  1. Runs the full 7x7 paired evaluation matrix using eval_matrix.py as a subprocess
  2. Computes Elo rankings from the raw results
  3. Generates a report with winrate matrix + Elo CI

Usage:
  cd D:/Dev/miniciv
  python experiments/v0.5.0/run_full_matrix.py
"""

import json, math, os, subprocess, sys, time

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(OUTPUT_DIR, "..", "..")

def main():
    # Step 1: Run the 7x7 matrix as a subprocess to avoid __main__ pickling issues
    print("=" * 70)
    print("  Step 1: Running 7x7 Paired Evaluation Matrix")
    print("  AIs: random, greedy, aggressive, flatmc, evo, bc, dqn")
    print("  Games per pair: 200 (x2 swapped = 400 games/pair)")
    print("  Total: 49 pairs x 400 = 19,600 games")
    print("=" * 70)
    t0 = time.perf_counter()

    cmd = [
        sys.executable, "-u", "-m", "prototype.eval_matrix",
        "--paired",
        "--ais", "random,greedy,aggressive,flatmc,evo,bc,dqn",
        "--games", "200",
        "--size", "15",
        "--gen", "balanced",
        "--workers", "24",
        "--output", OUTPUT_DIR,
    ]
    print(f"  Running: {' '.join(cmd)}")
    sys.stdout.flush()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:2000])
    if result.returncode != 0:
        print(f"  WARNING: eval_matrix exited with code {result.returncode}")
    else:
        print(f"  Matrix subprocess completed successfully")

    elapsed = time.perf_counter() - t0
    print(f"\n  Matrix completed in {elapsed:.0f}s\n")

    # Step 2: Compute Elo
    print("=" * 70)
    print("  Step 2: Computing Elo rankings")
    print("=" * 70)
    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    if not os.path.exists(summary_path):
        print(f"  ERROR: {summary_path} not found. Matrix run may have failed.")
        return

    with open(summary_path) as f:
        summary = json.load(f)

    pairs = summary["pairs"]
    ai_names = sorted(set(
        p["ai_a"] for p in pairs
    ))

    elo = compute_elo(pairs, ai_names)
    elo_path = os.path.join(OUTPUT_DIR, "elo_rankings.json")
    with open(elo_path, "w") as f:
        json.dump(elo, f, indent=2)
    print(f"  Saved Elo: {elo_path}")
    print()

    # Step 3: Generate report
    print("=" * 70)
    print("  Step 3: Generating report")
    print("=" * 70)
    report_path = os.path.join(OUTPUT_DIR, "report.md")
    report = generate_report(summary, elo, ai_names)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"  Saved: {report_path}")
    print()

    print("=" * 70)
    print("  ALL DONE")
    print(f"  Output: {OUTPUT_DIR}/")
    print("=" * 70)


def _ci95(p, n):
    """95% CI width for a proportion."""
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def compute_elo(pairs, ai_names, start_elo=1500, K=32, iterations=100):
    """Compute Elo ratings from paired evaluation results."""
    elo = {name: start_elo for name in ai_names}

    for it in range(iterations):
        for p in pairs:
            ai_a = p["ai_a"]
            ai_b = p["ai_b"]
            if ai_a not in elo or ai_b not in elo:
                continue
            n_games = p["n_games"]
            a_wins = int(p["ai_a_winrate"] * n_games)
            b_wins = n_games - a_wins

            ea = 1.0 / (1.0 + 10.0 ** ((elo[ai_b] - elo[ai_a]) / 400.0))
            eb = 1.0 / (1.0 + 10.0 ** ((elo[ai_a] - elo[ai_b]) / 400.0))

            elo[ai_a] += K * (a_wins / max(1, n_games) - ea)
            elo[ai_b] += K * (b_wins / max(1, n_games) - eb)

    # Compute 95% CI via bootstrap (resample pair winrates)
    n_bootstrap = 1000
    import random as _rnd
    boot = {name: [] for name in ai_names}
    for _ in range(n_bootstrap):
        boot_elo = {name: start_elo for name in ai_names}
        # Resample pairs with replacement
        for _ in range(len(pairs)):
            p = _rnd.choice(pairs)
            ai_a, ai_b = p["ai_a"], p["ai_b"]
            if ai_a not in boot_elo or ai_b not in boot_elo:
                continue
            n_games = p["n_games"]
            a_wins = int(p["ai_a_winrate"] * n_games)
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
    lines.append(f"- **Elapsed**: {summary['elapsed_s']}s")
    lines.append("")

    # Winrate matrix
    lines.append("## Winrate Matrix (Row AI vs Column AI)")
    lines.append("")
    lines.append("Values are Row AI's winrate as percentage (with 95% CI).")
    lines.append("")
    wr = {}
    ci_lookup = {}
    for p in pairs:
        wr[(p["ai_a"], p["ai_b"])] = p["ai_a_winrate"]
        ci_lookup[(p["ai_a"], p["ai_b"])] = p["ai_a_ci95"]

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
            ("random", "greedy"),
            ("random", "aggressive"),
            ("random", "flatmc"),
            ("greedy", "aggressive"),
            ("greedy", "flatmc"),
            ("aggressive", "flatmc"),
            ("random", "random"),
            ("greedy", "greedy"),
            ("aggressive", "aggressive"),
            ("flatmc", "flatmc"),
        ]
        seen = set()
        for a0, a1 in matchups:
            key = (a0, a1)
            if key in seen:
                continue
            seen.add(key)
            v4_val = v4_wr.get((a0, a1))
            # For paired mode mirror match, p0_winrate is the relevant stat
            v5_val = None
            v5_key = "p0_winrate" if a0 == a1 else "ai_a_winrate"
            for p in pairs:
                if p["ai_a"] == a0 and p["ai_b"] == a1:
                    v5_val = p[v5_key] if v5_key in p else p.get("ai_a_winrate")
                    break
            if v4_val is not None and v5_val is not None:
                delta = (v5_val - v4_val) * 100
                lines.append(f"| {a0} vs {a1} | {v4_val*100:.1f}% | {v5_val*100:.1f}% | {delta:+.1f}% |")
        lines.append("")
    else:
        lines.append("v0.4.0 data not available for comparison.")
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

    # Tier grouping
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

    # Paradigm analysis
    lines.append("### Paradigm Analysis")
    lines.append("")
    lines.append("The 7 AIs represent 4 different paradigms:")
    lines.append("")
    lines.append("1. **Rule-based (hardcoded)**: random, greedy, aggressive, flatmc")
    lines.append("2. **Weight-parameterized (evolvable)**: evo (pre-trained weights)")
    lines.append("3. **Behavior Cloning (supervised NN)**: bc (trained on Greedy demonstrations)")
    lines.append("4. **Reinforcement Learning (DQN)**: dqn (trained via self-play)")
    lines.append("")
    lines.append("Key findings:")
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

    # Mirror match P0 advantage
    lines.append("### First-Player Advantage (Mirror Matches)")
    lines.append("")
    lines.append("| AI | P0 Winrate in Mirror | 95% CI | P0 Advantage |")
    lines.append("|---|---:|---:|---:|")
    for name in ai_names:
        for p in pairs:
            if p["ai_a"] == name and p["ai_b"] == name:
                p0_wr = p["p0_winrate"]
                p0_ci = p["p0_ci95"]
                adv = (p0_wr - 0.5) * 100
                lines.append(f"| {name} | {p0_wr*100:.1f}% | +-{p0_ci*100:.1f}% | {adv:+.1f}% |")
                break
    lines.append("")

    # Victory type analysis
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


if __name__ == "__main__":
    main()
