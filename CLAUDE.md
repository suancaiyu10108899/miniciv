# CLAUDE.md — miniciv

## 当前阶段

**Rust 重构准备就绪。工作模式已切换：从"纯 AI 写代码"到"人-AI 协作学习"。**

> 方格终版矩阵：建设 31.5%，征服 24.1%，决定性 55.7%，P0=49.7%。
> 六边基线矩阵：Evo 67%，整体 Cq=37.8% Cs=30.7% Tb=31.6%（Greedy 需在 Rust 阶段重写）。
> **当前阻塞**：Rust 工具链未安装。安装后 → `cd miniciv-core && cargo build` → 按 Phase 2-9 推进。
> **新模式**：每个 Phase 先讲解概念 → 人阅读提问 → AI 写代码（带教学注释）→ 人 review → 人写学习笔记。
> 完整规划 → `docs/planning/2026-07-05-rust-implementation-plan.md` | 学习笔记 → `docs/learning/`

## 工作模式（铁律）

**每个 Phase 必须按以下流程，不可跳过任何步骤：**

1. **概念讲解**：AI 用 5-10 分钟解释这个 Phase 要做什么、涉及的 Rust 概念、对应的 Python 参照代码
2. **人提问**：人提出不理解的地方——AI 不准催、不准跳过
3. **AI 写代码**：带 `// NOTE:` 教学注释，标注每个关键决策的原因
4. **人 review**：人需能用自己的话解释核心逻辑
5. **人写学习笔记**：`docs/learning/phase-N-<名称>.md`，至少一句话总结
6. **门禁验证**：AI 跑测试/验证脚本，全部通过后进入下一个 Phase

**反模式（原型阶段的教训，Rust 阶段禁止）：**
- ❌ AI 连续写完多个 Phase 不等人 review
- ❌ AI 只给代码不给解释
- ❌ 人跳过学习笔记
- ❌ 追求速度 > 追求理解

## 原型阶段关键成果

- **5 轮完整矩阵**（v0.5.0 → v0.7.0, ~57,000 games total）
- **6 种 AI**（Evo 89.8%, DQN 73.0%, Greedy 29.1%, Aggressive 20.3%, FlatMC ~55%, Random 37.8%）
- **per-unit-type 数据**（步/骑/弓/侦/工 alive+dead+damage_dealt/taken）
- **设施分类型统计**（farm/lumbermill/mine）
- **per-victory-type P0**（三种胜利类型均 ≈50%）
- **六边形引擎**（prototype_hex/ — mapgen + movement + game + Greedy + Evo）
- **回放浏览器**（HTML, 中文化, 文件拖放, 设施渲染）
- **子 Agent 验证**（5/5 成功, 结构化输出可行）
- **6 条 Insights**（I001-I006）

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：P0 ≤ 55%（当前 49.7% ✅）
- 每局评估必须 paired 设计
- 不设 DDL
- **API key 不进 git 追踪文件**
- **单位堆叠限制**：每格 1 战斗 + 1 平民
- **坐标系**：六边形（轴向坐标 + 矩形环面）

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| **交接文档** | `docs/HANDOFF.md` |
| 长远愿景 | `docs/VISION.md` |
| 重构前完整规划 | `docs/planning/2026-07-05-complete-pre-rebuild.md` |
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| AI 状态 | `docs/AI-AUDIT.md` |
| 设计三原则 | `docs/DESIGN-PRINCIPLES.md` |
| 分析维度框架 | `docs/ANALYSIS-DIMENSIONS.md` |
| 数据管理规划 | `docs/DATA-MANAGEMENT.md` |
| 实验格式标准 | `docs/EXPERIMENT-FORMAT.md` |
| 基础设施 | `docs/INFRASTRUCTURE.md` |
| UI 计划 | `docs/UI-PLAN.md` |
| Session 日志 | `docs/sessions/` |
| Bug/Insight | `docs/journal/` |
| 实验数据 | `experiments/` |
| 六边形引擎 | `prototype_hex/` |
| 方格引擎 | `prototype/` |
| Rust 架构草稿 | `docs/rust-architecture.md` |
| 文档地图 | `docs/INDEX.md` |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
