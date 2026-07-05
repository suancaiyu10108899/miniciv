# 集成测试标准

> 2026-07-05 | Rust 重构的验收门禁。
> 每一项有：测试内容、Python 参照、验收阈值、失败意味着什么。

---

## 一、Golden Seeds

选定 10 个 seeds 作为标准测试集。所有跨语言验证使用同一组 seeds。

```
Golden seeds: 42, 123, 777, 2048, 9999, 1337, 50000, 31415, 2718, 65535
```

---

## 二、模块级集成测试

### IT-MAP-001: 地图生成一致性

**测试内容**: 同 seed，Rust 和 Python 生成的地图完全一致。
**Python 参照**: `prototype_hex/mapgen_hex.py` → `generate_map_hex(seed, "balanced")`
**验收阈值**: 10/10 golden seeds，所有 225 格的 terrain 值相同、城市位置相同。
**失败意味着**: mapgen 算法不一致——RNG 序列或地形放置逻辑有差异。

### IT-MOVE-001: 合法移动列表一致性

**测试内容**: 同地图 + 同单位位置，Rust 和 Python 返回相同的合法移动列表。
**Python 参照**: `prototype_hex/movement_hex.py` → `get_single_step_moves_hex(unit, grid)`
**验收阈值**: 50 个测试点（10 随机位置 × 5 兵种），合法移动列表顺序可不同但集合必须相同。
**失败意味着**: 移动规则（地形通行、骑兵限制）不一致。

### IT-MOVE-002: 环面距离计算一致性

**测试内容**: 同两点，Rust 和 Python 返回相同的 hex_distance。
**Python 参照**: `prototype_hex/movement_hex.py` → `hex_distance(q1, r1, q2, r2)`
**验收阈值**: 100 个随机点对，距离值完全相同。
**失败意味着**: hex distance 的 wrap 计算不一致——这是所有 AI 移动决策的基础。

### IT-COMBAT-001: 近战结算一致性

**测试内容**: 同兵种对 + 同地形，Rust 和 Python 的 `resolve_melee` 返回相同的伤害和存活状态。
**Python 参照**: `prototype/combat.py` → `resolve_melee(attacker, defender, terrain_att, terrain_def)`
**验收阈值**: 覆盖 (5 攻击方 × 5 防守方 × 5 地形 × 骑兵冲锋/无冲锋) = 250 组合，全部一致。
**失败意味着**: 战斗公式或地形加成不一致。

### IT-COMBAT-002: 远程攻击一致性

**测试内容**: 同上，`resolve_ranged`。
**验收阈值**: 弓手 vs (5 目标兵种 × 5 地形) = 25 组合，全部一致。

### IT-ECON-001: 工人操作一致性

**测试内容**: 同 GameState，Rust 和 Python 的建造/生产/单位生产结果相同。
**验收阈值**: 建造（可建格上建造）、生产（有设施上生产）、单位生产（城市旁生产），各 10 个测试点。

### IT-TECH-001: 科技树一致性

**测试内容**: 同 GameState，可研究列表、研究完成后效果相同。
**验收阈值**: 13 节点 DAG 的拓扑排序一致性 + 科技加成效果一致性。

---

## 三、端到端集成测试

### IT-E2E-001: Random vs Random 逐回合一致性

**测试内容**: 同 seed，Rust 和 Python 的 Random vs Random 游戏在每回合产生完全相同的 GameState。
**Python 参照**: `prototype_hex/eval_hex.py` Random vs Random
**验收阈值**: 10 golden seeds × 80 turns，每回合：
  - 所有单位位置 (x,y) 相同
  - 所有单位 HP 相同
  - 双方城市 HP 相同
  - 双方资源 (food, wood, gold) 相同
  - 双方已完成科技集合相同
**失败意味着**: RNG 序列或游戏逻辑有差异——需要逐模块排查。

### IT-E2E-002: 统计一致性矩阵

**测试内容**: 900 局 3×3 矩阵（Random/Greedy/Evo × 3 对 × 50 seeds paired），Rust 和 Python 的胜率统计不可区分。
**验收阈值**: 每个 matchup 的胜率差异 < 5pp，建设率/征服率/阶梯率差异 < 5pp。
**失败意味着**: AI 行为有系统性差异——通常是移动启发式或决策逻辑不一致。

### IT-E2E-003: GameReplay JSON 兼容性

**测试内容**: Rust 引擎输出的 GameReplay JSON 能被 Python 验证器接受，且能被回放浏览器加载。
**验收阈值**: 10 个 golden seeds 的回放文件全部通过 JSON Schema 验证 + 浏览器加载无报错。

---

## 四、性能测试（非正确性，但必须达标）

### IT-PERF-001: Random vs Random 吞吐量

**验收阈值**: ≥ 50,000 games/s（单核，headless）
**测量方法**: 10,000 局批量运行，wall-clock 计时。

### IT-PERF-002: GameState 深拷贝速度

**验收阈值**: < 1μs（单次 clone）
**测量方法**: 10,000 次 clone 的平均时间。

---

## 五、何时使用

- 每完成一个 Rust 模块 → 运行对应的模块级集成测试
- 所有模块完成 → 运行 E2E-001（逐回合）
- E2E-001 通过 → 运行 E2E-002（统计矩阵）
- E2E-002 通过 → 运行 E2E-003（回放兼容）
- 全部通过 → **Rust 引擎 v1.0 合格**

---

*基于 `docs/planning/2026-07-05-pre-rebuild-audit.md` Tier 2.1*
