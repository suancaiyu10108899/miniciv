# Replay Viewer v1 — 子 Agent 执行规格

> 2026-07-03 | 本文档给子 Agent (Flash) 直接执行。禁止模糊表述——所有要求有具体数值和示例。

---

## 一、交付物

一个自包含的 HTML 文件：`prototype/replay_viewer.html`

**技术约束**：
- 纯静态 HTML + 内联 CSS + 内联 JavaScript
- 零外部依赖（不加载 CDN、不 import npm 包、不需要服务器）
- 在 Chrome/Edge 最新版中正常工作
- 所有数据嵌入在 `<script>` 标签中（或通过文件拖放加载）
- 单文件，可直接在浏览器中打开

---

## 二、数据输入

### 方式 A（主要）：嵌入在 HTML 中

HTML 文件末尾的 `<script id="replay-data" type="application/json">` 标签中包含完整的 GameReplay JSON。子 Agent 的测试用样例数据见 `experiments/v0.5.0/facility-8-verify/sample_replay.json`。

### 方式 B（可选）：拖放加载

支持拖放一个 `.json` 文件到浏览器窗口来加载回放。如果实现方式 A 遇到了技术困难，可以只做方式 A。

### GameReplay JSON 结构

```json
{
  "format_version": "1.0",
  "config": { "size": 15, "gen": "balanced", "max_turns": 100, "seed": 42 },
  "turns": [
    {
      "turn": 1,
      "units": [
        {"type": "worker", "pid": 0, "x": 7, "y": 8, "hp": 10, "atk": 0, "def": 0}
      ],
      "cities": [{"pid": 0, "hp": 100, "x": 7, "y": 7}, {"pid": 1, "hp": 100, "x": 7, "y": 0}],
      "economies": [{"pid": 0, "food": 22, "wood": 25, "gold": 25}, {"pid": 1, "food": 22, "wood": 25, "gold": 25}],
      "techs": [{"pid": 0, "completed": [], "researching": null, "research_ticks": 0}],
      "facility_count": {"0": 0, "1": 0},
      "events": [{"type": "move", "pid": 0, "x": 8, "y": 8, "detail": "moved"}]
    }
  ],
  "result": {"winner": 0, "victory_type": "conquest", "final_turn": 45}
}
```

注意：`turns` 数组的索引 = 回合编号 - 1（`turns[0]` = 第 1 回合）。

---

## 三、视觉布局

### 整体布局

```
+--------------------------------------------------------------+
|  [<] [>] [auto: 1x 2x 5x]  Turn: 12/100   Winner: P0 (conquest) |
+------------------------------------------+-------------------+
|                                          |  P0 (Blue)        |
|                                          |  Food: 25         |
|          MAP VIEW (15x15 grid)           |  Wood: 25         |
|                                          |  Gold: 25         |
|                                          |  Techs: 3         |
|                                          |  Facilities: 4    |
|                                          |  Units alive: 8   |
|                                          |                   |
|                                          |  P1 (Red)         |
|                                          |  Food: 22         |
|                                          |  ...              |
+------------------------------------------+-------------------+
```

- **顶部**：控制栏（按钮 + 当前回合信息）
- **左侧**：地图主视图（占 70-75% 宽度）
- **右侧**：固定信息面板（占 25-30% 宽度）

### 控制栏

- `← Prev` 按钮 + `Next →` 按钮
- 自动播放模式切换按钮：`1x` / `2x` / `5x`（分别对应 500ms / 250ms / 100ms 间隔）
- 当前回合显示：`Turn: 12 / 100`
- 如果游戏已结束：显示 `Winner: P0 (conquest)`

快捷键：
- 左箭头：上一回合
- 右箭头：下一回合
- 空格键：切换自动播放

### 地图主视图

**格子尺寸**：每个格子 32×32 px（15×15 = 480×480 px 地图区域）

**地形颜色**（背景色）：
- 平原 (PLAIN)：`#c8e6c9`（浅绿）
- 森林 (FOREST)：`#388e3c`（深绿）
- 山地 (MOUNTAIN)：`#9e9e9e`（灰）
- 水域 (WATER)：`#64b5f6`（浅蓝）
- 城市 (CITY)：`#8d6e63`（棕）

**如何读取地形信息**：GameReplay JSON 的 `config.size` 给了地图尺寸，但 **turns 数组里没有 grid/terrain 数据**。因此 HTML 需要单独加载地形信息。

解决方案：在 `<script id="terrain-data" type="application/json">` 中嵌入一个简单的 grid 数组。格式：

```json
[[0,0,0,1,1,...], [0,0,2,1,...], ...]
```

其中 0=PLAIN, 1=FOREST, 2=MOUNTAIN, 3=WATER, 4=CITY。这个数组在生成回放时一起生成。

（如果子 Agent 发现没有 terrain-data，用纯色背景作为 fallback，并标注"terrain data not available"）

**单位渲染**：每个格子上如果存在单位，在地形背景上叠加单位信息：
- 单位缩写：I=步兵, C=骑兵, A=弓手, S=侦察兵, W=工人
- P0 的单位用蓝色边框 + 蓝色文字 (`#1565c0`)
- P1 的单位用红色边框 + 红色文字 (`#c62828`)
- 单位盒子尺寸：28×28 px，在格子内居中

**设施渲染**：如果格子上有设施（从 `facility_count` 或 events 推断），在格子角落显示小符号：
- 农场：F（绿色，字体 10px，在格子右下角）

注：GameReplay 目前不存储每个格的设施位置，只存储总数。设施渲染在 v1 中可以省略——只显示设施总数在侧边栏。

**关键事件高亮**：当前回合有 events 时，涉及到的格子在渲染时加一个闪烁/高亮边框（黄色 `#ffeb3b` 持续 0.5s）。

### 信息面板

固定宽度 250px，不随地图滚动。

**P0 信息**（蓝色标题 `#1565c0`）：
- Resources: Food / Wood / Gold（显示当前值）
- Techs completed: N（科技完成数）
- Researching: X（当前研究中的科技，或 "none"）
- Facilities: N（设施总数）
- Units alive: N
- Construction count: N（C1-C5 科技完成数）

**P1 信息**（红色标题 `#c62828`）：
- 同上

**分隔线**：P0 和 P1 之间用水平线分隔。

### 回合事件列表（面板底部）

如果当前回合有 events，在面板底部显示：
```
Turn 12 events:
  P0: built facility
  P1: moved scout to (8,3)
```

---

## 四、游戏数据参考面板（信息自足原则）

这部分是 v1 和"简陋回放"的关键区别。一个不了解 miniciv 的人，打开回放浏览器，应该能在不翻文档的情况下理解他看到的一切。

### 4.1 底部参考栏（固定）

地图主视图下方，一个固定高度 80px 的参考栏，分三个区域：

**左区：兵种速查**
```
  I 步兵   HP100 ATK45 DEF30 移1 视2  5粮          可上山
  C 骑兵   HP80  ATK60 DEF15 移2 视2  5粮+3金      禁山 遇林停 冲锋+10
  A 弓手   HP60  ATK50 DEF10 移1 视2  3粮+3木      射程2 不还手 不能占城
  S 侦察兵 HP40  ATK15 DEF5  移2 视3  3粮          可上山 无视地形
  W 工人   HP10  ATK0  DEF0  移1 视2  3粮          建+采+产
```

字体 10px，紧凑排列，不滚动。P0/P1 颜色标注（和地图一致）。

**中区：地形速查**
```
  平原 DEF0  可建农场    全员通行
  森林 DEF10 可建伐木场  骑兵遇林停  阻断弹道
  山地 DEF15 可建矿山    骑兵禁入    阻断弹道
  水域 DEF0  不可建      全员禁行    穿透弹道
  城市 DEF25 不可建      己=通行 敌=攻击
```

**右区：科技树缩略**
```
  M线(军事): M1→M2/M3→M4     E线(经济): E1→E2/E3→E4     C线(建设): C1→C2/C3→C4→C5(胜利)
```

字体 9px。M1=锻造(步弓ATK+5), M2=骑兵(冲锋+5), M3=筑垒(林山DEF+10), M4=精兵(全军HP+10), E1=耕作(农场+1), E2=伐木(伐木场+1), E3=采矿(矿山+1), E4=物流(工人移速+1), C1=奠基(开启建设), C2=城墙(城市+30HP), C3=学院(研究/2), C4=粮仓(城市+2粮), C5=纪念碑(建设胜利,需8设施)

### 4.2 悬停提示（tooltip）

**悬停地图格子**：
- 显示：地形名称、DEF 加成、可建设施、通行限制
- 格式：`森林 | DEF+10 | 可建伐木场 | 骑兵遇林停 | 阻断弹道`
- 尺寸：小字号，不遮挡相邻格子

**悬停单位**：
- 显示：单位类型、HP、ATK、DEF、所属玩家、当前科技加成（如果有）
- 格式：`P0 步兵 | HP 100/100 | ATK 45+5(M1) | DEF 30`

### 4.3 点击单位 — 详情弹出

点击地图上的单位 → 地图右侧弹出一个详情卡片（不遮挡该单位），包含：
- 单位类型全称（非缩写）
- 完整属性表：HP、ATK、DEF、移动力、视野、射程
- 科技加成明细（如"ATK+5 from M1 锻造"、"DEF+10 from M3 筑垒"）
- 成本：生产这个单位需要什么资源
- 特殊能力列表

卡片宽度 200px，半透明背景，点击地图空白处关闭。

### 4.4 侧栏数据加语义标注

当前侧栏只显示裸数字。改为显示数字 + 简短解释：

```
P0 (Blue)
  Food: 25 / Wood: 25 / Gold: 25  (start: 25/25/25)
  Techs completed: 3  (M1, E1, C1)
  Researching: M2 (1 turn remaining)
  Facilities: 4  (need 8 for C5 victory)
  Units alive: 8  (2I 1C 1A 1S 3W)
  Construction score: 2  (C1-C5: C1 C2 done)

P1 (Red)
  ...
```

关键数字加括号注释，让不懂游戏的人也能理解"这个数字意味着什么"。

---

## 五、初始化和加载

1. 页面加载时，读取 `<script id="replay-data">` 的内容
2. 解析 JSON
3. 如果有 `<script id="terrain-data">`，读取地形数据
4. 默认显示第 1 回合
5. 如果有 `result.winner` 不为 null，在控制栏显示最终结果

---

## 五、错误处理

- 如果 JSON 解析失败：在地图区域显示 "Error: invalid replay data"
- 如果 turns 数组为空：显示 "Error: no turns in replay"
- 如果某个 turn 缺少某个字段：使用默认值（units=[], economies=[], techs=[], events=[]）
- 不抛出未捕获的 JavaScript 异常：所有错误都要 catch 并显示在页面上

---

## 六、验收测试用例

子 Agent 在交付前应该自己验证以下场景（用 `sample_replay.json` 测试）：

| # | 操作 | 预期结果 |
|---|------|---------|
| 1 | 打开 HTML | 第 1 回合渲染，地图 15×15 格子可见，底部参考栏可见 |
| 2 | 按 → 10 次 | 第 11 回合显示，侧栏数据更新，语义标注可见 |
| 3 | 按 ← 5 次 | 第 6 回合显示 |
| 4 | 点击 "5x" 然后 "auto" | 回合自动推进，速度明显 |
| 5 | 跳到最后一回合（→ 到底） | 显示最终结果，winner 和 victory_type 在控制栏可见 |
| 6 | 看侧栏 | P0 和 P1 的资源/科技/设施/单位数量都在变化，数字有括号注释 |
| 7 | 悬停在一个森林格子上 | tooltip 显示"森林 | DEF+10 | 可建伐木场 | 骑兵遇林停" |
| 8 | 悬停在一个单位上 | tooltip 显示单位类型、HP、ATK、DEF、所属玩家 |
| 9 | 点击一个单位 | 详情卡片弹出，显示完整属性 + 科技加成 + 成本 + 特殊能力 |
| 10 | 看底部参考栏 | 兵种速查、地形速查、科技树缩略，字体 9-10px 清晰可读 |
| 11 | 换一个回放 | 替换 `<script id="replay-data">` 内容即可，不需要改 HTML 代码 |
| 12 | 断网打开 HTML | 所有功能正常，无任何外部资源加载 |

---

## 七、子 Agent 输出格式

交付时，子 Agent 需输出结构化 JSON（用于主 Agent 快速验证）：

```json
{
  "status": "completed|partial|failed",
  "artifacts": ["prototype/replay_viewer.html"],
  "self_check": {
    "test_1_load": "pass|fail",
    "test_2_forward": "pass|fail",
    "test_3_backward": "pass|fail",
    "test_4_autoplay": "pass|fail",
    "test_5_end": "pass|fail",
    "test_6_sidebar_semantic": "pass|fail",
    "test_7_terrain_tooltip": "pass|fail",
    "test_8_unit_tooltip": "pass|fail",
    "test_9_unit_detail_card": "pass|fail",
    "test_10_bottom_reference_bar": "pass|fail",
    "test_11_replay_swap": "pass|fail",
    "test_12_offline": "pass|fail"
  },
  "known_issues": ["terrain colors not rendering - needs terrain-data embed"],
  "token_used": 0
}
```

---

## 八、约束和禁止

- **禁止** 引入任何外部 CDN 依赖（Bootstrap、jQuery、React、Vue、d3 等）
- **禁止** 使用 fetch() 加载外部数据（纯静态）
- **禁止** 修改任何 Python 文件（只有这个 HTML 是你的产出）
- **允许** 使用 ES6+ 语法（Chrome/Edge 都支持）
- **允许** 输出中的已知问题——如实报告即可，不要求完美
