# miniciv 文档索引

## 入口

| 文档 | 内容 | 适合谁 |
|------|------|--------|
| [current-status.md](current-status.md) | 项目当前状态、参数、已知问题 | 所有人 |
| [gdd.md](gdd.md) | 游戏设计文档 | 新人入门 |
| [README.md](../README.md) | 项目简介 | 路人 |

## 设计文档

| 文档 | 内容 |
|------|------|
| [game-design-notes.md](game-design-notes.md) | 游戏设计笔记、数值理由、Meta 分析 |
| [param-grid-scan.md](param-grid-scan.md) | 参数网格扫描——8100 局找到最优 HP=100/DMG=15 |

## 开发文档

| 文档 | 内容 |
|------|------|
| [dev-workflow.md](dev-workflow.md) | 开发工作流、Agent 协作规范、多 Agent 并行教训 |
| [dev-system-thoughts.md](dev-system-thoughts.md) | 开发体系思考——原型到 Rust 过渡规划 |
| [rust-architecture.md](rust-architecture.md) | Rust 内核架构规划 |
| [report-system.md](report-system.md) | 文档体系规划（本文档体系的设计） |

## 分析报告

| 文档 | 内容 | 数据量 |
|------|------|--------|
| [reports/game-depth-analysis.md](reports/game-depth-analysis.md) | **游戏深度分析（梯度曲线）** | FlatMC+Evo+Greedy 梯度, ~9000局 |
| [reports/ai-paradigm-validation.md](reports/ai-paradigm-validation.md) | **AI 范式验证** | 7种范式对比 |
| [reports/p0-first-move-analysis.md](reports/p0-first-move-analysis.md) | 先手效应分析 | Paired 3000 局 |
| [reports/balance-tuning-log.md](reports/balance-tuning-log.md) | 平衡调优日志 | 5轮参数迭代 |

## 实验数据

| 目录 | 内容 | 总局数 |
|------|------|--------|
| `../eval_final/` | 4×4 全矩阵（Random/Greedy/Aggressive/FlatMC 各对战 1,000 局） | 16,000 |
| `../eval_results/` | 早期 3×3 矩阵（3 AI × 200 局） | 1,800 |
| `../experiments/v0.4.0/gradient/` | FlatMC rollout + Evo 代 + Evo 种群梯度实验 | ~15,000 |
| `../experiments/v0.4.0/greedy-grad/` | Greedy 版本梯度（v1-v4）+ 行为克隆 | ~7,000 |
| `../experiments/v0.4.0/randomness/` | 战斗随机性对比（Greedy vs Greedy / Random vs Greedy） | 2,000 |
| `../experiments/v0.4.0/paired-p0/` | Paired P0 标定（5 策略 × 200 局） | 1,000 |
| `../experiments/v0.4.0/paradigms/` | AI 范式对比（Evo/DQN/SelfPlay/BC/Hybrid） | ~8,000 |
| `../experiments/v0.4.0/full-matrix-partial/` | 7×7 完整矩阵（部分完成，含 Evo） | 规划中 |

## 项目元数据

| 文件 | 内容 |
|------|------|
| [../VERSION.txt](../VERSION.txt) | 版本号 |
| [../changelog/v0.4.0.md](../changelog/v0.4.0.md) | v0.4.0 变更日志 |

## 归档

| 文档 | 内容 |
|------|------|
| [archive/2026-07-01-session.md](archive/2026-07-01-session.md) | 07-01 会话摘要 |
| [archive/2026-07-01-decisions.md](archive/2026-07-01-decisions.md) | 07-01 决策记录 |
| [archive/devlog-2026-07-02.md](archive/devlog-2026-07-02.md) | 07-02 开发日志 |
| [archive/2026-07-01-b1-mapgen.md](archive/2026-07-01-b1-mapgen.md) | Agent B1 地图生成实验 |
| [archive/2026-07-01-gdd-board.md](archive/2026-07-01-gdd-board.md) | GDD 棋盘设计讨论 |
| [archive/2026-07-01-gdd-split.md](archive/2026-07-01-gdd-split.md) | GDD 拆分决策 |
| [archive/2026-07-01-gdd-units.md](archive/2026-07-01-gdd-units.md) | GDD 单位设计讨论 |
| [archive/2026-07-01-prototype-complete.md](archive/2026-07-01-prototype-complete.md) | 原型完成报告 |
| [archive/2026-07-01-prototype-plan.md](archive/2026-07-01-prototype-plan.md) | 原型规划 |
| [archive/devplan.md](archive/devplan.md) | 开发规划（v2026.07.01，已过时） |
| [archive/prototype-plan.md](archive/prototype-plan.md) | 原型规划（已过时） |
| [archive/eval-matrix.md](archive/eval-matrix.md) | 评估矩阵摘要（已过时） |
| [archive/first-move-report.md](archive/first-move-report.md) | 先手效应报告（英文早期草稿） |
| [archive/game-depth-report.md](archive/game-depth-report.md) | 游戏深度报告（英文早期草稿） |
| [archive/ai-paradigm-report.md](archive/ai-paradigm-report.md) | AI 范式报告（英文早期草稿） |
| [archive/data-book.md](archive/data-book.md) | 数据手册（英文综合参考） |
