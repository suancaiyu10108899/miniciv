#!/usr/bin/env python
"""Analyze v0.6.0 full matrix results and produce REPORT.md.
Run after eval_matrix completes.
"""
import json, os, sys, time
from collections import defaultdict
from pathlib import Path

DIR = Path(__file__).parent

def load_pair(filepath):
    with open(filepath) as f:
        return json.load(f)

def summarize_paired(ai_a, ai_b, results):
    """Paired summary with per-unit-type stats."""
    # results is from eval_matrix paired mode: list of dicts with ai_a_wins, p0_wins, etc.
    # OR verify_facility8 format: list of game results with _tag
    n = len(results)
    if n == 0:
        return None

    # Detect format
    r0 = results[0]
    if "ai_a_wins" in r0:
        # eval_matrix format
        ai_a_wins = sum(r["ai_a_wins"] for r in results)
        ai_b_wins = sum(r["ai_b_wins"] for r in results)
        p0_wins = sum(r["p0_wins"] for r in results)
        total_games = n * 2
        cq = sum(r["tot_conquest"] for r in results)
        cs = sum(r["tot_construction"] for r in results)
        tie = total_games - cq - cs
        return {
            "ai_a": ai_a, "ai_b": ai_b, "n_paired_seeds": n, "n_games": total_games,
            "ai_a_wr": round(ai_a_wins / total_games, 4) if total_games else 0,
            "ai_b_wr": round(ai_b_wins / total_games, 4) if total_games else 0,
            "p0_wr": round(p0_wins / total_games, 4) if total_games else 0,
            "conquest": round(cq / total_games, 4) if total_games else 0,
            "construction": round(cs / total_games, 4) if total_games else 0,
            "tiebreak": round(tie / total_games, 4) if total_games else 0,
        }
    elif "_tag" in r0:
        # verify_facility8 format
        forward = [r for r in results if r["_tag"] == "forward"]
        back = [r for r in results if r["_tag"] == "backward"]
        total = len(results)
        a_wins = sum(1 for r in forward if r["winner"]==0) + sum(1 for r in back if r["winner"]==1)
        b_wins = sum(1 for r in forward if r["winner"]==1) + sum(1 for r in back if r["winner"]==0)
        p0_w = sum(1 for r in results if r["winner"]==0)
        vtypes = [r.get("victory_type","") or "" for r in results]
        cq = sum(1 for v in vtypes if v=="conquest")
        cs = sum(1 for v in vtypes if v=="construction")
        tie = total - cq - cs
        # Per-unit-type
        utypes = ["infantry","cavalry","archer","scout","worker"]
        a_ut = {}; b_ut = {}
        for ut in utypes:
            a_alive = sum(r.get(f"p0_{ut}_alive",0) if r["_tag"]=="forward" else r.get(f"p1_{ut}_alive",0) for r in results)
            a_dead = sum(r.get(f"p0_{ut}_dead",0) if r["_tag"]=="forward" else r.get(f"p1_{ut}_dead",0) for r in results)
            b_alive = sum(r.get(f"p1_{ut}_alive",0) if r["_tag"]=="forward" else r.get(f"p0_{ut}_alive",0) for r in results)
            b_dead = sum(r.get(f"p1_{ut}_dead",0) if r["_tag"]=="forward" else r.get(f"p0_{ut}_dead",0) for r in results)
            a_ut[ut] = {"alive": round(a_alive/total,2), "dead": round(a_dead/total,2)}
            b_ut[ut] = {"alive": round(b_alive/total,2), "dead": round(b_dead/total,2)}
        a_facs = sum(r.get("p0_facilities",0) if r["_tag"]=="forward" else r.get("p1_facilities",0) for r in results)/total
        b_facs = sum(r.get("p1_facilities",0) if r["_tag"]=="forward" else r.get("p0_facilities",0) for r in results)/total
        return {
            "ai_a": ai_a, "ai_b": ai_b, "n_paired_seeds": total//2, "n_games": total,
            "ai_a_wr": round(a_wins/total,4) if total else 0,
            "ai_b_wr": round(b_wins/total,4) if total else 0,
            "p0_wr": round(p0_w/total,4) if total else 0,
            "conquest": round(cq/total,4) if total else 0,
            "construction": round(cs/total,4) if total else 0,
            "tiebreak": round(tie/total,4) if total else 0,
            "ai_a_units": a_ut, "ai_b_units": b_ut,
            "ai_a_facilities": round(a_facs,2), "ai_b_facilities": round(b_facs,2),
        }
    return None


def main():
    # Find all paired JSON files
    files = sorted(DIR.glob("paired_*.json"))
    if not files:
        print("No paired_*.json files found. Matrix still running?")
        return

    print(f"Analyzing {len(files)} pair files...")
    summaries = []
    for fp in files:
        stem = fp.name.replace("paired_","").replace(".json","")
        parts = stem.split("_vs_")
        if len(parts) != 2:
            print(f"  SKIP {fp.name}: can't parse AI names")
            continue
        ai_a, ai_b = parts[0], parts[1]
        results = load_pair(fp)
        if not results:
            print(f"  SKIP {fp.name}: empty")
            continue
        s = summarize_paired(ai_a, ai_b, results)
        if s:
            summaries.append(s)
            print(f"  {ai_a} vs {ai_b}: {s['ai_a_wr']:.1%} vs {s['ai_b_wr']:.1%}, "
                  f"CQ={s['conquest']:.1%} CS={s['construction']:.1%} TB={s['tiebreak']:.1%}")

    if not summaries:
        print("No summaries generated.")
        return

    # Global stats
    total_games = sum(s["n_games"] for s in summaries)
    total_cq = sum(int(s["conquest"]*s["n_games"]) for s in summaries)
    total_cs = sum(int(s["construction"]*s["n_games"]) for s in summaries)
    total_tb = sum(int(s["tiebreak"]*s["n_games"]) for s in summaries)
    avg_p0 = sum(s["p0_wr"]*s["n_games"] for s in summaries) / total_games

    # AI rankings
    AIS = ["random","greedy","aggressive","flatmc","dqn_trained","evo"]
    wr = defaultdict(lambda: defaultdict(float))
    for s in summaries:
        wr[s["ai_a"]][s["ai_b"]] = s["ai_a_wr"]
        wr[s["ai_b"]][s["ai_a"]] = s["ai_b_wr"]

    # Compute average winrate per AI
    ai_avg_wr = {}
    for ai in AIS:
        wrs = []
        for other in AIS:
            if ai == other: continue
            if wr[ai][other] > 0 or (other in wr and ai in wr[other]):
                val = wr[ai].get(other, 1 - wr[other].get(ai, 0.5))
                wrs.append(val)
        ai_avg_wr[ai] = sum(wrs)/len(wrs) if wrs else 0

    # Check targets
    checks = []
    checks.append(("建设率 > 30%", total_cs/total_games, 0.30, total_cs/total_games >= 0.30))
    checks.append(("征服率 > 30%", total_cq/total_games, 0.30, total_cq/total_games >= 0.30))
    checks.append(("阶梯率 < 25%", total_tb/total_games, 0.25, total_tb/total_games <= 0.25))
    evo_wr_val = ai_avg_wr.get("evo", 1.0)
    checks.append(("Evo < 60%", evo_wr_val, 0.60, evo_wr_val <= 0.60))
    checks.append(("P0 < 53%", avg_p0, 0.53, avg_p0 <= 0.53))

    # Check unit diversity
    unit_diversity_ok = True
    for ai in ["greedy","aggressive","dqn_trained"]:
        for ut in ["cavalry","archer"]:
            # Check if avg alive > 1.0 across all this AI's games
            total = 0
            count = 0
            for s in summaries:
                if s.get("ai_a_units") and s["ai_a"] == ai:
                    total += s["ai_a_units"].get(ut,{}).get("alive",0)
                    count += 1
                if s.get("ai_b_units") and s["ai_b"] == ai:
                    total += s["ai_b_units"].get(ut,{}).get("alive",0)
                    count += 1
            avg = total/count if count > 0 else 0
            if avg < 1.0:
                unit_diversity_ok = False
                break

    # Write REPORT.md
    report = []
    report.append("# v0.6.0 Full Matrix Report\n")
    report.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**Config**: facility=5, 15x15 balanced, stacking limit (1 combat+1 civilian/tile)")
    report.append(f"**Greedy**: v5 (construction intent + unit diversity + worker expansion)")
    report.append(f"**Games**: {total_games} total ({len(summaries)} pairs x 200 paired seeds)\n")

    report.append("## Win Rate Matrix\n")
    report.append(f"| | {' | '.join(AIS)} | Avg WR |")
    report.append(f"|---|{'|'.join(['---' for _ in AIS])}|---|")
    for ai_a in AIS:
        row = f"| {ai_a} |"
        wrs = []
        for ai_b in AIS:
            if ai_a == ai_b:
                row += " -- |"
            else:
                val = wr[ai_a].get(ai_b)
                if val is not None:
                    row += f" {val:.1%} |"
                    wrs.append(val)
                else:
                    row += " ? |"
        avg = sum(wrs)/len(wrs) if wrs else 0
        row += f" {avg:.1%} |"
        report.append(row)

    report.append(f"\n## Aggregate\n")
    report.append(f"- Construction: {total_cs/total_games:.1%}")
    report.append(f"- Conquest: {total_cq/total_games:.1%}")
    report.append(f"- Tiebreak: {total_tb/total_games:.1%}")
    report.append(f"- P0 winrate: {avg_p0:.1%}")

    report.append(f"\n## Target Check\n")
    for name, val, target, ok in checks:
        status = "PASS" if ok else "FAIL"
        report.append(f"- {status}: {name} (actual: {val:.1%}, target: {target:.1%})")

    report.append(f"\n## AI Rankings (avg winrate)\n")
    for ai in sorted(ai_avg_wr, key=lambda a: ai_avg_wr[a], reverse=True):
        report.append(f"- {ai}: {ai_avg_wr[ai]:.1%}")

    report.append(f"\n## Per-Pair Detail\n")
    for s in summaries:
        report.append(f"### {s['ai_a']} vs {s['ai_b']}")
        report.append(f"- Winrate: {s['ai_a']}={s['ai_a_wr']:.1%} {s['ai_b']}={s['ai_b_wr']:.1%} P0={s['p0_wr']:.1%}")
        report.append(f"- Victory: Conquest={s['conquest']:.1%} Construction={s['construction']:.1%} Tiebreak={s['tiebreak']:.1%}")
        if s.get("ai_a_units"):
            for ut in ["infantry","cavalry","archer","scout","worker"]:
                au = s["ai_a_units"].get(ut,{})
                bu = s["ai_b_units"].get(ut,{})
                report.append(f"- {ut}: {s['ai_a']}={au.get('alive',0)}/{au.get('dead',0)} {s['ai_b']}={bu.get('alive',0)}/{bu.get('dead',0)}")
        if s.get("ai_a_facilities"):
            report.append(f"- Facilities: {s['ai_a']}={s['ai_a_facilities']} {s['ai_b']}={s['ai_b_facilities']}")
        report.append("")

    report_path = DIR / "REPORT.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report))
    print(f"\nReport saved to {report_path}")

    # Summary JSON
    summary = {
        "experiment": "v0.6.0-full-matrix",
        "date": time.strftime("%Y-%m-%d"),
        "config": {"facility": 5, "size": 15, "stacking": "1 combat + 1 civilian per tile"},
        "aggregate": {
            "construction": round(total_cs/total_games, 4),
            "conquest": round(total_cq/total_games, 4),
            "tiebreak": round(total_tb/total_games, 4),
            "p0_winrate": round(avg_p0, 4),
        },
        "target_checks": {name: {"actual": round(val,4), "target": target, "pass": ok}
                         for name, val, target, ok in checks},
        "ai_rankings": {ai: round(wr,4) for ai, wr in sorted(ai_avg_wr.items(), key=lambda x: -x[1])},
    }
    with open(DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to {DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
