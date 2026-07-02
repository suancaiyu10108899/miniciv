# CLAUDE.md — miniciv

## 当前阶段

**Python 原型迭代**。GDD 设计完成，原型跑过 ~60k 局。下一阶段：参数对比实验 → 游戏设计定稿 → Rust 内核。

## 当前任务（优先级排序）

1. **文档体系重组**（进行中）— 建立可持续的文档纪律
2. **地图尺寸对比实验** — 15×15 vs 30×30，决定基准尺寸
3. **AI eval 标准化** — 三级评估协议 + 训练诊断 checklist
4. **Agent 协作流程试点** — Worktree 隔离 + 结构化接口

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
