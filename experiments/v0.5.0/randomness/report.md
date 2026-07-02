# Combat Randomness Experiment (Clean Rerun)

## Method
- 500 games per condition, 2000 total
- ±3 random damage via `combat.RANDOM_COMBAT` flag
- Post-tiebreak-fix, stable Greedy AI (no concurrent modifications)

## Results

### Greedy vs Greedy

| Mode | P0 | Conquest | Tiebreak | T | Dead | Turn Std |
|------|-----|----------|----------|-----|------|----------|
| Deterministic | 48.0% | 11.4% | **88.6%** | 95.4 | 50.4 | 14.7 |
| Random (±3) | 47.2% | **18.8%** | **81.2%** | 91.4 | 45.1 | **20.1** |

**Randomness reduces tiebreak 7.4pp, increases conquest 7.4pp.**

### Greedy vs Random

| Mode | Greedy Win | Conquest | Construction | Tiebreak |
|------|-----------|----------|-------------|----------|
| Deterministic | 80.4% | 41.2% | 39.0% | 19.8% |
| Random (±3) | 79.8% | 39.0% | 39.6% | 21.4% |

**Randomness does NOT help underdogs.** Greedy stays at ~80%.

## Analysis

1. **Mirror stalemate reduced**: Randomness breaks deterministic stalemate (identical AIs always get same combat results → tiebreak). ±3 variation means one side occasionally wins a key engagement.

2. **Underdog NOT helped**: Random AI still loses 80% of the time. The skill gap is too large for ±3 to bridge.

3. **Variance increases**: Turn std +36% — games are less predictable with randomness.

4. **No negative side effects**: P0 balance unchanged, construction rate unchanged.

## Recommendation

**Enable randomness as default.** Benefits mirror match decisiveness with no downside. Set `RANDOM_COMBAT = True` in combat.py.
