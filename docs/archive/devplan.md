# 开发规划 v2026.07.01

> 从 GDD 草稿到 Rust 内核的完整路线。

---

## 架构原则

### 核心与 UI 严格分离

```
┌──────────────────────────┐
│  UI 层（多种实现）         │
│  ├── terminal-ascii       │  ← 调试用，不依赖任何框架
│  ├── html-replay          │  ← 回放可视化
│  └── web-gui（远期）       │  ← Godot / 浏览器
├──────────────────────────┤
│  协议层（Python 或 Rust）  │  ← 序列化接口：状态快照 + 动作序列
├──────────────────────────┤
│  规则引擎（Rust 核心）     │  ← 纯函数。零 UI 依赖。零 I/O
│  ├── map.rs               │
│  ├── unit.rs              │
│  ├── combat.rs            │
│  ├── tech.rs              │
│  ├── economy.rs           │
│  └── game.rs（回合管理）    │
└──────────────────────────┘
```

**规则引擎不画任何东西。不写任何文件。不接受任何用户输入。** 它只做三件事：
1. 接收当前 GameState + Action
2. 应用规则 → 新 GameState
3. 返回结果

谁调用它，怎么渲染，是 UI 层的事。

### 这对 Rust 重写意味着什么

当 Rust 内核就绪时，UI 层一行不改。只是把规则引擎的 import 从 Python `core.rules` 换成 Rust `miniciv_core`（pyO3）。验收标准：同一个 seed 跑出来的终局状态和 Python 版本完全一致。

---

## Python 原型阶段

### 目标

不是写可维护的代码——是快速验证 GDD 里规则不矛盾。代码质量到"能跑 + 行为正确"即可。

### 需要实现的最小集合

| 模块 | 内容 | 优先级 |
|---|---|---|
| `prototype/map.py` | 15/30/50 尺寸 + 环面 + BFS 连通性 + 3 地形 | P0 |
| `prototype/unit.py` | 5 兵种 + HP/ATK/DEF/移速/视野 | P0 |
| `prototype/combat.py` | 伤害公式 + 近战互打 + 远程白嫖 + 占领判定 | P0 |
| `prototype/economy.py` | 三资源 + 工人采集 + 城市基础产出 + 生产 | P0 |
| `prototype/tech.py` | 13 节点 DAG + 研究槽位 + 花费 + 耗时 | P0 |
| `prototype/game.py` | 回合循环 + 胜利判定（含阶梯） + 100 上限 | P0 |
| `prototype/fow.py` | 三态迷雾 + 半径视野 | P1 |
| `prototype/snapshot.py` | GameState 序列化/反序列化（JSON） | P1 |

### 验证步骤

```
1. Random vs Random × 100 局
   → 先手胜率？平均回合数？最常胜出方式是征服还是建设？
   
2. 调数值（按击杀回合数目标）
   → 跑 100 局 → 看结果 → 改一个数值 → 再跑
   
3. 引入 Simple AI（Greedy / Aggressive）
   → 和 Random 对比 → 验证克制三角是否真实
   
4. 先手平衡方案测试
   → 选 D+E 组合 → 调开局规则 → 重跑 Random vs Random
   
5. 确认 P0 ≤ 55% → GDD 定稿 → 可以入 Rust
```

---

## 回放与快照系统

### GameState 快照

每回合结束后的完整状态序列化为 JSON。一个快照包含：

```json
{
  "version": "2026.07.01",
  "seed": 12345,
  "map_size": 30,
  "turn": 42,
  "scores": [230, 215],
  "units": [{"id":0, "type":"infantry", "x":14, "y":8, "hp":76, ...}, ...],
  "city": {"hp": 410, ...},
  "fow": "per-player fog state",
  "resources": [45, 30, 20],
  "techs": ["M1", "E1"],
  "researching": "M3",
  "construction_progress": [1, 0, 0, 0, 0]
}
```

### 动作序列

除了快照，还需要记录每一步的动作序列：

```json
[{"turn":1, "pid":0, "unit":2, "action":"move", "dx":0, "dy":1},
 {"turn":1, "pid":1, "unit":0, "action":"research", "tech":"E1"}]
```

### 回放

从初始 seed 重新执行全部动作序列 → 逐帧渲染。不需要存储中间快照（省磁盘），只需要初始 seed + 动作序列。这保证了 **100% 可复现**。

---

## 三种对战模式

### 模式 1：AI vs AI（主工作马）

```
game = Game(config, seed)
while not game.over:
    for pid in (0, 1):
        for unit in game.units_of(pid):
            action = ai.choose_action(game.state, pid, unit)
            game.apply(pid, action)
        game.collect_economy()
    game.advance_turn()
```

用于批量评估（100-500 局/组）和训练数据生成。不需要 UI——直接 `python run_experiment.py`。

### 模式 2：Human vs AI

人类操作者选择想控制的玩家（P0/P1），AI 控制另一方：

```
game = Game(config, seed)
human_pid = 0  # 玩家选P0，AI是P1
while not game.over:
    for pid in (0, 1):
        if pid == human_pid:
            render(game.state)           # 画地图+信息面板
            action = input("你的行动: ")    # 键盘/鼠标
        else:
            action = ai.choose_action(game.state, pid, unit)
        game.apply(pid, action)
```

用于：你自己打几局找感觉、截图/gif 展示、调试 AI 行为。

### 模式 3：Human vs Human

两个人类共用同一台设备（热座模式）或网络对战（远期）。同一个 UI 渲染双方。不涉及 AI。

---

## 版本管理

### 不同组件独立版本

| 组件 | 版本格式 | 例子 | 何时变 |
|---|---|---|---|
| 游戏规则 | vYYYY.MM.DD（Git tag） | `v2026.08.15` | 规则有改动 |
| AI 模型 | 描述性命名 | `bc_128_5000_v2`, `ppo_h64_m1` | 训练条件变 |
| 实验数据 | 关联规则 tag | `eval_v2026.08.15_bc128.json` | 评估完成 |
| 回放文件 | 关联规则 tag | `replay_v2026.08.15_seed42.json` | 录制时打标 |
| UI | 独立 | 不管。UI 不依赖规则版本 | UI 改版 |

### 规则版本兼容

```
RuleVersion {
    major: u32,    // 回放不兼容 → 旧回放无法播放
    minor: u32,    // 回放兼容但数值不同 → 警告但可播放
}
```

- 改了 AI 能看到的游戏机制（加新兵种、改胜利条件）→ bump major
- 只调了数值（HP 从 100→90）→ bump minor。旧回放仍可播放但打标警告

---

## 开发阶段总览

```
                现在 ──────────────────────────────→
                
GDD 完成 ──→ Python 原型 ──→ 验证通过 ──→ Rust 内核 ──→ v2026.XX.XX
  (当前)      (~1-2周)        (GDD定稿)     (~3-5周)     (首次发布)

                                          ├── 并行: UI (Python, 不改)
                                          └── 并行: AI 训练 (SB3, FlatMC)
```

**关键纪律**：Rust 内核没有自己的 UI。内核验证方式 = Python 测试套件调用 pyO3 做逐 seed 行为对照。Rust 内核的第一个"用户"是 Python 的 AI 训练脚本。

---

## 代码仓库结构（Rust 阶段）

```
miniciv/
├── Cargo.toml              ← Rust 根
├── src/                    ← 规则引擎（纯 Rust，无 I/O）
├── python_ref/             ← Python 原型（Rust 内核的行为基准）
├── pyo3_bridge/            ← pyO3 绑定（Python 调用 Rust）
├── sim/                    ← AI 训练 + 评估（Python，调用 pyO3）
├── ui/                     ← 终端渲染 + HTML 回放（Python）
├── tests/                  ← 单元测试 + 集成对照测试
├── data/                   ← 模型 + 实验数据 + 回放
├── docs/                   ← GDD + ADR + devlog
└── replay/                 ← 回放文件 (.json)
```

---

## 当前待办

| # | 事项 | 状态 |
|---|---|---|
| 1 | 地形生成参数（比例、聚类、连通性） | 待讨论 |
| 2 | 环面开局位置 | 待讨论 |
| 3 | 先手平衡方案最终选择 + 验证方法 | 待讨论 |
| 4 | Python 原型搭建 | 上述三个定稿后开始 |
| 5 | 文档原则 | ✅ 每次 push 时同步 |
