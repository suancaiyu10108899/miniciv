# Game Design Document — miniciv

> 已拆分为子模块文件夹。此文件保留为入口指针。

## 模块 → 子文件

| 模块 | 文件 | 最后更新 |
|---|---|---|
| 设计原则 + 全局参数 | `gdd/README.md` | 2026-07-01 |
| 棋盘 + 地形 + 地图生成 | `gdd/map.md` | 2026-07-01 |
| 单位 + 战斗 + 移动 | `gdd/units.md` | 2026-07-01 |
| 城市 | `gdd/city.md` | 2026-07-01 |
| 资源 + 采集 + 花费 | `gdd/economy.md` | 2026-07-01 |
| 科技树 | `gdd/tech.md` | 2026-07-01 |
| 胜利条件 + 阶梯判定 | `gdd/victory.md` | 2026-07-01 |
| 迷雾与视野 | `gdd/fow.md` | 2026-07-01 |
| 先手平衡 | `gdd/first-move.md` | 2026-07-01 |

## 设计决策记录

| ADR | 决策 | 文件 |
|---|---|---|
| ADR-001 | 环面拓扑 | `gdd/adr/adr-001-torus.md` |
| ADR-002 | 无单位数量上限 | `gdd/adr/adr-002-no-unit-cap.md` |
| ADR-003 | 固定伤害（非随机） | `gdd/adr/adr-003-fixed-damage.md` |
| ADR-004 | 不做经验/升级 | `gdd/adr/adr-004-no-xp.md` |

## 开发规划

→ `docs/devplan.md`
