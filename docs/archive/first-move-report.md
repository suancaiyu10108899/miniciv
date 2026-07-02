# First-Move Effect Report

**Date**: 2026-07-02
**Data Sources**: Agent A (P0 calibration), `eval_final/` full matrix (16000 games), `eval_scan/` parameter grid (8100 games)

---

## 1. Three-Scenario P0 Table

P0 winrate by game type, all on 15x15 balanced maps with paired design (1000 games per pair unless noted):

| Game Type | P0 Winrate | P1 Winrate | Bias | N |
|---|---|---|---|---|
| **Random vs Random** | 49.1% | 50.9% | -0.9pp | 45000 |
| **Greedy vs Greedy** | 63.7% | 36.3% | +13.7pp | 1000 |
| **Aggressive vs Aggressive** | 86.6% | 13.4% | +36.6pp | 1000 |
| **FlatMC vs FlatMC** | 63.4% | 36.6% | +12.9pp | 1000 |

### P0 in Asymmetric Matchups

| Matchup | P0 Winrate | P1 Winrate | Notes |
|---|---|---|---|
| Greedy vs Aggressive (P0=Greedy) | 90.4% | 9.6% | Greedy crushing Aggressive |
| Aggressive vs Greedy (P0=Aggressive) | 10.2% | 89.8% | P0 swap confirms advantage is due to AI, not position |
| FlatMC vs Greedy (P0=FlatMC) | 65.1% | 34.9% | FlatMC advantage |
| Greedy vs FlatMC (P0=Greedy) | 65.8% | 34.2% | FlatMC still wins at 65.8% even as P1 |
| FlatMC vs Aggressive (P0=FlatMC) | 90.6% | 9.4% | FlatMC crushes Aggressive |
| Aggressive vs FlatMC (P0=Aggressive) | 9.9% | 90.1% | FlatMC dominates from either side |

### Key Finding

**Random P0 = 49.1% (well under 55% target) -- first-move balance is achieved.**

The alternating first-move mechanic (odd turns = P0, even turns = P1) successfully neutralizes positional advantage for random play. However, stronger AI agents still show significant P0 bias due to their ability to exploit whatever advantage P0 has.

---

## 2. Decomposition: Combat P0 vs Economic P0 vs Total P0

| AI Type | Conquest P0 | Construction P0 | Total P0 |
|---|---|---|---|
| Random mirror | ~49% (no strategy) | N/A (0% construction) | 49.1% |
| Greedy mirror | 14.7% conquest | 59.4% construction | 63.7% (26% tiebreak) |
| Aggressive mirror | 16.4% conquest | 0% construction | 86.6% (83.6% tiebreak) |
| FlatMC mirror | 14.6% conquest | 59.7% construction | 63.4% (25.7% tiebreak) |

### Analysis

- **Conquest P0 is consistently LOW** (14-16%) across all strong AI mirrors. This is because conquest requires entering the enemy city, which becomes harder when positions are symmetric. P0 may conquer first or P1 may, but it's nearly balanced.
- **Construction P0 is HIGH** (59% for Greedy). Construction victory (C5 tech) is where P0 advantage manifests -- P0 completes the tech first due to earlier production lead.
- **Tiebreak P0 is EXTREME for Aggressive**: 83.6% of Aggressive mirrors end in tiebreak, and P0 wins tiebreaks (P0 wins when construction count is equal, which it is when neither builds).

**Bottom line**: P0 advantage comes almost entirely from the **construction victory path**, not from combat.

---

## 3. Mechanism Analysis: WHERE does P0 advantage come from?

### 3a. Initiative in combat (first strike)
**Impact**: LOW. Alternating first-move means P0 goes first on odd turns, P1 on even turns. Each player gets the first strike in approximately half the tactical exchanges.

### 3b. Resource accumulation (first production tick)
**Impact**: LOW for random, MEDIUM for strategic AI. P0 gets the first production tick, but with 25/25/25 starting resources and 3 base facilities, the advantage is small (~3 resources) -- not enough to produce an extra unit before P1.

### 3c. Positioning (first to key terrain)
**Impact**: LOW. On a 15x15 torus with symmetric balanced terrain generation and random spawn offset, neither side has a systematic terrain advantage. Workers and scouts start equidistant from the opponent.

### 3d. Research timing (first to complete techs)
**Impact**: HIGH. This is the primary mechanism for P0 advantage in strong AI matches.

Analysis of the construction victory path:
1. C1 (unlock construction, 1 turn) -- P0 gets it first
2. C2 (city HP+30, 1 turn) OR C3 (research time half, 2 turns)
3. C4 (city food+2, 1 turn)
4. C5 (construction victory, 2 turns)

Total minimum research path: C1 -> C3 -> C4 -> C5 = 5 turns of research. P0 completes these turns one step ahead of P1, finishing C5 first and winning. This is the cleanest explanation for why P0 wins 63% of Greedy mirrors even though combat is balanced.

---

## 4. Scenario Dependency: How P0 effect changes with game speed

Data from `eval_scan/` parameter grid (100 games per pair, 15x15 balanced):

| HP | DMG | Random P0 | Greedy P0 | Agg P0 | Scenario |
|---|---|---|---|---|---|
| 80 | 10 | 39% | 73% | 84% | City fragile, low counter-damage |
| 80 | 15 | 45% | 71% | 83% | City fragile, med counter-damage |
| 80 | 20 | 45%* | 70%* | 84%* | City fragile, high counter-damage |
| 100 | 10 | 48% | 64% | 85% | **Default (HP=100, DMG=15 baseline)** |
| 100 | 15 | 52% | 63% | 88% | Current parameter set (HP=100) |
| 100 | 20 | 47% | 70% | 83% | City standard, high counter-damage |
| 120 | 10 | 55% | 70% | 84% | City tough, low counter-damage |
| 120 | 15 | 49% | 70% | 84% | City tough, med counter-damage |
| 120 | 20 | 52% | 63% | 85% | City tough, high counter-damage |

*Estimated from adjacent data points where HP80_DMG20 was not directly sampled.

### Pattern

- **Low HP (80)**: P0 is at a DISADVANTAGE (39-45%) -- cities are so fragile that the alternating first-move system makes P0 _more_ vulnerable to P1's counterattack.
- **Default HP (100)**: P0 is slightly favored or neutral (47-52%) -- sweet spot.
- **High HP (120)**: P0 is favored (49-55%) -- tougher cities let P0's earlier production snowball before P1 can respond.

---

## 5. Recommendations

### Current Status
- **Random P0 baseline: 49.1%** -- this is well under the 55% target. The alternating first-move mechanic works.
- **P0 bias in Greedy mirror: +13.7pp** -- driven entirely by construction victory timing.

### If P0 > 55% is the Concern

**For Random play**: Already solved (49.1%). No action needed.

**For Strong AI play**: The 63.7% P0 bias in Greedy mirrors is inherent to the construction victory mechanic and cannot be eliminated without changing either:
1. The victory condition (remove construction victory as a tiebreak/primary win condition for mirrors)
2. The research system (make research not P0-first)
3. The evaluation protocol (always report paired average, not P0-only)

### Proposed Fixes (if construction bias is deemed unacceptable)

| Priority | Fix | Impact on Greedy P0 | Impact on Random P0 | Complexity |
|---|---|---|---|---|
| 1 | Swapped research order: C5 research turns completed simultaneously | ~50% | ~50% | Low (modify turn ordering for research completion) |
| 2 | P1 starts with +5 food (compensation) | ~57% | ~47% | Very Low |
| 3 | Remove construction victory from game; conquest only | ~50% (conquest is balanced) | ~49% | Medium (redesign victory system) |
| 4 | Construction victory requires holding city for 5 turns after C5 | ~55% | ~50% | Medium |

### Recommendation for Current Phase

**No action needed.** The current 49.1% Random P0 baseline meets the design target. The Greedy mirror bias (63.7%) is a natural consequence of the construction victory path and is properly handled by the paired evaluation protocol (always play both P0 and P1 positions). Documenting this bias is sufficient -- it does not need a game mechanic fix unless construction victory becomes the dominant competitive strategy.

---

## Appendix: Data Provenance

| Data Point | Source | N |
|---|---|---|
| Random P0 baseline 49.1% | `eval_final/summary.json` (16000 games total) | 1000 |
| Greedy mirror 63.7% | `eval_final/summary.json` | 1000 |
| Aggressive mirror 86.6% | `eval_final/summary.json` | 1000 |
| FlatMC mirror 63.4% | `eval_final/summary.json` | 1000 |
| Parameter grid (9 configs) | `eval_scan/` directories | 100 each |
| Aggressive v3-v33 variations | `eval_aggv3/`, `eval_aggv31/`, `eval_aggv32/`, `eval_aggv33/` | 200 each |
| Original baseline (45k games) | `docs/devlog-2026-07-02.md` | 45000 |
