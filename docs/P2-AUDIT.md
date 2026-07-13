# P2 启动审计 — 当前真实状态

> 2026-07-13 | 第七个 AI | P1.5 已关闭, P2 启动前全面审计
> 本文件记录"代码实际是什么样"，不是"文档说什么"。每个判断附证据位置。

---

## 一、总体判断

**P1.5 目标达成。** 用最小化游戏（15×15 单城/5兵种/13科技/无FOW）验证了红白反滚雪球方向有信号：
R-1 处境决定路线 ✅、R-3 频率依赖 48pp 逆转 ✅✅、FlatMC 深度 2→24 无平台期 ✅。

**P1.5 的"极端参数"（hp=2000, 科技慢12倍）是故意设计，不是缺陷。** 它在最小引擎上模拟了"游戏有足够时间展开"的环境来测试机制张力——张力存在。P2 用结构性改动替代乘数 hack。

**当前代码库可以接手 P2。** 地基稳固但需要先清理再扩建。

---

## 二、代码质量现状

### 2.1 测试
- **103 passed / 0 failed / 3 ignored**（0.87s, `cargo test --lib`）
- 覆盖：初始化/三种胜利/渐进攻城/弓手远程/骑兵冲锋/堆叠限制/N玩家/红白分叉/支持度衰减/团队建设/并行确定性
- 缺口：`random.rs` 无测试、N玩家eval未泛化、属性测试缺失

### 2.2 编译警告
- **46 clippy warnings**（库代码）：16未使用导入、8未使用变量、15非snake_case测试名、1死函数(`team_alive`)、8个`StrategicAssessment`死字段
- **1 bin 编译失败**：`bc-train-v2.rs` — `rand_mat` 闭包未声明 `mut`（1行修复）
- 多个 bin 有未使用导入/变量

### 2.3 已知 Bug / 死代码

| 问题 | 位置 | 严重度 |
|------|------|--------|
| M3 科技加成(`infantry_def_forest_mountain +10`)在 `get_tech_bonuses()` 中计算，但战斗公式未显式读取 | tech.rs + combat.rs | 🔴 待确认 |
| E4 `worker_speed` 加成计算但代码库零使用 | tech.rs → game.rs | 🟡 死代码 |
| `produce_unit` 用硬编码 `MAP_W/MAP_H` 做坐标包装，非 `grid.width` | economy.rs:? | 🟡 改map_size后bug |
| `hex_distance` 同上的硬编码 | movement.rs | 🟡 同上 |
| `RedeemOrg` 用字符串匹配而非 `OrgRedeemMode` 枚举 | game.rs:396 | 🟡 类型不安全 |
| `GameOutcome` 的 `p0_alive/p1_alive/p0_dead/p1_dead` 硬编码1v1，但声称N玩家通用 | eval.rs | 🟡 N>2时字段为0 |
| `constants.rs` 的 `CITY_HP=80/MAX_TURNS=80` 与 `GameConfig::default()` (160/100) 冲突 | constants.rs | 🟡 混淆源 |
| BUGS.md B3/B7 标题行重复（编辑冲突残留） | docs/BUGS.md:77-78,86-88 | 🟡 文档脏 |

### 2.4 Bin 工具膨胀
- 35 个 bin 文件，其中多个是同一扫描的不同参数版本（`scan-coarse→scan-fine→scan-fine-v5→scan-push`）
- `bc-train.rs` + `bc-train-v2.rs`（v2 编译失败）
- `train-evo.rs` + `train-evo-v1.rs` + `train-evo-v2.rs` + `train-evo-v3.rs`（4个版本）
- 活跃需要的约 8-10 个

---

## 三、文档现状

### 3.1 新鲜度分级

| 文档 | 状态 | 行动 |
|------|------|------|
| CLAUDE.md | ✅ 最新 (2026-07-13) | 主真相源 |
| DECISIONS.md | ✅ 最新 (#23-#25) | — |
| HANDOFF-P2.md | ✅ 最新 | P2参考 |
| north-star-vision.md | ✅ 最新 (活文档) | P2设计依据 |
| VISION.md | ⚠️ 2026-07-03, 方向仍对 | 保留作"宪法" |
| ENGINEERING.md | ⚠️ 部分过时 (测试数79→103, Evo状态) | 更新 |
| BUGS.md | ⚠️ 所有bug已修, 重复行待清 | 清理→归档? |
| GAME.md | 🔴 严重过时 (参数是P1.5前基线) | 需重写 |
| HANDOFF.md | 🔴 自承过期 | 归档 |
| rust-architecture.md | ⚠️ 常量过时 | 更新或归档 |
| INTEGRATION-TESTS.md | ⚠️ 要求Python↔Rust确定性(物理不可能) | 归档 |
| S2 goal-acceptance | ⚠️ 已完成但复选框未勾 | 归档 |
| WORKFLOW.md | ⚠️ 测试数/模型名过时 | 更新 |
| DESIGN-PRINCIPLES.md | ✅ 原则不过时 | — |

**核心矛盾：GAME.md（应该是最常查阅的设计文档）指向过时参数。当前真相全在 CLAUDE.md 交接块里。**

---

## 四、游戏引擎现状

### 4.1 已实现的机制（完整）
- 六边轴向坐标 + 环面拓扑
- 5兵种（步兵/骑兵/弓手/侦察兵/工人），全部机制完整（移速/射程/冲锋/遇林停）
- 13节点科技树DAG（M/E/C三线），含前置逻辑(And/Or)
- 渐进式攻城 + 城市防守伤害
- 双胜利（征服/建设）+ 阶梯判定
- 交替先手 + 随机tiebreak（消除P0偏差）
- N玩家 + 团队归属（`config.teams`）
- 红白分叉 + 支持度系统 + 组织度兑换
- 抽象扩张（`Expand`动作）
- 多回合设施建造（`build_ticks`）

### 4.2 结构性限制（P2需解决）

| 限制 | 根因 | P2解法 |
|------|------|--------|
| 游戏速度硬上限7-20T | 15×15=3-5T到敌城 | ≥25×25棋盘 |
| C1永远能立刻买 | 初始资源>C1最低成本 | 降低初始资源或提高C1成本 |
| 无信息维度 | 无FOW | FOW系统 |
| 无空间博弈 | 单城 | 2-3城/玩家 |
| 科技链太短 | 4步到C5 | 扩展科技树 |
| 建造/生产无trade-off | 1回合完成 | 多回合建造/生产 |
| 侦察兵无用 | 全信息+FOW不存在 | FOW+大棋盘（视野3有价值） |

### 4.3 C1 甜点参数（P1.5最终，非P2目标）
```
max_turns=250, tech_turns_mult=12, all_tech_cost_mult=4,
unit_cost_mult=8, facility_build_turns=14, city_hp=2000,
starting_resources=40, facility_output=4, starting_workers=2,
branch_available_turn=40
```
这些乘数是 P1.5 在 15×15 上模拟长游戏的 hack。**P2 用结构性改动替代之，目标是不需要极端乘数自然达到 100-200T。**

---

## 五、AI 现状

### 5.1 AI 列表与能力

| Agent | 文件 | 类型 | C1甜点胜率 | 说明 |
|-------|------|------|-----------|------|
| FlatMC | flatmc.rs | 1-ply搜索+rollout | 87.8%(d24) | 项目最强，但对手模型过拟合(d>40下降) |
| Evo | evo.rs | 15权重GA优化 | 59.5%(Rust重训后) | 天花板0.867，加特征不突破 |
| AlwaysWhite | probes.rs | 固定白线+Rusher | 49.3% | P1.5探针 |
| StateAware | probes.rs | 5维领先判断+团队协商 | 38.9% | 1v1优秀，2v2失效(1%) |
| Builder | fixed.rs | 纯建设 | 34.5% | 太极端，但作为基线有用 |
| Adaptive | probes.rs | Builder↔Defender切换 | 30.0% | 简单有效 |
| Greedy | greedy.rs | 4层分层启发式 | 48.4% | 最复杂手写AI，但未适配长游戏 |
| Random | random.rs | 随机 | 23.7% | 唯一无测试的AI |
| BC | bc.rs | 行为克隆 | — | 架构失败(动作分解)，待P2重做 |
| Search | search.rs | 策略级minimax | — | 被FlatMC替代，保留作对照 |
| AlwaysRed/TankThenRed/Defender/Rusher/CavRusher/Harasser/Turtle | probes.rs | 固定探针 | 35-69% | 证伪导向，便宜有效 |

### 5.2 AI 的关键局限

- **FlatMC 对手模型过拟合**：minimax 只假设 Builder/Rusher/CavRusher，不覆盖 AlwaysWhite → 深度>d40后对不熟悉对手下降。P2 需扩展对手集。
- **StateAware 2v2 失效**：5维个人领先判断在团队环境下错误。P2 需团队状态评估。
- **Evo 线性天花板**：0.867，已加交互特征(攻×防、资源比等)不突破。P2 需要更多训练代或不同架构(NN)。
- **BC 架构失败**：分解动作预测(研究/生产/姿态/分叉/兑换/扩张 各独立预测)→动作不协调。P2 需整体 turn-plan 预测。
- **所有手写 AI 用硬编码基础成本**：部分已修复(`effective_unit_cost`)，但 greedy.rs 和其他仍有残留。

---

## 六、实验数据现状

### 6.1 数据量
- 120 万局+对局数据
- 164K BC 自对弈样本
- FlatMC 深度 2→96 × 500 seeds 完整曲线
- 6 AI × 500 seeds 最终矩阵
- 6,912 组合粗扫 → 5候选甜点筛选

### 6.2 关键数据文件（`experiments/v0.10-redwhite/`）
- `VERDICT-FINAL.md` — P1.5 完整裁决
- `final-matrix-500s.json` — 6AI 最终矩阵
- `flatmc-d{2-96}.csv` — FlatMC 深度曲线
- `evo-trained-weights.json` — Evo 最佳权重(86.7%)
- `bc-selfplay-data.csv` — BC 自对弈数据(164K行)

---

## 七、P2 启动前的清理清单

### 阻塞级（不清理会直接导致P2 bug）
- [ ] 确认 M3 `infantry_def_forest_mountain` 是否在战斗中生效
- [ ] `produce_unit` + `hex_distance` 的硬编码 MAP_W/H → 改用 grid/config 参数
- [ ] 修 `bc-train-v2.rs` 编译错误

### 重要级（降低接手成本+减少噪声）
- [ ] `cargo fix --lib` 消除 46 clippy 警告
- [ ] 删除 `team_alive()` 死函数 + `StrategicAssessment` 8个死字段
- [ ] `RedeemOrg` 改用 `OrgRedeemMode` 枚举替代字符串
- [ ] `constants.rs` 加注释说明与 `config.rs` 的关系
- [ ] BUGS.md 清理重复行
- [ ] GAME.md 重写或追加"当前实际参数"附录

### 可后置
- [ ] 归档过期文档（HANDOFF.md, INTEGRATION-TESTS.md, S2 goal-acceptance）
- [ ] 清理废弃 bin（保留 8-10 个活跃的）
- [ ] `GameOutcome` N玩家泛化
- [ ] ENGINEERING.md 更新

---

*审计完成: 2026-07-13 | 下一步: P2 详细规划*
