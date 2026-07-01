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
