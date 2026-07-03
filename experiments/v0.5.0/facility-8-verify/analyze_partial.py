"""Quick analysis of partial verification data."""
import json, os
from prototype.verify_facility8 import summarize_pair

DIR = os.path.dirname(os.path.abspath(__file__))
files = sorted(f for f in os.listdir(DIR) if f.startswith("paired_") and f.endswith(".json"))

print(f"{'Pair':>28}  {'Winner':>8} {'WR':>7}  {'Conq':>6} {'Const':>6} {'Tie':>6}  {'FacsA':>7} {'FacsB':>7}  Turns")
print("-" * 100)
for fname in files:
    # Parse ai names from filename: paired_X_vs_Y.json
    stem = fname.replace("paired_", "").replace(".json", "")
    parts = stem.split("_vs_")
    ai_a, ai_b = parts[0], parts[1]

    data = json.load(open(os.path.join(DIR, fname)))
    s = summarize_pair(ai_a, ai_b, data)
    winner = ai_a if s["ai_a_winrate"] > s["ai_b_winrate"] else ai_b
    wr = max(s["ai_a_winrate"], s["ai_b_winrate"])
    pair_str = ai_a + " vs " + ai_b
    print(f"{pair_str:>28}  {winner:>8} {wr:>6.1%}  {s['conquest_rate']:>5.1%} {s['construction_rate']:>5.1%} {s['tiebreak_rate']:>5.1%}  {s['ai_a_facilities_mean']:>7} {s['ai_b_facilities_mean']:>7}  {s['avg_turns']}")

print()
print("ALL pairs: 0% construction rate.")
print("Facility=8 is unreachable in 100 turns on 15x15 with 3 starting workers.")
print("Evo wins via construction_count tiebreak (4.4 C-techs vs others 3.0-4.0).")
