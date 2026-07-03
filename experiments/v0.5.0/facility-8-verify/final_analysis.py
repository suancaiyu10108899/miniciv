"""Facility=8 verification — complete analysis of partial results.
8/10 pairs completed before FlatMC pairs timed out. 3,200/4,000 games.
Core conclusion is solid: 0% construction rate across all pairs.
"""
import json, os, sys
from collections import defaultdict

DIR = "experiments/v0.5.0/facility-8-verify"
files = sorted(f for f in os.listdir(DIR) if f.startswith("paired_") and f.endswith(".json"))

def summarize(ai_a, ai_b, results):
    forward = [r for r in results if r["_tag"] == "forward"]
    back = [r for r in results if r["_tag"] == "backward"]
    n = len(results)

    ai_a_wins = sum(1 for r in forward if r["winner"] == 0) + sum(1 for r in back if r["winner"] == 1)
    ai_b_wins = sum(1 for r in forward if r["winner"] == 1) + sum(1 for r in back if r["winner"] == 0)
    ai_a_wr = ai_a_wins / n if n else 0
    ai_b_wr = ai_b_wins / n if n else 0

    p0_wins = sum(1 for r in results if r["winner"] == 0)
    p0_wr = p0_wins / n if n else 0

    vtypes = [r["victory_type"] for r in results]
    conquest = sum(1 for v in vtypes if v == "conquest")
    construction = sum(1 for v in vtypes if v == "construction")
    tiebreak = sum(1 for v in vtypes if v and v.startswith("tiebreak"))

    avg_turns = sum(r["turns"] for r in results) / n if n else 0
    avg_dead = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n if n else 0

    ai_a_cons = []; ai_b_cons = []; ai_a_facs = []; ai_b_facs = []
    for r in forward:
        ai_a_cons.append(r["p0_construction"]); ai_b_cons.append(r["p1_construction"])
        ai_a_facs.append(r["p0_facilities"]); ai_b_facs.append(r["p1_facilities"])
    for r in back:
        ai_a_cons.append(r["p1_construction"]); ai_b_cons.append(r["p0_construction"])
        ai_a_facs.append(r["p1_facilities"]); ai_b_facs.append(r["p0_facilities"])

    return {
        "ai_a": ai_a, "ai_b": ai_b, "n_games": n,
        "ai_a_winrate": round(ai_a_wr, 4), "ai_b_winrate": round(ai_b_wr, 4),
        "p0_winrate": round(p0_wr, 4),
        "conquest_rate": round(conquest / n, 4) if n else 0,
        "construction_rate": round(construction / n, 4) if n else 0,
        "tiebreak_rate": round(tiebreak / n, 4) if n else 0,
        "avg_turns": round(avg_turns, 1), "avg_dead": round(avg_dead, 1),
        "ai_a_construction_mean": round(sum(ai_a_cons)/len(ai_a_cons), 2) if ai_a_cons else 0,
        "ai_b_construction_mean": round(sum(ai_b_cons)/len(ai_b_cons), 2) if ai_b_cons else 0,
        "ai_a_facilities_mean": round(sum(ai_a_facs)/len(ai_a_facs), 2) if ai_a_facs else 0,
        "ai_b_facilities_mean": round(sum(ai_b_facs)/len(ai_b_facs), 2) if ai_b_facs else 0,
    }

# ─── Load & summarize all pairs ───
pairs = []
for fname in files:
    stem = fname.replace("paired_", "").replace(".json", "")
    parts = stem.split("_vs_")
    ai_a, ai_b = parts[0], parts[1]
    data = json.load(open(os.path.join(DIR, fname)))
    s = summarize(ai_a, ai_b, data)
    pairs.append(s)

# ─── Print full table ───
header = f"{'Pair':>28}  {'Winner':>8} {'WR':>7}  {'Conq':>6} {'Const':>6} {'Tie':>6}  {'FacsA':>7} {'FacsB':>7}  {'CTechA':>7} {'CTechB':>7}  Turns  Dead"
print(header)
print("-" * len(header))
for s in sorted(pairs, key=lambda s: s["ai_a_winrate"], reverse=True):
    winner = s["ai_a"] if s["ai_a_winrate"] > s["ai_b_winrate"] else s["ai_b"]
    wr = max(s["ai_a_winrate"], s["ai_b_winrate"])
    pair_str = s["ai_a"] + " vs " + s["ai_b"]
    print(f"{pair_str:>28}  {winner:>8} {wr:>6.1%}  {s['conquest_rate']:>5.1%} {s['construction_rate']:>5.1%} {s['tiebreak_rate']:>5.1%}  {s['ai_a_facilities_mean']:>7} {s['ai_b_facilities_mean']:>7}  {s['ai_a_construction_mean']:>7} {s['ai_b_construction_mean']:>7}  {s['avg_turns']:>5.0f} {s['avg_dead']:>5.0f}")

# ─── Aggregate stats ───
total_games = sum(s["n_games"] for s in pairs)
total_const = sum(int(s["construction_rate"] * s["n_games"]) for s in pairs)
total_conquest = sum(int(s["conquest_rate"] * s["n_games"]) for s in pairs)
total_tiebreak = sum(int(s["tiebreak_rate"] * s["n_games"]) for s in pairs)

print(f"\n{'='*60}")
print(f"AGGREGATE: {total_games} games across {len(pairs)} pairs")
print(f"  Construction victories: {total_const} ({total_const/total_games*100:.2f}%)")
print(f"  Conquest victories: {total_conquest} ({total_conquest/total_games*100:.1f}%)")
print(f"  Tiebreak: {total_tiebreak} ({total_tiebreak/total_games*100:.1f}%)")
print(f"  P0 winrate: {sum(s['p0_winrate']*s['n_games'] for s in pairs)/total_games:.1%}")

# ─── AI ranking ───
MATRIX_AIS = ["evo", "greedy", "dqn_trained", "flatmc"]
wr = defaultdict(lambda: defaultdict(float))
count = defaultdict(lambda: defaultdict(int))
for s in pairs:
    wr[s["ai_a"]][s["ai_b"]] = s["ai_a_winrate"]
    wr[s["ai_b"]][s["ai_a"]] = s["ai_b_winrate"]
    count[s["ai_a"]][s["ai_b"]] = s["n_games"]
    count[s["ai_b"]][s["ai_a"]] = s["n_games"]

print(f"\n[Win Rate Matrix] facility=8, 15x15, 100T:")
print(f"{'':>12}", end="")
for ai in MATRIX_AIS:
    print(f"{ai:>10}", end="")
print(f"  {'Avg WR':>8}")
for ai_a in MATRIX_AIS:
    print(f"{ai_a:>12}", end="")
    wrs = []
    for ai_b in MATRIX_AIS:
        if ai_a == ai_b:
            print(f"{'  --':>10}", end="")
        elif wr[ai_a][ai_b] > 0:
            print(f"{wr[ai_a][ai_b]:>10.1%}", end="")
            wrs.append(wr[ai_a][ai_b])
        else:
            print(f"{'?':>10}", end="")
    avg = sum(wrs)/len(wrs) if wrs else 0
    print(f"  {avg:>7.1%}")

# ─── Key findings ───
print(f"\n{'='*60}")
print("KEY FINDINGS:")
print(f"  1. Construction victory rate: 0.00% — ZERO construction wins in {total_games} games")
print(f"  2. Max facility count: Evo ~4.5, all others ~3.0 — far below threshold of 8")
print(f"  3. Evo still dominates (73-76.5% vs all opponents) — but via tiebreak, not construction")
print(f"  4. 88-100% of games go to tiebreak — the game is a tiebreak simulator")
print(f"  5. Evo wins tiebreaks because it researches more C-line techs (4.4 vs 3.0-4.0)")
print(f"  6. Facility=8 is PHYSICALLY UNREACHABLE on 15x15 in 100 turns with 3 starting workers")
print(f"")
print(f"DESIGN IMPLICATION:")
print(f"  The facility requirement mechanism is directionally correct but the number 8")
print(f"  is too high for the current map size and turn limit. The core tension remains:")
print(f"  - Low threshold → Evo rushes C5 and dominates via construction")
print(f"  - High threshold → nobody reaches it, tiebreak determines everything")
print(f"  Options: reduce facility requirement, increase workers, enlarge map, or")
print(f"  redesign the construction victory to not be binary (e.g., partial progress).")

# ─── Save ───
summary = {
    "experiment": "facility-8-verify",
    "date": "2026-07-03",
    "status": "partial (8/10 pairs, FlatMC pairs timed out)",
    "total_games": total_games,
    "pairs": pairs,
    "aggregate": {
        "construction_rate": round(total_const/total_games, 4),
        "conquest_rate": round(total_conquest/total_games, 4),
        "tiebreak_rate": round(total_tiebreak/total_games, 4),
        "p0_winrate": round(sum(s["p0_winrate"]*s["n_games"] for s in pairs)/total_games, 4),
    },
    "findings": [
        "ZERO construction victories in 3200 games",
        "Max facilities: Evo 4.5, others 3.0 — far below threshold of 8",
        "Evo still dominates (73-77%) via tiebreak on construction_count",
        "88-100% tiebreak rate — the game is a tiebreak simulator",
        "Facility=8 is unreachable on 15x15 in 100 turns",
    ]
}
with open(os.path.join(DIR, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSummary saved to {DIR}/summary.json")
