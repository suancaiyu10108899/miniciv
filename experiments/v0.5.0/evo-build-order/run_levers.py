"""
Sequential scan: edit constants.py, test, record, repeat.
Simple and reliable — no multiprocessing, no module cache magic.
"""
import json, sys, subprocess, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent.parent
CONSTANTS = PROJECT / "prototype" / "constants.py"
TEST_SCRIPT = Path(__file__).resolve().parent / "quick_test.py"
ORIG = CONSTANTS.read_text(encoding='utf-8')

CONFIGS = [
    # (label, c5_cost, c5_turns)
    ("baseline(3,3,3)t2", (3,3,3), 2),
    ("C5(4,3,3)t2", (4,3,3), 2),
    ("C5(3,4,3)t2", (3,4,3), 2),
    ("C5(3,3,4)t2", (3,3,4), 2),
    ("C5(5,3,3)t2", (5,3,3), 2),
    ("C5(3,3,5)t2", (3,3,5), 2),
    ("C5(3,3,3)t4", (3,3,3), 4),
    ("C5(3,3,3)t6", (3,3,3), 6),
    ("C5(4,3,3)t4", (4,3,3), 4),
    ("C5(3,3,4)t4", (3,3,4), 4),
]

GAMES = 60
BASE_SEED = 555

def apply(cost, turns):
    content = CONSTANTS.read_text(encoding='utf-8')
    # Replace C5 line
    import re
    # Find the C5 entry
    old = '"C5":  {"cost": (3, 3, 3),   "turns": 2, "requires": ["C3","C4"],"effect": "construction_victory"}'
    new = f'"C5":  {{"cost": {cost},   "turns": {turns}, "requires": ["C3","C4"],"effect": "construction_victory"}}'
    if old in content:
        content = content.replace(old, new)
    else:
        # Fallback: regex replace
        content = re.sub(
            r'"C5":\s*\{"cost":\s*\([^)]+\),\s*"turns":\s*\d+',
            f'"C5": {{"cost": {cost}, "turns": {turns}',
            content
        )
    CONSTANTS.write_text(content, encoding='utf-8')

results = []
for label, cost, turns in CONFIGS:
    apply(cost, turns)
    print(f"{label}: ", end="", flush=True)
    r = subprocess.run(
        [sys.executable, str(TEST_SCRIPT), str(GAMES), str(BASE_SEED)],
        capture_output=True, text=True, timeout=3600, cwd=str(PROJECT)
    )
    if r.returncode == 0:
        data = json.loads(r.stdout.strip())
        data["label"] = label
        data["c5_cost"] = list(cost)
        data["c5_turns"] = turns
        results.append(data)
        print(f"wr={data['evo_winrate']:.1f}% const={data['construction_winrate']:.1f}% ({data['elapsed_s']}s)")
    else:
        print(f"FAILED: {r.stderr[:200]}")

# Restore
CONSTANTS.write_text(ORIG, encoding='utf-8')

# Summary
print(f"\n{'='*60}")
print(f"{'Config':<25} {'EvoWR':<8} {'ConstWR':<8}")
print("-" * 42)
for r in results:
    print(f"{r['label']:<25} {r['evo_winrate']:>5.1f}%   {r['construction_winrate']:>5.1f}%")

OUTDIR = Path(__file__).resolve().parent
with open(OUTDIR / "levers_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to {OUTDIR / 'levers_results.json'}")
