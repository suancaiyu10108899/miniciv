# prototype/server.py — miniciv Web 对战服务器
# 启动: python -m prototype.server
# 浏览器打开 http://localhost:8080

import http.server, json, urllib.parse, random, sys, os
from io import BytesIO
from prototype.game import init_game, step_game
from prototype.ai_rulesrandom import ai_decide
from prototype.terrain import Terrain


# ─── 全局状态（单局）────────────────────────────
_GAME = None
_FOGS = None
_HUMAN_PID = 0
_AI_RNG = None
_GENERATOR_ID = "balanced"
_SIZE = 15
_SEED = 42
_MESSAGE = ""


def _reset():
    global _GAME, _FOGS, _AI_RNG, _MESSAGE
    from prototype.fow import init_fog, update_fog
    _GAME = init_game(seed=_SEED, size=_SIZE, generator_id=_GENERATOR_ID)
    _FOGS = init_fog(_SIZE)
    update_fog(_GAME, _FOGS)
    _AI_RNG = random.Random(_SEED + 1)
    _MESSAGE = ""


# ─── HTML 生成 ───────────────────────────────────

_TERRAIN_COLORS = {
    "PLAIN": "#c8e6c9", "FOREST": "#388e3c", "MOUNTAIN": "#9e9e9e",
    "WATER": "#1565c0", "CITY": "#ff8f00",
}
_PLAYER_COLORS = {0: "#ffeb3b", 1: "#f44336"}
_UNIT_CHARS = {"infantry": "I", "cavalry": "C", "archer": "A", "scout": "S", "worker": "W"}
_FAC_CHARS = {"farm": "F", "lumbermill": "L", "mine": "M"}


def _render_html():
    gs = _GAME
    size = gs.size
    human = _HUMAN_PID
    ai = 1 - human
    econ = gs.economies
    tech = gs.techs
    cities = gs.cities

    # 棋盘
    rows = []
    for y in range(size):
        cells = []
        for x in range(size):
            bg = "#333"
            ch = "."
            fg = "#fff"
            # 迷雾
            if not _is_visible(x, y, human):
                cells.append(f'<div class=c style=background:#111></div>')
                continue
            t = gs.grid[y][x]["terrain"]
            bg = _TERRAIN_COLORS.get(t.name, "#333")
            ch = {"PLAIN": ".", "FOREST": ".", "MOUNTAIN": ".", "WATER": ".", "CITY": ""}.get(t.name, ".")
            # 单位
            for u in gs.units:
                if u.alive and u.x == x and u.y == y:
                    fg = _PLAYER_COLORS.get(u.player_id, "#fff")
                    ch = _UNIT_CHARS.get(u.unit_type, "?")
                    ch = ch.upper() if u.player_id == 0 else ch.lower()
            # 城市
            for c in cities:
                if c.x == x and c.y == y:
                    ch = f"C{c.player_id}"
                    bg = _TERRAIN_COLORS["CITY"]
            # 设施
            fac = gs.grid[y][x].get("facility")
            if fac:
                ch = _FAC_CHARS.get(fac.facility_type, "?")
            cells.append(f'<div class=c style=background:{bg};color:{fg}" title="({x},{y})">{ch}</div>')
        rows.append('<div class=r>' + ''.join(cells) + '</div>')

    board_html = '\n'.join(rows)

    # 人类单位列表
    my_units = [u for u in gs.units if u.player_id == human and u.alive]
    unit_opts = ''.join(f'<option value="{i}">P{human} {_UNIT_CHARS.get(u.unit_type,"?")} @({u.x},{u.y}) HP={u.hp}</option>'
                        for i, u in enumerate(my_units))

    # 可用科技
    avail_techs = tech[human].available_to_research()
    tech_opts = ''.join(f'<option value="{t}">{t}</option>' for t in avail_techs)

    # 建筑进度
    constr_p0 = tech[0].construction_count()
    constr_p1 = tech[1].construction_count()
    completed_p0 = ', '.join(sorted(tech[0].completed))
    completed_p1 = ', '.join(sorted(tech[1].completed))

    winner_html = ""
    if gs.winner is not None:
        winner_html = f'<div style="color:#ff0;font-size:20px;margin:12px">🏆 P{gs.winner} 获胜! ({gs.victory_type})</div>'

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>miniciv — P{human} vs AI</title>
<style>
body{{font-family:monospace;background:#1a1a2e;color:#eee;margin:0;padding:8px}}
.r{{display:flex}}
.c{{width:24px;height:24px;text-align:center;line-height:24px;font-size:13px;font-weight:bold;border:1px solid #222}}
.panel{{background:#16213e;padding:10px;border-radius:6px;margin:4px 0}}
select,button,input{{margin:4px;padding:4px 8px;font-size:13px;background:#0f3460;color:#eee;border:none;border-radius:4px;cursor:pointer}}
button:hover{{background:#1a5080}}
h3{{margin:4px 0;color:#e94560}}
.msg{{background:#0a0;padding:6px;border-radius:4px;margin:4px 0}}
</style></head><body>
<h3>miniciv — Human(P{human}) vs AI(P{ai}) | T{gs.turn}/100 | {_GENERATOR_ID} {_SIZE}×{_SIZE} seed={_SEED}</h3>
<div class=msg>{_MESSAGE}</div>
<div style=display:flex;gap:8px>
<div>{board_html}
<div style=font-size:10px;color:#888;margin-top:4px>I=步兵 C=骑兵 A=弓 S=侦察 W=工人 F=农场 L=伐木场 M=矿山</div>
</div>
<div style=flex:1>
<div class=panel>
<b>P{human} (你)</b><br>
粮:{econ[human].food} 木:{econ[human].wood} 金:{econ[human].gold}<br>
城HP:{cities[human].hp} | 科技:[{completed_p0}]<br>
建设中:{constr_p0}/5 | 研究:{tech[human].researching or '无'}
</div>
<div class=panel>
<b>P{ai} (AI)</b><br>
粮:{econ[ai].food} 木:{econ[ai].wood} 金:{econ[ai].gold}<br>
城HP:{cities[ai].hp} | 科技:[{completed_p1}]<br>
建设中:{constr_p1}/5 | 研究:{tech[ai].researching or '无'}
</div>
{winner_html}
<form method=post action=/act>
<select name=ui>{unit_opts}</select><br>
动作: <button name=act value=w>↑</button><button name=act value=s>↓</button><button name=act value=a>←</button><button name=act value=d>→</button>
<button name=act value=b>建造</button><button name=act value=p>生产</button><button name=act value=x>跳过</button><br>
产兵: <button name=act value=ui>步兵</button><button name=act value=ua>弓箭</button><button name=act value=uc>骑兵</button><button name=act value=skip_prod>跳过</button><br>
研究: <select name=tech>{tech_opts}</select> <button name=act value=research>研究</button> <button name=act value=skip_res>跳过</button><br>
<button name=act value=end style=background:#e94560;font-size:16px;padding:8px 24px>▶ 执行回合</button>
</form>
<div style=margin-top:8px>
<form method=post action=/reset>
生成器: <select name=gen><option>balanced</option><option>symmetric</option><option>fertile</option><option>harsh</option><option>mountain_pass</option><option>archipelago</option></select>
尺寸: <select name=size><option>10</option><option selected>15</option><option>20</option><option>30</option></select>
人类: <select name=pid><option value=0 selected>P0</option><option value=1>P1</option></select>
<button>新游戏</button>
</form>
</div>
</div></div>
<div style=font-size:10px;color:#666;margin-top:8px>科技树: M1(锻造+5ATK)→M2(骑冲+5)/M3(步防+10)→M4(+10HP) | E1(粮+1)→E2(木+1)/E3(金+1)→E4(工+1速) | C1→C2(城+100HP)/C3(研速÷2)→C4(+2粮)→C5(★建设胜利)</div>
</body></html>'''


def _is_visible(x, y, pid):
    if _FOGS is None:
        return True
    from prototype.fow import Visibility
    return _FOGS[pid][y][x] == Visibility.VISIBLE


# ─── HTTP 处理器 ─────────────────────────────────

class GameHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _MESSAGE
        if _GAME is None:
            _reset()
        html = _render_html()
        self._respond(html)

    def do_POST(self):
        global _GAME, _FOGS, _MESSAGE
        if _GAME is None:
            _reset()

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        params = urllib.parse.parse_qs(body)

        path = self.path

        if path == '/reset':
            global _GENERATOR_ID, _SIZE, _HUMAN_PID, _SEED
            _GENERATOR_ID = params.get('gen', ['balanced'])[0]
            _SIZE = int(params.get('size', ['15'])[0])
            _HUMAN_PID = int(params.get('pid', ['0'])[0])
            import random as _r
            _SEED = _r.randint(0, 99999)
            _reset()
            self._redirect('/')
            return

        if path == '/act':
            act = params.get('act', [''])[0]
            human = _HUMAN_PID
            ai = 1 - human

            if act == 'end':
                a0 = ai_decide(_GAME, 0, _AI_RNG)
                a1 = ai_decide(_GAME, 1, _AI_RNG)
                buf = _get_buffer()
                if human == 0:
                    step_game(_GAME, buf, a1)
                else:
                    step_game(_GAME, a0, buf)
                from prototype.fow import update_fog
                update_fog(_GAME, _FOGS)
                buf.clear()
                _MESSAGE = f"回合 {_GAME.turn} 完成"
            else:
                # 缓存人类动作
                ui = int(params.get('ui', ['0'])[0])
                buf = _get_buffer()
                dx, dy = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}.get(act, (0, 0))
                if act in "wasd":
                    buf.append({"unit_idx": ui, "type": "move", "dx": dx, "dy": dy})
                    _MESSAGE = f"单位{ui}: 移动 ({dx},{dy})"
                elif act == 'b':
                    buf.append({"unit_idx": ui, "type": "build"})
                    _MESSAGE = f"单位{ui}: 建造"
                elif act == 'p':
                    buf.append({"unit_idx": ui, "type": "produce"})
                    _MESSAGE = f"单位{ui}: 生产"
                elif act == 'x':
                    buf.append({"unit_idx": ui, "type": "end_turn"})
                    _MESSAGE = f"单位{ui}: 跳过"
                elif act == 'ui':
                    buf.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})
                    _MESSAGE = "城市: 生产步兵"
                elif act == 'ua':
                    buf.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "archer"})
                    _MESSAGE = "城市: 生产弓箭手"
                elif act == 'uc':
                    buf.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "cavalry"})
                    _MESSAGE = "城市: 生产骑兵"
                elif act == 'research':
                    t = params.get('tech', [''])[0]
                    if t:
                        buf.append({"unit_idx": -1, "type": "research", "tech_id": t})
                        _MESSAGE = f"研究: {t}"
                elif act == 'skip_prod' or act == 'skip_res':
                    _MESSAGE = "跳过"
            self._redirect('/')
            return

        self._redirect('/')

    def _respond(self, html):
        data = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, url):
        self.send_response(303)
        self.send_header('Location', url)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志


_HUMAN_BUFFER = []


def _get_buffer():
    return _HUMAN_BUFFER


def main():
    global _SEED
    import random as _r
    _SEED = _r.randint(0, 99999)
    _reset()
    port = 8080
    server = http.server.HTTPServer(('localhost', port), GameHandler)
    print(f'miniciv web server: http://localhost:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')


if __name__ == '__main__':
    main()
