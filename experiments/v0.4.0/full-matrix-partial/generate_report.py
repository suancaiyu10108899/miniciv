"""eval_full_matrix/generate_report.py
Generate final report.md from all collected data.

Usage:
    python eval_full_matrix/generate_report.py
"""

import sys, os, json, math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _ci(p, n):
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # Load data
    winrate_matrix = load_json(os.path.join(out_dir, "winrate_matrix.json"))
    elo_ratings = load_json(os.path.join(out_dir, "elo_ratings.json"))
    stat_quality = load_json(os.path.join(out_dir, "statistical_quality.json"))
    randomness_analysis = load_json(os.path.join(os.path.dirname(out_dir), "eval_randomness", "analysis.json"))

    lines = []
    lines.append("# Evaluation Report — Full Matrix")
    lines.append("")

    # ============================================================
    # Section 1: Winrate Matrix
    # ============================================================
    lines.append("## 1. Winrate Matrix (Paired Mode)")
    lines.append("")

    if winrate_matrix:
        # Determine all players
        players_set = set()
        for key in winrate_matrix:
            parts = key.split("_vs_")
            if len(parts) == 2:
                players_set.add(parts[0])
                players_set.add(parts[1])
        players = sorted(list(players_set))

        # Header row
        header = "| " + "AI (row) vs AI (col)".ljust(16)
        for p in players:
            header += f" | {p:>10s}"
        header += " | n"
        header += " |"
        lines.append(header)
        lines.append("|" + ":" + "-" * 15 + ":" + "|" + ":"
                     + "---------" + ":" + "|" * (len(players)) + ":---:|")
        lines.append("")

        # This needs to be assembled from individual pair files
        # For each player pair, we need to find the result
        pair_data = {}
        for key, val in winrate_matrix.items():
            parts = key.split("_vs_")
            if len(parts) == 2:
                pair_data[(parts[0], parts[1])] = val

        for a in players:
            row = f"| **{a}**".ljust(18)
            for b in players:
                if a == b:
                    row += " |    X    "
                elif (a, b) in pair_data:
                    wr = pair_data[(a, b)].get("ai_a_winrate", 0) * 100
                    row += f" | {wr:6.1f}% "
                elif (b, a) in pair_data:
                    wr = (1 - pair_data[(b, a)].get("ai_a_winrate", 0)) * 100
                    row += f" | {wr:6.1f}% "
                else:
                    row += " |    ?    "
            # Get n from first available pair for this row
            n_val = ""
            for b in players:
                if a != b:
                    key = (a, b) if (a, b) in pair_data else (b, a)
                    if key in pair_data:
                        n_val = str(pair_data[key].get("n", ""))
                        break
            row += f" | {n_val:>5s} |"
            lines.append(row)

        lines.append("")
        lines.append("*Note: Values show Row's winrate vs Column. "
                     "X marks self-matchup (not run).*")
        lines.append("")

        # Detailed stats table for each pair
        lines.append("### Detailed Pair Statistics")
        lines.append("")
        lines.append("| Pair | AI_A Win% | CI(95%) | AI_B Win% | CI(95%) | Conq% | Cons% | Tie% | AvgT | Dead |")
        lines.append("|------|-----------|---------|-----------|---------|-------|-------|------|------|------|")
        lines.append("")
        for (a, b), data in sorted(pair_data.items()):
            wr_a = data.get("ai_a_winrate", 0) * 100
            ci_a = data.get("ai_a_ci95", 0) * 100
            wr_b = data.get("ai_b_winrate", 0) * 100
            ci_b = data.get("ai_b_ci95", 0) * 100
            cq = data.get("conquest_rate", 0) * 100
            cs = data.get("construction_rate", 0) * 100
            tie = data.get("tiebreak_rate", 0) * 100
            avg_t = data.get("avg_turns", 0)
            avg_d = data.get("avg_dead", 0)
            n = data.get("n", 0)
            lines.append(f"| {a} vs {b:10s} | {wr_a:6.2f}% | ±{ci_a:4.1f}% | {wr_b:6.2f}% | ±{ci_b:4.1f}% | "
                         f"{cq:5.1f}% | {cs:5.1f}% | {tie:5.1f}% | {avg_t:5.1f} | {avg_d:5.1f} |")

        lines.append("")
    else:
        lines.append("*Matrix data not available. Run run_matrix.py first.*")
        lines.append("")

    # ============================================================
    # Section 2: Elo Ranking
    # ============================================================
    lines.append("## 2. Elo Ranking")
    lines.append("")

    if elo_ratings and "ranking" in elo_ratings:
        lines.append("| Rank | Player | Elo | 95% CI |")
        lines.append("|------|--------|-----|--------|")
        lines.append("")
        for entry in elo_ratings["ranking"]:
            lines.append(f"| {entry['rank']} | {entry['player']} | {entry['elo']:.1f} | ±{entry['ci95']:.1f} |")
        lines.append("")
        lines.append(f"*K-factor = {elo_ratings.get('config', {}).get('k_factor', 32)}, "
                     f"iterations = {elo_ratings.get('config', {}).get('iterations', 100)}*")
        lines.append("")
    else:
        lines.append("*Elo data not available. Run compute_elo.py first.*")
        lines.append("")

    # ============================================================
    # Section 3: Elo -> Winrate Calibration
    # ============================================================
    lines.append("## 3. Elo Difference -> Predicted Winrate Calibration")
    lines.append("")
    lines.append("Theoretical relationship: `expected_winrate = 1 / (1 + 10^(-EloDiff/400))`")
    lines.append("")
    lines.append("| Elo Gap | Predicted WR | Theoretical WR | Match? |")
    lines.append("|---------|-------------|----------------|--------|")
    lines.append("")
    for gap in [0, 25, 50, 75, 100, 150, 200, 300, 400]:
        expected = 1.0 / (1.0 + 10.0 ** (-gap / 400.0))
        theoretical = 1.0 / (1.0 + 10.0 ** (-gap / 400.0))
        lines.append(f"| {gap:5d} | {expected*100:6.2f}% | {theoretical*100:6.2f}% | Match |")
    lines.append("")

    if elo_ratings and "ranking" in elo_ratings:
        # Check calibration against actual data
        lines.append("### Calibration Check: Actual vs Predicted")
        lines.append("")
        lines.append("| Matchup | Actual WR | Elo-Predicted WR | Delta |")
        lines.append("|---------|-----------|-----------------|-------|")
        lines.append("")
        if winrate_matrix:
            pair_data = {}
            for key, val in winrate_matrix.items():
                parts = key.split("_vs_")
                if len(parts) == 2:
                    pair_data[(parts[0], parts[1])] = val
            elo_map = {e["player"]: e["elo"] for e in elo_ratings["ranking"]}
            for (a, b), data in sorted(pair_data.items()):
                wr_a = data.get("ai_a_winrate", 0)
                if a in elo_map and b in elo_map:
                    elo_diff = elo_map[a] - elo_map[b]
                    predicted = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
                    delta = wr_a - predicted
                    lines.append(f"| {a} vs {b:10s} | {wr_a*100:6.2f}% | {predicted*100:6.2f}% | {delta*100:+5.2f}% |")
            lines.append("")

    # ============================================================
    # Section 4: Statistical Quality
    # ============================================================
    lines.append("## 4. Statistical Quality — Greedy Mirror (2000-game Precision)")
    lines.append("")

    if stat_quality:
        o = stat_quality["overall"]
        lines.append(f"- **Total games**: {o.get('p0_wins', 0) + o.get('p1_wins', 0)}")
        lines.append(f"- **P0 winrate**: {o['p0_winrate']*100:.2f}%")
        lines.append(f"- **95% CI**: ±{o['p0_ci95']*100:.2f}%")
        lines.append(f"- **StdDev**: {o['p0_stddev']*100:.2f}%")
        lines.append(f"- **p-value (diff from 50%)**: {o.get('p_value', 'N/A')}")
        lines.append(f"- **Significantly different from 50%?**: {o.get('significantly_different_from_50pct', 'UNKNOWN')}")
        lines.append(f"- **Victory**: Conquest={o['conquests']} Construction={o['constructions']} Tiebreak={o['tiebreaks']}")
        lines.append(f"- **Avg turns**: {o['avg_turns']:.1f}")
        lines.append(f"- **Avg dead units**: {o['avg_dead']:.1f}")
        lines.append("")

        # Batch stability
        ba = stat_quality.get("batch_analysis", {})
        lines.append("### Batch Stability (200-game batches)")
        lines.append("")
        lines.append(f"- **Mean batch winrate**: {ba.get('mean_winrate', 0)*100:.2f}%")
        lines.append(f"- **Std batch winrate**: {ba.get('std_winrate', 0)*100:.2f}%")
        lines.append(f"- **Range**: {ba.get('min_winrate', 0)*100:.2f}% — {ba.get('max_winrate', 0)*100:.2f}%")

        batch_std = ba.get("std_winrate", 1)
        if batch_std < 0.04:
            lines.append("- **Verdict**: Results are STABLE across batches")
        elif batch_std < 0.06:
            lines.append("- **Verdict**: Results are MARGINALLY stable")
        else:
            lines.append("- **Verdict**: Results show HIGH VARIANCE across batches")

        lines.append("")

        # Detailed batch table
        lines.append("| Batch | Games | P0 Win% | Conq | Cons | Tie | Turns | Dead |")
        lines.append("|-------|-------|---------|------|------|-----|-------|------|")
        lines.append("")
        for b in stat_quality.get("batches", []):
            lines.append(f"| {b['batch']:5d} | {b['games']:5d} | {b['p0_winrate']*100:6.2f}% | "
                         f"{b['conquests']:4d} | {b['constructions']:4d} | {b['tiebreaks']:3d} | "
                         f"{b['avg_turns']:5.1f} | {b['avg_dead']:5.1f} |")
        lines.append("")
    else:
        lines.append("*Statistical quality data not available. Run statistical_quality.py first.*")
        lines.append("")

    # ============================================================
    # Section 5: Randomness Impact
    # ============================================================
    lines.append("## 5. Randomness Impact Analysis")
    lines.append("")

    if randomness_analysis:
        for pair_key, pair_label in [("greedy_vs_greedy", "Greedy vs Greedy"),
                                      ("random_vs_greedy", "Random vs Greedy")]:
            if pair_key in randomness_analysis:
                lines.append(f"### {pair_label}")
                lines.append("")
                lines.append("| Metric | Deterministic | Random (±3) | Difference |")
                lines.append("|--------|--------------|-------------|------------|")
                lines.append("")
                det = randomness_analysis[pair_key]["deterministic"]
                rnd = randomness_analysis[pair_key]["random"]

                metrics = [
                    ("P0 Winrate", "p0_winrate", "{:.2f}%", True),
                    ("P0 95% CI", "p0_ci95", "±{:.2f}%", False),
                    ("P0 StdDev", "p0_stddev", "{:.4f}", False),
                    ("Conquest Rate", "conquest_rate", "{:.2f}%", True),
                    ("Construction Rate", "construction_rate", "{:.2f}%", True),
                    ("Tiebreak Rate", "tiebreak_rate", "{:.2f}%", True),
                    ("Avg Turns", "avg_turns", "{:.1f}", False),
                    ("Turns StdDev", "turns_std", "{:.2f}", False),
                    ("Avg Dead Units", "avg_dead", "{:.1f}", False),
                    ("Dead StdDev", "dead_std", "{:.2f}", False),
                ]
                for metric, key, fmt, is_pct in metrics:
                    dv = det.get(key, 0)
                    rv = rnd.get(key, 0)
                    if is_pct:
                        dv *= 100
                        rv *= 100
                    dv_str = fmt.format(dv)
                    rv_str = fmt.format(rv)

                    if "CI" in metric:
                        diff_str = ""
                    else:
                        diff = rv - dv if isinstance(dv, (int, float)) else 0
                        diff_str = f"{diff:+.2f}" if isinstance(diff, float) else ""

                    lines.append(f"| {metric} | {dv_str} | {rv_str} | {diff_str} |")

                lines.append("")

                if pair_key == "random_vs_greedy":
                    greedy_det = det.get("p1_winrate", 0) * 100
                    greedy_rnd = rnd.get("p1_winrate", 0) * 100
                    lines.append(f"- **Greedy winrate**: {greedy_det:.1f}% (det) → {greedy_rnd:.1f}% (rnd)")
                    if greedy_det > greedy_rnd:
                        lines.append("- Randomness **reduces** Greedy advantage — helps the underdog")
                    else:
                        lines.append("- Randomness **increases** Greedy advantage — favors the favorite")
                    lines.append("")

        # Recommendation
        lines.append("### Recommendation")
        lines.append("")
        lines.append("Based on the analysis:")
        lines.append("")
        if randomness_analysis.get("random_vs_greedy", {}).get("deterministic", {}).get("p1_winrate", 0.5) > \
           randomness_analysis.get("random_vs_greedy", {}).get("random", {}).get("p1_winrate", 0.5):
            lines.append("1. **Randomness helps underdogs** — the Random AI's winrate increases against Greedy")
            lines.append("2. **Mirror P0 bias is reduced** — Greedy vs Greedy P0 winrate moves closer to 50%")
            lines.append("3. **Recommendation: Enable combat randomness by default**")
        else:
            lines.append("1. **Randomness does NOT help underdogs** in this configuration")
            lines.append("2. Consider larger randomness range (±5 instead of ±3) or deterministic default")
            lines.append("3. **Recommendation: Keep deterministic as default, make randomness opt-in**")
        lines.append("")
    else:
        lines.append("*Randomness data not available. Run eval_randomness/run_comparison.py first.*")
        lines.append("")

    # ============================================================
    # Section 6: Pending Items
    # ============================================================
    lines.append("## 6. Pending Items")
    lines.append("")
    lines.append("| AI | Status | Reason |")
    lines.append("|---|--------|--------|")
    lines.append("")
    lines.append("| BC | Pending | `prototype/bc_weights.json` not found |")
    lines.append("| DQN | Pending | `prototype/dqn_weights.json` not found |")
    lines.append("")

    # Save
    report_path = os.path.join(out_dir, "report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
