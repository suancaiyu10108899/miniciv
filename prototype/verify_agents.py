# test flatmc v3 + evo ai
from prototype.game import init_game, step_game
from prototype.eval import load_ai
from prototype.ai_evo import ai_decide as evo_decide, random_weights
import random, time

# 1. FlatMC v3 vs Random
print("=== FlatMC v3 vs Random (10 games) ===")
ai0 = load_ai('flatmc')
ai1 = load_ai('random')
p0w = 0
ts = []
t0 = time.perf_counter()
for s in range(42, 52):
    gs = init_game(seed=s, size=15, generator_id='balanced')
    r0 = random.Random(s)
    r1 = random.Random(s + 1)
    while gs.winner is None and gs.turn < 100:
        step_game(gs, ai0(gs, 0, r0), ai1(gs, 1, r1))
    if gs.winner == 0:
        p0w += 1
    ts.append(gs.turn)
    print(f"  s={s} w={gs.winner} T={gs.turn}")
elapsed = time.perf_counter() - t0
n = 10
print(f"FlatMC v3: P0={p0w}/{n} avgT={sum(ts)/n:.0f} {elapsed:.0f}s ({elapsed/n:.0f}s/g)")
print("BEATS RANDOM!" if p0w >= 5 else "Still losing...")
print()

# 2. Evo AI quick test
print("=== Evo AI vs Random (5 games) ===")
w = random_weights()
for s in range(42, 47):
    gs = init_game(seed=s, size=15, generator_id='balanced')
    r0 = random.Random(s)
    r1 = random.Random(s + 1)
    while gs.winner is None and gs.turn < 50:
        step_game(gs, evo_decide(gs, 0, r0, w), ai1(gs, 1, r1))
    print(f"  s={s} w={gs.winner} T={gs.turn}")
print("Evo AI works!")
