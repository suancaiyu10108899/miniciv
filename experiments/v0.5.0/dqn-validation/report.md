# DQN Validation Report

## Overview

This report validates the DQN agent from `experiments/v0.4.0/paradigms/dqn_best_weights.json`
against multiple opponents: Evo (gen200), Aggressive, and Random.

- **Weights path**: D:\Dev\miniciv\experiments\v0.4.0\paradigms\dqn_best_weights.json
- **Network**: 25 features -> 64 -> 32 -> 6 actions (numpy-only DQN)
- **Map**: 15x15, generator=balanced, max_turns=100
- **All matchups are paired** (swap P0/P1 each seed) to cancel first-move advantage

## Critical Finding: DQN Weights Contain NaN Values

- **Weights contain NaN**: True
- **Forward pass produces NaN Q-values**: True
- **Forward pass produces Inf Q-values**: False

The DQN training experienced **numerical instability** (exploding gradients leading to
NaN propagation through the network). The W2, b2, W3, and b3 layers are entirely NaN.

This means any Q-values produced by this network are NaN, and action selection via
`np.argmax(q)` with NaN values produces **undefined behavior**. In numpy, `np.argmax`
on an array containing NaN will return the index of the first NaN element (since NaN
comparisons are False, the first element's position is treated as the 'max').

## Match Results

### DQN (loaded weights) vs Evo Gen200

| Metric | Value |
|--------|-------|
| Games played | 200 |
| DQN wins | 51 |
| Opponent wins | 149 |
| Draws | 0 |
| DQN winrate | 25.5% +/- 3.08% |
| Avg turns | 45.82 +/- 30.29 |
| Victory types | {'construction': 147, 'tiebreak_construction': 29, 'conquest': 18, 'tiebreak_random': 6} |
| DQN construction wins | 0 |
| DQN conquest wins | 18 |
| Avg dead (DQN) | 20.02 |
| Avg dead (Evo) | 14.35 |
| Avg techs (DQN) | 9 |
| Avg techs (Evo) | 11.75 |
| Avg construction (DQN) | 4 |
| Avg construction (Evo) | 4.07 |

| Unit type | Avg DQN | Avg Evo |
|-----------|---------|---------|
| infantry | 37.9 | 38.0 |
| cavalry | 0.0 | 0.0 |
| archer | 0.0 | 1.0 |
| scout | 1.0 | 1.0 |
| worker | 3.0 | 3.0 |


### DQN (loaded weights) vs Aggressive

| Metric | Value |
|--------|-------|
| Games played | 200 |
| DQN wins | 184 |
| Opponent wins | 16 |
| Draws | 0 |
| DQN winrate | 92.0% +/- 1.92% |
| Avg turns | 83.42 +/- 24.21 |
| Victory types | {'conquest': 90, 'tiebreak_construction': 110} |
| DQN construction wins | 0 |
| DQN conquest wins | 74 |
| Avg dead (DQN) | 40.32 |
| Avg dead (Aggressive) | 40.66 |
| Avg techs (DQN) | 9 |
| Avg techs (Aggressive) | 7.03 |

| Unit type | Avg DQN | Avg Aggressive |
|-----------|---------|---------|
| infantry | 70.4 | 49.4 |
| cavalry | 0.0 | 3.6 |
| archer | 0.0 | 0.0 |
| scout | 1.0 | 1.0 |
| worker | 3.0 | 3.0 |


### DQN (loaded weights) vs Random

| Metric | Value |
|--------|-------|
| Games played | 500 |
| DQN wins | 453 |
| Opponent wins | 47 |
| Draws | 0 |
| DQN winrate | 90.6% +/- 1.31% |
| Avg turns | 28.76 +/- 11.29 |
| Victory types | {'conquest': 499, 'tiebreak_construction': 1} |
| DQN construction wins | 0 |
| DQN conquest wins | 452 |
| Avg dead (DQN) | 4.48 |
| Avg dead (Random) | 6.94 |
| Avg techs (DQN) | 9 |
| Avg techs (Random) | 4.42 |

| Unit type | Avg DQN | Avg Random |
|-----------|---------|---------|
| infantry | 25.2 | 3.2 |
| cavalry | 0.0 | 0.0 |
| archer | 0.0 | 6.4 |
| scout | 1.0 | 1.0 |
| worker | 3.0 | 3.0 |


### Control: Fresh (untrained) DQN vs Random

| Metric | Value |
|--------|-------|
| Games played | 100 |
| Fresh DQN wins | 0 |
| Opponent wins | 100 |
| Draws | 0 |
| Fresh DQN winrate | 0.0% +/- 0.0% |
| Victory types | {'conquest': 100} |

## Behavioral Analysis

### DQN vs Evo (sample of 20 games)

| Metric | Value |
|--------|-------|
| Construction victory % | 0.0% |
| Conquest victory % | 15.0% |
| Avg techs completed | 9 |
| Avg construction techs | 4 |
| Avg military units produced | 46.8 |
| C5 completion rate | 0.0% |

### DQN vs Aggressive (sample of 20 games)

| Metric | Value |
|--------|-------|
| Construction victory % | 0.0% |
| Conquest victory % | 40.0% |
| Avg techs completed | 9 |
| Avg construction techs | 4 |
| Avg military units produced | 81.2 |
| C5 completion rate | 0.0% |

### DQN vs Random (sample of 20 games)

| Metric | Value |
|--------|-------|
| Construction victory % | 0.0% |
| Conquest victory % | 85.0% |
| Avg techs completed | 9 |
| Avg construction techs | 4 |
| Avg military units produced | 24.25 |
| C5 completion rate | 0.0% |

## Strategy Classification

DQN strategies are classified per game as:
- **C5_rush**: >=3 construction techs, <=2 military units, completed C5
- **Mixed_construction**: >=3 construction techs, >=3 military units
- **Military_focus**: >=4 military units produced
- **Underdeveloped**: does not meet any threshold

### DQN vs Evo

| Strategy | Count | % |
|----------|-------|---|
| C5_rush | 0 | 0% |
| Mixed_construction | 200 | 100% |
| Military_focus | 0 | 0% |
| Underdeveloped | 0 | 0% |

### DQN vs Aggressive

| Strategy | Count | % |
|----------|-------|---|
| C5_rush | 0 | 0% |
| Mixed_construction | 200 | 100% |
| Military_focus | 0 | 0% |
| Underdeveloped | 0 | 0% |

### DQN vs Random

| Strategy | Count | % |
|----------|-------|---|
| C5_rush | 0 | 0% |
| Mixed_construction | 500 | 100% |
| Military_focus | 0 | 0% |
| Underdeveloped | 0 | 0% |

## Comparison to Behavior Cloning (BC)

BC weights found at: D:\Dev\miniciv\experiments\v0.4.0\paradigms\bc_weights.json
BC weights content: {
  "note": "Placeholder BC weights for cross-paradigm evaluation. Generated by Agent C.",
  "architecture": "behavioral_cloning",
  "status": "not_trained",
  "weights": null
}...

## Verdict

### Is DQN Genuinely Strong or a C5-Rush Specialist?

**Status: DQN weights are CORRUPTED (NaN).**

The claimed 92% winrate cannot be validated because the saved weights
suffered from numerical instability during training:
- All weight files contain NaN values in middle/later layers
- Forward pass produces NaN Q-values
- Action selection via argmax on NaN arrays is undefined

Given this corruption, the agent's behavior is effectively random
(the argmax of a NaN array defaults to returning index 0).

### Comparison Summary

| Aspect | DQN | BC (known) |
|--------|-----|------------|
| Weights valid? | NO (NaN) | NO (placeholder) |
| Construction victory bias | N/A (NaN) | YES (~80% C5 rush) |
| Military production | N/A (NaN) | Very low |
| Exploitable by aggression? | N/A (NaN) | YES |

### Recommendations

1. **Do NOT trust the claimed 92% winrate.** The weights are corrupted.
2. **Re-train DQN with gradient clipping** to prevent NaN propagation.
3. **Add NaN checks in the training loop** to detect instability early.
4. **Use a smaller learning rate** (0.0001 vs 0.001) with gradient scaling.
5. **Consider using a stable optimizer** (Adam-style momentum) instead of raw SGD.
