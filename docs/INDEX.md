# miniciv 文档索引

## 入口

| 文档 | 内容 | 何时读 |
|------|------|--------|
| [../CLAUDE.md](../CLAUDE.md) | 当前阶段 + 当前任务 | **每个 session 开始** |
| [VISION.md](VISION.md) | 长远愿景（项目"宪法"） | 做设计决策时、需要回顾"为什么做这个项目"时 |
| [DESIGN-PRINCIPLES.md](DESIGN-PRINCIPLES.md) | 设计原则——信息自足/新人可入/开发者可查 | 写文档/做工具/写UI时 |
| [INFRASTRUCTURE.md](INFRASTRUCTURE.md) | 开发基础设施待解决问题与标准 | 思考"游戏之外还要做什么"时 |
| [GAME.md](GAME.md) | 当前游戏参数（唯一真相源） | 参数相关操作时 |
| [DECISIONS.md](DECISIONS.md) | 设计决策日志 | 需要知道"为什么"时 |
| [WORKFLOW.md](WORKFLOW.md) | 开发纪律 + Agent 规范 | 写代码/跑实验/用 Agent 前 |
| [AI-EVAL.md](AI-EVAL.md) | AI 评估标准化协议 | 评估 AI 性能时 |
| [AI-AUDIT.md](AI-AUDIT.md) | 每个 AI 的实现审计和诊断 | 修复/改进 AI 时 |
| [ANALYSIS-DIMENSIONS.md](ANALYSIS-DIMENSIONS.md) | 游戏分析维度框架（7域 N维度, 分层可扩展）| 设计实验/分析数据时 |
| [DATA-MANAGEMENT.md](DATA-MANAGEMENT.md) | 数据管理规划（五类数据 + SQLite迁移路径）| 思考数据组织时 |
| [UI-PLAN.md](UI-PLAN.md) | UI 开发计划——从回放浏览器到决策可视化 | UI 相关决策时 |

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
| [sessions/2026-07-05.md](sessions/2026-07-05.md) | Multi-Agent设计探索 + 方格终版 + 六边形引擎 |
| [sessions/2026-07-04.md](sessions/2026-07-04.md) | 回放驱动设计发现 + 堆叠修复 + 方法论文体系建设 |
| [sessions/2026-07-03.md](sessions/2026-07-03.md) | 全矩阵 + API 泄露 + 建设胜利发现 |

## 规划

| 文档 | 内容 |
|------|------|
| [planning/2026-07-05-complete-pre-rebuild.md](planning/2026-07-05-complete-pre-rebuild.md) | **重构前完整规划** — 当前唯一参考文件，所有分项规划已合并 |
| [planning/2026-07-05-final-push.md](planning/2026-07-05-final-push.md) | 最终推进计划（已被上述文档合并） |
| [planning/2026-07-03-wrapup.md](planning/2026-07-03-wrapup.md) | 原型收尾评估（历史参考） |

## 归档

| 文档 | 内容 |
|------|------|
| [archive/2026-07-03-methodology-discussion.md](archive/2026-07-03-methodology-discussion.md) | 方法论讨论归档 — 灵活性/可延展性/子Agent协作 |

## 实验数据

| 目录 | 内容 | 总局数 |
|------|------|--------|
| `../eval_final/` | 4×4 核心全矩阵 | 16,000 |
| `../experiments/v0.4.0/` | v0.4.0 全部实验 | ~45,000 |
| `../experiments/v0.6.3/` | v0.6.3 实验（建设首次>30%） | 14,400 |
| `../experiments/v0.7.0-grid-final/` | v0.7.0 方格终版矩阵 | 10,000 |
| `../experiments/v0.7.0-hex-baseline/` | v0.7.0 六边形基线矩阵 | 900 |

## 规范与 Schema

| 文档 | 内容 |
|------|------|
| [INTEGRATION-TESTS.md](INTEGRATION-TESTS.md) | **Rust 重构集成测试标准** — 模块级 + 端到端验收门禁 |
| [specs/replay-schema-v1.0.json](specs/replay-schema-v1.0.json) | GameReplay JSON Schema v1.0 |
| [ENGINEERING.md](ENGINEERING.md) | 当前工程状态 + 技术债务 + 数据格式标准 |

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

---

*最后更新: 2026-07-05*
