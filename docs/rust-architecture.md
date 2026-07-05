# Rust 引擎架构设计 v1.0

> 2026-07-05 | 从 42 行草稿扩展。六边形轴向坐标 (q,r)，矩形环面 15×15。
> **本文档是 Rust 重构的唯一施工蓝图。** 所有实现决策追溯至此。

---

## 一、Crate 结构

```
miniciv/                          # repo root
  miniciv-core/                   # 核心引擎 crate（本次重构范围）
    Cargo.toml
    src/
      lib.rs                      # re-exports
      constants.rs                # 游戏参数（翻译 constants.py）
      map.rs                      # 六边形地图生成 + 地形
      unit.rs                     # Unit, City, Facility 数据结构
      combat.rs                   # 战斗结算
      economy.rs                  # 经济系统（资源、工人操作）
      tech.rs                     # 科技树 DAG
      movement.rs                 # 六边移动 + 环面距离
      game.rs                     # GameState + init + step
      snapshot.rs                 # JSON 序列化（GameReplay 格式）
      eval.rs                     # 批量评估
      ai/
        mod.rs
        random.rs                 # Random baseline
        greedy.rs                 # Greedy v6（移植 + 六边几何修正）
        evo.rs                    # Evo（15 权重参数化）
      py_bindings.rs              # PyO3 接口（可选 feature gate）

  miniciv-py/                     # Python 包（后续）
  miniciv-render/                 # 渲染（后续）
  miniciv-server/                 # WebSocket（后续）
```

**依赖（Cargo.toml）**：
- `rand` + `rand_chacha` — 确定性 RNG（ChaCha12，seedable）
- `serde` + `serde_json` — 序列化
- `pyo3` — Python bindings（optional feature）
- 无其他重依赖。核心引擎保持最小依赖树。

---

## 二、GameState 设计

### 2.1 数据结构

```rust
/// 完整游戏状态。所有字段公开以支持快速访问。
/// Copy-on-Write 通过 Arc 实现（见 §2.2）。
pub struct GameState {
    pub seed: u64,
    pub size: u8,                    // 15（编译期常量，但存运行时以支持未来扩展）
    pub generator_id: String,        // "balanced" | "symmetric" | ...
    pub turn: u16,                   // 0..80
    pub grid: Grid,                  // 地图（不可变，初始化后不改）
    pub units: Vec<Unit>,            // 存活单位
    pub dead_units: Vec<Unit>,       // 已死单位（统计用）
    pub cities: [City; 2],           // P0 和 P1 城市
    pub economies: [Economy; 2],
    pub techs: [TechManager; 2],
    pub winner: Option<u8>,          // None = 进行中
    pub victory_type: Option<VictoryType>,
    pub rng: GameRng,                // 确定性 RNG
    pub action_log: Vec<TurnActions>,
    pub turn_snapshots: Vec<TurnSnapshot>,  // GameReplay 格式
}

pub struct Grid {
    pub width: u8,
    pub height: u8,
    /// grid[r][q] — 六边形轴向坐标的行优先存储
    pub tiles: Box<[Tile]>,
}

pub struct Tile {
    pub terrain: Terrain,
    pub facility: Option<Facility>,
}
```

### 2.2 Copy-on-Write 方案

**选择 `Arc<GameStateInner>` + `make_mut` 模式（类似 Rust 的 `Cow`）**：

```rust
pub struct GameState {
    inner: Arc<GameStateInner>,
}

impl GameState {
    /// 浅克隆：O(1)，共享内部状态
    pub fn clone_shallow(&self) -> Self {
        Self { inner: Arc::clone(&self.inner) }
    }

    /// 深克隆：用于搜索型 AI（FlatMC/MCTS）
    pub fn clone_deep(&self) -> Self {
        Self { inner: Arc::new((*self.inner).clone()) }
    }
}
```

对于 FlatMC：每个搜索节点调用 `clone_shallow()`（O(1)），写时自动触发 `make_mut`（O(n) 仅在首次写入时）。

**性能目标**：浅克隆 < 100ns，深克隆 < 1μs，全状态 < 10KB。

### 2.3 确定性 RNG

**方案**：使用 `rand_chacha::ChaCha12Rng` + `SeedableRng`。

**跨语言一致性**：
- Python 端：`random.Random(seed)` 使用 Mersenne Twister (MT19937)
- Rust 端：ChaCha12 算法与 Python MT19937 不同！**同 seed 不会产生相同序列。**
- **解决方案**：在 `mapgen` 中实现 Rust 版 MT19937（用 `mersenne_twister` crate 或手写），或接受 RNG 算法差异并改为"统计一致性"验证（不要求逐位一致）。

**推荐方案**：Rust 端用 `rand::rngs::StdRng`（当前是 ChaCha12），不追求 Python MT19937 逐位一致。改为在模块级验证"同 seed 同算法"一致性。跨语言验证改为"统计不可区分"而非"逐回合逐位相同"。

**具体做法**：
1. 所有 RNG 调用集中在 `GameRng` 包装器中
2. `GameRng` 提供 `gen_range`, `gen_bool`, `shuffle` 等方法
3. 每个需要 RNG 的模块（mapgen, combat, AI）从 `GameRng` 获取确定性的随机数

---

## 三、模块详细设计

### 3.1 constants.rs

```rust
// 直接翻译 prototype/constants.py
pub const MAP_W: u8 = 15;
pub const MAP_H: u8 = 15;
pub const MAX_TURNS: u16 = 80;
pub const CITY_HP: i32 = 80;
pub const CITY_DEF: i32 = 5;
pub const CITY_DAMAGE: i32 = 5;
pub const CITY_BASE_FOOD: i32 = 1;
pub const CAVALRY_CHARGE_BONUS: i32 = 10;
pub const CONSTRUCTION_VICTORY_REQUIRE_FACILITIES: u8 = 4;
// ... (全部参数)
```

### 3.2 map.rs — 六边形地图生成

**入口**：`generate_map(seed: u64, generator_id: &str) -> Grid`

**算法**：翻译 `prototype_hex/mapgen_hex.py`。
1. 全平原初始化
2. 城市位置：P0 随机，P1 对角（环面对径）
3. 3×3 城市布局（6 邻 = 平原，对角 = 山/林交替）
4. 聚类地形放置（BFS 扩散）
5. 连通性验证（BFS 从 P0 城到 P1 城，只走可行地形）

**验证**：10 golden seeds 与 Python 输出逐格比对。

### 3.3 movement.rs — 六边移动

```rust
/// 六边形方向（轴向坐标）
pub const HEX_DIRS: [(i32, i32); 6] = [
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1),
];

/// 环面 wrap
pub fn wrap(q: i32, r: i32) -> (i32, i32) { ... }

/// 环面六边形距离（9 种 wrap 变体取最短）
pub fn hex_distance(q1: i32, r1: i32, q2: i32, r2: i32) -> u8 { ... }

/// 单步合法移动
pub fn legal_moves(unit: &Unit, grid: &Grid) -> Vec<(i32, i32)> { ... }
```

### 3.4 unit.rs — 单位/城市/设施

```rust
pub struct Unit {
    pub unit_type: UnitType,
    pub player_id: u8,
    pub q: i32,  // axial q (stored as x in Python)
    pub r: i32,  // axial r (stored as y in Python)
    pub hp: i32,
    pub atk: i32,
    pub def: i32,
    pub move_speed: u8,
    pub vision: u8,
    pub can_enter_mountain: bool,
    pub ranged: bool,
    pub range_dist: u8,
    pub alive: bool,
    pub damage_dealt: i32,
    pub damage_taken: i32,
}

pub enum UnitType { Infantry, Cavalry, Archer, Scout, Worker }

pub struct City { pub player_id: u8, pub q: i32, pub r: i32, pub hp: i32 }
pub struct Facility { pub facility_type: FacilityType, pub player_id: u8, pub q: i32, pub r: i32 }
pub enum FacilityType { Farm, Lumbermill, Mine }
```

### 3.5 combat.rs — 战斗结算

```rust
pub struct MeleeResult {
    pub att_damage: i32,
    pub def_damage: i32,
    pub attacker_alive: bool,
    pub defender_alive: bool,
}

pub fn resolve_melee(
    attacker: &mut Unit, defender: &mut Unit,
    terrain_att: Terrain, terrain_def: Terrain,
    attacker_just_charged: bool,
) -> MeleeResult { ... }

pub fn resolve_ranged(archer: &mut Unit, target: &mut Unit, terrain_target: Terrain) -> RangedResult { ... }
```

**公式**：与 Python 完全相同：`damage = max(1, ATK + att_DEF_bonus - DEF - def_DEF_bonus)`

### 3.6 economy.rs — 经济系统

翻译 `prototype/economy.py`。`Economy` 结构体 + `worker_action_build/produce` + `produce_unit` + `city_base_income`。

### 3.7 tech.rs — 科技树

13 节点 DAG，与 Python `tech.py` 相同逻辑。`TechManager` 结构体管理研究状态。

### 3.8 game.rs — 游戏循环

```rust
pub fn init_game(seed: u64, generator_id: &str) -> GameState { ... }
pub fn step_game(gs: &mut GameState, actions_p0: &[Action], actions_p1: &[Action]) -> StepResult { ... }
```

**交替先手**：奇数回合 P0 先，偶数回合 P1 先。科技 tick 双方同时。

**胜利判定**（每回合）：
1. 建设：C5 完成 + 设施 ≥ 4 → winner
2. 征服：敌城 HP ≤ 0 → winner
3. 回合上限：construction_count → city_hp → random

---

## 四、Action 和 Agent trait

### 4.1 Action 枚举

```rust
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Action {
    Move { unit_idx: usize, dq: i32, dr: i32 },
    Build { unit_idx: usize },
    Produce { unit_idx: usize },
    ProduceUnit { unit_type: UnitType },
    Research { tech_id: String },
    Destroy { unit_idx: usize },
    EndTurn,
}
```

### 4.2 Agent trait

```rust
pub trait Agent: Send + Sync {
    /// 给定游戏状态和玩家 ID，返回动作列表。
    /// rng 用于随机决策（epsilon-greedy、随机移动等），
    /// 不用于 GameState 修改（那由 step_game 控制）。
    fn decide(&self, state: &GameState, player: u8, rng: &mut dyn RngCore) -> Vec<Action>;

    /// Agent 名称（用于日志和回放）
    fn name(&self) -> &str;
}
```

**设计要点**：
- `&GameState` 不可变引用——Agent 不应修改状态
- `&mut dyn RngCore` ——允许 Agent 使用随机性但不控制引擎 RNG
- `Send + Sync` ——允许并行批量评估（多线程各跑一局）

### 4.3 Python FFI（后续）

```rust
// miniciv-py/src/lib.rs
use pyo3::prelude::*;

#[pyfunction]
fn init_game_py(seed: u64, generator_id: &str) -> PyResult<String> {
    let gs = miniciv_core::game::init_game(seed, generator_id);
    Ok(serde_json::to_string(&gs)?)
}

#[pyfunction]
fn step_game_py(state_json: &str, actions_p0_json: &str, actions_p1_json: &str) -> PyResult<String> {
    let mut gs: GameState = serde_json::from_str(state_json)?;
    let a0: Vec<Action> = serde_json::from_str(actions_p0_json)?;
    let a1: Vec<Action> = serde_json::from_str(actions_p1_json)?;
    miniciv_core::game::step_game(&mut gs, &a0, &a1);
    Ok(serde_json::to_string(&gs)?)
}
```

---

## 五、实现顺序与验证门禁

### Phase 1: 骨架 + 常量
- [ ] `cargo init miniciv-core --lib`
- [ ] `Cargo.toml` 依赖配置
- [ ] `constants.rs` 完整翻译
- [ ] `lib.rs` 模块声明
- **门禁**: `cargo build` 通过

### Phase 2: 地图生成
- [ ] `map.rs`：Grid, Tile, Terrain, generate_map()
- [ ] `snapshot.rs`：grid_to_json() 用于验证输出
- **门禁**: 10/10 golden seeds 与 Python mapgen 输出一致

### Phase 3: 移动 + 距离
- [ ] `movement.rs`：hex_distance, wrap, legal_moves
- **门禁**: 100 随机点对距离一致；50 测试点合法移动集合一致

### Phase 4: 单位 + 战斗
- [ ] `unit.rs`：Unit, City, Facility, UnitType
- [ ] `combat.rs`：resolve_melee, resolve_ranged
- **门禁**: 250 近战组合 + 25 远程组合全部一致

### Phase 5: 经济 + 科技
- [ ] `economy.rs`
- [ ] `tech.rs`
- **门禁**: 建造/生产/研究 各 10 测试点

### Phase 6: 游戏循环
- [ ] `game.rs`：init_game, step_game, victory checks
- [ ] `ai/random.rs`：Random baseline AI
- **门禁**: IT-E2E-001 — 10 seeds × 80 turns 逐回合与 Python 一致

### Phase 7: Greedy AI 移植（**重点**）
- [ ] `ai/greedy.rs`：战略评估 + 部队协调 + 对手建模 + 自适应生产
- **注意**：六边形几何修正——移动启发式中的距离权重需调整（当前 Python hex Greedy 已确认为 broken，Rust 移植时需重新调优阈值）
- **门禁**: Greedy vs Random 胜率 ≥ 50%（六边上的合理目标）

### Phase 8: Evo AI 移植
- [ ] `ai/evo.rs`：15 权重参数化 + JSON 权重加载
- **门禁**: Evo vs Random 胜率 ≥ 60%

### Phase 9: 集成验证
- [ ] `eval.rs`：批量评估（与 Python eval_hex.py 相同功能）
- [ ] Rust 引擎 900 局 3×3 矩阵 vs Python 六边矩阵
- **门禁**: IT-E2E-002 — 统计不可区分

---

## 六、关键设计决策

### D1: 不追求 Python MT19937 逐位一致
**选择**：Rust 用 ChaCha12 RNG。跨语言验证改为"统计一致性"。
**理由**：MT19937 的 Rust 实现维护成本高；ChaCha12 更快且质量更好；统计一致性对游戏行为验证已足够。

### D2: Arc 浅克隆而非手动 arena
**选择**：`Arc<GameStateInner>` + Copy-on-Write。
**理由**：FlatMC 搜索（depth ≤ 20）的 clone 次数有限（< 1000/局）；Arc 实现简单、正确性有编译期保证；arena 方案性能更好但实现复杂，v1 不值得。

### D3: 不引入 Bevy ECS
**选择**：简单 `Vec<Unit>` + 手动遍历。
**理由**：最多 ~50 单位同时存活，线性遍历足够（50 × 80 turns = 4000 次迭代/局，远未到性能瓶颈）；Bevy ECS 引入大量依赖和学习成本，与"最小依赖"原则冲突。

### D4: Agent 使用 trait object 而非泛型
**选择**：`Box<dyn Agent>` 用于批量评估。
**理由**：批量评估需要混合不同 Agent 类型（同一次 eval 跑 Random vs Greedy vs Evo）；trait object 的虚函数开销在每局级别的粒度上可忽略。

### D5: 六边形 Greedy 需要重新调优，不是机械翻译
**选择**：Rust Greedy 移植时重新校准移动启发式中的距离权重和策略阈值。
**理由**：Python hex Greedy 已通过实验确认为 broken（机械翻译自方格版导致距离梯度问题）。Rust 移植是重新设计这些阈值的自然时机。
**方法**：在 Rust 引擎上用参数扫描（distance_weight: 1.0/2.0/3.0/5.0，terrain_weight: 0.05/0.10/0.15）找到最优组合。

---

## 七、性能预算

| 操作 | 目标 | 测量方法 |
|------|------|---------|
| init_game | < 100μs | 1000 次平均 |
| step_game (空动作) | < 10μs | 1000 次平均 |
| step_game (Greedy vs Greedy) | < 500μs | 1000 局平均 |
| GameState 浅克隆 | < 100ns | 10000 次平均 |
| GameState 深克隆 | < 1μs | 10000 次平均 |
| Random vs Random 吞吐 | ≥ 50,000 games/s | 单核 headless，10000 局计时 |
| 单局内存 | < 10KB | GameState 深克隆后的堆大小 |

---

*替代：docs/rust-architecture.md（42 行草稿，内容已合并）*
