# miniciv

AI-first 六边形回合制策略游戏平台。**北极星:一个 AI 能真正玩出策略深度的游戏。**

> 当前状态(2026-07-10, 第三个 AI): **一阶深度"温和成立"**。
> 从"5 回合建设速通支配"调到"建设↔军事有制衡、40-80T 决出、无单一支配"。
> 深度真实但温和(简单策略就接近最优),下一步深化内容。
> 完整现状 → `CLAUDE.md` 顶部 | 深度体检 → `experiments/v0.8.2-balance-scan/DEPTH-REPORT.md`

---

## 快速开始

```bash
cd miniciv-core
cargo test              # 79 tests, 0 error
cargo build --release   # 构建所有工具
```

## 怎么看回放(两种方式)

**方式 1 — 浏览器可视化(推荐,能看棋盘)**
```bash
cd /d/Dev/miniciv
explorer.exe replay_viewer.html      # 打开查看器(或文件管理器双击它)
```
页面里点"选择文件",加载 `replays/` 下任意 `.json`。六边棋盘 + 逐回合滑块/播放。
已备 4 个甜点带对局:`adaptive-vs-rusher`(征服46T)、`defender-vs-cav`(建设11T)等。

**方式 2 — 终端文本回放(最快,逐回合摘要)**
```bash
cd /d/Dev/miniciv/miniciv-core
cargo run --release --bin replay -- Adaptive Rusher 50000 "" 25 3.0 160
#                                     ↑P0     ↑P1    ↑seed ↑不存 ↑资源 ↑成本× ↑城HP
```
末三个 `25 3.0 160` = 甜点带配置(起手资源/C线成本倍率/城市HP)。
可选 AI:Builder/Rusher/CavRusher/Harasser/Turtle/Defender/Adaptive/Search/Greedy/Evo/Random。

生成新回放供查看器看(第4参数给文件名):
```bash
cargo run --release --bin replay -- Defender Rusher 50300 ../replays/my.json 25 3.0 160
```

## 分析工具(全在 `miniciv-core`, `cargo run --release --bin <名>`)

| 工具 | 用法示例 | 作用 |
|------|------|------|
| `eval` | `eval 500 balanced out.json 25 3.0 160` | N×N paired 矩阵:支配性/胜利类型/先手/谁靠什么赢 |
| `scan` | `scan 200` | 参数扫描(找平衡杠杆) |
| `table` | `table 150` | 成本×城防 × 多攻防AI 打表 |
| `content` | `content 60 17` | per兵种战斗数据(伤害/存活) |
| `depth` | `depth 12` | 深度体检:决策分叉 + 应变实证 |
| `m3` | `m3 30` | 策略级搜索AI vs 探针 |
| `replay` | 见上 | 逐回合看一局 |

参数含义:`eval [seeds] [generator] [out] [起手资源] [C线成本×] [城市HP]`。甜点带 = `... 25 3.0 160`。

## 文档导航

| 找什么 | 去哪 |
|--------|------|
| 当前状态(唯一真相源) | `CLAUDE.md` 顶部 |
| 一阶深度目标+验收标准 | `docs/planning/2026-07-10-stage1-goal-acceptance.md` |
| 方法论(验证金字塔) | `docs/planning/2026-07-10-validation-pyramid.md` |
| M1-M2 阶段归档 | `docs/planning/2026-07-10-M1M2-archive.md` |
| 深度体检报告 | `experiments/v0.8.2-balance-scan/DEPTH-REPORT.md` |
| 平衡扫描全过程+数据 | `experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md` |
| 5T速通裁决 | `experiments/v0.8.1-honest-eval/VERDICT.md` |
| 设计决策 | `docs/DECISIONS.md`(#18=甜点带) |
| 游戏参数 | `docs/GAME.md` |

## 给下一个对话/AI 的交接

1. 读 `CLAUDE.md` 顶部(10 分钟了解现状) + `DEPTH-REPORT.md`(深度判断)。
2. 当前是干净交接点:所有工作已推送 `nightly-ai`,79 tests 绿。
3. **下一阶段 = 深化游戏内容**(增加决策维度):建议顺序 科技强互斥 → 迷雾FOW → 多城/开拓。
4. **纪律:每个深化用 `depth`/`table` 体检验证,确认真加了深度(黄灯转绿),不是加噪声。**
5. 待查:Rusher 镜像 P0 33% 偏低;CavRusher 弱(骑兵寻路残留)。
6. 核心教训:参数设环境、平滑靠 AI 决策;探针数据方向可信精度不可信;小样本别下结论;
   真相活在可执行工件(eval/depth)里,不活在对话上下文。

## 前身

继承自 [MiniCiv AI Lab](https://github.com/suancaiyu10108899/MiniCiv-AI-Lab)(已封存)。
