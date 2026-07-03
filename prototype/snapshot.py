# prototype/snapshot.py — GameState 序列化/反序列化

import json
from prototype.terrain import Terrain
from prototype.game import GameState, init_game
from prototype.unit import Unit, City


def terrain_to_str(t: Terrain) -> str:
    return t.name


def str_to_terrain(s: str) -> Terrain:
    return Terrain[s]


def game_to_dict(gs: GameState) -> dict:
    """将 GameState 序列化为 JSON 兼容的 dict"""
    return {
        "version": "2026.07.01",
        "seed": gs.seed,
        "size": gs.size,
        "generator_id": gs.generator_id,
        "turn": gs.turn,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "grid": [[{
            "terrain": terrain_to_str(c["terrain"]),
            "facility": {
                "type": c["facility"].facility_type,
                "player": c["facility"].player_id,
                "x": c["facility"].x,
                "y": c["facility"].y,
            } if c["facility"] else None
        } for c in row] for row in gs.grid],
        "units": [{
            "type": u.unit_type, "pid": u.player_id,
            "x": u.x, "y": u.y, "hp": u.hp,
            "atk": u.atk, "def": u.def_, "alive": u.alive,
        } for u in gs.units + gs.dead_units],
        "cities": [{
            "pid": c.player_id, "x": c.x, "y": c.y, "hp": c.hp,
        } for c in gs.cities],
        "economies": [{
            "food": e.food, "wood": e.wood, "gold": e.gold,
        } for e in gs.economies],
        "techs": [{
            "completed": list(t.completed),
            "researching": t.researching,
            "ticks": t.research_ticks,
        } for t in gs.techs],
        "action_log": gs.action_log,
    }


def game_to_json(gs: GameState, indent: int = 2) -> str:
    return json.dumps(game_to_dict(gs), indent=indent, ensure_ascii=False)


def dict_to_game(d: dict) -> GameState:
    """从 dict 重构 GameState（不含 action_log 重放——仅恢复静态状态）"""
    gs = GameState(seed=d["seed"], size=d["size"], generator_id=d["generator_id"])
    gs.turn = d["turn"]
    gs.winner = d["winner"]
    gs.victory_type = d["victory_type"]

    # grid
    gs.grid = [[{
        "terrain": str_to_terrain(c["terrain"]),
        "facility": None,
    } for c in row] for row in d["grid"]]
    # restore facilities
    for y, row in enumerate(d["grid"]):
        for x, c in enumerate(row):
            if c["facility"]:
                from prototype.unit import Facility
                gs.grid[y][x]["facility"] = Facility(
                    c["facility"]["type"],
                    c["facility"]["player"],
                    c["facility"]["x"],
                    c["facility"]["y"],
                )

    # units
    gs.units = []
    gs.dead_units = []
    for ud in d["units"]:
        u = Unit.create(ud["type"], ud["pid"], ud["x"], ud["y"])
        u.hp = ud["hp"]; u.atk = ud["atk"]; u.def_ = ud["def"]
        u.alive = ud["alive"]
        if u.alive:
            gs.units.append(u)
        else:
            gs.dead_units.append(u)

    # cities
    gs.cities = [City(c["pid"], c["x"], c["y"]) for c in d["cities"]]
    for i, c in enumerate(d["cities"]):
        gs.cities[i].hp = c["hp"]

    # economies
    from prototype.economy import Economy
    gs.economies = []
    for ed in d["economies"]:
        e = Economy(0)
        e.food = ed["food"]; e.wood = ed["wood"]; e.gold = ed["gold"]
        gs.economies.append(e)

    # techs
    from prototype.tech import TechManager
    gs.techs = []
    for td in d["techs"]:
        t = TechManager(0)
        t.completed = set(td["completed"])
        t.researching = td["researching"]
        t.research_ticks = td["ticks"]
        if "C3" in t.completed:
            t.has_academy = True
        gs.techs.append(t)

    gs.action_log = d.get("action_log", [])
    return gs


def json_to_game(s: str) -> GameState:
    return dict_to_game(json.loads(s))


# ─── GameReplay format ────────────────────────────────
# 轻量级回放格式：每回合只存变化量（units摘要 + economies + techs + events），
# 不存完整grid（地形不变）。用于 HTML 回放浏览器。

def snapshot_turn(gs) -> dict:
    """单回合状态快照——只存摘要，不存完整grid。
    返回 dict，符合 GameReplay turns[] 格式。
    """
    # Units summary
    units = []
    for u in gs.units:
        if u.alive:
            units.append({
                "type": u.unit_type,
                "pid": u.player_id,
                "x": u.x, "y": u.y,
                "hp": u.hp, "atk": u.atk, "def": u.def_,
            })

    # Cities
    cities = []
    for c in gs.cities:
        cities.append({
            "pid": c.player_id,
            "x": c.x, "y": c.y,
            "hp": c.hp,
        })

    # Economies
    economies = []
    for e in gs.economies:
        economies.append({
            "pid": e.pid,
            "food": e.food, "wood": e.wood, "gold": e.gold,
        })

    # Techs
    techs = []
    for t in gs.techs:
        techs.append({
            "pid": t.pid,
            "completed": sorted(list(t.completed)),
            "researching": t.researching,
            "research_ticks": t.research_ticks,
        })

    # Facilities count + positions
    from prototype.mapgen import get_facility
    facility_count = {0: 0, 1: 0}
    facilities = []  # list of {pid, type, x, y}
    for y in range(gs.size):
        for x in range(gs.size):
            f = get_facility(gs.grid, x, y)
            if f is not None:
                facility_count[f.player_id] += 1
                facilities.append({
                    "pid": f.player_id,
                    "type": f.facility_type,
                    "x": x, "y": y
                })

    # Events from action_log (last entry = this turn)
    events = []
    if gs.action_log:
        last = gs.action_log[-1]
        if last.get("turn") == gs.turn:
            # Parse action_log into events
            for pid_key, actions in [("p0", last.get("p0", [])), ("p1", last.get("p1", []))]:
                p = 0 if pid_key == "p0" else 1
                for act in actions:
                    atype = act.get("type", "")
                    if atype == "build":
                        u = _find_unit_in_snapshot(units, p, act)
                        if u:
                            events.append({
                                "type": "build",
                                "pid": p,
                                "x": u["x"], "y": u["y"],
                                "detail": "built facility",
                            })
                    elif atype == "move":
                        u = _find_unit_in_snapshot(units, p, act)
                        if u:
                            events.append({
                                "type": "move",
                                "pid": p,
                                "x": u["x"], "y": u["y"],
                                "detail": f"moved to ({u['x']},{u['y']})",
                            })
                    elif atype == "research" and act.get("tech_id"):
                        events.append({
                            "type": "research",
                            "pid": p,
                            "detail": f"started {act['tech_id']}",
                        })
                    elif atype == "produce_unit" and act.get("unit_type"):
                        events.append({
                            "type": "produce_unit",
                            "pid": p,
                            "detail": f"produced {act['unit_type']}",
                        })

    return {
        "turn": gs.turn,
        "units": units,
        "cities": cities,
        "economies": economies,
        "techs": techs,
        "facility_count": facility_count,
        "facilities": facilities,
        "events": events,
    }


def _find_unit_in_snapshot(units: list, pid: int, act: dict) -> dict | None:
    """从当前回合的 units snapshot 中找到执行动作的单位（基于 unit_idx）。"""
    ui = act.get("unit_idx", -1)
    # Count units belonging to pid
    pid_units = [u for u in units if u["pid"] == pid]
    if 0 <= ui < len(pid_units):
        return pid_units[ui]
    return None


def create_replay(gs, seed: int = 0, ai_a: str = "P0", ai_b: str = "P1") -> dict:
    """从已完成的 GameState 创建 GameReplay JSON。
    ai_a/ai_b: AI 名称（用于回放显示）。
    """
    turns = getattr(gs, "turn_snapshots", [])

    # Encode terrain grid (doesn't change during game, store once)
    terrain_grid = []
    from prototype.terrain import Terrain
    terrain_map = {Terrain.PLAIN: 0, Terrain.FOREST: 1, Terrain.MOUNTAIN: 2,
                   Terrain.WATER: 3, Terrain.CITY: 4}
    for y in range(gs.size):
        row = []
        for x in range(gs.size):
            t = gs.grid[y][x]["terrain"]
            row.append(terrain_map.get(t, 0))
        terrain_grid.append(row)

    return {
        "format_version": "1.0",
        "config": {
            "size": gs.size,
            "gen": gs.generator_id,
            "max_turns": 100,
            "seed": seed,
            "terrain_grid": terrain_grid,
            "ai_a": ai_a,
            "ai_b": ai_b,
        },
        "turns": turns,
        "result": {
            "winner": gs.winner,
            "victory_type": gs.victory_type,
            "final_turn": gs.turn,
        },
    }


def save_replay(gs, filepath: str, seed: int = 0):
    """保存 GameReplay JSON 到文件。"""
    replay = create_replay(gs, seed)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(replay, f, indent=2, ensure_ascii=False)
    return replay
