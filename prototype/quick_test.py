# quick test: FlatMC v2 + construction rate
from prototype.game import init_game, step_game
from prototype.eval import load_ai
import random, time

# 1. FlatMC v2 vs Random
print("=== FlatMC v2 vs Random (10 games) ===")
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
    vt = str(gs.victory_type or 't')
    print(f"  s={s} w={gs.winner} {vt:25s} T={gs.turn} hp0={gs.cities[0].hp} hp1={gs.cities[1].hp}")
elapsed = time.perf_counter() - t0
print(f"  P0={p0w}/10 avgT={sum(ts)/10:.0f} {elapsed:.0f}s ({elapsed/10:.1f}s/g)")
print()

# 2. Current construction/tie rates (symmetric)
print("=== Greedy vs Greedy (symmetric, 100 games) ===")
ai0 = load_ai('greedy')
ai1 = load_ai('greedy')
cq = cs = tie = 0
ts = []
t0 = time.perf_counter()
for s in range(42, 142):
    gs = init_game(seed=s, size=15, generator_id='symmetric')
    r0 = random.Random(s)
    r1 = random.Random(s + 1)
    while gs.winner is None and gs.turn < 100:
        step_game(gs, ai0(gs, 0, r0), ai1(gs, 1, r1))
    vt = str(gs.victory_type or 't')
    if 'conquest' in vt: cq += 1
    elif 'construction' in vt: cs += 1
    else: tie += 1
    ts.append(gs.turn)
n = 100
print(f"  cq={cq} cs={cs}({cs/n*100:.0f}%) tie={tie}({tie/n*100:.0f}%) T={sum(ts)/n:.0f}")
print(f"  {time.perf_counter()-t0:.0f}s")
