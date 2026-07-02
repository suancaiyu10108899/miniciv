# Python 原型 — 开发规划

> 目标：快速验证 GDD 规则不矛盾 + 跑出 Random baseline 先手胜率。代码质量到"能跑 + 行为正确"，不求生产级。

---

## 一、文件结构

```
prototype/
├── conftest.py           ← pytest fixtures (共享)
├── mapgen.py             ← 地图生成器 (~150行)
├── terrain.py            ← Terrain 枚举 + 属性表 (~30行)
├── unit.py               ← Unit/City/Facility 数据类 (~80行)
├── combat.py             ← 伤害公式 + 战斗结算 (~80行)
├── movement.py           ← 合法移动 + 环面wrap (~60行)
├── economy.py            ← 工人操作 + 设施 + 生产 (~100行)
├── tech.py               ← DAG + 研究 (~80行)
├── game.py               ← GameState + 回合循环 + 胜利判定 (~150行)
├── fow.py                ← 三态迷雾 + 半径视野 (~60行)
├── ai_rulesrandom.py     ← 最低合理基线AI (~60行)
├── snapshot.py            ← JSON 序列化/反序列化 (~50行)
├── summary.py             ← 单局统计摘要 (~50行)
├── render_ascii.py        ← 终端 ASCII 渲染 (~80行)
├── render_html.py         ← HTML 回放可视化 (~100行)
├── eval.py                ← 批量 AI vs AI 评估脚本 (~60行)
├── play.py                ← Human vs AI 命令行入口 (~60行)
└── replay.py              ← 回放播放器 (~40行)
```

## 二、验收标准（按模块）

### mapgen.py

- [ ] `generate_map(seed, size, generator_id)` → 2D 列表，可索引 `map[y][x]`
- [ ] 6 种生成器全部可成功生成 15/30/50 尺寸
- [ ] 同 seed + 同 generator → 同 map（可复现）
- [ ] 地形比例误差 < 5%
- [ ] BFS 从 P0 城市到 P1 城市可达
- [ ] 城市四正方向 = 平原
- [ ] 环面坐标：`get_terrain(x,y)` 等价于 `get_terrain(x%W, y%H)`

### unit.py + combat.py

- [ ] 5 兵种属性表可查询。`stat_table["infantry"]["atk"]` → 40
- [ ] `resolve_combat(attacker, defender, terrain)` → `(att_hp_lost, def_hp_lost)`
- [ ] 近战双方扣血。远程(弓箭)只扣防守方
- [ ] `max(1, ...)` 保底伤害
- [ ] 地形 DEF 加成正确（平原 0 / 林 +10 / 山 +15 / 城市 +25）
- [ ] 骑兵冲锋 +10 ATK（走 2 格平原后触发）
- [ ] 科技加成可应用（`unit.atk += tech_bonus`）

### movement.py

- [ ] 环面 wrap：`(x+dx) % W, (y+dy) % H`
- [ ] 骑兵：2 格平原 walkable。第 1 格林→停。山地→不能进入
- [ ] 步/弓/工人：1 格，任何地形（含山）。不能进水
- [ ] 侦察兵：2 格，无视地形（可上山，仍不能进水）
- [ ] `get_legal_moves(unit, map)` → 合法方向的 `[(dx,dy), ...]`

### economy.py

- [ ] 工人每回合 1 操作：`MOVE` / `BUILD` / `PRODUCE`
- [ ] BUILD：对当前格建造对应设施（平原→农场，森林→伐木场，山地→矿山）
- [ ] PRODUCE：工人站在己方已完成设施上 → 产出资源
- [ ] 设施持久——`map[y][x].facility = {type: "farm", owner: pid}`
- [ ] 敌方近战站在设施格上 → 可选"摧毁设施"代替攻击
- [ ] 城市基础产出 +1 粮/T
- [ ] 在城市四邻格生产→瞬间+当回合可动
- [ ] 资源足够才能生产

### tech.py

- [ ] 13 节点 DAG 拓扑正确——`get_available_techs(completed)` 返回可研究列表
- [ ] 前置检查："M4 需要 M2 或 M3"——完成 M4 前必须已完成至少一个
- [ ] 研究槽位：同时只能一个。`city.researching = "M1"`
- [ ] 学院(C3)完成后→研究耗时减半
- [ ] C5 纪念碑：花费 + 完成 → 建设胜利触发

### game.py

- [ ] 50 局 Random vs Random 不崩溃
- [ ] 所有局在 ≤100T 内以阶梯判定结束
- [ ] 征服胜利检测正确（近战入城 + 伤害 ≥ 城 HP）
- [ ] 建设胜利检测正确（C5 完成）
- [ ] 阶梯判定顺序正确：建设项目数 → 城市 HP → P0 胜
- [ ] 回合循环：P0 动所有单位 → P1 动所有单位 → 结算经济 → 回合+1
- [ ] 同一 seed 的两局完全一致

### fow.py

- [ ] 三态正确：每个格 UNKNOWN/EXPLORED/VISIBLE
- [ ] 单位移动后视野更新。环面视野计算正确
- [ ] 水域不阻断视野（v1 半径视野下无区别）

### snapshot.py

- [ ] `game.to_dict()` → JSON 可序列化的 dict
- [ ] `game.from_dict(d)` → 重构 GameState
- [ ] 往返：`from_dict(to_dict(g))` == g（除 rng 状态外）
- [ ] 动作序列记录：`[(turn, pid, unit_id, action_type, params), ...]`

### summary.py

- [ ] `summarize_game(snapshot)` → 单局统计 dict
- [ ] 包含：先手胜率、科技路径、首接敌回合、首战斗回合、总战斗次数、双方击杀数、终局资源、胜利方式+回合

## 三、AI vs AI 评估（`eval.py`）

```bash
python prototype/eval.py --games 500 --size 30 --gen balanced --ai rulesrandom --output data/eval_500.json
```

输出：500 局的 summary 汇总。包括：
- P0 winrate / P1 winrate / paired side advantage
- 平均回合数分布
- 胜利路径分布（征服 vs 建设 vs 阶梯判定）
- 平均资源曲线（每 10T 的双方资源均值）

## 四、Human vs AI（`play.py`）

```bash
python prototype/play.py --size 30 --gen balanced --ai-flatmc --human-pid 0
```

ASCII 渲染终端。人类选 P0 或 P1。另一侧 AI 可选 RulesRandom 或其他。

**两个视角验收**：
- 人类 P0 vs AI P1：看先手的"感觉"
- 人类 P1 vs AI P0：看后手是否可打

## 五、回放（`replay.py`）

```bash
python prototype/replay.py data/replays/r_42.json --format html
```

从 seed + 动作序列重放 → HTML。每回合显示棋盘 + 双方资源 + 科技状态。

## 六、批次划分

| 批次 | 模块 | 验收方式 |
|---|---|---|
| **B1** | mapgen + terrain + unit(数据类) | pytest 全绿 + 手动 print 一个 map 看地形分布 |
| **B2** | combat + movement | pytest 全绿 + 手跑 10 局两个 RulesRandom AI 互殴看战斗正确 |
| **B3** | economy + tech + game loop | `eval.py --games 50` 不崩溃 + summary 数据合理 |
| **B4** | fow + snapshot + summary | snapshot 往返测试 + 回放可播放 |
| **B5** | render_ascii + render_html + play | 你在终端打一局 Human vs AI |
| **B6** | eval.py 跑 500 局 + 调数值 | 正式 baseline 数据 |

## 七、开发纪律

- 每批次结束 → commit + push + devlog
- 测试先写（TDD：先写验收标准里的测试，再用实现去 pass）
- 不优化性能（FlatMC 还没上场。Python 原型的瓶颈在算法不是代码）
- 数值全部集中在一个 `prototype/constants.py` 里，不改散落常量
