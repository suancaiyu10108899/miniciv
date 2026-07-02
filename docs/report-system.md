# 文档体系规划

## 问题

多 Agent 并行 + 频繁实验 → 大量小报告散落在各处：
- `eval_*/report.md` (实验报告)
- `docs/*.md` (全局文档)
- `eval_*/summary.json` (原始数据)
- Agent 产出混杂（代码/数据/报告混在一个目录）

## 三层文档架构

```
docs/                          ← 永久文档（手写, 精心维护）
  INDEX.md                     ← 文档索引（入口）
  gdd.md                       ← 游戏设计文档
  current-status.md            ← 当前项目状态（每次大改后更新）
  dev-workflow.md              ← 开发工作流 + Agent 协作规范
  dev-system-thoughts.md       ← 开发体系思考
  rust-architecture.md         ← Rust 内核架构规划
  game-design-notes.md         ← 游戏设计笔记
  archive/                     ← 归档（过时但保留参考价值）
    2026-07-01-xxx.md
    2026-07-02-xxx.md
  reports/                     ← 重要分析报告（从实验提炼）
    p0-first-move-analysis.md  ← 先手效应完整分析
    ai-paradigm-validation.md  ← AI 范式验证结论
    game-depth-analysis.md     ← 游戏深度分析
    balance-tuning-log.md      ← 平衡调优日志

eval_results/                  ← 核心评估数据（长期保留）
  eval_final/                  ← 正式矩阵（16,000局）

eval_experiments/              ← 实验数据（按主题分组）
  gradience/                   ← 梯度实验
  randomness/                  ← 随机性实验
  paired-p0/                   ← Paired P0 标定
  paradigms/                   ← AI 范式对比
  full-matrix/                 ← 完整矩阵
```

## 命名规范

- 永久文档: `topic-name.md` (kebab-case)
- 实验报告: `eval_experiments/<theme>/report.md`
- 归档文档: `docs/archive/YYYY-MM-DD-topic.md`
- Git commit: `[模块]: 摘要\n\n数据: 关键数字\n\nCo-Authored-By: Claude`

## 文档生命周期

```
实验跑完 → 自动生成 report.md 在实验目录
         → 提取关键发现 → 更新 docs/reports/ 下的对应专题报告
         → 原始数据保留在 eval_experiments/
         → 过时文档移到 docs/archive/
```

## 入口文件

`docs/INDEX.md` 作为唯一入口，列出所有文档及其简介。
新来的人（或未来的自己）从这里开始导航。

## 本次会话的整理任务

1. ✅ `docs/INDEX.md` — 新建文档索引
2. ✅ `docs/dev-workflow.md` — 更新 Agent 协作规范
3. 🔄 `docs/current-status.md` — 更新当前状态
4. 🔄 将临时报告文件重命名/归类
5. ⏳ Agent B 完成后 → `docs/reports/game-depth-analysis.md`
6. ⏳ 自对弈完成后 → `docs/reports/ai-paradigm-validation.md`
