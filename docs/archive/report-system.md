# 文档体系规划

## 问题

多 Agent 并行 + 频繁实验 → 大量小报告散落在各处：
- `experiments/v0.4.0/*/report.*` (实验报告)
- `docs/*.md` (全局文档)
- `eval_final/summary.json` (原始数据)
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
  param-grid-scan.md           ← 参数网格扫描
  archive/                     ← 归档（过时但保留参考价值）
    2026-07-01-xxx.md
    2026-07-02-xxx.md
  reports/                     ← 重要分析报告（从实验提炼）
    p0-first-move-analysis.md  ← 先手效应完整分析
    ai-paradigm-validation.md  ← AI 范式验证结论
    game-depth-analysis.md     ← 游戏深度分析
    balance-tuning-log.md      ← 平衡调优日志

eval_final/                    ← 核心评估数据（长期保留, 16,000局）
  summary.json

experiments/v0.4.0/            ← 实验数据（按主题分组）
  gradient/                    ← FlatMC rollout + Evo 梯度实验
  greedy-grad/                 ← Greedy 版本梯度 + 行为克隆
  randomness/                  ← 战斗随机性对比
  paired-p0/                   ← Paired P0 标定
  paradigms/                   ← AI 范式对比（Evo/DQN/SelfPlay/BC/Hybrid）
  full-matrix-partial/         ← 7×7 完整矩阵（部分完成）
```

## 命名规范

- 永久文档: `topic-name.md` (kebab-case)
- 实验报告: `experiments/v0.4.0/<theme>/report.*`
- 归档文档: `docs/archive/YYYY-MM-DD-topic.md`
- Git commit: `[模块]: 摘要\n\n数据: 关键数字\n\nCo-Authored-By: Claude`

## 文档生命周期

```
实验跑完 → 自动生成 report.* 在实验目录
         → 提取关键发现 → 更新 docs/reports/ 下的对应专题报告
         → 原始数据保留在 experiments/v0.4.0/
         → 过时文档移到 docs/archive/
```

## 入口文件

`docs/INDEX.md` 作为唯一入口，列出所有文档及其简介。
新来的人（或未来的自己）从这里开始导航。

## 本次会话的整理任务

1. ✅ `docs/INDEX.md` — 更新索引路径, 反映新版目录结构
2. ✅ `docs/current-status.md` — 更新为 v0.4.0 最终状态
3. ✅ `docs/report-system.md` — 更新目录结构
4. ✅ 归档临时文件, 清理重复
