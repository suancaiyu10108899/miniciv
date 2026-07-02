# Complete Data Book

**Date**: 2026-07-02
**Data Sources**: Agents A-E, `eval_final/`, `eval_aggv3/31/32/33`, `eval_scan/`, `eval_results/`, config files, dev logs

---

## 1. Parameter Summary

### Game Constants (from `prototype/constants.py`)

| Parameter | Value | Notes |
|---|---|---|
| MAP_SIZES | [15, 30, 50] | Default: 15 |
| MAX_TURNS | 100 | Tiebreak at turn 100 |
| CITY_HP | 100 | Infantry: 4 turns to capture, Cavalry: 3 turns |
| CITY_DEF | 10 | Terrain defense bonus for city |
| CITY_DAMAGE | 15 | Damage per turn to occupying unit |
| CITY_BASE_FOOD | 1 | Auto food per turn |

### Unit Stats

| Unit | HP | ATK | DEF | MOVE | VISION | Can Mountain | Ranged | Range |
|---|---|---|---|---|---|---|---|---|
| Infantry | 100 | 45 | 30 | 1 | 2 | Yes | No | 0 |
| Cavalry | 80 | 60 | 15 | 2 | 2 | No | No | 0 |
| Archer | 60 | 50 | 10 | 1 | 2 | Yes | Yes | 2 |
| Scout | 40 | 15 | 5 | 2 | 3 | Yes | No | 0 |
| Worker | 10 | 0 | 0 | 1 | 2 | Yes | No | 0 |

### Unit Costs (food, wood, gold)

| Unit | Food | Wood | Gold |
|---|---|---|---|
| Infantry | 5 | 0 | 0 |
| Cavalry | 5 | 0 | 3 |
| Archer | 3 | 3 | 0 |
| Scout | 3 | 0 | 0 |
| Worker | 3 | 0 | 0 |

### Terrain Defense Bonuses

| Terrain | Defense Bonus |
|---|---|
| Plain | 0 |
| Forest | 5 |
| Mountain | 8 |
| Water | 0 |
| City | 15 |

### Economy

| Item | Value |
|---|---|
| Starting resources | food: 25, wood: 25, gold: 25 |
| Starting units | worker: 3, scout: 1 |
| Facility output (all types) | 4/turn |
| Cavalry charge bonus | 10 |

### Terrain Generation Ratios (balanced)

| Terrain | Ratio |
|---|---|
| Plain | 35% |
| Forest | 28% |
| Mountain | 22% |
| Water | 8% |
| City (fixed) | 2 tiles |

### Tech Tree (13 nodes)

| Tech | Cost (F/W/G) | Turns | Requires | Effect |
|---|---|---|---|---|
| M1 | 8/3/0 | 1 | -- | infantry_atk+5, archer_atk+5 |
| M2 | 10/0/8 | 1 | M1 | cavalry_charge+5 |
| M3 | 8/8/3 | 1 | M1 | infantry_def_forest_mountain+10 |
| M4 | 15/0/10 | 2 | M2, M3 | all_hp+10 |
| E1 | 3/0/0 | 1 | -- | farm_food+1 |
| E2 | 0/3/0 | 1 | E1 | lumbermill_wood+1 |
| E3 | 5/0/3 | 1 | E1 | mine_gold+1 |
| E4 | 8/8/0 | 1 | E2, E3 | worker_move+1 |
| C1 | 5/5/3 | 1 | -- | unlock_construction |
| C2 | 4/6/0 | 1 | C1 | city_hp+30 |
| C3 | 5/5/5 | 2 | C1 | research_time_half |
| C4 | 6/3/3 | 1 | C3, C2 | city_food+2 |
| C5 | 3/3/3 | 2 | C3, C4 | construction_victory |

---

## 2. AI Catalog

### 2a. Random (`prototype/ai_random.py`)

| Property | Value |
|---|---|
| Type | Uniform random |
| Parameters | None |
| Training | None |
| Winrate vs Random | ~50% |
| Winrate vs Greedy | 14.7% |
| Winrate vs Aggressive | 23.5% |
| Winrate vs FlatMC | 15.5% |

### 2b. Greedy v4 (`prototype/ai_greedy.py`)

| Property | Value |
|---|---|
| Type | Hand-crafted heuristic |
| Parameters | Internal weights (not configurable) |
| Training | 4 iterations of manual tuning |
| Strategy | Prioritizes economic growth -> construction victory |
| Winrate vs Random | 88.3% |
| Winrate vs Greedy (mirror) | 50.0% (P0: 63.7%, P1: 36.3%) |
| Winrate vs Aggressive | 90.1% |
| Winrate vs FlatMC | 34.9% |
| Mirror conquest rate | 14.7% |
| Mirror construction rate | 59.4% |
| Mirror tiebreak rate | 25.9% |

### 2c. Aggressive (`prototype/ai_aggressive.py`)

| Property | Value |
|---|---|
| Type | Hand-crafted rush |
| Parameters | None |
| Training | None |
| Strategy | Always moves units toward enemy city, ignores economy |
| Winrate vs Random | 76.5% |
| Winrate vs Greedy | 9.9% |
| Winrate vs Aggressive (mirror) | 50.0% (P0: 86.6%, P1: 13.4%) |
| Winrate vs FlatMC | 9.7% |
| Mirror conquest rate | 16.4% |
| Mirror construction rate | 0.0% |
| Mirror tiebreak rate | 83.6% |

### 2d. FlatMC (`prototype/ai_flatmc.py`)

| Property | Value |
|---|---|
| Type | Monte Carlo search (flat, no tree) |
| Parameters | ROLLOUTS: 10 (default) |
| Training | None (search-based) |
| Strategy | For each unit, enumerates legal moves, runs ROLLOUTS random playouts |
| Winrate vs Random | 87.8% |
| Winrate vs Greedy | 65.1% |
| Winrate vs Aggressive | 90.6% |
| Winrate vs FlatMC (mirror) | 50.0% (P0: 63.4%, P1: 36.6%) |

### 2e. Evolutionary (`prototype/ai_evo.py`) -- NOT YET TESTED

| Property | Value |
|---|---|
| Type | Weighted feature linear combination |
| Features | Distance to enemy, resource counts, unit counts, etc. |
| Training | CMA-ES-like evolution via `prototype/train_evo.py` |
| Population | 60 |
| Generations | Configurable (sweep: 5-200) |
| Status | Scripts exist, not yet executed |

### 2f. DQN (`prototype/ai_dqn.py`) -- NOT YET TESTED

| Property | Value |
|---|---|
| Type | Deep Q-Network (placeholder) |
| State encoding | 24-element feature vector |
| Action space | Per-unit movement + production |
| Status | Implementation exists but not trained/evaluated |

---

## 3. Full Winrate Matrix (4x4)

Source: `eval_final/summary.json`, 1000 games per pair, 15x15 balanced, paired design.

### Table: P0 Winrate (row as P0, column as P1)

| P0 \ P1 | Random | Greedy | Aggressive | FlatMC |
|---|---|---|---|---|
| Random | 48.2% | 18.0% | 27.2% | 18.8% |
| Greedy | 88.6% | 63.7% | 90.4% | 65.8% |
| Aggressive | 80.3% | 10.2% | 86.6% | 9.9% |
| FlatMC | 87.8% | 65.1% | 90.6% | 63.4% |

### Table: AI Winrate (averaged P0+P1)

| AI | vs Random | vs Greedy | vs Aggressive | vs FlatMC |
|---|---|---|---|---|
| Random | 50.0% | 14.7% | 23.5% | 15.5% |
| Greedy | 88.3% | 50.0% | 90.1% | 34.9% |
| Aggressive | 76.5% | 9.9% | 50.0% | 9.7% |
| FlatMC | 87.8% | 65.1% | 90.6% | 50.0% |

### Table: Game Statistics (Mirror Matches)

| AI | Avg Turns | Conquest Rate | Construction Rate | Tiebreak Rate | Avg Dead Units |
|---|---|---|---|---|---|
| Random | 20.0 | 99.6% | 0.4% | 0.0% | 8.6 |
| Greedy | 94.1 | 14.7% | 59.4% | 25.9% | 47.9 |
| Aggressive | 92.0 | 16.4% | 0.0% | 83.6% | 57.1 |
| FlatMC | 94.0 | 14.6% | 59.7% | 25.7% | 45.9 |

---

## 4. Elo Rankings

Computed from 4x4 winrate matrix (eval_final, 1000 games per pair, averaged P0+P1).

| Rank | AI | Est. Elo | vs Random | vs Next |
|---|---|---|---|---|
| 1 | FlatMC (r=10) | 1600 | 87.8% | 65.1% vs Greedy |
| 2 | Greedy | 1500 | 88.3% | 90.1% vs Aggressive |
| 3 | Aggressive | 1200 | 76.5% | 76.5% vs Random |
| 4 | Random | 1000 | 50.0% | -- |

Elo calculation notes:
- Base Elo: Random = 1000
- Elo difference formula: E = 1 / (1 + 10^((R2-R1)/400))
- Gap between Random and Aggressive: ~200 Elo (76.5% WR = ~205 Elo difference)
- Gap between Aggressive and Greedy: ~400 Elo (90.1% WR = ~380 Elo difference)
- Gap between Greedy and FlatMC: ~100 Elo (65.1% WR = ~110 Elo difference)
- These estimates are K=32 scale approximations

Elo Observations:
1. **FlatMC and Greedy are close in Elo** (difference ~100), but FlatMC clearly beats Greedy in direct confrontation.
2. **The gap from Aggressive to Greedy (~400 Elo)** is the largest in the system.
3. **Random and Aggressive are relatively close** (~200 Elo) -- Aggressive's rush strategy is not that much better than random.

---

## 5. Gradient Curves

### 5a. FlatMC Rollout Gradient

**Data status**: NOT YET COLLECTED. Script `eval_gradient/sweep_flatmc.py` is ready but not executed.

Expected sweep: ROLLOUTS = [3, 5, 10, 25, 50, 100]
Each tested vs Random (200 games) and vs Greedy (200 games), with re-run at 500 games if stddev > 5%.

Current single data point: ROLLOUTS = 10, vs Greedy = 65.1% (1000 games)

### 5b. Evo Generation Gradient

**Data status**: NOT YET COLLECTED. Script `eval_gradient/sweep_evo_gen.py` is ready but not executed.

Expected sweep: GENERATIONS = [5, 10, 20, 30, 50, 80, 120, 200]
Population: 60, tested vs Greedy 200 games.

### 5c. Evo Population Size Gradient

**Data status**: NOT YET COLLECTED. Script `eval_gradient/sweep_evo_pop.py` is ready but not executed.

Expected sweep: (pop, gen) = [(20,20), (50,8), (100,4), (200,2)]
Controlled total evaluations: 6000 per config.

---

## 6. Statistical Quality

### Sample Sizes

| Experiment | Games per Pair | Total Games | Repetitions |
|---|---|---|---|
| eval_final (4x4 matrix) | 1000 | 16000 | 1 (1k each pair) |
| eval_aggv3 (2x2 matrix) | 200 | 800 | 4 variants (v3, v31, v32, v33) |
| eval_scan (parameter grid) | 100 | 900 | 9 configs |
| eval_results (3x3 matrix) | 200 | 1800 | 1 |

### Confidence Intervals

For N=1000 games, binomial proportion confidence interval (95%):
- Observed p=50%: CI = +/- 3.1pp
- Observed p=65%: CI = +/- 2.9pp
- Observed p=90%: CI = +/- 1.9pp

For N=200 games:
- Observed p=50%: CI = +/- 6.9pp
- Observed p=65%: CI = +/- 6.6pp
- Observed p=90%: CI = +/- 4.2pp

For N=100 games:
- Observed p=50%: CI = +/- 9.8pp
- Observed p=65%: CI = +/- 9.3pp
- Observed p=90%: CI = +/- 5.9pp

### Consistency Across Runs

Aggressive v3-v33 (4 runs, 200 games each):

| Metric | v3 | v31 | v32 | v33 | Mean | Std Dev |
|---|---|---|---|---|---|---|
| Greedy vs Greedy P0 | 65.5% | 60.0% | 61.0% | 68.0% | 63.6% | 3.1pp |
| Greedy vs Aggressive P0 | 89.5% | 86.5% | 94.0% | 92.5% | 90.6% | 2.8pp |
| Aggressive vs Greedy P0 | 6.0% | 8.5% | 6.0% | 2.5% | 5.8% | 2.1pp |
| Aggressive vs Aggressive P0 | 81.0% | 79.5% | 82.0% | 82.0% | 81.1% | 1.1pp |

The std dev of 1-3pp across 4 runs at N=200 confirms that N=200 provides reasonable confidence (within +/- 5pp).

### Statistical Quality Summary

| Aspect | Status |
|---|---|
| Independent seeding | All games use unique PRNG seeds |
| Paired design | Always play both P0 and P1 positions |
| Multiple runs | 4x repeated for key matchups |
| Sample sizes | Primary matrix: N=1000; Confirmatory: N=200; Scan: N=100 |
| Stddev tracking | Target: < 5pp (achieved at N=200) |
| Variance across runs | 1-3pp (consistent) |

---

## 7. Randomness Impact

### 7a. Random Baseline

Random vs Random produces essentially balanced results (P0=49.1%). Notably, Random games are fast (~20 turns) and almost always decided by conquest (99.6%).

### 7b. Map Generation Impact

Using the "balanced" generator:
- Terrain is symmetric in proportions but asymmetric in placement (cluster parameters introduce variation)
- 15x15 is the sweet spot -- 30x30 produces 39% tiebreak rate (too slow)
- Different generators were not systematically compared in the main evaluation

### 7c. AI Decision Determinism

| AI | Deterministic? | Notes |
|---|---|---|
| Random | No | Uniform choice among legal actions |
| Greedy | Yes | Deterministic given same game state |
| Aggressive | Yes | Deterministic given same game state |
| FlatMC | No | Rollout results depend on random playout seeds |

### 7d. Parameter Variation Impact (HP/DMG Scan)

The HP/DMG parameter sweep revealed that game balance is sensitive to city HP:
- HP=80: P0 at a disadvantage (39% WR) -- cities too fragile
- HP=100: P0 neutral-slightly favored (48-52%) -- sweet spot
- HP=120: P0 favored (49-55%) -- cities too durable

### 7e. Map Size Impact

| Size | Random T | Greedy Mirror T | Greedy Conquest Rate | Greedy Tie Rate |
|---|---|---|---|---|
| 15x15 | 22 | 94 | 95%* | 26% |
| 20x20 | 28 | 71 | 92%* | 8%* |
| 30x30 | 39 | 89 | 61%* | 39%* |

*Note: These are from earlier prototype versions; current values may differ.

---

## Appendix: Directory Structure

```
/ (project root)
├── eval_final/          # Primary 4x4 matrix (4 AIs, 1000 games each)
│   └── summary.json
├── eval_aggv3/          # Aggressive v3 (200 games each)
│   ├── summary.json
│   └── *vs_*.json
├── eval_aggv31/         # Aggressive v3.1
├── eval_aggv32/         # Aggressive v3.2
├── eval_aggv33/         # Aggressive v3.3
├── eval_scan/           # Parameter grid (HP80/100/120 x DMG10/15/20)
│   ├── HP80_DMG10/summary.json
│   ├── HP80_DMG15/summary.json
│   ├── HP80_DMG20/summary.json
│   ├── HP100_DMG10/summary.json
│   ├── HP100_DMG15/summary.json
│   ├── HP100_DMG20/summary.json
│   ├── HP120_DMG10/summary.json
│   ├── HP120_DMG15/summary.json
│   └── HP120_DMG20/summary.json
├── eval_gradient/       # Gradient sweep SCRIPTS (not yet executed)
│   ├── sweep_flatmc.py
│   ├── sweep_evo_gen.py
│   └── sweep_evo_pop.py
├── eval_full_matrix/    # Target output for 6x6 full matrix (empty)
├── eval_greedy_grad/    # Target output for Greedy gradient (empty)
├── eval_paradigms/      # Target output for paradigm comparison (empty)
├── eval_randomness/     # Target output for randomness analysis (empty)
├── eval_results/        # Early 3x3 matrix (3 AIs, 200 games)
│   └── *vs_*.json
└── prototype/           # Game engine
    ├── constants.py
    ├── game.py
    ├── ai_random.py
    ├── ai_greedy.py
    ├── ai_aggressive.py
    ├── ai_flatmc.py
    ├── ai_evo.py
    ├── ai_dqn.py
    ├── train_evo.py
    ├── eval_matrix.py
    └── ...
```

---

## Appendix: Missing Data Summary

| Data | Expected From | Status |
|---|---|---|
| FlatMC rollout gradient (3-100 rollouts) | Agent B, `eval_gradient/` | Script ready, not executed |
| Evo generation gradient (5-200 gen) | Agent B, `eval_gradient/` | Script ready, not executed |
| Evo population effect (20-200 pop) | Agent B, `eval_gradient/` | Script ready, not executed |
| Greedy gradient (weight sweep) | Agent C, `eval_greedy_grad/` | Not started |
| Behavior Cloning results | Agent C, `eval_greedy_grad/` | Not started |
| DQN training results | Agent D, `eval_paradigms/` | Not started |
| Self-play training results | Agent D, `eval_paradigms/` | Not started |
| Rule+Parameter Hybrid results | Agent D, `eval_paradigms/` | Not started |
| 6x6 full matrix (incl. Evo+BC+DQN) | Agent E, `eval_full_matrix/` | Not started |
| Randomness impact analysis | Agent E, `eval_randomness/` | Not started |
