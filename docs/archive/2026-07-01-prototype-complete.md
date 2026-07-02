# 2026-07-01 — Python 原型开发完成

## 批次总结

| 批次 | 模块 | 测试 | 状态 |
|---|---|---|---|
| B1 | mapgen + terrain + unit | 54 tests | ✅ |
| B2 | combat + movement | 32 tests (86 total) | ✅ |
| B3 | economy + tech + game + AI | 无新测试(引擎测试通过手动) | ✅ |
| B4 | fow + snapshot + summary | 无新测试 | ✅ |
| B5 | render_ascii + play | 无新测试 | ✅ |
| B6 | eval 50局 | — | ✅ |

## 代码量

| 文件 | 行数 | 说明 |
|---|---|---|
| prototype/constants.py | ~120 | 可调数值集中 |
| prototype/terrain.py | ~75 | 5地形枚举+属性查询 |
| prototype/mapgen.py | ~220 | 6生成器+环面BFS+镜像 |
| prototype/unit.py | ~85 | 5兵种+城市+设施 |
| prototype/combat.py | ~65 | GDD伤害公式 |
| prototype/movement.py | ~115 | 环面移动+骑兵规则 |
| prototype/economy.py | ~110 | 工人三操作+资源+生产 |
| prototype/tech.py | ~105 | DAG研究+科技加成 |
| prototype/game.py | ~180 | 完整游戏循环 |
| prototype/ai_rulesrandom.py | ~180 | 最低合理基线AI |
| prototype/eval.py | ~80 | 批量评估 |
| prototype/fow.py | ~55 | 三态迷雾 |
| prototype/snapshot.py | ~110 | 序列化/反序列化 |
| prototype/summary.py | ~65 | 统计摘要 |
| prototype/render_ascii.py | ~80 | 终端渲染 |
| prototype/play.py | ~80 | Human vs AI |
| **总计** | **~1,725** | |

## 评估结果 (50局 RulesRandom vs RulesRandom)

- P0 winrate: 100% (全部通过阶梯判定P0获胜)
- 平均回合数: 100.0
- 零战斗 (50/50 tiebreak)
- 科技: 平均1.8完成

### 初步结论

1. **游戏引擎功能完整**。所有系统(map/unit/combat/economy/tech/victory)协同工作
2. **RulesRandom AI 太保守**。工人先用资源研究科技→花掉木材金币→无法造伐木场/矿山→经济卡死
3. **100回合+30×30环面**。距离太大，单位在回合上限前难以接触
4. **先手优势需要改进AI后测量**。当前数据被AI行为扭曲

### 改进方向（下次会话）

- AI: 工人优先建伐木场/矿山→再研究科技→再建农场
- AI: 战斗单位从开局就向敌城推进，不等待经济积累
- 距离: 考虑15×15地图做快速验证，或增加单位初始移速
- 评估: 等AI合理后再测先手基线

## 关键设计决策记录

| 决策 | 文件 |
|---|---|
| 战斗公式修正为GDD版本(地形双影响) | combat.py rewrite |
| 工人必须建设施→设施持久→产出来自设施 | ADR-005 |
| v1半径视野(v2升级LOS) | fow.py |
| JSON快照往返一致 | snapshot.py |

## 文件结构

```
prototype/  — 16个Python文件, ~1725行
tests/      — 86项测试, 0失败
docs/gdd/   — 10个子文件+5ADR
```
