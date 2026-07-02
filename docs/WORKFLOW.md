# 开发纪律 — miniciv 工作流规范

> 本文档是所有开发活动的"宪法"。改流程先改这个文件。

---

## 一、文档体系总览

### 核心原则
- **文档越少越好，每份文档必须有明确读者和时效**
- **真相源是代码（constants.py）+ 决策记录（DECISIONS.md）**
- **过程产物塞 session 日志，不建独立文件**

### 文件地图

```
CLAUDE.md              ← Session 入口。阶段+任务+导航。每个 session 结束必须更新
docs/
  INDEX.md             ← 文档地图（≤30行）
  GAME.md              ← 当前游戏参数，手动与 constants.py 同步
  DECISIONS.md         ← 设计决策日志，只追加不删除
  WORKFLOW.md          ← 本文件。开发纪律+Agent规范
  design/              ← 原始GDD+ADR（已冻结，只读参考）
  sessions/            ← 每个session一个文件（YYYY-MM-DD.md）
  archive/             ← 被取代的文档（日期前缀，保留历史）
```

### 文档分类与生命周期

| 类型 | 位置 | 谁写 | 更新频率 | 示例 |
|------|------|------|---------|------|
| 锚点 | 根目录 | 人+AI | 每session | CLAUDE.md |
| 真相 | docs/ | 人+AI | 参数/决策变动时 | GAME.md, DECISIONS.md |
| 规范 | docs/ | 人+AI | 流程变更时 | WORKFLOW.md |
| 档案 | docs/design/ | 人+AI | **冻结** | GDD模块, ADR |
| 过程 | docs/sessions/ | AI | 每session | 2026-07-02.md |
| 实验 | experiments/ | AI | 每次实验 | config.json + 数据 |

### 中间产物往哪塞

```
设计讨论 → Session日志（讨论过程+结论）
实验计划 → Session日志（计划）→ experiments/（数据+config.json）
Bug调查 → Session日志（调查过程）→ git commit（修复）
参数变更 → constants.py + GAME.md（同步）→ Session日志（为什么）
架构决策 → DECISIONS.md（追加）→ Session日志（上下文）
```

---

## 二、Session 生命周期（铁律）

### 开始（Claude 自动执行）

1. 读 `CLAUDE.md` → 当前阶段、当前任务
2. 读 `docs/INDEX.md` → 文档布局
3. 读最近 `docs/sessions/` → 上次做到哪
4. 加载 CC Memory → 跨 session 上下文

### 工作期间

5. 设计决策 → **当时就写**进 `DECISIONS.md`，不等结束
6. 参数变更 → 同步 `constants.py` + `docs/GAME.md`
7. 实验 → `experiments/` 下建目录 + `config.json`（保证可复现）

### 结束（强制性，不可跳过）

8. 写 session 日志 `docs/sessions/YYYY-MM-DD.md`：
   - 做了什么（具体、可验证）
   - 决定了什么（为什么）
   - 跑了什么实验（数据在哪、结论是什么）
   - 出现了什么问题（未解决的标记 **OPEN**）
   - 下一步（给下一个 session 的明确指令）

9. 更新 `CLAUDE.md`（如果阶段/任务变了）

10. 更新 CC Memory（跨 session 需要记住的事）

11. 如果有文档被取代 → 加 `[superseded]` 标签移到 `docs/archive/`

12. 如果新增/移动了文件 → 更新 `docs/INDEX.md`

---

## 三、实验规范

### 标准评估协议

每个 AI 或参数变更必须通过三级评估：

```
L1: Sanity check — vs Random 500局，胜率必须 > 70%（非随机基线）
L2: Baseline    — vs Greedy 500局 paired
L3: Full eval   — 加入全矩阵（如果 L1+L2 通过）
```

### 实验目录结构

```
experiments/vX.Y.Z/<experiment-name>/
  config.json     ← 参数/git hash/重现命令（必须）
  results.json    ← 原始数据
  report.md       ← 分析报告（可选，重要实验写）
  notes.md        ← 临时笔记（可选）
```

### config.json 模板

```json
{
  "experiment": "map-size-comparison",
  "date": "2026-07-02",
  "git_commit": "abc1234",
  "parameters": {
    "sizes": [15, 30],
    "games_per_pair": 500,
    "ais": ["random", "greedy", "aggressive"],
    "generator": "balanced",
    "max_turns": 100
  },
  "reproduce": "python -m prototype.eval --ai0 greedy --ai1 random --games 500 --size 30"
}
```

### 参数扫描方法论

- 先定性后定量：sensitivity analysis（每次变一个参数）→ 找出敏感维度 → 网格扫描
- 网格扫描用自动化脚本，不要手工调
- 扫描结果产出热力图（数据 + 一句话结论）

---

## 四、Agent 协作规范

### 模型分工

| 角色 | 模型 | CC alias | 职责 |
|------|------|----------|------|
| 主Agent | DeepSeek V4 Pro | `opus`（默认） | 设计决策、架构判断、数据审核、写文档 |
| 子Agent | DeepSeek V4 Flash | `haiku` / `sonnet` | 代码修改+测试、跑实验、数据分析初版、格式化 |

> **DeepSeek 官方映射规则**（2026-07-02）：
> - `claude-opus-*` → `deepseek-v4-pro`
> - `claude-haiku-*` / `claude-sonnet-*` → `deepseek-v4-flash`
>
> 因此子 Agent 调用时指定 `model: "haiku"` 即可走 Flash（省 token），主 Agent 不指定或用 `opus` 走 Pro。

### 子Agent 任务定义规范

**错误**（太模糊）：
> "修 FlatMC，让它变好"

**正确**（有完成标准）：
> "FlatMC 对 Random 胜率 > 50%，200局验证，单局 < 15秒。不达标注失败原因，最多尝试5次。"

### 隔离规则

- **写代码的子Agent** → `EnterWorktree` 隔离，改完 review + merge
- **跑实验的子Agent** → 等代码稳定后在稳定版本上执行，不写代码
- **读数据的子Agent** → 只读，随时可跑

### 子Agent 输出格式（结构化）

```json
{
  "status": "completed|failed|partial",
  "artifacts": ["path/to/result.json"],
  "metrics": {"games_run": 4900, "elo_spread": 123.4},
  "errors": [],
  "token_used": 45000
}
```

### 反模式（v0.5.0 的教训）

- ❌ 多个 Agent 并行修改同一文件
- ❌ 子Agent 无超时/预算控制 → 死循环灌垃圾
- ❌ 子Agent 输出自由文本 → 主Agent 难以验证
- ❌ Agent 产出不经 review 直接合并

---

## 五、Git 规范

- 分支：`nightly-ai`（日常开发）/ `master`（稳定）
- Commit 消息模板：
  ```
  [模块]: 改动摘要

  数据: 关键数字对比

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
- 每次改动独立 commit，方便回退
- 数值改动 commit 必须包含前后对比数据

---

## 六、测试规范

- 代码修改后 → `pytest tests/`（86项, <0.2s）
- 新功能 → 先写测试，再写实现
- 集成测试：至少 3 个完整 game loop smoke test（待补）
- 参数变更后 → 跑 L1 sanity check（500局 vs Random）

---

## 七、版本号

- 格式：`vYYYY.MM.DD`（不按 semver）
- 版本升级在 VERSION.txt + changelog/vX.Y.Z.md

---

*最后更新: 2026-07-02*
