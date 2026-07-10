# 实验数据格式规范 v1.0

> 2026-07-03 | 定义实验数据的组织方式。不强制字段列表——强制字段的组织和描述方式。
>
> 设计原则：元数据 > 具体字段。分层 + 自描述 + 渐进演化。

---

## 一、Schema 结构

每个实验的输出文件（`summary.json`）必须包含以下顶层字段：

```json
{
  "schema_version": "1.0",
  "experiment": { ... },
  "config_snapshot": { ... },
  "results": {
    "summary": { ... },
    "per_game": [ ... ],
    "_fields": { ... }
  }
}
```

### 1.1 schema_version

字符串。当前为 `"1.0"`。格式变更时递增主版本号（1.0 → 2.0 表示不兼容变更，1.0 → 1.1 表示向后兼容）。

### 1.2 experiment

```json
{
  "id": "facility-8-verify",
  "hypothesis": "facility=8会让Evo胜率降到65%以下",
  "date": "2026-07-03",
  "git_commit": "4c9c532",
  "question": "facility门槛对Evo建设胜率的影响",
  "measurement_method": "4-AI paired matrix, 200 seeds/pair",
  "success_criteria": "Evo avg winrate < 65% AND construction_rate > 10%",
  "why_this_method": "paired消除P0偏差, 200 seeds足够检测10%+效应"
}
```

`id`, `date`, `git_commit` 为必填。其余字段为建议填——它们让你在三个月后能理解当初为什么这么设计实验。

### 1.3 config_snapshot

**自动从 `constants.py` 注入**（不手写）。包含所有可调参数的完整快照：

```json
{
  "source": "auto-injected from prototype/constants.py",
  "values": {
    "MAX_TURNS": 100,
    "DEFAULT_SIZE": 15,
    "CITY_HP": 100,
    "CITY_DAMAGE": 15,
    "CONSTRUCTION_VICTORY_REQUIRE_FACILITIES": 8,
    "STARTING_RESOURCES": {"food": 25, "wood": 25, "gold": 25},
    "STARTING_UNITS": {"worker": 3, "scout": 1}
  }
}
```

`experiment_utils.inject_config_snapshot()` 负责此功能。

### 1.4 results

#### results.summary — 聚合统计

```json
{
  "total_games": 3200,
  "p0_winrate": 0.508,
  "p0_ci95": 0.031,
  // ... 实验自定义的聚合指标
}
```

#### results.per_game — 每局详细数据

数组，每局一个 dict。字段由实验自行定义。

#### results._fields — 自描述（必填）

```json
{
  "p0_winrate": {
    "level": "L1",
    "type": "float",
    "range": [0.0, 1.0],
    "description": "P0胜率 (paired: 每seed各执P0一次)",
    "source": "auto-computed"
  },
  "construction_rate": {
    "level": "L2",
    "type": "float",
    "range": [0.0, 1.0],
    "description": "建设胜利占比",
    "source": "computed from victory_type"
  },
  "p0_avg_distance_to_enemy": {
    "level": "L3",
    "type": "float",
    "range": [0.0, 50.0],
    "description": "P0单位到敌方城市平均距离 (实验性: 探索空间控制指标)",
    "source": "per-game computation"
  }
}
```

每个字段必须声明：
- `level`：L1（核心）/ L2（标准）/ L3（实验性）
- `type`：数据类型
- `description`：人类可读的说明
- `source`：这个字段是怎么算出来的

---

## 二、三层指标定义

### L1 — 核心指标（自动注入，不可跳过）

所有实验输出必须包含。由 `compute_standard_metrics()` 自动生成：

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_games` | int | 总局数 |
| `p0_winrate` | float | P0 胜率（paired 模式下的 P0 偏差） |
| `p0_ci95` | float | P0 胜率的 95% 置信区间半宽 |
| `avg_turns` | float | 平均回合数 |
| `conquest_rate` | float | 征服胜利占比 |
| `construction_rate` | float | 建设胜利占比 |
| `tiebreak_rate` | float | 阶梯判定占比 |

### L2 — 标准指标（默认开启，可手动关闭）

大多数实验应该记录。由实验脚本默认计算，可通过 `--minimal` 标志跳过：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ai_X_winrate` | float | 每个 AI 的胜率 |
| `avg_dead` | float | 平均死亡单位数 |
| `avg_facilities_P0/P1` | float | 双方平均设施数 |
| `avg_construction_P0/P1` | float | 双方平均建设科技数 |
| `avg_resources_P0/P1` | float | 双方平均总资源 |
| `avg_units_alive_P0/P1` | float | 双方平均存活单位数 |

### L3 — 实验性指标（自由定义）

实验根据需要添加。必须在 `_fields` 中自描述。一旦某个 L3 指标在 ≥ 3 个实验中被证明有价值 → 考虑升级到 L2。一旦某个 L2 指标被证明对所有实验都必要 → 升级到 L1。

**升级流程**：不修改历史数据——只在新实验中提升该字段的 level。分析工具按 level 过滤，不按字段名过滤。

---

## 三、实验配置模板

新建实验时，使用以下模板写 `config.json`（或嵌入 summary.json 的 `experiment` 字段）：

```json
{
  "id": "<kebab-case-id>",
  "question": "<一句话——这个实验要回答什么问题>",
  "hypothesis": "<预期结果>",
  "measurement_method": "<怎么测的——方法+规模>",
  "success_criteria": "<什么结果算'假设成立'>",
  "why_this_method": "<为什么选这个方法而不是别的>",
  "date": "<YYYY-MM-DD>",
  "git_commit": "<自动注入>",
  "parameters": {
    "size": 15,
    "gen": "balanced",
    "games_per_pair": 200,
    "ais": ["evo", "greedy", "dqn_trained", "flatmc"],
    "paired": true
  }
}
```

---

## 四、分析工具约定

分析工具（未来会写的聚合/对比脚本）应遵循：

1. **读 `_fields` 而不是硬编码字段名**：用 `_fields[name].level` 判断指标层级，用 `_fields[name].description` 生成人类可读标签
2. **按 `schema_version` 做兼容处理**：不同版本可能有不同的字段组织方式
3. **跨实验对比时按字段名匹配**：如果两个实验都有 `avg_facilities_P0`，自动对齐；如果只有一个有，跳过
4. **对 L3 字段不做假设**：不假设所有实验都有某个 L3 字段

---

## 五、迁移指南（从旧格式）

旧格式（facility-8-verify 之前的实验）缺少 `schema_version`、`_fields`、`config_snapshot`。

迁移步骤：
1. 用 `experiment_utils.inject_config_snapshot()` 生成参数快照
2. 用 `experiment_utils.validate_experiment_output()` 检查缺失字段
3. 手动补 `_fields`（L1+L2 字段有标准定义，L3 字段按实际情况填写）
4. 设 `schema_version = "1.0"`

旧格式的实验数据**不需要立即迁移**——它们仍然是有效的历史数据。但新实验必须用新格式。

---

*关联文档：INFRASTRUCTURE.md B 域、planning/2026-07-03-next-execution.md 轨道 1*
