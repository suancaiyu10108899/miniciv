# Game Design Notes

## Combat Formula
GDD: damage = max(1, ATK + terrain_att - DEF - terrain_def)
Key insight: terrain affects BOTH sides (attacker terrain helps attacker, defender terrain helps defender)
Same terrain = same as plains. Attacking INTO better terrain = severely punished.

## Why These Values
CITY_HP=100: infantry 4 turns, cavalry 3 turns to capture
Terrain forest=5: attacker does 5 dmg (vs 1 at original 10)
Terrain mountain=8: attacker does 2 dmg (was 1)
FACILITY_OUTPUT=3: ~9 resources/turn with 3 facilities
Starting resources 15/15/15: ~2 starting units

## Victory Conditions
Conquest: destroy enemy city (HP<=0 via occupation)
Construction: research C5 (needs C1-C4 line, cost 60/57/40 total)
Tiebreak at 100T: construction_count -> city_hp -> p0_wins

## P0 Balance
Alternating first-move eliminates P0 advantage
Random vs Random: P0=49.1% (well under 55% target)

## Meta Analysis
Current meta: rush-focused, ~22 turns
Construction path non-viable at current speed
No defensive AI -> always rush meta
Cavalry key unit for city capture (3 turns vs infantry 4)
