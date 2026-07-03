# 数据管理规划

> 2026-07-03 | 本文档定义项目所有数据的组织方式、生命周期和演进路径。
>
> 核心原则：**文件系统先行，元数据驱动，查询需求驱动数据库迁移。**
> v1.0 之前只做文件系统方案——但留好升迁到数据库的接口。

---

## 一、数据类型全景

项目会产生五类数据：

| 类型 | 内容 | 单条大小 | 增长速度 | 查询需求 |
|------|------|---------|---------|---------|
| **回放 (Replay)** | 一局完整对局的逐回合快照 | ~10-50 KB/局 | 实验驱动（每轮几百局） | "找所有 Evo 建设胜利的回放" |
| **评估结果 (Eval)** | 批量对局的终局统计 + 聚合 | ~1-5 KB/局（终局摘要） | 实验驱动 | "对比不同参数下的 AI 胜率" |
| **AI 模型 (Model)** | 训练好的权重文件 | ~1 KB (Evo JSON) ~1 MB (DQN npz) | 训练驱动 | "加载 2026-07-03 训练的 Evo v3" |
| **训练日志 (Train Log)** | 训练过程的 loss/reward 序列 | ~100 KB/次 | 训练驱动 | "对比两次训练的收敛速度" |
| **实验配置 (Config)** | 实验参数 + 假设 + 结论 | ~1 KB/次 | 每个实验一次 | "这个实验当时为什么这么设计" |

### 数据之间的关系

```
实验配置 (config.json)
  ├── 产出: 评估结果 (summary.json + per_game/*.json)
  ├── 产出: 代表性回放 (replays/*.json)
  └── 使用的 AI 模型版本 (model_version: "evo_gen200")

AI 模型 (weights.json)
  ├── 训练来源: 训练日志 (train_log.jsonl)
  └── 验证来源: 评估结果 (某个实验的 summary.json)
```

---

## 二、Phase 1：文件系统方案（当前 — v1.0）

### 目录结构

```
data/
  replays/
    YYYY-MM-DD/
      {experiment_id}/
        paired_{ai_a}_vs_{ai_b}_seed{seed}_{winner}_t{turn}.json
        _index.json          # 本目录所有回放的元数据索引
  models/
    evo/
      evo_gen{gen}_{date}.json
      _current -> evo_gen200_2026-07-02.json  # 符号链接指向当前最优
    dqn/
      dqn_{date}_step{steps}.npz
      _current -> ...
  experiments/
    {experiment_id}/
      config.json            # 实验配置（EXPERIMENT-FORMAT v1.0）
      summary.json           # 聚合结果
      per_game/              # 每局终局摘要（可选）
        {seed}_{ai_a}_vs_{ai_b}.json
      replays/               # 代表性回放（可选，3-10 个）
        ...
      README.md              # 假设+方法+结论（5行即可）
  train_logs/
    {ai_name}_{date}.jsonl
```

### 为什么是文件系统不是数据库

1. **数据量还没到**：全矩阵 36,000 局的终局数据才 ~200 MB。SQLite 的收益在这种情况下是负的——schema 维护成本 > 查询便利性。
2. **数据格式还在变**：GameReplay 格式 v1.0 可能会随游戏机制增加而变化。文件系统对格式变化宽容（旧文件留在那，新文件用新格式），数据库需要 migration。
3. **探索阶段查询是 ad-hoc 的**：你现在不会问"给我过去三个月所有 Evo vs Greedy 对局的 P0 胜率趋势"——你只会问"最近这个实验 Evo 胜率多少"。文件系统 + Python 脚本足够回答这类问题。

### 关键约定

**1. 文件名自带元数据**

回放文件名包含：对手、种子、胜者、回合数。不需要打开文件就能知道内容：

```
paired_evo_vs_greedy_seed42_P0_conquest_t45.json
```

**2. 每个目录有 `_index.json`**

```json
{
  "experiment_id": "facility-8-verify",
  "date": "2026-07-03",
  "replays": [
    {"file": "paired_evo_vs_greedy_seed42_P0_tiebreak_t100.json",
     "ai_a": "evo", "ai_b": "greedy", "seed": 42,
     "winner": "P0", "victory_type": "tiebreak_construction", "turns": 100,
     "evo_facilities": 5, "greedy_facilities": 3}
  ]
}
```

这个索引文件由实验脚本自动生成。回放浏览器或其他工具读取索引来展示可选的回放列表。

**3. 模型版本化**

AI 模型不是"最新版"——是标注了代际和日期的具体版本：
- `evo_gen200_2026-07-02.json`（不是 `evo_best.json`）
- `evo_gen200_2026-07-02.json` 的符号链接 `_current` 供脚本加载"当前最优"

### 查询工具（未来写）

```python
# data_utils.py（未来）
from data_utils import find_replays

# 找到所有 Evo 胜利的建设胜利回放
replays = find_replays(
    ai="evo",
    victory_type="construction",
    after="2026-07-01"
)
# 返回: list of file paths（通过扫描 _index.json 实现）
```

这个工具现在不需要写——因为查询需求还不明确。但文件命名约定和 `_index.json` 确保了将来能写。

---

## 三、Phase 2：SQLite 迁移（v1.0+，当以下任一条件满足时）

### 触发条件

- [ ] 回放文件总数 > 1,000 且你确实在跨实验查询
- [ ] 需要回答"Evo 在不同 facility 门槛下的建设率趋势"这种跨实验聚合问题
- [ ] `_index.json` 扫描开始变慢（> 2 秒）
- [ ] 你需要 Web UI 直接查询而非 Python 脚本

### 迁移策略

**不迁移原始数据。** SQLite 存元数据索引，原始 JSON 文件保持在原位。

```sql
-- 核心表结构（草案，不是现在要实现）
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    date TEXT,
    git_commit TEXT,
    config_snapshot TEXT,  -- JSON blob, 完整参数快照
    summary TEXT           -- JSON blob, 聚合结果
);

CREATE TABLE replays (
    id INTEGER PRIMARY KEY,
    experiment_id TEXT,
    file_path TEXT,        -- 指向原始 JSON 文件
    ai_a TEXT, ai_b TEXT,
    seed INTEGER,
    winner TEXT,
    victory_type TEXT,
    turns INTEGER,
    -- AI 行为指标（从 replay JSON 中提取）
    ai_a_facilities INTEGER,
    ai_b_facilities INTEGER,
    ai_a_construction INTEGER,
    ai_b_construction INTEGER,
    -- 附加指标可以随时加列
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

CREATE TABLE models (
    id INTEGER PRIMARY KEY,
    ai_type TEXT,          -- evo / dqn / flatmc / ...
    version TEXT,          -- gen200 / v3 / ...
    date TEXT,
    file_path TEXT,
    training_experiment_id TEXT,
    eval_winrate REAL,
    is_current BOOLEAN
);
```

**关键设计**：
- `file_path` 列指向原始 JSON——SQLite 是索引，不是替代。原始数据永远在 JSON 文件中。
- 索引提取了查询常用字段（AI 名、胜者、胜利类型、设施数），但完整数据在 JSON 里。
- 如果 JSON 格式变化，只需要更新索引提取逻辑，不需要 migration。

### 迁移脚本

```python
# migrate_to_sqlite.py（未来写）
# 1. 扫描 data/replays/ 下所有 _index.json
# 2. 插入 SQLite
# 3. 之后新实验自动写入 SQLite + 文件系统
```

---

## 四、AI 模型管理

### 当前

模型权重是散落的 JSON 文件——`prototype/evo_best_weights.json`、`prototype/bc_weights.json` 等。没有版本信息，不知道是第几代训练的，不知道在什么参数下训练的。

### Phase 1 改进（现在就做）

1. **权重文件移到 `data/models/`**，按 AI 类型分目录
2. **每个权重文件旁放 `_meta.json`**：

```json
{
  "ai_type": "evo",
  "generation": 200,
  "population_size": 50,
  "training_date": "2026-07-02",
  "training_opponents": ["greedy"],
  "game_parameters": {
    "size": 15,
    "max_turns": 100,
    "facility_requirement": 8
  },
  "eval_winrate": 0.75,
  "eval_opponents": ["greedy", "dqn_trained", "flatmc"],
  "notes": "Trained under PRE-FIX rules (C5 instant win, no facility requirement)"
}
```

这样你加载一个旧模型时，能立刻知道它在什么条件下训练的、当时表现如何。

3. **配置文件记录模型版本**：实验的 `config.json` 中标注 `model_versions: {"evo": "gen200_2026-07-02"}`，保证可复现。

### Phase 2（v1.0+）

模型注册表：一个 `data/models/registry.json`，列出所有可用模型、它们的元数据和加载方式。AI 加载器通过注册表查找模型，不硬编码路径。

---

## 五、回放数据生成策略

### 当前问题

只有手动生成的样例回放。批量实验不产出回放数据——只有终局统计。

### 改进（修改 eval_matrix.py）

加 `--save-replays N` 参数（默认 3）：

```
python -m prototype.eval_matrix --paired --ais evo,greedy --games 200 --save-replays 3
```

行为：
- 对所有对局正常运行，产出 summary.json（和以前一样）
- 每对 AI 保存 N 个代表性回放：
  - 第一个：ai_a 胜利的局（如果有）
  - 第二个：ai_b 胜利的局（如果有）
  - 第三个：最接近平均回合数的局
  - 如果某种胜利类型不存在，跳过
- 回放保存为 GameReplay JSON，放在 `experiments/{id}/replays/` 下
- 自动生成 `_index.json`

### 存储预算

一局 100 回合回放 ≈ 12-50 KB（取决于单位数量）。一个实验保存 3 对 × 3 回放 × 50 KB = 450 KB。磁盘完全不是问题。

---

## 六、回放浏览器的数据接入

### 当前

数据硬编码在 `<script id="replay-data">` 里。换回放要编辑 HTML。

### 改进（现在就做）

1. **文件拖放**：拖 JSON 到浏览器窗口 → 加载回放
2. **文件选择按钮**：`<input type="file">` 选文件
3. **目录索引模式（可选）**：如果加载的是一个 `_index.json`，显示回放列表让用户选

不需要服务器，不需要数据库。所有逻辑在浏览器 JS 里。

### Phase 2（v1.0+）

可选：一个轻量 Python HTTP 服务器（`python -m prototype.replay_server`），启动后在浏览器里列出所有可用回放，点击即看。底层读 `_index.json` 文件。不需要 SQLite。

---

## 七、总结：什么时候上 SQLite？

```
现在          → 文件系统 + _index.json + 命名约定（本文档 Phase 1）
v1.0 之前     → 不需要 SQLite
当以下之一    → 考虑 SQLite（本文档 Phase 2）
  发生时:
  - 回放 > 1000 且你在跨实验查询
  - _index.json 扫描 > 2 秒
  - 需要 Web UI 直接查而非 Python 脚本
```

在满足条件之前，文件系统方案足够。`_index.json` + 命名约定 + Python 查询脚本能覆盖你未来 3-6 个月的所有查询需求。

关键是**现在就遵守约定**（文件名格式、`_index.json`、模型元数据），这样将来要迁移时数据已经是有结构的。
