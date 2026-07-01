# CLAUDE.md — miniciv

> 给 Claude Code 的项目上下文。每次新会话自动加载。

## 项目是什么

miniciv 是一个复杂度可分级缩放、AI 友好的回合制策略游戏平台。前身是 MiniCiv AI Lab（v0-v13，已封存归档）。

## 当前阶段：GDD 设计

游戏设计文档在 `docs/gdd.md`。**当前是纯设计阶段——不要写代码，先讨论设计。** 每个模块讨论一轮，定稿一个再开下一个。

## 开发流程

1. 讨论 GDD 模块 → 定稿
2. Python 快速原型验证（需要时）
3. GDD 全部定稿 + Python 原型验证通过后 → Rust 内核

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩（但两者尽量兼顾）
- 先手平衡目标：Random vs Random P0 ≤ 55%
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥

## 旧项目参考

`docs/reference/old-project-index.md` — 指向旧 repo 的关键文件索引

## CC Memory

项目 CC Memory 在 `C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
