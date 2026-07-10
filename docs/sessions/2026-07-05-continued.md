# Session 2026-07-05 续 — Rust Phase 2-6 + 文档体系优化

> 第二个 AI 接手后的完整 session。从 Rust 工具链安装到游戏可运行。

## 做了什么

### Rust 重构 Phase 2-6（6 个模块，62 测试）
- Phase 2 map.rs: 六边形地图生成，ChaCha12 RNG，7 tests
- Phase 3 movement.rs: hex_distance（9种wrap取最短），10 tests
- Phase 4 unit.rs + combat.rs: 单位创建+近战/远程战斗结算，21 tests
- Phase 5 economy.rs + tech.rs: 三资源经济+13节点DAG科技树，20 tests
- Phase 6 game.rs + ai/random.rs: 完整游戏循环+Random AI，4 tests
- Random vs Random 端到端测试通过

### 文档体系优化
- CLAUDE.md 重构为唯一真相源，嵌入 Phase 进度表+学习笔记列
- Session 日志改为增量追加模式（每 Phase 一段）
- 归档 INFRASTRUCTURE/DATA-MANAGEMENT/EXPERIMENT-FORMAT → ENGINEERING.md
- INDEX.md 精简至 8 份活跃文档

## 决定了什么

### 关键技术决策
- RNG: ChaCha12（不追Python MT19937逐位一致，改统计验证）
- 存储: 一维 Vec<Tile> 行优先（单次分配，cache友好）
- 科技树: static ALL_NODES 编译期数组（零堆分配）
- 战斗双借用: split_at_mut 方案
- 中文注释: 所有 Rust 代码
- Phase Greedy 移植需参数重校准（Python hex 版已确认为 broken）

### 文档体系决策
- "当前状态"只存一处（CLAUDE.md），不分散
- Phase 文档更新缩至 1 分钟（一行表格 + 一段日志）
- 活跃文档从 ~15 砍到 ~8
- 学习笔记: 一句话表格（不建独立文件）

## 实验

- 六边 mini-matrix: 450 games（Tier 1.1）
- 无其他新实验——Python 端六边数据已足够

## 问题

- Phase 5: HashSet<String>::contains Borrow 泛型推导——改用 .iter().any()
- Phase 5: all_tech_nodes() 临时值生命周期——改用 static ALL_NODES
- Phase 4: 战斗测试一个预期值算错（手算失误）
- GitHub push 后半段断网——6 个 commit 在本地，未推送
- 学习笔记零执行——因为格式门槛太高，已降低为一句话表格

### Phase 7-9 完成（追加）

**Phase 7 Greedy AI**：
- 翻译四层架构（战略评估/策略选择/战术执行/经济研究生产），1300 行
- GreedyConfig 参数化权重，600 局扫描：TW=0.15 最优，DW 影响不大
- **核心修复**: hex_distance() 替换了 Python 版的 _td()+_td() 方格曼哈顿距离
- Greedy vs Random: 36% (64→36% after RNG fix: 46.7%)
- Greedy mirror 建设率: 83.3% (Python hex: 0%)

**Phase 8 Evo AI**：
- 15 权重参数化决策，from_json 加载 evo_hex_weights.json
- 复用 GreedyConfig 移动校准参数
- **已知问题**: 权重是 Python MT19937 下进化的，Rust ChaCha12 上失效（10.8% vs Python 67%）

**Phase 9 集成验证**：
- Rust 3×3 矩阵（30 seeds paired × 9 = 270 局）
- Greedy 60.8% vs others（Python hex: 8.5% → 7x 提升）
- Evo 10.8%（需在 Rust 引擎上重训）
- Random 78.3%
- P0 偏差: Greedy mirror 63.3%（偏高，待调查）

### 文档收尾
- CLAUDE.md 进度表更新至 9/9
- Changelog v0.8.0 里程碑
- VERSION.txt → v0.8.0
- Git tag v0.8.0
- HANDOFF.md 新增 Rust 引擎入口
- ENGINEERING.md 更新技术债务
- AI-AUDIT.md 更新 Rust 端数据
- CC Memory 更新至 9/9

## 最终状态

**Rust 引擎 v0.8.0**: 9/9 Phase, 68 tests, 0 errors
**Greedy 60.8%** (7x improvement over Python hex), **Evo 10.8%** (needs retrain)
**3 AI 均可运行**, 2 AI (Random/Greedy) 可用
**已知缺口**: snapshot.rs todo!(), eval.rs todo!(), Evo 需重训, P0 偏差偏高

---
*Session 2026-07-05 续 | 第二个 AI | 完成于 Phase 9 集成验证*
