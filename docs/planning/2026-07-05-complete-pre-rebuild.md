# 重构前完整规划

> 2026-07-05 | **本文档是重构前唯一的参考文件。** 所有之前的分项规划合并于此。
> 覆盖：游戏本体剩余工作、开发体系补齐、六边形决策、重构启动条件。

---

## 零、当前状态基线

### 游戏本体

| 参数 | 值 |
|------|-----|
| 坐标系 | 方格（六边形原型可用） |
| 地图 | 15×15 环面 |
| 堆叠 | 1 战斗 + 1 平民/格 |
| 回合上限 | 80 |
| Facility | 4 |
| 城市 HP/DEF/DMG | 80 / 5 / 5 |
| 胜利条件 | 征服 + 建设（C5+4设施）+ 阶梯判定 |
| P0 交替 | 奇数回合 P0 先 / 偶数回合 P1 先 |

### 方格终版矩阵（v0.7.0, 10,000 games）

| 指标 | 数值 | 判断 |
|------|------|------|
| 建设率 | 31.5% | 达标（>30%） |
| 征服率 | 24.1% | 接近（差 6pp） |
| 阶梯率 | 44.3% | 接近（<50% 已达成, 目标 <25%） |
| 决定性 | 55.7% | 首次过半 |
| P0 | 49.7% | 完美（<53%） |

### AI（方格）

| AI | 平均胜率 | 兵种特征 |
|----|---------|---------|
| Evo #3 | 89.8% | 骑兵 41%, 建设 rush |
| DQN #2 | 73.0% | 纯步兵（生产不经过 NN） |
| Greedy v6 | 29.1% | 骑 2.4 + 弓 2.9 + 步 1.3 |
| Aggressive v3.4 | 20.3% | 骑兵 31%, 工人死 6.1/game |
| FlatMC | ~55%（推测）| ≈ Greedy + 3% |
| Random | 37.8% | 弓手 4.9/game |

### 六边形

| 组件 | 状态 |
|------|------|
| 引擎（mapgen/movement/game）| ✅ |
| Greedy 适配 | ✅ 冒烟通过 |
| Evo 训练 | ❌ |
| DQN 适配 | ❌ |
| 矩阵 | ❌ |

---

## 一、游戏本体剩余工作

### 1.1 六边形 AI 补齐（~3h）

| 任务 | 内容 | 时间 |
|------|------|------|
| Evo(hex) | 50 代训练 | 5min |
| DQN(hex) | 机械翻译（改方向+距离） | 30min |
| Greedy(hex) | 已完成 ✅ | — |

### 1.2 方格 vs 六边对比实验（~2h）

**五个假说，每个一条指标：**

| # | 假说 | 测量指标 | 六边更好意味着 |
|---|------|---------|-------------|
| H1 | 邻居等价 → 无隐藏规则 | Evo Gen 0 胜率（随机权重） | 六边更高 → 搜索空间更友好 |
| H2 | 弓手射程 18 格 vs 12 格 | 弓手存活率 + damage_dealt | 六边更高 → 远程 niche 扩大 |
| H3 | 包围 6 面 vs 4 面 | 敌城周围单位密度 | 六边更多 → 攻城更可行 |
| H4 | 分支因子 6 vs 4 | Evo 收敛速度（Gen 0→50→200） | 六边更快 → 进化效率更高 |
| H5 | 策略分化 | AI 间兵种组成方差 | 六边更大 → 策略空间更大 |

**方法**：3 AI（Greedy v6, Evo, Random）× 3 对 × 50 seeds paired × 2 坐标系 = 1,800 games（~30min）。

### 1.3 决策

你操作 `hex_viewer.html`，结合对比数据，决定方格还是六边形。

---

## 二、开发体系补齐

### 2.1 集成测试标准（P0 — 重构前必须定义）

不是"写测试代码"——是**定义哪些场景需要集成测试、怎么判定通过**。

```
test_game_rules:
  - "facility=4 + Greedy v6 → 100 局中至少 5 局建设胜利"
  - "stacking=1+1 → 终局时不应有同类别单位在同一格"
  - "Evo vs Random → Evo 胜率 >= 70%"
  - "Greedy mirror → 弓手 alive >= 1.0/game"
  - "任何对局 → 不应出现 negative resource"

test_performance:
  - "Random vs Random → >= 50,000 games/s (Rust 单核)"
  - "完整 6×6 矩阵 → <= 2 min (Rust)"
  - "FlatMC 1 局 → <= 5s (Rust)"

test_data:
  - "eval_matrix 输出 → 包含 schema_version, _fields"
  - "GameReplay → 符合 JSON Schema"
  - "per-unit-type 字段 → 5 种兵种全部非空"
```

**产出**：`docs/INTEGRATION-TESTS.md`（标准文档，不是代码）。

### 2.2 回放格式 Schema（P0 — 重构前必须定稿）

当前 GameReplay JSON 没有正式定义。Rust 引擎第一天就要输出兼容格式。

```
需要定义:
  - JSON Schema (v1.0 字段定义 + 类型 + 必填/可选)
  - 版本迁移规则 (v1.0 → v2.0 怎么处理)
  - 验证器（replay_viewer 加载时自动检查）
  - 与 replay_viewer.html 的兼容性测试
```

**产出**：`docs/specs/replay-schema-v1.0.json` + `prototype/validate_replay.py`。

### 2.3 AI-AUDIT 更新（P1）

当前审计数据是 v0.5.0 的。更新到 v0.7.0，包含每个 AI 的兵种指纹、策略特征、已知问题。

### 2.4 版本标记（P1）

| 版本 | 里程碑 | 状态 |
|------|--------|------|
| v0.5.0 | 全矩阵 + 文档体系 | ✅ |
| v0.6.2 | per-unit-type + 三轮矩阵 | ✅ |
| v0.7.0 | 方格终版 + 六边原型 | ✅ |
| v0.7.x | 六边决策后 → 终版 | 当前 |
| v1.0.0 | Rust 引擎 v1 | 重构后 |

`changelog/v0.7.0.md`：一段话总结从 v0.5.0 到 v0.7.0 的关键变化。

### 2.5 训练记录模板（P2）

不是现在补历史——是**定义模板，下次重训开始用**。

```
experiments/training_runs/{ai}_{run_id}/
    config.json       ← 对手/参数/代数/种子
    results.json      ← 最终胜率/训练曲线
    weights.json      ← 备份
    README.md         ← 一句话
```

### 2.6 Multi-Agent 经验归档（P2）

从这轮的 5 个子 Agent 经验提炼：
- 结构化输出模板
- 任务规格模板
- 验收检查清单
- 已知 failure mode（文件冲突/评估噪声/Windows 兼容性）

---

## 三、文档体系健康检查

| 文档 | 状态 | 需要 |
|------|------|------|
| VISION.md | ✅ 最新 | — |
| GAME.md | ⚠️ | 更新方格终版参数 |
| DECISIONS.md | ⚠️ | 追加 facility/堆叠/建设机制 决策 |
| WORKFLOW.md | ✅ | 规划执行纪律已加 |
| INFRASTRUCTURE.md | ✅ | — |
| DESIGN-PRINCIPLES.md | ✅ | — |
| ANALYSIS-DIMENSIONS.md | ✅ | — |
| DATA-MANAGEMENT.md | ✅ | — |
| EXPERIMENT-FORMAT.md | ✅ | — |
| UI-PLAN.md | ⚠️ | replay viewer 已超出原计划, 需更新 |
| AI-EVAL.md | ⚠️ | L1/L2/L3 标准需用新数据更新 |
| AI-AUDIT.md | ❌ | **v0.5.0 数据, 完全过时** |
| CLAUDE.md | ✅ | 刚更新 |
| VERSION.txt | ✅ | 刚更新 |
| INDEX.md | ⚠️ | 新增了几个文档未索引 |
| CC Memory | ⚠️ | prototype-status 已更新, session 07-04/05 缺失 |

---

## 四、重构启动条件

### 必须满足（硬性）

- [ ] 坐标系已选定（方格或六边）且有数据支撑
- [ ] 建设率 > 25%（当前 31.5% ✅）
- [ ] 征服率 > 15%（当前 24.1% ✅）
- [ ] P0 < 53%（当前 49.7% ✅）
- [ ] 集成测试标准文档已写
- [ ] 回放 JSON Schema 已定稿
- [ ] 文档体系健康（AI-AUDIT + GAME + DECISIONS + INDEX 已同步）

### 建议满足（软性）

- [ ] 你自己玩过 ≥ 3 局并觉得"这个游戏有趣"
- [ ] 弓手使用率 > 1.0/game（当前 3.4 ✅）
- [ ] 至少一个非 Evo AI 使用骑兵 > 1.0（Greedy 2.4 ✅）
- [ ] 决定性对局 > 50%（当前 55.7% ✅）

### 明确不做（留给 Rust 后）

- 不加新系统（开拓者/外交/宗教/伟人/城邦）
- 不扩大地图（15×15 已锁定为默认, Rust 上配置可调）
- 不加新兵种/科技
- 不做实时对战 UI
- 不做迷雾
- 不做 BC（等参数稳定）
- 不修 FlatMC 性能
- 不发论文

---

## 五、执行序列

```
Phase A: 六边形补齐 + 对比实验 + 你决策          ← 2-3h 开发 + 30min 计算
    │
Phase B: 开发体系补齐（集成测试/回放Schema/AI-AUDIT）
    │
Phase C: 选定坐标系 → 终版参数锁定 → 终版矩阵    ← 通宵 6h
    │
Phase D: 文档归档 + 版本标记 + changelog
    │
█████ Rust 重构开工 █████
```

---

## 六、关键决策点

| # | 决策 | 谁做 | 依赖什么 |
|---|------|------|---------|
| 1 | **方格 vs 六边** | **你** | hex_viewer.html 手感 + 五假说对比数据 |
| 2 | 终版参数锁定 | 主 Agent | 你选定坐标系后 |
| 3 | 集成测试标准 | 主 Agent + 你审核 | — |
| 4 | 回放 Schema 定稿 | 主 Agent + 你审核 | — |
| 5 | Rust 架构设计 | 主 Agent | 1-4 全部完成 |

---

*本文件替代以下文档（内容已合并）：*
- *docs/planning/2026-07-04-autonomous-matrix.md*
- *docs/planning/2026-07-05-multi-agent-design-space.md*
- *docs/planning/2026-07-05-pre-rebuild-roadmap.md*
- *docs/planning/2026-07-05-final-push.md*
