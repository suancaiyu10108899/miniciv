# CLAUDE.md — miniciv

## 当前阶段

**Python 原型收尾** — 建设胜利平衡是最后一道坎，然后进入 Rust 架构设计。

## 当前任务（优先级排序）

1. **建设胜利平衡** — Evo 75% 统治，需调 C5 成本/加 AI 拦截逻辑
2. **20×20 验证** — 建设胜利是否地图越大越强
3. **参数锁定** — GAME.md 标注 Rust 目标值
4. **Rust 架构设计** — 模块树、trait、移植路径

## 上次做到哪了

- **全矩阵 6×6 N=500 完成**：36,000 局，11h，完整数据在 `experiments/v0.5.0/full-matrix/`
- **Evo 建设胜利统治**：75% 平均胜率，42 回合 C5，几乎不死兵
- **API Key 泄露已处理**：旧 key 删除，新增 `.env.example` + gitignore
- **eval_matrix 增强**：经济指标、checkpoint、种子确定性、30 workers
- 详细 → `docs/sessions/2026-07-03.md`
- 规划 → `docs/planning/2026-07-03.md`

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
