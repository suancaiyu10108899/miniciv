# Randomness Impact Analysis

## Configuration
- Games per mode: 500
- Map: 15x15 balanced
- Max turns: 100

## Greedy vs Greedy (Mirror Matchup)

| Metric | Deterministic | Random (¡À3) | Difference |
|--------|--------------|-------------|------------|
| P0 Winrate | 86.8% | 86.6% | -0.20 |
| P0 95% CI | ¡À0.0% | ¡À0.0% |  |
| P0 StdDev | 0.0151 | 0.0152 | +0.00 |
| Conquest Rate | 0.4% | 0.6% | +0.20 |
| Construction Rate | 0.0% | 0.0% | +0.00 |
| Tiebreak Rate | 99.6% | 99.4% | -0.20 |
| Avg Turns | 99.9 | 99.8 | -0.13 |
| Turns StdDev | 1.14 | 2.61 | +1.47 |
| Avg Dead Units | 5.7 | 5.4 | -0.31 |
| Dead StdDev | 20.10 | 19.48 | -0.62 |

## Random vs Greedy (Underdog Effect)

| Metric | Deterministic | Random (¡À3) | Difference |
|--------|--------------|-------------|------------|
| Greedy Winrate | 35.8% | 31.6% | -4.2% |
| Greedy 95% CI | ¡À4.2% | ¡À4.1% | |
| Random Winrate | 64.2% | 68.4% | +4.2% |
| Conquest Rate | 28.4% | 23.2% | -5.20 |
| Construction Rate | 7.6% | 10.6% | +3.00 |
| Tiebreak Rate | 64.0% | 66.2% | +2.20 |
| Avg Turns | 85.8 | 87.8 | +1.90 |
| Turns StdDev | 22.52 | 20.66 | -1.86 |
| Avg Dead Units | 45.7 | 46.6 | +0.91 |
| Dead StdDev | 17.07 | 16.46 | -0.61 |

## Summary

- Randomness reduces Greedy winrate from 35.8% to 31.6%
- RECOMMENDATION: Randomness helps underdogs. Enable as default for fairer play.
- Randomness widens the winrate gap from -14.2% to -18.4% (less balanced)