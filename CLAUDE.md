# CLAUDE.md — miniciv

## 当前阶段

**P2 规划设计 — 已完成 8+ 轮讨论 + 3 组外部 AI 输入整合，等待 P2-PLAN 合同提炼。**

> 🧭 **P2 规划设计 (2026-07-13~15 第七个 AI):**
> P1.5 已关闭(tag: v0.10-p1.5, H1 裁决)。本轮对话完成：
> 1. **P2-AUDIT**: 全面审计代码/文档/实验真实状态 → `docs/P2-AUDIT.md`
> 2. **8+ 轮 P2 设计讨论**: 四时代框架、聚落分级、Flexible Zoning、河流水域格、五货币三战略、
>    天命系统、贸易依赖度、清洁能源、核威慑中断机制、多边贸易竞争、灾害军民两用、
>    沙漠/海洋地形价值重定义、铜双铸、战争烈度分级、行政力等 → `docs/planning/2026-07-13-P2-planning-discussion.md`
> 3. **3 组外部 AI 输入整合**: GPT-5.6 Sol / DeepSeek V4 Pro / Claude Fable 5 各提供
>    完整规划蓝图 + 中国史机制灵感素材库 → `docs/planning/P2-external-inputs/`
> 4. **综合整理**: 交叉验证 + 新元素评估 + P2-PLAN 推荐结构 → `docs/planning/P2-external-synthesis.md`
> **下一个对话**: 审阅综合整理 → 决断 P2 范围 → 提炼 `docs/P2-PLAN.md`（合同）。
> **代码状态**: 103 tests 绿, 1 个 commit 未 push(网络问题), working tree clean。
> **版本**: V1.0.0-dev (P2 规划锁定，尚未开始实现)

---

## 交接清单 (P1.5 完成 → P2)

### 1. 最终甜点参数 (C1)
```
max_turns: 250            tech_turns_mult: 12.0       all_tech_cost_mult: 4.0
unit_cost_mult: 8.0       facility_build_turns: 14    city_hp: 2000
c_line_cost_mult: 1.0     starting_resources: 40      facility_output: 4
starting_workers: 2       branch_available_turn: 40
```
**结果**: 82.9T均结束, 征服41/建设50/阶梯9%。FlatMC d24全局87.8%最强。
克制环: StateAware>AlwaysWhite>Builder>StateAware。

### 2. 已完成 (P1.5全部)
| # | 任务 | 状态 |
|---|------|------|
| 1 | 全局压缩延寿 7-35T→82.9T | ✅ |
| 2 | 红白分叉点 branch@T40 | ✅ |
| 3 | 完整1v1 500s矩阵 (6 AI) | ✅ |
| 4 | 完整2v2矩阵 | ✅ |
| 5 | 修CavRusher (0.5%→35%) | ✅ |
| 6 | FlatMC深度曲线 2→96×500s | ✅ |
| 7 | Evo GA重训 (3.3%→86.7%) | ✅ |
| 8 | Evo三方向升级 (V1/V2/V3) | ✅ |
| 9 | BC蒸馏框架 (164K自对弈数据) | ✅ |
| 10 | 文档+裁决+VERDICT | ✅ |

### 3. P1.5关键发现
- **对手模型过拟合**: FlatMC深度>40后对所有对手下降 (minimax只假设Builder/Rusher/CavRusher)
- **非传递克制环**: StateAware>AlwaysWhite>Builder>StateAware
- **频率依赖**: WvR 1v1 64%→2v2 15%, 48pp逆转
- **线性Evo天花板**: 0.867, 加交互特征不突破
- **NN(2000参)+ES**: 0.863, 需要更好优化器

### 4. P2需要做的事
| # | 任务 | 原因 |
|---|------|------|
| 1 | 更大棋盘 (≥25×25) | 突破15×15硬天花板 |
| 2 | 扩展FlatMC minimax对手集 | 修对手模型过拟合 |
| 3 | NN继续训练 (Adam+更多代) | V2b已到0.863, 有潜力超线性Evo |
| 4 | BC重新设计 (整体turn-plan) | 动作分解架构失败 |
| 5 | 多回合建造/更多科技节点 | 增加决策深度 |
| 6 | 迷雾FOW | 信息博弈 |
| 7 | StateAware 2v2修复 | 当前1% |

### 5. 关键数据文件
```
experiments/v0.10-redwhite/
├── flatmc-d{2-96}.csv          — FlatMC深度曲线(500 seeds)
├── flatmc-self-d*.csv          — 自对弈数据
├── phase-a-matrix.csv          — FlatMC×Evo矩阵
├── final-matrix-500s.json      — 6AI最终矩阵
├── bc-selfplay-data.csv        — BC自对弈164K行
├── evo-trained-weights.json    — Evo最佳权重(86.7%)
├── evo-v2b-weights.json        — NN权重(86.3%)
├── VERDICT-FINAL.md            — 完整裁决
└── scan-push-30s.csv           — 6912组合粗扫
```

### 6. 测试: 103 passed / 0 failed / 3 ignored

### 7. 数据目录
```
experiments/v0.10-redwhite/
├── scan-coarse.txt/v2/v3   — 粗扫(972+648+432组)
├── scan-fine.txt/v2/v3/v4  — 细扫(216+144+192+96组)
├── sweet-1v1-200seeds.json — 甜点完整矩阵
├── final-1v1-500seeds.json — 基础阶段最终矩阵(hp=100旧甜点)
├── final-2v2-200seeds.json — 基础阶段2v2
├── VERDICT.md              — 基础阶段裁决
└── (其他中间数据文件)
```

> ⚠️ **顶层真相(2026-07-11 第四个 AI, S2 立裁判):**
> **接手判断**:此前"一阶深度成立"是**循环论证**——旧 Search/depth 只在 4 手写剧本里选,
> "无支配"只证明"我的脚本互相不碾压"。且甜点只活在 CLI 参数 `25 2.0 160`,默认仍是 5T 坏基线、
> depth.rs 漂移到旧甜点×3、哨兵守坏基线。**先立裁判 + 固化地基,再谈深化**(和交接文档"先做科技互斥"分歧)。
>
> **S2 做完**:①**默认=甜点**(`GameConfig::default()`=成本×2 HP160),eval/depth 无参即甜点,
> 哨兵翻为守健康基线,B6(Greedy非确定)修。②**FlatMC 裁判**(`ai/flatmc.rs`):操作层级在剧本之下,
> 从真实动作基元(研究/生产/姿态)组合 + minimax + 全 rollout,能用侦察兵/弓箭手/非标准科技。
> **裁决(60 seeds)**:FlatMC vs 全部剧本 45-50%(**双向无支配**);死机制被摸到但**换不来胜率**
> → **简单策略近最优 → 深度温和偏浅(H0)**。首个非循环深度证据,收紧旧"温和成立"。
> **诚实边界**:FlatMC 略低于剧本,"游戏浅"vs"裁判不够强"需下阶段**真 MCTS/学习型**区分。
> 数据 → `experiments/v0.9-judge/S2-VERDICT.md`;合同 → `docs/planning/2026-07-11-stage-S2-goal-acceptance.md`。
> **推论(下一步方向)**:真深度需**机制/内容改动**(让不同选择有不同回报),非精调参数。
> **发现性能债**:评估全单线程(无 rayon),FlatMC 矩阵跑几分钟只用 1 核 → 待加并行。
>
> ---
> **S1 遗留真相(第三个 AI, 仍有效)**:游戏曾存 5 回合建设速通支配(Builder 100%通杀)。
> 修完硬伤 B1-B7(攻城渐进/移速2/射程2/冲锋/遇林停)+ 甜点(成本×2 HP160)后 → 建设↔军事↔防守
> **三方制衡、有克制环**(骑兵>步兵78%/防守>骑兵53%)、征服43/建设47均衡、40-80T决出。
> 兵种机制完整。硬伤 → `docs/BUGS.md`;平衡全过程 → `experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md`;
> 阶段合同 → `docs/planning/2026-07-10-stage1-goal-acceptance.md`;方法论=验证金字塔 → `2026-07-10-validation-pyramid.md`。

| Phase | 内容 | 状态 | 测试 | 学习笔记 |
|-------|------|------|------|---------|
| 1 | cargo 骨架 | ✅ | — | — |
| 2 | map.rs — 地图生成 | ✅ | 7 | enum/struct ≈ C++，rem_euclid 是 Python % |
| 3 | movement.rs — 移动+距离 | ✅ | 10 | hex_distance 9种wrap取最短，cube distance公式 |
| 4 | unit.rs + combat.rs — 单位+战斗 | ✅ | 21 | &mut 可变引用，split_at_mut 解决双借用 |
| 5 | economy.rs + tech.rs — 经济+科技 | ✅ | 20 | HashSet Borrow 泛型推导坑，static 数组替代 Vec |
| 6 | game.rs + ai/random.rs — 游戏循环+Random | ✅ | 4 | 首次端到端！split_at_mut 实战，所有权移动 |
| 7 | ai/greedy.rs — Greedy AI | ✅ | 4 | 600局参数扫描: TW=0.15最优, hex_distance修复是关键 |
| 8 | ai/evo.rs — Evo AI | ✅ | 3 | 权重从JSON加载, 但需Rust引擎上重训 |
| 9 | 集成验证矩阵 | ✅ | 1 | ~~Greedy 60.8%~~ 30-seed 噪声,见门禁1修正 |
| G1 | eval.rs 批量评估 (第三AI) | ✅ | 3 | 500-seed 诚实矩阵: Greedy vs Random 41.4% |
| S1 | 一阶深度 M1-M2 (第三AI) | 🔄 | +tests | 起手资源=甜点杠杆; 步兵+弓箭手防守有效 |

> **~~Rust 集成矩阵 (30 seeds paired)~~ — 已被 500-seed 修正,勿引用:**
> ~~Greedy 60.8% | Random 78.3%~~ 这是 30-seed 噪声 + 拿坏 Evo 刷平均。
> **诚实版 (500 seeds):Greedy vs Random 41.4% | Evo vs Random 8.6% | Greedy 镜像 P0 50.8%**
> Rust 代码: ~4,600 行, 70 tests (+2 ignored), 0 errors
> 复现: `cd miniciv-core && cargo run --release --bin eval -- 500 balanced out.json`

## 工作模式（铁律）

**每个 Phase 必须按以下流程，不可跳过任何步骤：**

1. **概念讲解**：AI 用 5-10 分钟解释这个 Phase 要做什么、涉及的 Rust 概念、对应的 Python 参照
2. **人提问**：人提出不理解的地方——AI 不准催、不准跳过
3. **AI 写代码**：带 `// NOTE:` 教学注释，中文，标注每个关键决策的原因
4. **人 review**：人需能用自己的话解释核心逻辑
5. **学习笔记**：人在 Phase 进度表里写一句话（学到了什么或哪里模糊）
6. **门禁验证**：`cargo test` 全通过后进入下一个 Phase

**Phase 完成后 AI 必须做：**
- 更新本文件 Phase 进度表（一行 + 测试数）
- 在 session 日志追加一段（5行：做了什么/决定了什么/什么问题/测试数）
- Git commit + push

**反模式（严禁）：**
- ❌ AI 连续写完多个 Phase 不等人 review
- ❌ AI 只给代码不给解释
- ❌ 连续多个 Phase 不更新进度表
- ❌ 追求速度 > 追求理解

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI训练）
- AI 友好 > 人类好玩
- 先手平衡目标：P0 ≤ 55%（当前 49.7% ✅）
- 每局评估必须 paired 设计
- 不设 DDL
- API key 不进 git 追踪文件
- 单位堆叠限制：每格 1 战斗 + 1 平民
- 坐标系：六边形（轴向坐标 + 矩形环面）

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| Phase 进度 + 当前状态 | **本文件**（唯一真相源） |
| **P2 设计讨论完整记录** | **`docs/planning/2026-07-13-P2-planning-discussion.md`**（8+轮共识+待决事项） |
| **P2 外部输入综合整理** | **`docs/planning/P2-external-synthesis.md`**（三AI交叉验证+推荐结构） |
| **P2 启动审计** | **`docs/P2-AUDIT.md`**（代码/文档/AI/实验真实状态） |
| **北极星愿景(中国史4X/红白反滚雪球/三步走)** | **`docs/planning/2026-07-12-north-star-vision.md`**（活文档,最长远愿景+深度规格） |
| 游戏参数（唯一真相源） | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| Rust 架构设计 | `docs/rust-architecture.md` |
| Rust 学习路线 | `docs/planning/2026-07-05-rust-implementation-plan.md` |
| 集成测试标准 | `docs/INTEGRATION-TESTS.md` |
| 工程状态+技术债务 | `docs/ENGINEERING.md` |
| 硬伤记录(攻城/兵种机制 B1-B7) | `docs/BUGS.md` |
| 当前甜点数据+平衡全过程 | `experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md` |
| 文档索引(活跃/历史分层) | `docs/INDEX.md` |
| Rust 代码 | `miniciv-core/src/` |
| Python 六边引擎 | `prototype_hex/` |
| 交接文档(深化起点,已过期) | `docs/HANDOFF.md` |
| P1.5 交接(最新) | `docs/HANDOFF-P2.md` |
| Session 日志 | `docs/sessions/` |
| 学习笔记 | `docs/learning/` |
