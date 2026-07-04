# Tactical Analysis: v0.6.2 AI Matchups

Generated: 2026-07-05
Source: `experiments/v0.6.2/full-matrix/` paired summaries
Settings: city_hp=80, city_damage=5, size=15, gen=balanced, 200 seeds each pairing (400 games)

---

## 1. Evo vs Greedy: 65.5% -- 34.5%

**Source** `paired_evo_vs_greedy.json`

### Strategic Fingerprint

| Feature | Evo (ai_a) | Greedy (ai_b) |
|---|---|---|
| Infantry (alive+dead) | 25.7 | 20.3 |
| Cavalry (alive+dead) | **13.8** | 1.0 |
| Archer (alive+dead) | 0.4 | 0.0 |
| Total units built | ~50.9 | ~26.1 |
| Total resources | 527 | 726 |

**Evo** runs a cavalry-heavy combined-arms doctrine. It fields 13.8 cavalry per game (13x the opponent's count), using them for mobility and flanking alongside a solid infantry core. Archers are negligible -- Evo does not invest in ranged defense.

**Greedy** plays a pure infantry garrison strategy with token scouts. It produces zero archers and almost no cavalry. Greedy accumulates more total resources (726 vs 527) but converts them into fewer total units, suggesting it invests heavily in building upgrades or static defenses rather than force projection.

### Decisiveness
- Conquest: 1.5% (only 6 games ended by conquest)
- Construction: 55.5% (222 games)
- Tiebreak: 43.0% (172 games)
- Combined decisive rate: **57.0%**

The low conquest rate confirms neither side aggressively hunts the opponent's city. Games end primarily through construction completion or tiebreak.

### Economic Efficiency
- Evo: **1.24** units per resource unit
- Greedy: **0.47** (less than half as efficient)

Evo gets 2.6x more army per resource spent. Greedy's resource stockpiling (726 avg) does not translate into proportional combat power.

### Worker Safety
- Evo: 2.63 alive, **0.37 dead** (12.3% death rate)
- Greedy: 2.90 alive, **0.10 dead** (3.3% death rate)

Greedy protects its workers exceptionally well -- only 1 in 10 workers dies. Evo loses workers at 3.7x the rate, likely because cavalry-forward play exposes back lines.

### Key Insight
Evo wins 65.5% by converting a leaner resource base into a much larger army (51 vs 26 units) through cavalry-heavy force multiplication, but the 43% tiebreak rate shows its military advantage often fails to translate into decisive conquest before construction closes the game.

---

## 2. DQN Trained vs Greedy: 96.25% -- 3.75%

**Source** `paired_dqn_trained_vs_greedy.json`

### Strategic Fingerprint

| Feature | DQN Trained (ai_a) | Greedy (ai_b) |
|---|---|---|
| Infantry (alive+dead) | **25.0** | 21.8 |
| Cavalry (alive+dead) | **0.0** | 1.0 |
| Archer (alive+dead) | 0.0 | 0.0 |
| Total units built | ~28.3 | ~26.6 |
| Total resources | 1061 | 1033 |
| Facilities built | **4.00** (0 std!) | 3.02 |

**DQN** plays pure infantry -- zero cavalry, zero archers, zero scouts for combat. Every game it builds exactly 4.00 facilities (zero variance across 400 games), indicating a hardcoded or learned optimal build order.

**Greedy** also fields infantry (21.8 total) with token cavalry (1.0) but builds only 3.02 facilities on average.

### Decisiveness
- Conquest: **3.0%** (12 games)
- Construction: **0.75%** (3 games)
- Tiebreak: **96.25%** (385 games)
- Combined decisive rate: **3.75%**

This is the most remarkable number in the dataset: 96.25% of games end via tiebreak. DQN wins 96.25% of games but almost never by conquest or construction -- it wins by accumulating more victory points (presumably from its guaranteed 4 facilities).

### Economic Efficiency
- DQN: **0.91**
- Greedy: **0.04**

DQN is 22x more resource-efficient than Greedy in this matchup. Despite similar resource incomes (1061 vs 1033) and similar army sizes (28.3 vs 26.6), the efficiency metric suggests DQN's units are far more cost-effective, or that its 4-facility build order generates disproportionate scoring value.

### Worker Safety
- DQN: 2.27 alive, **0.73 dead** (24.3% death rate)
- Greedy: 2.44 alive, **0.56 dead** (18.7% death rate)

DQN loses 30% more workers than Greedy. Pure infantry doctrine may leave workers exposed during marches, or the DQN agent may not value worker survival highly in its reward function.

### Construction Analysis
DQN builds exactly 4.00 facilities every single game (std=0.00) -- a completely deterministic behavior. Greedy averages 3.02 but with low variance (std=0.12), suggesting it reliably reaches 3 but stops there. In v0.6.2 the construction victory threshold appears to be above 4, so neither side can trigger construction victory reliably (only 0.75% of games end this way). DQN's extra facility gives it a decisive tiebreak advantage.

### Key Insight
DQN achieves a near-perfect 96.25% winrate through an inflexible but optimal strategy: build exactly 4 facilities every game and field only infantry, winning almost exclusively on tiebreak points rather than military or construction victory -- a victory-point optimization that the Evo and Greedy agents do not replicate.

---

## 3. Aggressive vs Random: 50.0% -- 50.0%

**Source** `paired_aggressive_vs_random.json`

### Strategic Fingerprint

| Feature | Aggressive (ai_a) | Random (ai_b) |
|---|---|---|
| Infantry (alive+dead) | 19.8 | 4.3 |
| Cavalry (alive+dead) | **6.4** | 0.0 |
| Archer (alive+dead) | 3.4 | **15.9** |
| Scout (alive+dead) | 1.0 | 1.0 |
| Worker (alive+dead) | **18.9** | 3.0 |
| Total units built | **~49.5** | ~24.2 |
| Total resources | **261** | 878 |
| Facilities built | 2.42 | 1.91 |

**Aggressive** lives up to its name: it floods the map with 49.5 units per game (2x the opponent) despite having only 30% of the resources. The standout number is **18.9 workers** built per game -- it treats workers as combat units, sending them forward in waves. Cavalry (6.4) provides the primary striking arm, with infantry (19.8) and archers (3.4) in support.

**Random** (which appears to be an archer-heavy random strategy) builds 15.9 archers per game -- a pure ranged defense. It builds almost no infantry (4.3) and zero cavalry, relying entirely on archer mass for map control. Its resource income (878) is 3.4x higher than Aggressive, suggesting Random's AI prioritizes economic development.

### Decisiveness
- Conquest: **21.0%** (84 games) -- highest conquest rate of any pairing
- Construction: 14.5% (58 games)
- Tiebreak: 64.5% (258 games)
- Combined decisive rate: **35.5%**

Aggressive achieves the highest conquest rate in the dataset (21%), but it is still outnumbered by tiebreak finishes.

### Economic Efficiency
- Aggressive: **1.91** (highest in dataset)
- Random: **0.57**

Aggressive has the best resource efficiency of any AI surveyed (1.91). This is a direct consequence of its rush strategy: low resource accumulation per turn is paired with relentless unit production. Every resource is immediately converted into combat power.

### Worker Safety
- Aggressive: 3.68 alive, **15.23 dead** (80.5% death rate!)
- Random: 2.63 alive, **0.37 dead** (12.3% death rate)

This is the most extreme number in the analysis. Aggressive loses **15.23 workers per game** -- 80% of all workers it builds die. Workers are clearly deployed in front-line roles, possibly as city attackers or bait. Random's workers are well protected (0.37 dead), similar to Greedy in other matchups.

### How Does Aggressive Win 50% With 80% Worker Deaths?
The 50-50 winrate despite losing 2x the units and 41x the workers can be explained by: (a) Aggressive's constant pressure forces Random into a defensive posture that delays its construction progress, and (b) the 64.5% tiebreak rate suggests many games end on points, where Aggressive's map presence (more units on the board) partly offsets Random's economic lead. Aggressive's 2.42 facilities vs Random's 1.91 also helps in tiebreak scoring.

### Key Insight
Aggressive vs Random is the only 50-50 matchup in the set, but it is anything but balanced in style: Aggressive achieves parity through suicidal worker rushes and cavalry charges against an archer-spamming Random economy, sacrificing 41x more workers to close the gap -- the highest-cost tie in the dataset.

---

## Cross-Matchup Comparison

| Metric | Evo vs Greedy | DQN vs Greedy | Agg vs Random |
|---|---|---|---|
| Winrate (ai_a) | 65.5% | **96.25%** | 50.0% |
| Decisive rate | 57.0% | 3.75% | 35.5% |
| Conquest rate | 1.5% | 3.0% | **21.0%** |
| Construction rate | **55.5%** | 0.75% | 14.5% |
| Avg game length | 57.6 | 78.4 | 66.7 |
| Worker death disparity | 1:3.7 | 1:1.3 | **41:1** |
| Unit disparity | 1.95x | 1.06x | 2.04x |
| Resource disparity | 1:1.38 | 1:1.03 | **1:3.37** |
| Efficiency leader | Evo (1.24) | DQN (0.91) | Agg (1.91) |

### Summary of Findings

1. **DQN is the strongest AI** at 96.25% winrate via tiebreak optimization, but its strategy is brittle -- pure infantry + exactly 4 facilities, no variation.
2. **Evo is the most balanced** at 65.5% winrate with hybrid cavalry/infantry and the highest decisive finish rate (57%).
3. **Aggressive is the biggest spender** -- lowest resources, highest efficiency, highest worker casualties, and the only AI to achieve a meaningful conquest rate (21%).
4. **No AI has cracked decisive warfare** -- tiebreak ends 43-96% of games across all matchups. Even Aggressive's rush succeeds only 21% of the time at conquest.
5. **Worker safety correlates with resource income** -- the AIs that protect workers best (Greedy, Random) also accumulate the most resources, suggesting worker survival is central to economic scaling.

### Status

```json
{
  "analysis": "tactical_analysis.md",
  "files_read": 3,
  "matchups_analyzed": [
    "paired_evo_vs_greedy.json",
    "paired_dqn_trained_vs_greedy.json",
    "paired_aggressive_vs_random.json"
  ],
  "findings": {
    "strongest_ai": "dqn_trained (96.25% winrate)",
    "most_decisive": "evo (57% decisive finish rate)",
    "highest_conquest_rate": "aggressive (21%)",
    "most_efficient": "aggressive (1.91 units/resource)",
    "best_worker_safety": "greedy (3.3% death rate vs evo)",
    "worst_worker_safety": "aggressive (80.5% death rate)",
    "longest_games": "dqn_trained vs greedy (avg 78.4 turns)",
    "most_resources": "random (878 avg vs aggressive)"
  }
}
```
