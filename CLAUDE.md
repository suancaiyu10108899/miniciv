# CLAUDE.md — miniciv

## 当前阶段

**原型阶段完成。坐标系已锁定六边形。Rust 重构准备就绪。**

> 方格终版矩阵：建设 31.5%，征服 24.1%，决定性 55.7%，P0=49.7%。
> 六边基线矩阵：Evo 67%，整体 Cq=37.8% Cs=30.7% Tb=31.6%（Greedy 需在 Rust 阶段重写）。
> **2026-07-05 第二 AI 完成**：全项目审计 + 真相源修复 + 六边验证 + 开发体系修补 + Rust 架构设计 + cargo 脚手架。
> 下一步：安装 Rust → `cd miniciv-core && cargo build` → 按 `docs/rust-architecture.md` §5 逐模块实现。
> 交接文档 → `docs/HANDOFF.md` | 完整规划 → `docs/planning/2026-07-05-pre-rebuild-audit.md`

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
