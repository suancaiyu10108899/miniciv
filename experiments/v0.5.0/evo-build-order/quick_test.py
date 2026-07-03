"""
Quick test: Evo vs Greedy, N paired games. Uses current constants.py.
Usage: python quick_test.py <games> <base_seed>
Prints: JSON with winrate, construction_winrate, avg_turns
"""
import json, sys, random, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

games = int(sys.argv[1])
base_seed = int(sys.argv[2])

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
result = {"games": games, "total": total, "evo_winrate": round(wr,1),
          "construction_winrate": round(cwr,1), "elapsed_s": round(elapsed,1)}
print(json.dumps(result))
