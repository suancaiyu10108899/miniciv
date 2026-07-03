# CLAUDE.md — miniciv

## 当前阶段

**Python 原型深度迭代 — 回放驱动的设计发现 + 方法论文体系建设。**

> 堆叠 bug 已修复，兵种级统计已就绪，回放浏览器可实战。
> 发现了旧批量数据无法揭示的 AI 行为问题。
> 详细 → `docs/sessions/2026-07-04.md`

## 当前任务（优先级排序）

1. **AI 兵种偏好修复** — Greedy 从不造骑兵/弓手，需要修改生产逻辑
2. **Facility 门槛解决** — 堆叠修复未改变 0% 建设率
3. **旧数据重跑** — 全矩阵数据在堆叠 bug 下采集，关键结论需重新验证
4. **人类可玩性测试** — 用回放浏览器看对战，建立设计直觉

## 上次做到哪了

- **堆叠 bug 修复**：每格最多 1 战斗 + 1 平民（`game.py` `_do_move()`）
- **兵种级统计**：eval 输出含步/骑/弓/侦/工 的 alive+dead（`eval_matrix.py`）
- **回放浏览器实战**：中文化 + 文件拖放 + 设施渲染 + AI 名称显示
- **验证数据**：堆叠修复后 120 局 — Evo 90% vs Greedy, Greedy 0 骑兵/弓手
- **方法论文档**：EXPERIMENT-FORMAT, DATA-MANAGEMENT, DESIGN-PRINCIPLES
- **安全自动化**：check_leaks.py (pre-commit) + cleanup.py (atexit) + check_docs.py
- **Bug/Insight Journal**：I001 设施门槛悬崖效应
- 详细 → `docs/sessions/2026-07-04.md`
- 数据管理规划 → `docs/DATA-MANAGEMENT.md`
- 实验格式标准 → `docs/EXPERIMENT-FORMAT.md`
- 设计三原则 → `docs/DESIGN-PRINCIPLES.md`

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：Random vs Random P0 ≤ 55%（当前 49.2% ✅ ——但数据在堆叠 bug 下采集）
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥
- **API key 不进 git 追踪文件**
- **单位堆叠限制**：每格 1 战斗 + 1 平民（2026-07-04 修复）

## Agent 协作速查

| 角色 | 模型 | CC alias | 用于 |
|------|------|----------|------|
| 主 Agent | DeepSeek V4 Pro | `opus`（默认） | 设计、决策、审核、核心代码、跑中小规模实验 |
| 子 Agent | DeepSeek V4 Flash | `haiku` | 需求明确的独立任务（UI/文档/格式化），结构化 JSON 输出 |

- 子 Agent 适用于：需求明确、技术简单、工作量大、不碰核心游戏逻辑
- 核心游戏逻辑必须主 Agent 自己做
- 子 Agent 产出需人类验收
- 开发过程中随时 commit + push

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| 长远愿景 | `docs/VISION.md`（项目"宪法"，每个设计决策的最终依据） |
| 设计三原则 | `docs/DESIGN-PRINCIPLES.md`（信息自足/新人可入/开发者可查） |
| 数据管理规划 | `docs/DATA-MANAGEMENT.md`（五类数据全景 + 演进路径） |
| 实验格式标准 | `docs/EXPERIMENT-FORMAT.md`（分层指标 + 自描述） |
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| 基础设施问题 | `docs/INFRASTRUCTURE.md` |
| UI 开发计划 | `docs/UI-PLAN.md` |
| AI 评估协议 | `docs/AI-EVAL.md` |
| 各 AI 状态 | `docs/AI-AUDIT.md` |
| Session 日志 | `docs/sessions/` |
| Bug/Insight | `docs/journal/` |
| 实验数据 | `experiments/` |
| 回放数据 | `experiments/.../replays/_index.json` |
| 文档地图 | `docs/INDEX.md` |
| 原始 GDD | `docs/design/`（已冻结） |
| Rust 架构草稿 | `docs/rust-architecture.md` |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
