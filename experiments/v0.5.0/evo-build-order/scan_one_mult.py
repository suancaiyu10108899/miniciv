"""
Run one C5 multiplier config as subprocess. Memory-patch, no file race.
Usage: python scan_one_mult.py <mult> <games> <base_seed>
"""
import json, sys, random, time, os
from pathlib import Path

mult = float(sys.argv[1])
games = int(sys.argv[2])
base_seed = int(sys.argv[3])

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# ── Memory-patch BEFORE any prototype imports ──
# The key insight: patch the module dict BEFORE other modules cache it.
import prototype.constants as c
nc = (round(3*mult), round(3*mult), round(3*mult))
c.TECH_TREE["C5"] = {"cost": nc, "turns": 2, "requires": ["C3","C4"], "effect": "construction_victory"}
# Also need to clear any cached TECH_TREE_COST in modules that import it
# Force re-import of affected modules by removing from sys.modules
for mod in list(sys.modules):
    if 'prototype' in mod and mod not in ('prototype.constants',):
        del sys.modules[mod]

# Now import cleanly
from prototype.game import init_game, step_game
from prototype.eval import load_ai

evo = load_ai("evo")
results = []

for opp_name in ["greedy", "flatmc"]:
    opp = load_ai(opp_name)
    evo_wins = 0
    const_wins = 0
    total = 0
    t0 = time.time()

    for i in range(games):
        seed = base_seed + i * 1000 + int(mult * 100000)
        for evo_p0 in [True, False]:
            gs_seed = seed if evo_p0 else seed + 1000000
            gs = init_game(seed=gs_seed, size=15, generator_id="balanced")
            r0, r1 = random.Random(gs_seed), random.Random(gs_seed + 1)
            if evo_p0:
                while gs.winner is None and gs.turn < 100:
                    step_game(gs, evo(gs, 0, r0), opp(gs, 1, r1))
            else:
                while gs.winner is None and gs.turn < 100:
                    step_game(gs, opp(gs, 0, r0), evo(gs, 1, r1))
            evo_won = (evo_p0 and gs.winner == 0) or (not evo_p0 and gs.winner == 1)
            total += 1
            if evo_won:
                evo_wins += 1
                if gs.victory_type == "construction":
                    const_wins += 1

        if (i + 1) % 25 == 0:
            wr = evo_wins / total * 100
            cwr = const_wins / total * 100
            print(f"  {opp_name}: {i+1}/{games} wr={wr:.1f}% const={cwr:.1f}%")

    wr = evo_wins / total * 100
    cwr = const_wins / total * 100
    elapsed = time.time() - t0
    print(f"  DONE {opp_name}: wr={wr:.1f}% const={cwr:.1f}% ({elapsed:.0f}s)")
    results.append({
        "c5_mult": mult, "c5_cost": list(nc), "opponent": opp_name,
        "evo_winrate": round(wr, 1), "construction_winrate": round(cwr, 1),
        "total_games": total
    })

# Output JSON marker for parent to extract
print("__JSON_START__")
print(json.dumps(results))
print("__JSON_END__")
