"""
Run one C5 config as independent subprocess. In-memory patch, no file writes.
Usage: python scan_one_config.py <label> <c5_cost_food> <c5_cost_wood> <c5_cost_gold> <c5_turns> <games> <base_seed>
Outputs JSON to stdout (single line).
"""
import json, sys, random, time

label = sys.argv[1]
c5_cost = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
c5_turns = int(sys.argv[5])
games = int(sys.argv[6])
base_seed = int(sys.argv[7])

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# ── In-memory patch (before any other prototype import) ──
import prototype.constants as c
c.TECH_TREE["C5"] = {
    "cost": c5_cost, "turns": c5_turns,
    "requires": ["C3","C4"], "effect": "construction_victory"
}
# Clear cached imports so they pick up the patched TECH_TREE
for mod in ['prototype.game', 'prototype.tech', 'prototype.eval',
            'prototype.ai_evo', 'prototype.ai_greedy',
            'prototype.ai_rulesrandom', 'prototype.ai_aggressive',
            'prototype.ai_flatmc', 'prototype.ai_dqn',
            'prototype.combat', 'prototype.movement',
            'prototype.economy', 'prototype.unit',
            'prototype.mapgen', 'prototype.terrain']:
    sys.modules.pop(mod, None)

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

print(json.dumps({
    "label": label, "c5_cost": list(c5_cost), "c5_turns": c5_turns,
    "games": games, "total": total,
    "evo_winrate": round(wr, 1), "construction_winrate": round(cwr, 1),
    "elapsed_s": round(elapsed, 1)
}))
