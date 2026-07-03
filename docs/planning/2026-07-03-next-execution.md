# 下一步执行计划 — Phase M1: 方法论基础设施 + UI 试点

> 2026-07-03 | 本计划覆盖未来 1-3 个 session 的自主执行任务
>
> 设计原则：能交给子 Agent 的不自己做，能自动化的人不手工，每个任务有明确验收标准。

---

## 总览：任务地图

```
Phase M1 分为四条并行的轨道：

  轨道 1: 实验框架 (主Agent)    → 灵活数据标准 + 自描述格式
  轨道 2: UI 试点   (子Agent)    → 回放浏览器 v1
  轨道 3: 安全自动化 (主Agent)   → leak check + atexit cleanup
  轨道 4: 快照升级   (主Agent)    → GameReplay 格式 + game.py 埋点

四条轨道完成后，你手上会有：
  - 一个能看回放的工具（轨道2）
  - 一套灵活的实验数据标准（轨道1）
  - 自动防止 API key 泄露和孤儿进程（轨道3）
  - 统一的回放数据格式（轨道4）
  - 已验证的多 Agent 协作模式（轨道2的成功或失败都是数据）
```

---

## 轨道 1: 实验框架 — 灵活数据标准

### 目标

建立"分层 + 自描述 + 渐进式"的实验数据格式，替代当前的硬编码字段列表。

### 产出物

**`docs/EXPERIMENT-FORMAT.md`** — 实验数据格式规范 v1.0

内容包括：
- Schema 结构定义（`schema_version`, `experiment`, `config_snapshot`, `results`, `_fields`）
- 三层指标定义（L1 核心 / L2 标准 / L3 实验性）及默认字段列表
- `_fields` 自描述格式
- 实验配置模板（`question`, `measurement_method`, `success_criteria`, `why_this_method`）
- 从旧格式迁移的指南

**`prototype/experiment_utils.py`** — 实验工具函数

- `inject_config_snapshot()` — 从 constants.py 自动抓取完整参数
- `validate_experiment_output()` — 检查格式合规
- `compute_standard_metrics()` — L1+L2 自动计算（胜率、CI、效应量）
- `merge_experiments()` — 跨实验聚合（读取 `_fields` 做字段匹配）

**升级 `eval_matrix.py`** — 输出新格式

- 在现有 `summary.json` 基础上加 `schema_version`, `config_snapshot`, `_fields`
- 不破坏现有输出——增量升级

### 主 Agent 执行步骤

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1.1 | 写 EXPERIMENT-FORMAT.md | 一次完成 |
| 1.2 | 写 experiment_utils.py | 一次完成 |
| 1.3 | 修改 eval_matrix.py 输出新格式 | 少量改动 |
| 1.4 | 用 facility-8-verify 数据验证：旧格式能无损转新格式 | 验证 |

### 验收标准

- [ ] `docs/EXPERIMENT-FORMAT.md` 存在，包含上述所有内容
- [ ] `experiment_utils.py` 三个函数可导入且通过 smoke test
- [ ] `eval_matrix.py` 产出的 `summary.json` 包含 `schema_version` 和 `_fields`
- [ ] 现有 `facility-8-verify/summary.json` 能通过 `validate_experiment_output()`

### 风险

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| 格式设计过度复杂 | 中 | v1.0 只做最小可用——三层指标 + _fields，不加其他功能 |
| 旧格式迁移成本高 | 低 | 增量升级，不破坏现有输出 |

---

## 轨道 2: UI 试点 — 回放浏览器 v1（子 Agent 执行）

### 目标

产出一个纯静态 HTML 回放浏览器，同时验证"主 Agent 设计 + 子 Agent 执行 + 人类验收"的协作模式。

### 为什么这是理想的试点任务

| 维度 | 评估 |
|------|------|
| 技术不确定性 | **极低** — HTML+原生 JS，零依赖，纯静态 |
| 验收明确性 | **高** — 加载回放、看回合、看数据、回答具体问题 |
| 失败代价 | **低** — 一个 HTML 文件，不动游戏逻辑 |
| 对人的价值 | **极高** — 立刻改善你分析游戏的能力 |
| 对方法论的验证 | **高** — 完整的"需求→执行→验收"闭环 |

### 主 Agent 产出：需求文档

我会写一份详细到子 Agent 可以直接执行的需求文档，包含：

1. **数据格式规范**：GameReplay JSON schema（每回合快照的字段定义）
2. **渲染规范**：地形颜色码、单位缩写、设施符号、格子尺寸
3. **交互规范**：回合控制（← → 快捷键、自动播放、速度切换）
4. **信息面板规范**：侧栏布局、显示内容、更新逻辑
5. **关键事件规范**：战斗高亮、科技完成提示、建造提示
6. **验收测试用例**：具体的"加载 X 回放，应该能看到 Y"的场景
7. **技术约束**：纯静态、零依赖、单文件、Chrome/Edge 兼容

### 子 Agent 任务定义

```
模型: haiku (DeepSeek V4 Flash)
预算: 150k tokens / 30 分钟 wall time
隔离: 不涉及游戏核心代码修改
输入: 需求文档 + 样例 GameReplay JSON
输出: 
  1. replay_viewer.html (自包含，JS 内联)
  2. 验收自检报告 (结构化 JSON)
  3. 已知问题列表
```

### 子 Agent 验收标准

- [ ] 加载一个 100 回合的回放 JSON，浏览器无报错
- [ ] 地图正确渲染：5 种地形用不同颜色，单位用缩写显示，P0/P1 用颜色区分
- [ ] 侧栏显示：回合数、双方资源、科技、设施数、存活单位
- [ ] ← → 方向键切换回合，地图和数据同步更新
- [ ] 自动播放模式可用（1× 速度）
- [ ] 验收测试：你能在 5 分钟内看完 Evo vs Greedy 一局完整回放，并回答"Evo 第几回合完成第一个科技？Evo 的工人在做什么？"

### 人类验收步骤

1. 打开 `replay_viewer.html` + 一个样例回放 JSON
2. 按验收标准逐项检查
3. 如果不通过 → 列出具体问题 → 主 Agent 评估是主 Agent 修还是子 Agent 修
4. 如果通过 → 标记轨道 2 完成，记录协作模式经验

### 风险

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| 子 Agent 产出的 HTML 不可用 | 中 | 需求文档足够详细（连 CSS 颜色码都提前规定），降低歧义 |
| 子 Agent 超预算 | 中 | 预算上限 + 完成标准明确 → 超预算即判定失败 |
| 回放 JSON 太大（100 回合 × 100 个格子 = 大文件）| 低 | v1 只存每回合的单位/城市/经济摘要，不存完整 grid state |
| 需求文档本身有歧义 | 中 | 人类审核需求文档后再交给子 Agent |

---

## 轨道 3: 安全自动化

### 目标

建立两道防线：pre-commit API key 检测 + atexit 孤儿进程清理。

### 产出物

**`scripts/check_leaks.py`**

- 扫描所有 git 追踪文件中的敏感模式（`sk-`、`Bearer `、`api_key`、`ANTHROPIC_AUTH_TOKEN=` 后紧跟非空值）
- 检查 `.env` 是否在 gitignore 中
- 输出：OK 或列出违规文件
- 集成到 `.git/hooks/pre-commit`

**`prototype/cleanup.py`**（模板）

- `atexit.register(cleanup)` 的标准实现
- 所有实验脚本（eval.py, eval_matrix.py, verify_facility8.py）加一行 `import prototype.cleanup`
- cleanup 函数做的事：终止本进程的所有子进程、关闭 ProcessPoolExecutor

### 主 Agent 执行步骤

| 步骤 | 内容 |
|------|------|
| 3.1 | 写 check_leaks.py |
| 3.2 | 安装 pre-commit hook（复制或符号链接到 .git/hooks/）|
| 3.3 | 写 cleanup.py |
| 3.4 | 修改 eval_matrix.py + verify_facility8.py 导入 cleanup |

### 验收标准

- [ ] `python scripts/check_leaks.py` 在当前仓库输出 "OK: no leaks detected"
- [ ] 故意在某个文件写入假 key → check_leaks.py 检测到并报错
- [ ] eval_matrix.py 运行后，进程全部退出（无残留）
- [ ] 按 Ctrl+C 中断实验 → 子进程被 cleanup

### 风险

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| Windows 上 pre-commit hook 执行权限问题 | 中 | Git Bash 中 Python 脚本可直接作为 hook（`#!/usr/bin/env python`）|
| atexit 在硬杀进程（kill -9）时不会触发 | 低 | 不可抗力——这种情况需要 session 开始时的进程检查作为兜底 |
| 假阳性（检测到注释中的 sk-） | 低 | 用正则而非简单字符串匹配，区分 `sk-xxx`（真 key）和 `# sk-xxx`（注释）|

---

## 轨道 4: 快照升级 — GameReplay 格式

### 目标

定义统一的回放数据格式，修改 game.py 产出每回合快照，让轨道 2 的 UI 有数据可读取。

### 产出物

**`prototype/snapshot.py` 升级**（已有基础，扩展）

新增函数：
- `snapshot_turn(gs) -> dict` — 单回合状态快照（units 摘要 + cities + economies + techs + events）
- `record_replay(gs) -> list[dict]` — 完整回放（每回合调用 snapshot_turn）
- 序列化/反序列化（已有 `to_json`/`from_json`，可能需要适配）

**`prototype/game.py` 修改**

- 在 `step_game()` 末尾加一行 `gs.turn_snapshots.append(snapshot_turn(gs))`
- 新增 `export_replay(gs) -> dict` 方法，产出标准 GameReplay JSON

**GameReplay JSON 格式**

```json
{
  "format_version": "1.0",
  "config": { "size": 15, "gen": "balanced", "max_turns": 100, "seed": 42 },
  "turns": [
    {
      "turn": 1,
      "units": [
        {"type": "worker", "pid": 0, "x": 7, "y": 8, "hp": 10, "action": "build"}
      ],
      "cities": [{"pid": 0, "hp": 100, "x": 7, "y": 7}],
      "economies": [{"pid": 0, "food": 22, "wood": 25, "gold": 25}],
      "techs": [{"pid": 0, "completed": [], "researching": "E1"}],
      "events": [
        {"type": "build", "pid": 0, "x": 8, "y": 8, "facility": "farm"},
        {"type": "combat", "attacker_pid": 1, "defender_pid": 0, "x": 10, "y": 10}
      ]
    }
  ],
  "result": {"winner": 0, "victory_type": "conquest", "final_turn": 45}
}
```

### 主 Agent 执行步骤

| 步骤 | 内容 |
|------|------|
| 4.1 | 在 snapshot.py 中新增 snapshot_turn() 和 record_replay() |
| 4.2 | 修改 game.py step_game() 埋点 |
| 4.3 | 在 game.py 新增 export_replay() |
| 4.4 | 跑 3 局测试：生成回放 JSON → 验证格式合规 → 用手工检查数据合理 |
| 4.5 | 产出一个样例回放文件供轨道 2 的子 Agent 使用 |

### 验收标准

- [ ] `snapshot_turn(gs)` 可调用，返回 dict 包含上述字段
- [ ] `export_replay(gs)` 产出的 JSON 通过 schema 验证
- [ ] 一局 100 回合的回放 JSON 文件 < 2MB
- [ ] 样例回放文件存在：`experiments/v0.5.0/facility-8-verify/sample_replay.json`

### 风险

| 风险 | 可能性 | 缓解 |
|------|--------|------|
| 每回合快照导致 game.py 变慢 | 中 | snapshot 只记录摘要（不 deepcopy 整个 grid），单回合开销 < 1ms |
| 回放 JSON 过大 | 中 | 只存变化量（events）而非完整 grid state |
| 和轨道 2 的需求对不齐 | 低 | 需求文档提前定义 schema，两个轨道用同一份 schema |

---

## 轨道间依赖关系

```
轨道 1 (实验框架)     ← 独立，无依赖
轨道 3 (安全自动化)   ← 独立，无依赖
轨道 4 (快照升级)     ← 独立，但产出被轨道 2 使用
轨道 2 (UI 试点)      ← 依赖轨道 4 的样例回放文件 + 需求文档
```

**可以并行执行**：轨道 1、3、4（需求文档部分）由主 Agent 同时推进。
**需要等待**：轨道 2 的子 Agent 部分需要等需求文档 + 样例回放文件就绪。

---

## 执行节奏

### Round 1（主 Agent 自主执行，~半天的量）

```
并行：
  写 EXPERIMENT-FORMAT.md           (轨道1, ~1h)
  写 experiment_utils.py            (轨道1, ~1h)
  写 check_leaks.py + hook          (轨道3, ~0.5h)
  写 cleanup.py + 修改实验脚本      (轨道3, ~0.5h)
  写 UI 需求文档                    (轨道2 前半, ~1h)
  升级 snapshot.py + game.py        (轨道4, ~1.5h)
  生成样例回放文件                  (轨道4, ~0.5h)
```

产出：所有文档 + 代码改动。你可以在这个节点审核所有设计，确认方向。

### Round 2（人类审核 + 子 Agent 并行）

```
人类：审核 Round 1 的所有产出，提出修改意见
主 Agent：根据反馈修改

审核通过后：
  子 Agent：读 UI 需求文档 + 样例回放 → 实现 replay_viewer.html
  主 Agent：如果子 Agent 在跑，可以做其他事（如实验格式验证、check_docs.py）
```

### Round 3（验收 + 归档）

```
主 Agent：验收子 Agent 产出
人类：实际打开回放浏览器，看一局回放，给出最终判定
归档：记录协作模式经验（成功/失败/学到了什么）
```

---

## 成功标志

本轮结束时，以下所有项应为真：

- [ ] `docs/EXPERIMENT-FORMAT.md` 存在且被人类确认
- [ ] `eval_matrix.py` 输出包含 `schema_version` 和 `_fields`
- [ ] `scripts/check_leaks.py` 作为 pre-commit hook 运行
- [ ] 实验脚本导入 `prototype.cleanup`，不再残留进程
- [ ] `prototype/snapshot.py` 支持 GameReplay 格式
- [ ] `replay_viewer.html` 存在，你能用它看完一局回放
- [ ] 你不后悔让子 Agent 做这件事（协作模式验证通过）
- [ ] 本轮的经验和教训已写入文档

---

## 不做的事（本轮）

- 不调 facility 门槛（游戏设计迭代——等工具就绪后再做）
- 不碰 Rust（游戏设计未稳定）
- 不写 check_docs.py（P2，本轮优先 P0/P1）
- 不做侦察兵价值实验（P2，等实验框架就绪后用新格式跑）
- 不清理实验目录（P3，不急）
