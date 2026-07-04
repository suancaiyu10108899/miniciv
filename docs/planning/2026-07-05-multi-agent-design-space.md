# Multi-Agent 设计空间探索 — 执行计划

> 2026-07-05 | 本文档不只是任务分配表——是对开发体系本身的压力测试。
> 核心问题：我们能否在"一个主 Agent + N 个子 Agent"的模式下，
> 高效、不冲突、可复现地探索游戏设计空间？

---

## 零、这一轮要学到的五件事

1. **设计空间探索的 ROI**：用 3 个子 Agent 并行探索工人经济，是否比我自己写一种实现 + 跑矩阵更快找到好方案？
2. **文件隔离的可靠性**：EnterWorktree 能否让多个 Agent 并行改同一文件而不冲突？
3. **验收标准的可操作性**：50 seeds 的数据能否足够区分"这个实现比那个好"？
4. **协作开销的量化**：写规格 + 验收 + 纠错的时间，占"我自己写"的比例是多少？
5. **文档体系的抗压能力**：9 个 Agent 同时产出时，文档会不会乱？

**如果这五件事都得到正面答案——"Multi-Agent 设计探索"就是重构后的标准工作模式。**

---

## 一、任务依赖图

```
                        主Agent准备工作
                       (damage_dealt, CC Memory, 规格文档)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         Round 1: 工人经济  Round 1: 数据   Round 1: 六边形
         (3 agents 并行)   (2 agents 并行)   (1 agent)
              │               │               │
              └───── 验收 ────┘               └── 你操作判断
              │
         选择最优工人策略
              │
         Round 2: 兵种策略
         (3 agents 并行, 基于Round1结果)
              │
              └───── 验收 ────┘
              │
         选择最优兵种策略
              │
         合并 → 小矩阵验证 → 重训 → 完整矩阵
```

**为什么不把所有 9 个 agent 同时启动？**

工人经济 → 兵种策略 有依赖。兵种策略的质量取决于可用的资源——如果工人不采木头，弓手策略（Agent D）天然不合格，不是因为它写得差，是因为经济不支持。所以 Round 1 先定经济，Round 2 在确定的经济基础上测兵种。

**哪些可以并行？**
- Round 1 内部：3 个工人 agent + 2 个数据 agent + 六边形 agent = 6 个并行
- Round 2 内部：3 个兵种 agent = 3 个并行
- 数据 agent 和六边形 agent 完全独立，可以在任何时间跑

---

## 二、文件冲突：怎么让多个 Agent 改同一个文件

Track 1 的 3 个 Agent 都改 `ai_greedy.py` 的 `_greedy_worker_v3`。
Track 2 的 3 个 Agent 都改 `ai_greedy.py` 的 `_do_production`。

**方案：每个 Agent 用独立的 git worktree。**

```
主仓库: D:\Dev\miniciv\
    │
    ├─ .claude/worktrees/agent-a-economy/    ← Agent A 的隔离副本
    ├─ .claude/worktrees/agent-b-quantity/   ← Agent B 的隔离副本
    └─ .claude/worktrees/agent-c-safety/     ← Agent C 的隔离副本
```

每个 Agent 在隔离的 worktree 里工作：
- 改 `ai_greedy.py` → 跑 `pytest tests/` → 跑验证 50 seeds → 输出 diff + 数据
- Agent 不知道其他 Agent 的存在
- 主 Agent 验收时：逐个进入 worktree → 看 diff → 看数据 → 选最优

**Agent 输出格式（强制）**：
```json
{
  "agent_id": "agent-a-economy",
  "strategy": "经济优先",
  "files_changed": ["prototype/ai_greedy.py"],
  "diff": "--- a/ai_greedy.py\n+++ b/...",
  "verification": {
    "tests_pass": true,
    "50seeds_vs_random": {
      "winrate": 0.85,
      "facility_count": 5.2,
      "lumbermill_count": 1.3,
      "worker_deaths": 1.1
    }
  },
  "token_used": 45000,
  "notes": "Agent started with init_game worker placement..."
}
```

**主 Agent 验收清单**：
- [ ] `pytest tests/` 86 passed
- [ ] diff 只改了声称要改的文件
- [ ] 验证数据符合该 Agent 的验收标准
- [ ] 没有引入新 bug（代码审查）

---

## 三、进程管理：9 个 Agent 不乱跑

### 问题

每个 Agent 可能启动 Python 子进程（验证 50 seeds）。如果 Agent 崩溃或超时，子进程残留。9 个 Agent = 最多 9 × N 个残留进程。

### 防护

**Agent 层**：
- 每个 Agent 启动时 `python -c "import prototype.cleanup"` 注册 atexit
- 预算上限：150K tokens 或 30min wall time
- 超时 → 主 Agent 强制 kill worktree 进程

**主 Agent 层**：
- 每 10 分钟检查一次 `Get-Process python*`，超过 50 个进程 → 告警
- Session 结束时强制运行 `prototype/cleanup.py`（kill 所有 python 子进程）
- 每个 worktree 完成后立即 `git worktree remove`（清理磁盘）

**兜底**：
- `scripts/check_processes.sh`——不计入规范，但留作紧急情况手动运行

---

## 四、文档管理：9 个 Agent 产出不乱

### Agent 产出放哪

```
experiments/v0.6.3/design-exploration/
    worker-economy/
        agent-a-economy/
            spec.md          ← 主Agent写的需求规格
            report.json      ← Agent的结构化输出
            diff.patch       ← 代码改动
            verification/    ← 验证数据 (50 seeds)
        agent-b-quantity/
            ...
        agent-c-safety/
            ...
        DECISION.md          ← 主Agent写的：选了哪个，为什么
    unit-strategy/
        agent-d-archer/
            ...
        DECISION.md
    hex-prototype/
        agent-g-hex/
            ...
    data-analysis/
        agent-h-correlation/
            ...
```

### 主 Agent 在每轮结束时写

1. `DECISION.md`：三个 Agent 的数据对比 → 选了哪个 → 为什么
2. `INSIGHTS.md` 新条目：如果发现反直觉的结果
3. `docs/sessions/2026-07-05.md`：整个 Multi-Agent 探索的过程记录

### 不做什么

- Agent 不能修改 `CLAUDE.md`、`VISION.md`、`DECISIONS.md`、`WORKFLOW.md`
- Agent 不能修改 game.py（核心规则）
- Agent 的 commit 不能直接 push——只存在于 worktree 中，由主 Agent 合并

---

## 五、验收标准：怎么判断"这个比那个好"

不是比"谁胜率高"——50 seeds 的胜率噪声太大。比的是**这个 Agent 是否达到了它的设计意图**。

| Agent | 主要验收指标 | 达标线 | 次要指标 |
|-------|------------|--------|---------|
| A: 经济优先 | 设施总数 + 伐木场数 | 设施 ≥ 5, 伐木场 ≥ 1 | 工人死亡 < 2 |
| B: 数量优先 | 设施总数 | ≥ 6 | 不限类型 |
| C: 安全优先 | 工人死亡数 | < 1 | 设施不限 |
| D: 弓手阵地 | 弓手 alive 数 | ≥ 2 | — |
| E: 骑兵游击 | 骑兵 alive 数 | ≥ 3 | — |
| F: 步兵推进 | 步兵数 + 征服率 | 步兵 > 10, CQ > 10% | — |
| G: 六边形 | 你操作感觉 | 主观 | — |
| H: 相关性 | 发现数 | ≥ 3 条显著相关 | — |
| I: 回放战术 | 行为描述准确度 | 主观 | — |

**选最优的标准**：达标的前提下，选"超额最多"的那个。多个达标 → 跑中型验证（100 seeds vs 3 个对手）分出胜负。

---

## 六、风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Worktree 在 Windows 上不稳定 | 中 | Agent 无法工作 | 降级方案：主 Agent 手动创建 worktree，Agent 直接在主仓库的子目录工作 |
| 子 Agent 产出不符合验收标准 | 高 | 需要重跑 | 每 Agent 最多重试 1 次；两次都失败 → 主 Agent 自己做 |
| 3 个工人策略都达不到验收标准 | 中 | 需要重新设计验收线 | 降低验收标准 → 选最好的 → 分析根因 |
| 9 个 Agent 耗尽 token 预算 | 中 | 任务中断 | Flash 模型 150K/Agent, Pro 模型不做子 Agent |
| 多个 worktree 的 diff 合并冲突 | 低 | 需要手动合并 | 只合并被选中的 Agent 的 diff |
| Python 进程残留累积 | 中 | 系统变慢 | 定期清理 + 上限监控 |
| 六边形原型工作量被低估 | 高 | Agent 超预算未完成 | 验收标准降低为"只要能渲染+移动"，不要求完整战斗 |

---

## 七、开发体系的收获清单

这一轮结束后，我们应该能回答：

- [ ] EnterWorktree 在 Windows 上是否可用？隔离效果如何？
- [ ] 子 Agent 写一个函数（~30 行）的代码质量比主 Agent 差多少？
- [ ] 结构化 JSON 输出是否被严格遵守？
- [ ] 写规格 + 验收的开销 vs 自己写代码的开销，比例是多少？
- [ ] 多个 Agent 并行时，主 Agent 的 context 是否够用？
- [ ] 哪种类型的任务最适合子 Agent？（改代码 / 数据分析 / 原型构建）
- [ ] 文档体系在 9 个 Agent 同时产出时是否仍然自洽？

**这些问题的答案比"哪个工人策略最好"更有长期价值。** 因为如果 Multi-Agent 模式跑通了，重构后每次设计迭代都可以用它——一个下午并行探索 6 个设计变体，数据说话选最优。

---

## 八、前置准备（主 Agent 现在做）

在启动任何子 Agent 之前，先做好基础层：

| # | 准备项 | 目的 |
|---|--------|------|
| 1 | 写 9 份 Agent 需求规格 | 每个 Agent 有明确的"要改什么、验收什么" |
| 2 | damage_dealt/taken 字段 | 加到 Unit + combat + eval_matrix，兵种数据更完整 |
| 3 | 更新 CC Memory | 下次 AI 助手看到的是 v0.6.2 状态 |
| 4 | VERSION.txt → v0.6.3-dev | 版本标记 |
| 5 | 创建 `experiments/v0.6.3/design-exploration/` | 目录结构就绪 |
| 6 | 跑一轮 check_docs + check_leaks + pytest | 确认基线干净 |
