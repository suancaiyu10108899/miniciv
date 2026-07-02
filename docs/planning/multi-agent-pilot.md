# Multi-Agent 试点规划 — 2026-07-02

> 实验目的：验证 Worktree 隔离 + 结构化输出 + 预算控制能否避免 v0.5.0 的失败模式。

---

## 一、实验设计

### 三个子 Agent（并行，Wave 1）

| # | 任务 | 难度 | 风险 |
|---|------|------|------|
| A | DQN 修复（梯度裁剪 + 降LR + 重训） | 中 | 可能 NaN 不止一个原因 |
| B | FlatMC 修复（加深 rollout + 换 policy） | 低 | 几乎确定有效 |
| C | FlatMC 深度扫描（不改代码，只跑数据） | 低 | 纯数据采集 |

**为什么选这三个**：
- B 和 C 风险低，大概率成功 → 保证至少有一个可验证结果
- A 是真实 bug 修复 → 测试诊断→修复→验证的完整链路
- BC 暂时跳过：需要先生成训练数据再训练，链路过长

### 不做什么

- 不用 Workflow tool（容易失控）
- 子 Agent 不互相通信
- 子 Agent 不改同一个文件
- 子 Agent 输出必须是结构化 JSON，不超过 300 字摘要

---

## 二、任务规格书

### Agent A: DQN NaN 修复

**文件隔离**: 只改 `prototype/ai_dqn.py`（可能改 `prototype/train_dqn.py`）

**改动清单**:
1. 在 `DQNAgent.train()` 中添加梯度裁剪：`np.clip(grad, -1.0, 1.0)`
2. 默认 `learning_rate`: 0.001 → 0.0001
3. 默认 `epsilon`: 0.3 → 0.1

**验证**:
1. 用修改后的参数重训 2000 局
2. 训练完成后检查所有权重 `np.isfinite(w).all()`
3. L1 check: vs Random 200 局，胜率需 > 70%
4. 如果 NaN 仍然出现 → 标记 `failed, reason=nan_persists`

**产出格式**:
```json
{
  "status": "completed|failed",
  "files_changed": ["ai_dqn.py:L45-L48"],
  "l1_winrate": 0.82,
  "weights_nan": false,
  "attempts": 2,
  "training_games": 2000,
  "error_if_failed": null
}
```

**预算**: 150k tokens, 3 次尝试上限

---

### Agent B: FlatMC 修复

**文件隔离**: 只改 `prototype/ai_flatmc.py`

**改动清单**:
1. `ROLLOUT_DEPTH = 5` → `20`
2. `ROLLOUTS = 10` → `5`（补偿深度增加的性能损失）
3. Rollout policy: `ai_rulesrandom` → `ai_greedy`（line 34 的 import 和 line 42-43 的调用）

**验证**:
1. L1 check: vs Random 200 局，胜率需 > 70%
2. 单局耗时 < 60s（接受比原来的 11s 慢，但必须可接受）
3. 如果超时 → 标记 `partial`，报告深度=20 的实际耗时

**产出格式**:
```json
{
  "status": "completed|failed|partial",
  "files_changed": ["ai_flatmc.py:L15-L16"],
  "l1_winrate": 0.75,
  "avg_time_per_game_s": 25.0,
  "attempts": 1,
  "error_if_failed": null
}
```

**预算**: 100k tokens, 3 次尝试上限

---

### Agent C: FlatMC 深度扫描

**文件隔离**: 不改代码。在 `experiments/v0.5.0/flatmc-depth-scan/` 下创建实验脚本和数据

**任务**:
1. 创建扫描脚本，测试 `ROLLOUT_DEPTH = [5, 10, 20, 50]`
2. 每个深度 vs Random 200 局 paired
3. 记录: depth, winrate, avg_time, conquest_rate

**产出格式**:
```json
{
  "status": "completed",
  "results": [
    {"depth": 5, "winrate": 0.84, "avg_time_s": 12, "games": 200},
    {"depth": 10, "winrate": 0.86, "avg_time_s": 22, "games": 200},
    {"depth": 20, "winrate": 0.88, "avg_time_s": 40, "games": 200},
    {"depth": 50, "winrate": 0.87, "avg_time_s": 95, "games": 200}
  ],
  "data_file": "experiments/v0.5.0/flatmc-depth-scan/results.json"
}
```

**预算**: 80k tokens, 不允许多次尝试（纯数据采集）

---

## 三、风控规则

### 主Agent 红线
- 本轮新增 token 消耗 > 200k → 立即收尾
- 上下文总消耗 > 500k → 立即收尾
- 单个子 Agent 审核 > 15k tokens → 跳过，标记 `timeout`

### 子Agent 规则
- 最大尝试次数: 3（Agent C 为 1）
- 输出只能是 JSON + 改动 diff + 必要注释，不超过 500 字
- 不允许 dump 堆栈、对话历史、完整训练日志
- 遇到 3 次失败 → 标记 `failed`，不继续尝试

### 收尾流程
1. 存活的子 Agent → 等待完成（最长 5 分钟）
2. 汇总结果 → 写 session 日志
3. 更新 CLAUDE.md + CC Memory
4. 记录: 几个成功、几个失败、为什么、学到了什么

---

## 四、成功/失败判定

### 成功（任何一项）
- ≥1 个子 Agent 产出可验证的有效结果并合并到主分支
- 如果 DQN NaN 被修复 → 重大胜利

### 部分成功
- Agent B 或 C 成功（低风险项），Agent A 失败 → 学到了 DQN NaN 可能不止一个原因

### 失败
- 三个全崩 → 证明当前 Agent 基础设施不够成熟
- 原因分析写入 session 日志
- 下次我自己亲自修

---

*最后更新: 2026-07-02*
