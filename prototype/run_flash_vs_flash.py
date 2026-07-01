# prototype/run_flash_vs_flash.py — Flash vs Flash 完整对局 + 思考回放
# 用法: python -m prototype.run_flash_vs_flash

import json, os, time, random as _random
from prototype.game import init_game, step_game
from prototype.ai_flash import ai_flash_decide, clear_flash_log

OUTPUT = "data/flash_vs_flash.html"


def main():
    print("=== Flash(P0) vs Flash(P1) — 10×10 对局 ===")
    seed = 42
    gs = init_game(seed, size=10)
    clear_flash_log()

    # 存储每回合游戏快照 + 双方思考
    frames = []
    turn = 0
    max_turns = 50

    while gs.winner is None and turn < max_turns:
        turn += 1
        print(f"\n--- Turn {turn} ---")

        # P0 决策
        print("  P0 thinking...", end="", flush=True)
        t0_start = time.time()
        result0 = ai_flash_decide(gs, 0)
        t0_time = time.time() - t0_start
        actions0 = result0.get("actions", [])
        thinking0 = result0.get("_thinking", "")
        tokens0 = result0.get("_tokens", {})
        print(f" {t0_time:.1f}s, {tokens0.get('input_tokens','?')}+{tokens0.get('output_tokens','?')}tokens")

        # P1 决策
        print("  P1 thinking...", end="", flush=True)
        t1_start = time.time()
        result1 = ai_flash_decide(gs, 1)
        t1_time = time.time() - t1_start
        actions1 = result1.get("actions", [])
        thinking1 = result1.get("_thinking", "")
        tokens1 = result1.get("_tokens", {})
        print(f" {t1_time:.1f}s, {tokens1.get('input_tokens','?')}+{tokens1.get('output_tokens','?')}tokens")

        # 执行
        step_game(gs, actions0, actions1)

        # 保存帧
        frames.append({
            "turn": turn,
            "p0_thinking": thinking0[:1500],
            "p1_thinking": thinking1[:1500],
            "p0_actions": [str(a) for a in actions0],
            "p1_actions": [str(a) for a in actions1],
            "p0_tokens": tokens0,
            "p1_tokens": tokens1,
            "p0_resources": {"food": gs.economies[0].food, "wood": gs.economies[0].wood,
                            "gold": gs.economies[0].gold},
            "p1_resources": {"food": gs.economies[1].food, "wood": gs.economies[1].wood,
                            "gold": gs.economies[1].gold},
            "p0_techs": sorted(list(gs.techs[0].completed)),
            "p1_techs": sorted(list(gs.techs[1].completed)),
            "p0_units": [{"type": u.unit_type, "x": u.x, "y": u.y, "hp": u.hp}
                         for u in gs.units if u.player_id == 0 and u.alive],
            "p1_units": [{"type": u.unit_type, "x": u.x, "y": u.y, "hp": u.hp}
                         for u in gs.units if u.player_id == 1 and u.alive],
            "p0_dead": len([u for u in gs.dead_units if u.player_id == 0]),
            "p1_dead": len([u for u in gs.dead_units if u.player_id == 1]),
        })

    # 终局
    # 用现有 replay + 手动注入思考帧
    from prototype.render_html import generate_replay
    generate_replay(gs, "data/flash_vs_flash_map.html")

    # 生成思考日志 HTML
    _write_thinking_html(frames, gs)

    total = sum(f["p0_tokens"].get("input_tokens", 0) + f["p0_tokens"].get("output_tokens", 0) +
                f["p1_tokens"].get("input_tokens", 0) + f["p1_tokens"].get("output_tokens", 0)
                for f in frames)
    print(f"\n=== 完成 ===")
    print(f"回合: {turn}, 胜者: P{gs.winner} ({gs.victory_type})")
    print(f"总 tokens: {total}, 预估成本: ${total * 0.00000027:.4f}")
    print(f"思考日志: {OUTPUT}")
    print(f"地图回放: data/flash_vs_flash_map.html")


def _write_thinking_html(frames, gs):
    """生成带思考过程的 HTML"""
    frames_json = json.dumps(frames, ensure_ascii=False)
    n = len(frames)

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Flash vs Flash — 思考回放</title><style>
body{{font-family:monospace;background:#1a1a2e;color:#eee;margin:10px}}
.frame{{margin:8px 0;padding:10px;background:#16213e;border-radius:6px}}
.thinking{{background:#111;padding:8px;margin:4px 0;border-left:3px solid #e94560;font-size:12px;white-space:pre-wrap;max-height:300px;overflow-y:auto}}
.p0{{color:#ffeb3b}} .p1{{color:#f44336}}
button{{padding:6px 12px;margin:2px;background:#0f3460;color:#eee;border:none;border-radius:4px;cursor:pointer}}
button:hover{{background:#1a5080}}
.header{{position:sticky;top:0;background:#1a1a2e;padding:8px;z-index:10}}
</style></head><body>
<h2>🧠 Flash vs Flash — 思考过程回放</h2>
<div class=header>
回合: <span id=tl>1</span>/{n} &nbsp;
<button onclick="go(0)">&#9198;</button>
<button onclick="go(Math.max(0,cur-1))">&#9664;</button>
<button onclick="go(Math.min({n-1},cur+1))">&#9654;</button>
<button onclick="go({n-1})">&#9197;</button>
<button onclick="autoPlay()">▶播放</button>
<button onclick="stopAuto()">⏸</button>
地图回放: <a href="flash_vs_flash_map.html" style=color:#42a5f5>打开</a>
</div>
<div>胜者: P{gs.winner} ({gs.victory_type}) | {n}回合</div>
<div id=frames></div>
<script>
var frames={frames_json};
var cur=0,timer=null;
function go(n){{cur=n;render(cur);document.getElementById('tl').textContent=cur+1;}}
function autoPlay(){{if(timer)return;timer=setInterval(function(){{if(cur<frames.length-1)go(cur+1);else stopAuto();}},3000);}}
function stopAuto(){{clearInterval(timer);timer=null;}}
function render(i){{
  var f=frames[i],h='';
  h+='<div class=frame>';
  h+='<b>T'+f.turn+'</b> P0资源:'+f.p0_resources.food+'粮 '+f.p0_resources.wood+'木 '+f.p0_resources.gold+'金';
  h+=' | P1资源:'+f.p1_resources.food+'粮 '+f.p1_resources.wood+'木 '+f.p1_resources.gold+'金';
  h+=' | P0死:'+f.p0_dead+' P1死:'+f.p1_dead;
  h+='<br>P0科技:['+f.p0_techs.join(',')+'] P1科技:['+f.p1_techs.join(',')+']';
  h+='<br>P0单位:'+JSON.stringify(f.p0_units)+'<br>P1单位:'+JSON.stringify(f.p1_units);
  h+='<br>P0动作:'+f.p0_actions.join('; ')+'<br>P1动作:'+f.p1_actions.join('; ');
  h+='<div class=thinking><b class=p0>P0 思考:</b>\\n'+f.p0_thinking+'</div>';
  h+='<div class=thinking><b class=p1>P1 思考:</b>\\n'+f.p1_thinking+'</div>';
  h+='</div>';
  document.getElementById('frames').innerHTML=h;
  window.scrollTo(0,0);
}}
go(0);
</script></body></html>'''

    os.makedirs(os.path.dirname(OUTPUT) or '.', exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Wrote {len(html)} chars to {OUTPUT}")


if __name__ == '__main__':
    main()
