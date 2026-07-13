# miniciv 文档索引

> 2026-07-10 | 第三个 AI 整理。分"当前活跃(可信)"和"历史(勿当现状)"两层。

---

## ⭐ 当前活跃真相源(先读这些)

| 文档 | 内容 | 何时读 |
|------|------|--------|
| [../CLAUDE.md](../CLAUDE.md) | **当前状态(唯一真相源,顶部真相区)** | 每次开始 |
| [../README.md](../README.md) | 快速开始 + 工具用法 + 怎么看回放 | 上手 |
| [HANDOFF.md](HANDOFF.md) | **深化阶段交接(叙事化完整上下文)** | 接手时 |
| [BUGS.md](BUGS.md) | 硬伤记录(B1-B7,含攻城/兵种机制修复) | 改引擎前 |
| [DECISIONS.md](DECISIONS.md) | 设计决策日志(#18=甜点成本×2) | 需知"为什么" |
| [GAME.md](GAME.md) | 游戏参数(⚠️ 弱AI平衡结论已作废,见顶部警告) | 参数操作 |
| [ENGINEERING.md](ENGINEERING.md) | 工程状态 + 技术债务 | 了解基础设施 |

## 深化阶段规划 + 实验(当前)

| 文档 | 内容 |
|------|------|
| [planning/2026-07-10-validation-pyramid.md](planning/2026-07-10-validation-pyramid.md) | 验证金字塔方法论(锚点分层) |
| [planning/2026-07-10-stage1-goal-acceptance.md](planning/2026-07-10-stage1-goal-acceptance.md) | 一阶深度目标 + 验收标准 A-J |
| [planning/2026-07-10-M1M2-archive.md](planning/2026-07-10-M1M2-archive.md) | M1-M2 阶段归档 |
| [planning/2026-07-10-takeover-plan.md](planning/2026-07-10-takeover-plan.md) | 第三AI接手三门禁规划 |
| `../experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md` | **平衡扫描+打表+甜点全过程数据** |
| `../experiments/v0.8.2-balance-scan/DEPTH-REPORT.md` | 深度体检报告(9信号) |
| `../experiments/v0.8.1-honest-eval/VERDICT.md` | 5T速通裁决 + PROBE-MATRIX |

## 方法论 + 长远(稳定)

| 文档 | 内容 |
|------|------|
| [VISION.md](VISION.md) | 长远愿景(项目"宪法") |
| [DESIGN-PRINCIPLES.md](DESIGN-PRINCIPLES.md) | 设计/文档原则 |
| [WORKFLOW.md](WORKFLOW.md) | 开发纪律 |
| [rust-architecture.md](rust-architecture.md) | Rust 架构 |

---

## 📜 历史(记录用,勿当现状)

> 这些反映的是过去某时点的状态,**不是当前**。查历史脉络时读,别据它下判断。

- **AI-AUDIT.md** — ⚠️ v0.8.0 方格AI数据(Evo 89.8%等),**已过时**。当前AI/兵种真相见 BUGS.md + SCAN-FINDINGS.md。
- **AI-EVAL.md / ANALYSIS-DIMENSIONS.md / UI-PLAN.md** — 原型阶段方法论文档,部分仍参考价值。
- **design/**(GDD 已冻结) — 原始设计文档,与实际有偏离(见 DECISIONS)。
- **sessions/2026-07-01~05** — 原型+重构早期日志。**sessions/2026-07-10.md** 是当前阶段。
- **planning/2026-07-05-*** — 重构前规划(已完成)。
- **archive/** + 旧 experiments(v0.4~v0.7) — 旧基础设施/方格实验数据。
- **INTEGRATION-TESTS.md / specs/** — Rust 重构期标准。

## 项目元数据

- [../VERSION.txt](../VERSION.txt) | [../changelog/](../changelog/) | [reference/](reference/)(旧项目索引)

---

*最后更新: 2026-07-13 | 当前阶段: P1.5完成。裁决H1, C1甜点(ttM=12/hp=2000/fBT=14)。克制环+频率依赖确认。准备P2。*
