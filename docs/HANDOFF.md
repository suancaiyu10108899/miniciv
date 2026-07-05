# 原型阶段交接文档

> 2026-07-05 | **给下一个 AI 助手的完整上下文。** 读这个 5 分钟，了解全局。

---

## 项目是什么

miniciv —— AI-first 回合制策略游戏平台。目标：一个 AI 真正能玩出深度的策略游戏。

当前：Python 原型阶段收尾，准备 Rust 重构。

---

## 最重要的事

**坐标系已选定六边形。** 轴向坐标 (q,r)，矩形环面（15×15 = 225 格，和方格面积相同）。六边原型在 `prototype_hex/`。

**为什么选六边**：对比实验显示六边对 AI 更友好（随机权重 Evo 在六边上 34% vs 方格 1%），建设率更高（67% vs 25%），所有方向等价（无"斜角陷阱"）。

**方格引擎在 `prototype/` 保留**——作为参考实现。Rust 引擎应该和 Python 方格引擎产生相同的游戏结果（同 seed 验证）。

---

## 原型阶段成果

### 游戏规则（已锁定）
- 六边形矩形环面，15×15（Rust 上可配置尺寸）
- 单位堆叠：1 战斗 + 1 平民/格
- 回合上限：80
- 建设胜利：C5 研究完成 + 4 个设施，每回合检查
- 征服胜利：敌方城市 HP ≤ 0
- 阶梯判定：construction_count → city_hp → random
- 交替先手（奇数回合 P0 先/偶数回合 P1 先）
- 固定伤害（可选 ±3 随机）

### 数值参数（已锁定）
| 参数 | 值 |
|------|-----|
| CITY_HP | 80 |
| CITY_DEF | 5 |
| CITY_DAMAGE | 5 |
| Facility 门槛 | 4 |
| 初始资源 | 25/25/25 |
| 设施产出 | 4/T |

### AI（方格终版数据）
| AI | 胜率 | 兵种特征 |
|----|------|---------|
| Evo #3 | 89.8% | 骑兵 41% |
| DQN #2 | 73.0% | 纯步兵（生产不经过 NN） |
| Greedy v6 | 29.1% | 骑 2.4 + 弓 2.9 |
| Aggressive v3.4 | 20.3% | 工人死 6.1/game |
| FlatMC | ~55% | ≈ Greedy+3% |
| Random | 37.8% | 基线 |

### 六边形 AI（原型阶段）
- Greedy v6 ✅ — `prototype_hex/ai_greedy_hex.py`
- Evo ✅ — `prototype_hex/evo_hex_weights.json`
- Random ✅ — 方格版直接可用
- DQN ❌ — 未适配
- Aggressive ❌ — 未适配
- FlatMC ❌ — 未适配

### 数据基础设施
- per-unit-type alive/dead/damage_dealt/damage_taken
- 设施分类型（farm/lumbermill/mine）
- per-victory-type P0（三种胜利类型均 ≈50%——交替先手机制完美）
- 回放浏览器（`prototype/replay_viewer.html`）
- 实验格式标准（`docs/EXPERIMENT-FORMAT.md`）
- 分析维度框架（`docs/ANALYSIS-DIMENSIONS.md`）

### 开发体系
- 安全：check_leaks.py (pre-commit) + cleanup.py (atexit)
- 一致性：check_docs.py (constants ↔ GAME.md)
- 86 单元测试（0.13s 全通过）
- 5/5 子 Agent 验证通过
- WORKFLOW.md 含规划执行纪律

---

## Rust 重构需要做的

### 第一步：架构设计
- 阅读 `docs/rust-architecture.md`（当前是草稿——42 行）
- 阅读 `docs/VISION.md`（长远愿景）
- 定义 crate 结构、核心 trait（GameState, Agent, Action）
- 定义 Python→Rust 一致性验证方案

### 第二步：核心引擎
- 优先级：map → movement → combat → economy → tech → game loop
- 每个模块完成后用 Python 同 seed 验证结果一致性
- 目标：100K games/s Random vs Random（单核）

### 第三步：AI 移植
- 先移植 Greedy v6（最重要的手写 AI）
- 然后 Evo（15 个权重，机械翻译）
- 然后 DQN v2（需要重新设计——当前 DQN 生产不经过 NN）
- FlatMC 在 Rust 上会有质的飞跃

### 第四步：集成测试
- 定义"游戏规则 → 预期 AI 行为"的测试标准
- 每次 commit 自动跑 mini-matrix（3 对 AI × 50 seeds, <1 分钟）
- 参考 `docs/planning/2026-07-05-complete-pre-rebuild.md` §2.1

### 第五步：回放兼容
- Rust 引擎输出和 Python 相同格式的 GameReplay JSON
- 当前 `replay_viewer.html` 能加载 Rust 产出的回放
- JSON Schema 定义在重构前未完成——Rust 阶段需要定义

---

## 重要文件速查

| 问题 | 文件 |
|------|------|
| 项目是什么、为什么 | `docs/VISION.md` |
| 当前规则参数 | `docs/GAME.md` |
| 设计决策（为什么这么设计） | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| 每个 AI 的状态和问题 | `docs/AI-AUDIT.md` |
| 重构前规划 | `docs/planning/2026-07-05-complete-pre-rebuild.md` |
| 方格引擎 | `prototype/game.py` |
| 六边引擎 | `prototype_hex/game_hex.py` |
| 最近 session | `docs/sessions/2026-07-05.md` |
| 实验数据 | `experiments/v0.7.0-grid-final/` |
| Insights | `docs/journal/INSIGHTS.md` |

---

## 不要做的事

- 不调游戏参数了（三轮矩阵已锁定）
- 不加新系统（开拓者/外交/宗教/伟人——全部留给 Rust 后）
- 不扩大地图（15×15 是默认，Rust 上可配置）
- 不修 FlatMC 性能（Python 天花板，Rust 解决）
- 不训 BC（等参数稳定）
- 不做迷雾（Rust 后做）

---

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`

已更新到最新状态：项目概况、原型进度、AI 排名、开发环境。
