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
| [reports/p0-first-move-analysis.md](reports/p0-first-move-analysis.md) | 先手效应完整分析 | Paired 3000 局 |
| [reports/ai-paradigm-validation.md](reports/ai-paradigm-validation.md) | AI 范式验证 | 多种 AI 对比 |
| [reports/game-depth-analysis.md](reports/game-depth-analysis.md) | 游戏深度分析（梯度曲线） | FlatMC+Evo+Greedy 梯度 |
| [reports/balance-tuning-log.md](reports/balance-tuning-log.md) | 平衡调优日志 | 多次参数迭代 |

## 实验数据

| 目录 | 内容 | 总局数 |
|------|------|--------|
| `../eval_final/` | 4×4 全矩阵（16,000 局） | 16,000 |
| `../eval_experiments/gradience/` | FlatMC+Evo+Greedy 梯度实验 | ~15,000 |
| `../eval_experiments/randomness/` | 战斗随机性对比 | 2,000 |
| `../eval_experiments/paired-p0/` | Paired P0 标定 | 6,000 |
| `../eval_experiments/paradigms/` | AI 范式对比（BC/DQN/SelfPlay） | ~5,000 |
| `../eval_experiments/full-matrix/` | 7×7 完整矩阵 | 规划中 |

## 归档

| 文档 | 内容 |
|------|------|
| [archive/2026-07-01-session.md](archive/2026-07-01-session.md) | 07-01 会话摘要 |
| [archive/2026-07-01-decisions.md](archive/2026-07-01-decisions.md) | 07-01 决策记录 |
| [archive/devlog-2026-07-02.md](archive/devlog-2026-07-02.md) | 07-02 开发日志 |
