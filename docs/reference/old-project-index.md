# 旧项目索引

> 旧项目：`D:\Dev\MiniCiv AI Lab` | GitHub: [suancaiyu10108899/MiniCiv-AI-Lab](https://github.com/suancaiyu10108899/MiniCiv-AI-Lab)（已封存）
>
> 本文件不迁移内容——只索引路径和为什么值得看。

---

## 🧠 AI 方法学（在新项目中直接复用）

| 文件 | 为什么值得看 |
|---|---|
| `core/encoding.py` → `_encode_base()` | 26 维状态编码的设计思路（坐标归一化、地形分、距离归一化、存活比例）。新游戏编码会不同，但**编码维度分类框架**不变 |
| `agents/flatmc_agent.py` → `_simplified_search()` | FlatMC 核心逻辑——对每个合法动作等量 rollout、取平均分最高。~50 行，语言无关 |
| `sim/experiment_runner.py` | paired 评估协议（每局 P0+P1 各一次）+ 每局独立种子 + Mann-Whitney U 检验 + 95% CI。**新项目评估 AI 的方法论模板** |

## 🔴 踩坑记录（避免重蹈）

| 文件 | 教训 |
|---|---|
| `docs/bug-journal/B01-state-next-state-ref-bug.md` | `state == next_state` 引用同一个对象 → RL 五次失败。**永远 copy 状态再传给 AI** |
| `docs/bug-journal/B12-experiment-fixed-seed.md` | 200 局用同一个 seed → 同一张地图 → 评估不可靠。**每局独立种子** |
| `docs/bug-journal/B13-ppo-env-action-space-mismatch.md` | PPO action space 和实际可用动作数不匹配 |
| `docs/bug-journal/B14-ppo-adapter-2units.md` | PPO adapter 硬编码 2 单位 |
| `docs/bug-journal/B11-uct-performance-catastrophe.md` | Python `deepcopy` 让 UCT 18.5s/局——**搜索型方法在 Python 中的性能瓶颈** |
| `docs/bug-journal/B09-no-training-feedback.md` | 训练 800k 步但没有中间评估——**训练过程必须可视化** |
| `docs/insight-journal/I11-feature-dilution.md` | v6/v7 加了 5 维特征，胜率反而下降。**特征数量 ≠ 信息量** |
| `docs/insight-journal/I13-non-interactive-strategy.md` | BC 从 FlatMC 学到的不是"分差最大化"而是"分数最大化"。**BC 教师的行为决定 BC 学什么——如果教师不与对手交互，BC 也学不会** |

## 📐 架构决策（模式参考）

| ADR | 决策 | 在新项目中的参考价值 |
|---|---|---|
| ADR-001 | Python+numpy only | 原型阶段仍然适用 |
| ADR-002 | Flat MC（非 UCT） | 分支因子大时 FlatMC 比 UCT 更高效 |
| ADR-003 | 手写 DQN | 学习价值 > 实用价值。新项目用 SB3/PyTorch |
| ADR-004 | 统一 AI 签名 | 所有 AI 可互换——**这是好模式，保留** |
| ADR-005 | Game Mode vs Lab Mode | 同一份规则引擎，不同入口——**保留** |
| ADR-008 | Rust 增量迁移 | v8.0.0 的迁移策略——**新项目直接 Rust 优先，不需要这个** |

## 📊 实验数据（基线对比）

| 数据 | 路径 | 用途 |
|---|---|---|
| v13 配对评估 | `data/v13_paired/*.json` | 旧游戏的完整 AI 对比基线。新游戏可以跑同样的 AI 矩阵做新旧对比 |
| v12 单侧评估 | `data/v12_eval/*.json` | ⚠️ 未去偏，仅参考 |

## 📝 文档体系参考

- 9 个 ADR：`docs/architecture/ADR-*.md`
- 37+ devlog：`docs/devlog/INDEX.md`
- bug journal：`docs/bug-journal/INDEX.md`
- insight journal：`docs/insight-journal/INDEX.md`

---

> 不需要读的东西（已被新设计取代）：`core/rules_*.py`、`core/config.py`、所有 `sim/train_*.py`、95+ BC 模型文件、531MB trajectory JSON。
