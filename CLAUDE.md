# CLAUDE.md — miniciv

## 当前阶段

**Python 原型收尾完成 → Rust 架构设计。**

## 当前任务（优先级排序）

1. **Rust 架构设计** — 模块树、trait、Python→Rust 移植路径
2. **参数锁定签字** — GAME.md + DECISIONS.md 标注 Rust 目标值
3. **20×20 验证** — 建设胜利是否地图越大越强（可选，Rust 里跑更快）

## 上次做到哪了

- **Python 阶段完成**：全矩阵 36,000 局 + C5 成本扫描 + 设施前置条件修复
- **建设胜利已修复**：C5 研究需先建 8 个设施（`CONSTRUCTION_VICTORY_REQUIRE_FACILITIES=8`），建设胜率 75%→0%
- **Evo 仍靠阶梯判定赢**（旧参数不适用新规则），需 Rust 重训解决——不是设计问题
- **API Key 泄露已处理**：旧 key 删除，新增 `.env.example` + gitignore
- **eval_matrix 增强**：经济指标、checkpoint、种子确定性、30 workers
- 详细 → `docs/sessions/2026-07-03.md`
- 规划 → `docs/planning/2026-07-03.md`
- Rust 架构草稿 → `docs/rust-architecture.md`

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：Random vs Random P0 ≤ 55%（当前 49.2% ✅）
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥
- **API key 不进 git 追踪文件**（教训：泄露 300M tokens）

## Agent 协作速查

| 角色 | 模型 | CC alias | 用于 |
|------|------|----------|------|
| 主 Agent | DeepSeek V4 Pro | `opus`（默认） | 设计、决策、审核、写文档、跑中小规模实验 |
| 子 Agent | DeepSeek V4 Flash | `haiku` | 改代码+验证、简单数据分析 |

- 长实验脚本：主 Agent 写 → 用户手动跑 或 主 Agent 后台跑
- 子 Agent 代码改动：文件隔离，结构化 JSON 输出
- 开发过程中随时 commit + push

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| Agent 协作规范 | `docs/WORKFLOW.md` §四 |
| AI 评估协议 | `docs/AI-EVAL.md` |
| 各 AI 状态 | `docs/AI-AUDIT.md` |
| Session 日志 | `docs/sessions/` |
| 下一步规划 | `docs/planning/2026-07-03.md` |
| 实验数据 | `experiments/` |
| 文档地图 | `docs/INDEX.md` |
| 原始 GDD | `docs/design/`（已冻结） |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
