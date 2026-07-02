# Randomness experiment runner
import sys, os, json, time
sys.path.insert(0, 'D:/Dev/miniciv')
import prototype.combat as combat
from prototype.game import init_game, step_game
from prototype.eval import load_ai
import random

def run_batch(games, ai0_name, ai1_name, random_combat=False):
    combat.RANDOM_COMBAT = random_combat
    ai0 = load_ai(ai0_name); ai1 = load_ai(ai1_name)
    p0w = p1w = cq = cs = tie = 0
    ts = []; ds = []
    for s in range(42, 42+games):
        gs = init_game(seed=s, size=15, generator_id='balanced')
        r0 = random.Random(s); r1 = random.Random(s+1)
        while gs.winner is None and gs.turn < 100:
            step_game(gs, ai0(gs, 0, r0), ai1(gs, 1, r1))
        if gs.winner == 0: p0w += 1
        elif gs.winner == 1: p1w += 1
        vt = str(gs.victory_type or 't')
        if 'conquest' in vt: cq += 1
        elif 'construction' in vt: cs += 1
        else: tie += 1
        ts.append(gs.turn); ds.append(sum(1 for u in gs.dead_units))
    n = len(ts)
    return {
        'ai0': ai0_name, 'ai1': ai1_name, 'random_combat': random_combat,
        'n': n, 'p0_winrate': p0w/n, 'p1_winrate': p1w/n,
        'conquest_rate': cq/n, 'construction_rate': cs/n, 'tiebreak_rate': tie/n,
        'avg_turns': sum(ts)/n, 'min_turns': min(ts), 'max_turns': max(ts),
        'avg_dead': sum(ds)/n, 'min_dead': min(ds), 'max_dead': max(ds),
        'turns_std': (sum((t-sum(ts)/n)**2 for t in ts)/(n-1))**0.5 if n>1 else 0,
    }

os.makedirs('D:/Dev/miniciv/experiments/v0.5.0/randomness', exist_ok=True)
t0 = time.time()
results = []
print("=== Combat Randomness Experiment (500 games each) ===")

# Greedy vs Greedy
for rc in [False, True]:
    r = run_batch(500, 'greedy', 'greedy', random_combat=rc)
    results.append(r)
    label = "RANDOM" if rc else "DETERMINISTIC"
    print(f"GvG {label}: P0={r['p0_winrate']*100:.1f}% tie={r['tiebreak_rate']*100:.1f}% T={r['avg_turns']:.0f} dead={r['avg_dead']:.0f}")

# Greedy vs Random
for rc in [False, True]:
    r = run_batch(500, 'greedy', 'random', random_combat=rc)
    results.append(r)
    label = "RANDOM" if rc else "DETERMINISTIC"
    print(f"GvR {label}: P0(Greedy)={r['p0_winrate']*100:.1f}% tie={r['tiebreak_rate']*100:.1f}% T={r['avg_turns']:.0f} dead={r['avg_dead']:.0f}")

with open('D:/Dev/miniciv/experiments/v0.5.0/randomness/results.json', 'w') as f:
    json.dump({'results': results, 'elapsed_s': time.time()-t0}, f, indent=2)
print(f"\nDone in {time.time()-t0:.0f}s. Results saved.")
