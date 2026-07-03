"""
Evo 建设胜利时间轴诊断
跑 50 局 Evo vs Greedy，记录每次科技完成的回合
"""
import json, os, sys, random, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from prototype.game import init_game, step_game
from prototype.eval import load_ai

N_GAMES = 50
SIZE = 15
MAX_TURNS = 100
BASE_SEED = 42

evo_decide = load_ai("evo")
greedy_decide = load_ai("greedy")

all_timelines = []
evo_wins = 0
construction_wins = 0

for i in range(N_GAMES):
    seed = BASE_SEED + i * 1000
    gs = init_game(seed=seed, size=SIZE, generator_id="balanced")
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)

    tech_timeline = []  # (turn, tech_id) pairs for Evo (P0)
    seen_techs = set()

    while gs.winner is None and gs.turn < MAX_TURNS:
        a0 = evo_decide(gs, 0, rng0)
        a1 = greedy_decide(gs, 1, rng1)
        step_game(gs, a0, a1)

        # Record newly completed techs for Evo
        for tid in gs.techs[0].completed:
            if tid not in seen_techs and tid.startswith("C"):
                seen_techs.add(tid)
                tech_timeline.append((gs.turn, tid))

    all_timelines.append({
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
        "tech_timeline": tech_timeline,
        "evo_food": gs.economies[0].food,
        "evo_wood": gs.economies[0].wood,
        "evo_gold": gs.economies[0].gold,
        "evo_units_produced": sum(1 for u in gs.units if u.player_id == 0 and u.alive) + sum(1 for u in gs.dead_units if u.player_id == 0),
        "evo_construction": gs.techs[0].construction_count(),
    })

    if gs.winner == 0:
        evo_wins += 1
        if gs.victory_type == "construction":
            construction_wins += 1

    if (i+1) % 10 == 0:
        print(f"  {i+1}/{N_GAMES}... evo_wr={evo_wins/(i+1)*100:.0f}% const_wr={construction_wins/(i+1)*100:.0f}%")

# Analysis
print(f"\n=== Evo Build Order Analysis ({N_GAMES} games) ===")
print(f"Evo winrate: {evo_wins/N_GAMES*100:.1f}%")
print(f"Construction winrate: {construction_wins/N_GAMES*100:.1f}%")

# Collect C1-C5 completion turns
c_turns = {f"C{i}": [] for i in range(1, 6)}
for tl in all_timelines:
    for turn, tid in tl["tech_timeline"]:
        if tid in c_turns:
            c_turns[tid].append(turn)

print("\nTech completion turns (avg ± std):")
for c in ["C1", "C2", "C3", "C4", "C5"]:
    turns = c_turns[c]
    if turns:
        avg = sum(turns) / len(turns)
        std = (sum((t-avg)**2 for t in turns) / len(turns)) ** 0.5
        print(f"  {c}: {avg:.1f} ± {std:.1f} turns (n={len(turns)})")

# Show first 3 games in detail
print("\nSample games (first 3):")
for tl in all_timelines[:3]:
    print(f"  seed={tl['seed']} winner={'Evo' if tl['winner']==0 else 'Greedy'} "
          f"victory={tl['victory_type']} turns={tl['turns']}")
    print(f"    techs: {tl['tech_timeline']}")
    print(f"    construction: {tl['evo_construction']}, units: {tl['evo_units_produced']}")

# Save
outdir = Path(__file__).resolve().parent
outdir.mkdir(parents=True, exist_ok=True)
with open(outdir / "evo_timeline.json", "w") as f:
    json.dump({"c_turns": {k: v for k, v in c_turns.items()}, "all": all_timelines}, f, indent=2)
print(f"\nSaved to {outdir / 'evo_timeline.json'}")
