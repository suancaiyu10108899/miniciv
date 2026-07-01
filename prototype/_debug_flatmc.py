# Debug helper: compare Greedy vs FlatMC decisions
from prototype.game import init_game, step_game
from prototype.ai_greedy import ai_decide as greedy
from prototype.ai_flatmc import ai_decide as flatmc
from prototype.ai_rulesrandom import ai_decide as random_ai
from prototype.movement import get_single_step_moves
import random

gs = init_game(seed=42, size=15, generator_id='balanced')

# Play 5 turns first so there are combat units
for t in range(5):
    a0 = greedy(gs, 0, random.Random(gs.seed + t*1000))
    a1 = random_ai(gs, 1, random.Random(gs.seed + t*1000 + 1))
    step_game(gs, a0, a1)

# Now compare Greedy vs FlatMC decisions for combat units
print('=== Turn', gs.turn)
print('P0 city hp:', gs.cities[0].hp, 'at', (gs.cities[0].x, gs.cities[0].y))
print('P1 city hp:', gs.cities[1].hp, 'at', (gs.cities[1].x, gs.cities[1].y))

# P0 units
print('\nP0 Units:')
for i, u in enumerate(gs.units):
    if u.player_id == 0 and u.alive:
        legal = get_single_step_moves(u, gs.grid)
        print(f'  [{i}] {u.unit_type} ({u.x},{u.y}) HP={u.hp} atk={u.atk} def={u.def_} moves={legal}')

print('\nP1 Units:')
for i, u in enumerate(gs.units):
    if u.player_id == 1 and u.alive:
        print(f'  [{i}] {u.unit_type} ({u.x},{u.y}) HP={u.hp} atk={u.atk} def={u.def_}')

print('\nGreedy actions:', greedy(gs, 0, random.Random(gs.seed + gs.turn*1000)))
print('FlatMC actions:', flatmc(gs, 0, random.Random(gs.seed + gs.turn*1000)))
