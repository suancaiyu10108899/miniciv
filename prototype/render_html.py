# prototype/render_html.py — 生成自包含 HTML 回放查看器
# 数据嵌入 HTML，无需服务器。浏览器直接打开。

import json, os
from prototype.snapshot import game_to_dict
from prototype.terrain import Terrain, TERRAIN_CHAR
from prototype.constants import TECH_TREE, UNIT_STATS


# ─── 颜色映射 ──────────────────────────────────────
TERRAIN_COLORS = {
    "PLAIN": "#c8e6c9", "FOREST": "#388e3c", "MOUNTAIN": "#9e9e9e",
    "WATER": "#1565c0", "CITY": "#ff8f00",
}
PLAYER_COLORS = {0: "#ffeb3b", 1: "#f44336"}
FACILITY_LABELS = {"farm": "F", "lumbermill": "L", "mine": "M"}


def generate_replay(gs, output_path: str = "data/replay.html", ai0="P0_AI", ai1="P1_AI"):
    """从终局 GameState 生成自包含 HTML 回放文件。"""
    # 从 seed 重建逐帧快照
    frames = _rebuild_frames(gs)

    tech_data_js = json.dumps({k:{'cost':v['cost'],'turns':v['turns'],'requires':v['requires'],'effect':v['effect']} for k,v in TECH_TREE.items()}, ensure_ascii=False)
    frames_json = json.dumps(frames, ensure_ascii=False)
    n = len(frames)

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>miniciv replay — {ai0} vs {ai1}</title><style>
body{{font-family:monospace;background:#1a1a2e;color:#eee;margin:0;padding:10px}}
#board{{display:inline-block;line-height:1.1;font-size:12px}}
#panel{{display:inline-block;vertical-align:top;margin-left:16px;background:#16213e;padding:12px;border-radius:6px;min-width:220px}}
.row{{display:flex}}
.cell{{width:18px;height:18px;text-align:center;font-weight:bold;border:1px solid #222;font-size:11px;line-height:18px}}
.legend{{font-size:11px;margin:4px 0}}
button{{padding:6px 12px;margin:2px;font-size:13px;cursor:pointer;border:none;border-radius:4px;background:#0f3460;color:#eee}}
button:hover{{background:#1a5080}}
input[type=range]{{width:300px}}
#info{{font-size:14px;margin:8px 0}}
#fowmode{{margin:6px 0}}
.fowbtn{{background:#333;padding:4px 8px;font-size:11px}}
.fowbtn.active{{background:#e94560}}
</style></head><body>
<h2>miniciv replay — {ai0} vs {ai1} | seed={gs.seed} size={gs.size}</h2>
<div id="fowmode">
视角: <button class="fowbtn active" onclick="setFog(0)">P0</button>
<button class="fowbtn" onclick="setFog(1)">P1</button>
<button class="fowbtn" onclick="setFog(2)">上帝</button>
</div>
<div id="info">回合 <span id="tl">1</span>/{n}</div>
<input type="range" id="slider" min="0" max="{n-1}" value="0" oninput="goTo(+this.value)">
<br>
<button onclick="goTo(0)">&#9198; 开头</button>
<button onclick="goTo(Math.max(0,cur-1))">&#9664;</button>
<button onclick="goTo(Math.min({n-1},cur+1))">&#9654;</button>
<button onclick="goTo({n-1})">&#9197;</button>
<button onclick="autoPlay()">&#9654;播放</button>
<button onclick="stopAuto()">&#9208;</button>
<br><br>
<div id="board"></div><div id="panel"></div>
<script>
var frames = {frames_json};
var cur = 0, timer = null, fogMode = 0;
function setFog(m) {{
  fogMode = m;
  document.querySelectorAll('.fowbtn').forEach((b,i)=>{{b.classList.toggle('active',i===m);}});
  render(cur);
}}
function goTo(n){{cur=n;render(cur);document.getElementById('slider').value=cur;document.getElementById('tl').textContent=cur+1;}}
function autoPlay(){{if(timer)return;timer=setInterval(function(){{if(cur<frames.length-1)goTo(cur+1);else stopAuto();}},400);}}
function stopAuto(){{clearInterval(timer);timer=null;}}
function render(i){{
  var f=frames[i];
  document.getElementById('tl').textContent=i+1;
  if(f.winner!==null) document.getElementById('tl').textContent+=' 🏆P'+f.winner+'('+f.vtype+')';
  var h='';
  f.grid.forEach(function(row,y){{
    h+='<div class=row>';
    row.forEach(function(c,x){{
      var bg='#333',ch='.',fg='#fff';
      if(fogMode===0){{
        if(!f.fog[0][y][x]){{h+='<div class=cell style=background:#111></div>';return;}}
      }}else if(fogMode===1){{
        if(!f.fog[1][y][x]){{h+='<div class=cell style=background:#111></div>';return;}}
      }}
      var t=c[0], fac=c[1];
      bg=TERRAIN_COLORS[t]||'#333';
      ch='.';
      // units
      f.units.forEach(function(u){{
        if(u.x===x&&u.y===y&&u.alive){{fg=PLAYER_COLORS[u.pid];ch=UNIT_CHARS[u.type];}}
      }});
      // facilities
      if(fac) ch=FAC_LABELS[fac.type]||'?';
      if(t==='CITY'){{ch='C'+c[2];}}
      h+='<div class=cell style=background:'+bg+';color:'+fg+'>'+ch+'</div>';
    }});
    h+='</div>';
  }});
  document.getElementById('board').innerHTML=h;
  // panel
  var p='<b>T'+f.turn+'/'+f.max_turns+'</b><br>';
  p+='<span style=color:#ffeb3b>P0:</span> '+f.p0.food+'粮 '+f.p0.wood+'木 '+f.p0.gold+'金<br>';
  p+='<span style=color:#f44336>P1:</span> '+f.p1.food+'粮 '+f.p1.wood+'木 '+f.p1.gold+'金<br>';
  p+='<br>P0科技:'+f.p0.techs.join(',')+'<br>P1科技:'+f.p1.techs.join(',')+'<br>';
  p+='<br>P0建设:'+f.p0.constr+'/5 P1建设:'+f.p1.constr+'/5<br>';
  p+='<br>P0单位:'+f.p0.nalive+' P1单位:'+f.p1.nalive;
  p+='<br><br><b>科技树:</b><div style=display:grid;grid-template-columns:repeat(3,1fr);gap:3px;font-size:9px;margin-top:4px>';
  Object.entries(TECH_DATA).forEach(function(e){{
    var k=e[0],v=e[1],done=(f.p0.techs||[]).includes(k)||(f.p1.techs||[]).includes(k);
    var cls=done?'color:#4caf50':'color:#666';
    var cat=k[0],catc=cat=='M'?'#ff9800':cat=='E'?'#2196f3':'#e94560';
    p+='<div style=background:#1a1a2e;padding:3px 5px;border-left:2px solid '+catc+';'+cls+'>';
    p+='<b>'+k+'</b> '+v.effect+'<br><span style=color:#888>('+v.cost.join('/')+') '+v.turns+'T</span>';
    p+='</div>';
  }});
  p+='</div>';
  document.getElementById('panel').innerHTML=p;
}}
var TECH_DATA = {tech_data_js};
var TERRAIN_COLORS={{'PLAIN':'#c8e6c9','FOREST':'#388e3c','MOUNTAIN':'#9e9e9e','WATER':'#1565c0','CITY':'#ff8f00'}};
var PLAYER_COLORS={{0:'#ffeb3b',1:'#f44336'}};
var UNIT_CHARS={{'infantry':'I','cavalry':'C','archer':'A','scout':'S','worker':'W'}};
var FAC_LABELS={{'farm':'F','lumbermill':'L','mine':'M'}};
goTo(0);
</script></body></html>'''

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


def _rebuild_frames(gs):
    """从 action_log 重建逐帧快照（轻量，仅含渲染所需）"""
    from prototype.game import init_game, step_game
    from prototype.ai_rulesrandom import ai_decide
    from prototype.fow import init_fog, update_fog
    import random
    import copy as _copy

    # 重新执行游戏，每回合保存轻量快照
    gs2 = init_game(seed=gs.seed, size=gs.size, generator_id=gs.generator_id)
    fogs = init_fog(gs2.size)
    update_fog(gs2, fogs)
    rng0 = random.Random(gs.seed)
    rng1 = random.Random(gs.seed + 1)

    size = gs2.size
    max_turns = gs2.turn + 100  # safety
    frames = [_light_frame(gs2, fogs, size)]

    for t, turn_acts in enumerate(gs.action_log):
        if gs2.winner is not None:
            break
        a0 = turn_acts.get("p0", [])
        a1 = turn_acts.get("p1", [])
        step_game(gs2, a0, a1)
        update_fog(gs2, fogs)
        frames.append(_light_frame(gs2, fogs, size))

    return frames


def _light_frame(gs2, fogs, size):
    """单帧轻量 JSON：grid压缩 + units + fogs + resources"""
    # grid: 每个格 [terrain_name, facility_type_or_null, city_player]
    grid_c = []
    for y in range(size):
        row_c = []
        for x in range(size):
            t = gs2.grid[y][x]["terrain"].name
            fac = gs2.grid[y][x].get("facility")
            fac_type = fac.facility_type if fac else None
            cp = None
            for c in gs2.cities:
                if c.x == x and c.y == y:
                    cp = c.player_id
            row_c.append([t, fac_type, cp])
        grid_c.append(row_c)

    units_c = [{"type": u.unit_type, "pid": u.player_id,
                "x": u.x, "y": u.y, "hp": u.hp, "alive": u.alive}
               for u in gs2.units + gs2.dead_units]

    # fogs: 0=hidden, 1=visible
    fog_c = []
    for pid in (0, 1):
        f = [[1 if fogs[pid][y][x].value >= 2 else 0 for x in range(size)] for y in range(size)]
        fog_c.append(f)

    return {
        "turn": gs2.turn,
        "max_turns": 100,
        "winner": gs2.winner,
        "vtype": gs2.victory_type,
        "grid": grid_c,
        "units": units_c,
        "fog": fog_c,
        "p0": {"food": gs2.economies[0].food, "wood": gs2.economies[0].wood,
               "gold": gs2.economies[0].gold,
               "techs": sorted(list(gs2.techs[0].completed)),
               "constr": gs2.techs[0].construction_count(),
               "nalive": sum(1 for u in gs2.units if u.player_id == 0 and u.alive)},
        "p1": {"food": gs2.economies[1].food, "wood": gs2.economies[1].wood,
               "gold": gs2.economies[1].gold,
               "techs": sorted(list(gs2.techs[1].completed)),
               "constr": gs2.techs[1].construction_count(),
               "nalive": sum(1 for u in gs2.units if u.player_id == 1 and u.alive)},
    }
