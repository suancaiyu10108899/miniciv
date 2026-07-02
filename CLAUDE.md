# CLAUDE.md — miniciv

## 当前阶段

**Python 原型迭代 + Multi-Agent 协作试点**。

## 当前任务（优先级排序）

1. **Multi-Agent 试点**（进行中）— DQN修复 + FlatMC修复 + FlatMC深度扫描，三个子Agent并行
2. **DQN 重训** — 梯度裁剪 + 降LR，修复 NaN bug
3. **FlatMC 加深** — 20T rollout + Greedy policy
4. **BC 多对手重训** — Greedy+Aggressive+Random 混合数据

## 上次做到哪了

→ `docs/sessions/2026-07-02.md`
→ `docs/planning/multi-agent-pilot.md`（本任务详细规划）

## 上次做到哪了

→ `docs/sessions/2026-07-02.md`

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：Random vs Random P0 ≤ 55%
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| 原始 GDD 设计 | `docs/design/`（已冻结） |
| Session 日志 | `docs/sessions/` |
| 实验数据 | `experiments/` |
| 文档地图 | `docs/INDEX.md` |
| 旧项目参考 | `docs/reference/old-project-index.md` |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
