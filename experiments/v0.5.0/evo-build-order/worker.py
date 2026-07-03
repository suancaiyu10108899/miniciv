"""
Worker: copy prototype/ to temp dir, patch constants, run games.
No file conflicts, no module cache issues. Each worker is fully isolated.
Usage: python worker.py <label> <food> <wood> <gold> <turns> <games> <seed>
"""
import json, sys, shutil, os, random, time, tempfile
from pathlib import Path

label = sys.argv[1]
c5_cost = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
c5_turns = int(sys.argv[5])
games = int(sys.argv[6])
base_seed = int(sys.argv[7])

PROJECT = Path(__file__).resolve().parent.parent.parent.parent

# 1. Copy prototype/ to temp dir
tmpdir = tempfile.mkdtemp(prefix="miniciv_evo_")
shutil.copytree(PROJECT / "prototype", Path(tmpdir) / "prototype")

# 2. Patch constants in temp copy
const_path = Path(tmpdir) / "prototype" / "constants.py"
content = const_path.read_text(encoding='utf-8')
old = '"C5":  {"cost": (3, 3, 3),   "turns": 2, "requires": ["C3","C4"],"effect": "construction_victory"},'
new = f'"C5":  {{"cost": {c5_cost},   "turns": {c5_turns}, "requires": ["C3","C4"],"effect": "construction_victory"}},'
if old in content:
    content = content.replace(old, new)
else:
    # Fallback: just change the C5 line (more robust)
    import re
    content = re.sub(
        r'"C5":\s*\{[^}]*"cost":\s*\([^)]*\)[^}]*\}',
        f'"C5": {{"cost": {c5_cost}, "turns": {c5_turns}, "requires": ["C3","C4"], "effect": "construction_victory"}}',
        content
    )
const_path.write_text(content, encoding='utf-8')

# 3. Add temp dir to path BEFORE project root
sys.path.insert(0, tmpdir)

# 4. Import from temp copy
from prototype.game import init_game, step_game
from prototype.eval import load_ai

evo = load_ai("evo")
greedy = load_ai("greedy")

evo_wins, const_wins, total = 0, 0, 0
t0 = time.time()

for i in range(games):
    seed = base_seed + i * 1000
    for evo_p0 in [True, False]:
        gs_seed = seed if evo_p0 else seed + 1000000
        gs = init_game(seed=gs_seed, size=15, generator_id="balanced")
        r0, r1 = random.Random(gs_seed), random.Random(gs_seed + 1)
        if evo_p0:
            while gs.winner is None and gs.turn < 100:
                step_game(gs, evo(gs, 0, r0), greedy(gs, 1, r1))
        else:
            while gs.winner is None and gs.turn < 100:
                step_game(gs, greedy(gs, 0, r0), evo(gs, 1, r1))
        evo_won = (evo_p0 and gs.winner == 0) or (not evo_p0 and gs.winner == 1)
        total += 1
        if evo_won:
            evo_wins += 1
            if gs.victory_type == "construction":
                const_wins += 1

wr = evo_wins / total * 100
cwr = const_wins / total * 100
elapsed = time.time() - t0

# 5. Cleanup temp dir
shutil.rmtree(tmpdir, ignore_errors=True)

print(json.dumps({
    "label": label, "c5_cost": list(c5_cost), "c5_turns": c5_turns,
    "games": games, "total": total,
    "evo_winrate": round(wr, 1), "construction_winrate": round(cwr, 1),
    "elapsed_s": round(elapsed, 1)
}))
