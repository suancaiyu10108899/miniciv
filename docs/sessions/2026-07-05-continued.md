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

## 下一步

1. 文档修补收尾（归档旧文件 + INDEX 清理 + CC Memory 更新）
2. Phase 7: Greedy AI 移植（最大工作量，需参数重校准）
3. Phase 8: Evo AI 移植
4. Phase 9: 集成验证矩阵
5. 网络恢复后 push 全部 commit

---
*Session 2026-07-05 续 | 第二个 AI*
