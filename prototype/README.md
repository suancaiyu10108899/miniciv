# miniciv 原型 — 验收指南

> 以下命令全部在项目根目录 `D:\Dev\miniciv` 下运行。

## 1. 跑测试

```bash
cd D:\Dev\miniciv
python -m pytest tests/ -v
```

预期：86 passed。

## 2. AI 批量对弈

```bash
python -m prototype.eval --games 10 --size 15 --verbose
```

预期：10 局全部跑完。每 20 回合打印资源状态。

## 3. 生成 HTML 回放并查看

```bash
python -c "
from prototype.game import init_game, step_game
from prototype.ai_rulesrandom import ai_decide
from prototype.render_html import generate_replay
import random
gs=init_game(42,size=15)
r0=random.Random(42); r1=random.Random(43)
while gs.winner is None and gs.turn<150:
    step_game(gs, ai_decide(gs,0,r0), ai_decide(gs,1,r1))
generate_replay(gs, 'data/replay_check.html')
print('OK. Open data/replay_check.html in browser')
"
```

浏览器打开 `data/replay_check.html`：
- 点击 P0/P1/上帝 切换视角
- 拖动滑条或点 ◀▶ 逐帧切换
- 点"播放"自动播放

## 4. Human vs AI（终端）

```bash
python -m prototype.play --human-pid 0 --size 15
```

操作：
- `wasd` — 移动当前单位
- `b` — 建造设施
- `p` — 在生产设施上生产
- `x` 或回车 — 跳过当前单位
- 城市提示时输入 `i/a/c/s/w` — 产兵，回车跳过
- 研究提示时输入科技 ID（如 `E1`），回车跳过

## 5. 单独看一张地图长什么样

```bash
python -c "
from prototype.mapgen import generate_map
from prototype.terrain import TERRAIN_CHAR, Terrain
m=generate_map(42,15,'balanced')
for y in range(15):
    print(''.join(TERRAIN_CHAR[m[y][x]['terrain']] for x in range(15)))
print()
print('. = PLAIN  F = FOREST  M = MOUNTAIN  ~ = WATER  C = CITY')
"
```

试试换 `'symmetric'` / `'harsh'` / `'archipelago'` 看不同生成器的效果。

## 6. 换地图大小

把上面命令里的 `15` 换成 `30` 或 `50`。

## 7. 验证序列化往返

```bash
python -c "
from prototype.game import init_game, step_game
from prototype.ai_rulesrandom import ai_decide
from prototype.snapshot import game_to_json, json_to_game
import random
gs=init_game(42,size=15)
r0=random.Random(42); r1=random.Random(43)
for _ in range(10):
    step_game(gs, ai_decide(gs,0,r0), ai_decide(gs,1,r1))
j=game_to_json(gs)
gs2=json_to_game(j)
assert gs.turn==gs2.turn
assert len(gs.units)==len(gs2.units)
print(f'OK: snapshot round-trip. Turn={gs.turn}, Units={len(gs.units)}')
"
```

---

有问题直接截图或描述给我。
