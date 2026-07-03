# miniciv 文档索引

## 入口

| 文档 | 内容 | 何时读 |
|------|------|--------|
| [../CLAUDE.md](../CLAUDE.md) | 当前阶段 + 当前任务 | **每个 session 开始** |
| [VISION.md](VISION.md) | 长远愿景（项目"宪法"） | 做设计决策时、需要回顾"为什么做这个项目"时 |
| [INFRASTRUCTURE.md](INFRASTRUCTURE.md) | 开发基础设施待解决问题与标准 | 思考"游戏之外还要做什么"时 |
| [GAME.md](GAME.md) | 当前游戏参数（唯一真相源） | 参数相关操作时 |
| [DECISIONS.md](DECISIONS.md) | 设计决策日志 | 需要知道"为什么"时 |
| [WORKFLOW.md](WORKFLOW.md) | 开发纪律 + Agent 规范 | 写代码/跑实验/用 Agent 前 |
| [AI-EVAL.md](AI-EVAL.md) | AI 评估标准化协议 | 评估 AI 性能时 |
| [AI-AUDIT.md](AI-AUDIT.md) | 每个 AI 的实现审计和诊断 | 修复/改进 AI 时 |

## 设计（已冻结）

| 文档 | 内容 |
|------|------|
| [design/README.md](design/README.md) | GDD 入口 + GDD vs 实际的偏离说明 |
| [design/map.md](design/map.md) | 棋盘 + 地形 + 地图生成 |
| [design/units.md](design/units.md) | 单位 + 战斗 + 移动 |
| [design/city.md](design/city.md) | 城市 |
| [design/economy.md](design/economy.md) | 资源 + 采集 + 花费 |
| [design/tech.md](design/tech.md) | 科技树 |
| [design/victory.md](design/victory.md) | 胜利条件 |
| [design/fow.md](design/fow.md) | 迷雾与视野 |
| [design/first-move.md](design/first-move.md) | 先手平衡 |
| design/adr/ | 5 个架构决策记录 |

## Session 日志

| 日期 | 内容 |
|------|------|
| [sessions/2026-07-01.md](sessions/2026-07-01.md) | GDD 设计 + 原型开发 |
| [sessions/2026-07-02.md](sessions/2026-07-02.md) | 调参 + AI 大军 + 文档重启 + Multi-Agent 试点 |
| [sessions/2026-07-03.md](sessions/2026-07-03.md) | 全矩阵 + API 泄露 + 建设胜利发现 |

| [UI-PLAN.md](UI-PLAN.md) | UI 开发计划——从回放浏览器到决策可视化 | UI 相关决策时 |

## 规划

| 文档 | 内容 |
|------|------|
| [planning/2026-07-03-next-execution.md](planning/2026-07-03-next-execution.md) | **下一步执行计划** — Phase M1: 方法论文基础设施 + UI 试点，含 Agent 分工/验收/风险 |
| [planning/2026-07-03-wrapup.md](planning/2026-07-03-wrapup.md) | **原型收尾评估** — 已验证/未验证审计 + 收尾执行计划 |
| [planning/2026-07-03.md](planning/2026-07-03.md) | 建设胜利平衡 + Rust 前最后一轮规划 |

## 归档

| 文档 | 内容 |
|------|------|
| [archive/2026-07-03-methodology-discussion.md](archive/2026-07-03-methodology-discussion.md) | 方法论讨论归档 — 灵活性/可延展性/子Agent协作 |

## 实验数据

| 目录 | 内容 | 总局数 |
|------|------|--------|
| `../eval_final/` | 4×4 核心全矩阵 | 16,000 |
| `../experiments/v0.4.0/` | v0.4.0 全部实验 | ~45,000 |
| `../experiments/v0.5.0/` | v0.5.0 实验（含全矩阵 36,000 局） | ~50,000 |

## 归档

| 文档 | 内容 |
|------|------|
| [archive/balance-tuning-log.md](archive/balance-tuning-log.md) | 平衡调优五轮完整日志 |
| [archive/param-grid-scan.md](archive/param-grid-scan.md) | 参数网格扫描 8100 局 |
| [archive/game-design-notes.md](archive/game-design-notes.md) | 游戏设计笔记 |
| [archive/2026-07-01-prototype-complete.md](archive/2026-07-01-prototype-complete.md) | 原型完成详细报告 |
| [archive/2026-07-01-prototype-plan.md](archive/2026-07-01-prototype-plan.md) | 原型开发规划 |
| archive/2026-07-01-gdd-*.md | GDD 各模块设计讨论 |

## 旧项目

| 文档 | 内容 |
|------|------|
| [reference/old-project-index.md](reference/old-project-index.md) | 旧 MiniCiv AI Lab 关键文件索引 |
| [reference/env-setup.md](reference/env-setup.md) | 环境配置 |

## 项目元数据

| 文件 | 内容 |
|------|------|
| [../VERSION.txt](../VERSION.txt) | 版本号 |
| [../changelog/](../changelog/) | 版本变更日志 |

## 其他（待整理）

以下文件仍在 docs/ 根目录，尚未完成迁移或归档：

- `docs/gdd/` — 原始GDD目录（→ 迁移到 `docs/design/`）
- `docs/gdd.md` — GDD入口指针（→ 废弃，被 `docs/design/README.md` 替代）
- `docs/current-status.md` — 旧当前状态（→ 废弃，被 CLAUDE.md + session日志替代）
- `docs/report-system.md` — 旧文档体系设计（→ 废弃，被 WORKFLOW.md 替代）
- `docs/dev-workflow.md` — 旧开发流程（→ 内容已合并到 WORKFLOW.md）
- `docs/dev-system-thoughts.md` — 旧开发体系思考（→ 移到 archive/）
- `docs/rust-architecture.md` — Rust 架构规划（保留，未来有用）
- `docs/reports/` — 旧报告目录（→ 移到 archive/）
- `docs/planning/` — 旧规划目录（→ 移到 archive/）

---

*最后更新: 2026-07-02*
