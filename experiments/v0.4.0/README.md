# v0.4.0 Experiments Index

"Gradient Experiments" -- 游戏深度验证

> 核心数据在 `../../eval_final/`（16,000 局 4x4 完整矩阵），以下为各子实验目录说明。

---

## Directory Index

### `full-matrix-16k/` -- NOT HERE

核心 4x4 矩阵数据（16,000 局）在 `../../eval_final/`，未移入本目录。包含 random/greedy/aggressive/flatmc 四个 AI 的全部配对结果，每对 1,000 局 x 2 (P0/P1 对调) = 2,000 局。

### `full-matrix-partial/`

7x7 完整矩阵尝试（partial）。仅完成 random/greedy/aggressive 部分的 paired eval。因实验规模过大（49 对 x 600 = 29,400 局）中止，改为聚焦 4x4。含 paired 数据 2,400 局。

### `gradient/`

AI 能力梯度探索，3 条线：

| Subdir | Description |
|--------|-------------|
| `sanity_test/` | Evo 训练管线冒烟测试（80 局） |
| `flatmc_test/` | FlatMC vs Greedy/Random 首次测试（80 局, 5 sims） |
| `flatmc_test2/` | FlatMC 复测（80 局, 5 sims） |
| `flatmc_opt_test/` | FlatMC 优化版（80 局） |
| `flatmc_100_test/` | FlatMC 100-sim 测试（40 局） |
| `evo_checkpoints/` | Evo 代际梯度数据（含 gen10 checkpoints） |
| `b1_test5/` | FlatMC 补充测试（80 局） |

### `greedy-grad/`

Greedy 版本梯度 + BC 行为克隆实验：

| Subdir | Description |
|--------|-------------|
| `v1_vs_random/` | Greedy v1 paired eval vs Random（1,200 局） |
| `v1_mirror/` | Greedy v1 mirror（300 局） |
| `v1_vs_agg/` | Greedy v1 vs Aggressive |
| `v2_vs_random/` | Greedy v2 paired eval（1,200 局） |
| `v2_mirror/` | Greedy v2 mirror（300 局） |
| `v2_vs_agg/` | Greedy v2 vs Aggressive |
| `v3_vs_random/` | Greedy v3 paired eval（1,200 局） |
| `v3_mirror/` | Greedy v3 mirror（300 局） |
| `v3_vs_agg/` | Greedy v3 vs Aggressive |
| `v4_vs_random/` | Greedy v4 paired eval（1,200 局） |
| `v4_mirror/` | Greedy v4 mirror（300 局） |
| `v4_vs_agg/` | Greedy v4 vs Aggressive |
| `bc_vs_greedy/` | BC vs Greedy paired（2,000 局） |
| `bc_vs_random/` | BC vs Random paired（2,000 局） |
| `bc_mirror/` | BC mirror（500 局） |
| `paired_test2/` | Greedy v1 paired 协议测试（40 局，低样本） |

### `paired-p0/`

P0 先手优势校准实验（paired evaluation protocol）：

| Subdir | Description |
|--------|-------------|
| `rush/` | Rush 模式（无 construction tech），P0=83.4%（1,000 局） |
| `standard/` | 标准模式（含 construction），P0=84.5%（1,000 局） |
| `develop/` | 发展模式（size 20），P0=95.4%（1,000 局） |
| `combat_only/` | 纯战斗模式，P0=98.5%（600 局） |
| `econ_only/` | 纯经济模式，P0=100%（600 局） |

\* 以上为 tiebreak bug 修复前的校准数据，已标记为 stale。

### `randomness/`

随机性影响分析：

| File | Description |
|------|-------------|
| `greedy_vs_greedy_det.json` | 确定性战斗 mirror（500 局） |
| `greedy_vs_greedy_rnd.json` | 随机战斗 mirror（500 局） |
| `random_vs_greedy_det.json` | 确定性战斗 underdog（500 局） |
| `random_vs_greedy_rnd.json` | 随机战斗 underdog（500 局） |
| `analysis.json` | 对比分析（2,000 局） |
| `report.md` | 结论报告 |

结论：随机战斗使 Greedy 胜率降低 4.2%，有助于弱势方。

### `paradigms/`

DQN / Self-Play / Hybrid / BC ML 范式评估：

| File | Description |
|------|-------------|
| `report.txt` | 完整评估报告（含待定数值 TBD） |
| `dqn_best_weights.json` | DQN 最佳权重 |
| `dqn_eval_results.json` | DQN 评估结果 |
| `bc_weights.json` | BC 权重 |

注意：DQN 训练日志不完整，评估数据大部分标记为 TBD，尚不可引用。

---

## Reference

- 版本总览：`../../VERSION.txt`
- 完整变更日志：`../../changelog/v0.4.0.md`
- 核心矩阵数据：`../../eval_final/summary.json`
