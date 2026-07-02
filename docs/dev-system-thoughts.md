# 开发体系思考 — 从原型到Rust内核的过渡规划

## 一、当前原型验证了什么

通过8,100+16,000+45,000=69,100局评估, 原型阶段已确认:

1. **回合制战斗公式可行**: damage=max(1, ATK+att_terrain-DEF-def_terrain)
2. **经济-科技-军事三角存在**: 三者互相竞争资源, 产生有意义的策略选择
3. **先手可平衡**: 交替先手机制使P0≈50%(±2%)
4. **AI层次可测量**: random << aggressive < greedy ≈ flatmc
5. **建设胜利可行**: C线半价后建设率52-65%
6. **地图15×15是甜点**: 20×20可用, 30×30破碎

## 二、原型阶段的工具链成熟度

| 工具 | 状态 | 说明 |
|------|------|------|
| eval.py | ✅ | 单组评估, 输出JSON |
| eval_matrix.py | ✅ | 并行全矩阵, 177局/秒 |
| bench.py | ✅ | 速度基准 |
| verify_agents.py | ✅ | Agent快速验证 |
| HTML回放 | ✅ | 科技树面板嵌入 |
| 测试 | ✅ | 86项, <0.2秒 |
| 参数网格扫描 | ✅ | Flash agent自动扫9组合 |

## 三、Rust内核架构规划

### 模块树
```
miniciv-core/
  src/
    lib.rs           — re-exports, GameEngine struct
    game.rs          — GameState, init(), step()
    map.rs           — MapGen, Grid, Terrain, Toroidal topology
    unit.rs          — Unit, UnitType, stats, UnitPool
    combat.rs        — CombatResolver, damage formula
    economy.rs       — Economy, ResourceManager
    tech.rs          — TechTree, TechManager, research
    fow.rs           — FogOfWar (optional)
    snapshot.rs      — serde Serialize/Deserialize
    constants.rs     — Tuning parameters (hot-reloadable?)
    eval.rs          — Batch evaluation
    replay.rs        — ActionLog → ReplayBuilder

miniciv-ai/
  src/
    lib.rs
    agent.rs         — Agent trait
    random.rs        — RandomAgent
    greedy.rs        — GreedyAgent
    aggressive.rs    — AggressiveAgent
    flatmc.rs        — FlatMCAgent
    evo.rs           — EvolutionAgent (weight vector)
    mcts.rs          — MCTS (future)

miniciv-py/
  src/
    lib.rs           — PyO3 bindings
    python types     — GameState → Python dict

miniciv-server/
  src/
    main.rs          — WebSocket game server
```

### 关键设计决策

1. **ECS vs OOP**: 原型用OOP(GameState dataclass), Rust建议SOA(Struct of Arrays)
   — UnitPool: Vec<UnitType>, Vec<HP>, Vec<Position> 同索引
   — 缓存友好, 批量更新快

2. **Action抽象**: 
   ```rust
   enum Action {
       Move { unit_idx: usize, dx: i8, dy: i8 },
       Build { unit_idx: usize },
       Produce { unit_idx: usize },
       ProduceUnit { unit_type: UnitType },
       Research { tech_id: TechId },
       EndTurn,
   }
   ```

3. **Agent trait**:
   ```rust
   trait Agent {
       fn decide(&self, state: &GameState, player: PlayerId, rng: &mut Rng) -> Vec<Action>;
   }
   ```

4. **Snapshot/回放**:
   — ActionLog: Vec<TurnActions> (只存动作, 不存完整状态)
   — 回放: 从seed+action_log重建任意帧
   — 压缩率: ~100x (动作列表 vs 全状态快照)

5. **性能目标**:
   — Random vs Random: 500k 局/秒 (单核)
   — 深拷贝: <1μs (copy-on-write或差分)
   — 内存: <1KB/GameState

## 四、AI训练体系规划

### 三层AI架构

```
Layer 1: 手写启发式 (当前)
  - Greedy: 贪心最优, 战术意识
  - Aggressive: 暴兵推进, 绕路, 波浪
  - Random: 基准线
  
Layer 2: 进化权重 (evo AI)
  - ~15参数, 进化算法调优
  - 训练快(<1分钟), 可解释
  - 上限: 略优于手写AI
  
Layer 3: 深度RL (未来)
  - 状态编码→NN→动作概率
  - 训练慢(小时-天), 上限高
  - DQN/PPO/AlphaZero风格
```

### 训练基础设施

```
eval_matrix.py → Rust miniciv-eval (二进制)
  - 多线程并行
  - 增量结果保存
  - 支持自定义Agent (Python插件→WASM→trait impl)

训练循环:
  while training:
      population.play_games(opponents)  # 并行评估
      population.select_elite()         # 选优
      population.breed()                # 交叉变异
      population.save_checkpoint()      # 容灾
```

## 五、从原型到Rust的迁移策略

### 不是一次性重写, 是逐步替换

```
Phase 1: Rust核心 + Python绑定 (2-3周)
  - 实现 game.rs + map.rs + unit.rs + combat.rs + economy.rs + tech.rs
  - PyO3绑定 → Python可以直接调用Rust引擎
  - 验证: Rust引擎输出与Python原型一致 (100局对比)

Phase 2: AI迁移 (1-2周)
  - Rust trait Agent → 实现所有手写AI
  - Python可以通过PyO3注册自定义Agent
  - eval_matrix在Rust中重写(性能100x+)

Phase 3: RL训练 (2-4周)
  - Rust引擎作为gym环境
  - Python训练脚本(Ray/RLlib)调用Rust引擎
  - 训练速度瓶颈从Python GIL转移到Rust引擎

Phase 4: 清理 (1周)
  - 删除Python原型中已被Rust替代的模块
  - 保留Python用于数据分析/可视化/训练脚本
```

### 为什么不全用Rust

1. Python的ML生态(RLlib, SB3, numpy)无可替代
2. 原型快速迭代是Python的优势
3. PyO3桥接: Rust做引擎(CPU密集), Python做训练(GPU密集)
4. 类似AlphaZero: C++引擎+Python训练

## 六、开发流程标准化建议

### Git规范
- 分支: main(稳定) / nightly-ai(日常) / feat-xxx(特性)
- Commit: `[模块]: 改动\n\n数据: 前后对比\n\nCo-Authored-By: Claude`
- 每个commit包含相关测试数据

### 评估规范
- 参数改动先跑200局快速矩阵
- 确认方向后跑1000局精确矩阵
- 大改动前存baseline JSON
- 用 eval_matrix.py 的 --output 自动命名

### Agent分工规范
- 明确任务: "改X, 跑pytest, 跑200局, 回报胜率"
- 并行任务: 不修改同一文件
- 产出格式: 表格+结论(而非代码dump)
