# CLAUDE.md — miniciv

## 当前阶段

**Python 原型迭代 + 实验加速**。Multi-Agent 协作试点已完成。

## 当前任务（优先级排序）

1. **FlatMC 参数修正** — 扫描数据明确：depth=5~10 + ROLLOUTS=10~20 + random policy >> depth=20+greedy
2. **DQN 正式归档** — NaN 已修复（87.6%），需跑 L2 vs Greedy 验证 + 纳入 eval 矩阵
3. **eval.py 并行化** — 当前单线程，32 核空闲。加 ProcessPoolExecutor 加速全矩阵
4. **全矩阵更新** — 新 DQN + 调整后 FlatMC 重新跑 4×4 矩阵
5. **BC 多对手重训** — Greedy+Aggressive+Random 混合数据（暂缓）
6. **Evo softmax 改进** — 替代随机阈值决策（暂缓）

## 上次做到哪了

- **Multi-Agent 试点完成**：3 子 Agent 并行，2 成功 1 部分成功
- **DQN NaN 修复成功**：梯度裁剪 + 降LR → 87.6% vs Random
- **FlatMC 深度扫描结论**：depth=5 最优 (90%)，deepcopy 是 Python 天花板
- **FlatMC Agent B 改动保留但需回滚**：depth=20+greedy 太慢 (129s/局)
- **Agent 协作规范成熟**：WORKFLOW.md 已补充模型映射 + 子 Agent 风控规则
- 详细 → `docs/sessions/2026-07-02.md`
- 下一步规划 → `docs/planning/2026-07-03.md`

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：Random vs Random P0 ≤ 55%
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥

## Agent 协作速查

| 角色 | 模型 | CC alias | 用于 |
|------|------|----------|------|
| 主 Agent | DeepSeek V4 Pro | `opus`（默认） | 设计、决策、审核、写文档 |
| 子 Agent | DeepSeek V4 Flash | `haiku` | 改代码+验证、简单数据分析 |

- 长实验脚本：主 Agent 写 → 用户手动跑 → 回来分析
- 子 Agent 代码改动：文件隔离，结构化 JSON 输出
- 子 Agent 不改实验脚本，不代跑长时间任务

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
