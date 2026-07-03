"""Verify facility requirement impact on Evo winrate. FlatMC is self-adapting."""
import sys, random, time, json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

def _play(args):
    seed, ai0_name, ai1_name = args
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai
    from prototype.mapgen import get_facility
    ai0 = load_ai(ai0_name); ai1 = load_ai(ai1_name)
    gs = init_game(seed=seed, size=15, generator_id="balanced")
    r0 = random.Random(seed); r1 = random.Random(seed+1)
    while gs.winner is None and gs.turn < 100:
        step_game(gs, ai0(gs, 0, r0), ai1(gs, 1, r1))
    fc0 = sum(1 for y in range(gs.size) for x in range(gs.size) if (f:=get_facility(gs.grid,x,y)) and f.player_id==0)
    fc1 = sum(1 for y in range(gs.size) for x in range(gs.size) if (f:=get_facility(gs.grid,x,y)) and f.player_id==1)
    return {'winner': gs.winner, 'victory': gs.victory_type, 'turns': gs.turn, 'p0_fac': fc0, 'p1_fac': fc1}

from prototype.constants import CONSTRUCTION_VICTORY_REQUIRE_FACILITIES

pairs = [('evo','greedy'), ('evo','flatmc'), ('evo','dqn_trained'),
         ('flatmc','greedy'), ('flatmc','dqn_trained')]
G = 50

print(f"Facility requirement: {CONSTRUCTION_VICTORY_REQUIRE_FACILITIES}\n")

for p0_name, p1_name in pairs:
    tasks = [(42 + i*1000, p0_name, p1_name) for i in range(G)]
    p0_wins = 0; p1_wins = 0; const_wins = 0; total_turns = 0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_play, t): t for t in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            total_turns += r['turns']
            if r['winner'] == 0: p0_wins += 1
            elif r['winner'] == 1: p1_wins += 1
            if r['winner'] == 0 and r['victory'] == 'construction': const_wins += 1
    wr = p0_wins / G * 100
    cwr = const_wins / G * 100
    avg_t = total_turns / G
    print(f'{p0_name:>8} vs {p1_name:<10}: wr={wr:5.1f}% const={cwr:5.1f}% turns={avg_t:.0f} ({time.time()-t0:.0f}s)')

print("\n=== COMPARISON (before vs after) ===")
print("Facility requirement: 0 (old) -> 8 (new)")
print("Expected: Evo construction wins should drop significantly")
