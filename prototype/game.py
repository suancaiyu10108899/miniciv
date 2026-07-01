# prototype/game.py — 完整游戏循环 + 胜利判定

import random
from dataclasses import dataclass, field
from prototype.mapgen import generate_map, get_terrain
from prototype.terrain import Terrain
from prototype.unit import Unit, City
from prototype.combat import resolve_melee, resolve_ranged, can_occupy_city, city_occupation_damage
from prototype.economy import (
    Economy, worker_action_move, worker_action_build,
    worker_action_produce, produce_unit, destroy_facility, city_base_income,
)
from prototype.tech import TechManager, apply_tech_to_unit
from prototype.constants import MAX_TURNS, DEFAULT_SIZE, CITY_HP, UNIT_STATS
from prototype.movement import (
    get_legal_moves, get_single_step_moves, apply_move,
    cavalry_forest_check,
)


@dataclass
class GameState:
    """完整游戏状态"""
    seed: int
    size: int
    generator_id: str
    turn: int = 0
    grid: list = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    economies: list[Economy] = field(default_factory=list)
    techs: list[TechManager] = field(default_factory=list)
    winner: int | None = None
    victory_type: str | None = None  # "conquest" | "construction" | "tiebreak"
    rng: random.Random = field(default_factory=lambda: random.Random(0))
    fog: list = field(default_factory=list)  # per-player fog state, lazy init
    dead_units: list[Unit] = field(default_factory=list)  # 已死单位（回放用）
    action_log: list[dict] = field(default_factory=list)  # 动作序列


def init_game(seed: int, size: int = DEFAULT_SIZE,
              generator_id: str = "balanced") -> GameState:
    """初始化一局新游戏"""
    gs = GameState(seed=seed, size=size, generator_id=generator_id)
    gs.rng = random.Random(seed)

    # 地图
    gs.grid = generate_map(seed=seed, size=size, generator_id=generator_id)

    # 找城市位置
    cities_info = []
    for y in range(size):
        for x in range(size):
            if gs.grid[y][x]["terrain"] == Terrain.CITY:
                cities_info.append((x, y))

    # P0 城市 (先找到的→可能是任一个，按 x 排序取先)
    cities_info.sort(key=lambda c: (c[1], c[0]))
    cx0, cy0 = cities_info[0]
    cx1, cy1 = cities_info[1]

    gs.cities = [City(0, cx0, cy0), City(1, cx1, cy1)]

    # 初始单位
    from prototype.constants import STARTING_UNITS
    gs.units = []
    n_workers = STARTING_UNITS.get("worker", 2)
    n_scouts = STARTING_UNITS.get("scout", 1)
    for pid, (cx, cy) in enumerate([(cx0, cy0), (cx1, cy1)]):
        for _ in range(n_workers):
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = (cx + dx) % size, (cy + dy) % size
                t = get_terrain(gs.grid, nx, ny)
                if t == Terrain.PLAIN:
                    occupied = any(u.x == nx and u.y == ny for u in gs.units)
                    if not occupied:
                        gs.units.append(Unit.create("worker", pid, nx, ny))
                        break
        for _ in range(n_scouts):
            for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                nx, ny = (cx + dx) % size, (cy + dy) % size
                t = get_terrain(gs.grid, nx, ny)
                if t == Terrain.PLAIN:
                    occupied = any(u.x == nx and u.y == ny for u in gs.units)
                    if not occupied:
                        gs.units.append(Unit.create("scout", pid, nx, ny))
                        break

    # 经济
    gs.economies = [Economy(0), Economy(1)]

    # 科技
    gs.techs = [TechManager(0), TechManager(1)]

    return gs


def step_game(gs: GameState, actions_p0: list[dict],
              actions_p1: list[dict]) -> dict:
    """
    执行一回合。
    actions_pX: [{"unit_idx": N, "type": "move"/"build"/"produce"/"produce_unit"/"research"/"destroy"/"end_turn"}, ...]
    所有单位可以执行一个动作，然后回合推进。

    返回本回合摘要。
    """
    gs.turn += 1
    gs.action_log.append({"turn": gs.turn, "p0": actions_p0, "p1": actions_p1})

    for pid, actions in [(0, actions_p0), (1, actions_p1)]:
        units = [u for u in gs.units if u.player_id == pid and u.alive]
        econ = gs.economies[pid]
        tech = gs.techs[pid]
        bonuses = tech.get_tech_bonuses()

        for act in actions:
            atype = act.get("type", "end_turn")
            ui = act.get("unit_idx", -1)
            unit = units[ui] if (ui >= 0 and ui < len(units)) else None

            if atype == "move" and unit:
                dx, dy = act.get("dx", 0), act.get("dy", 0)
                _do_move(unit, gs, dx, dy)

            elif atype == "build" and unit and unit.unit_type == "worker":
                worker_action_build(unit, gs.grid, pid)

            elif atype == "produce" and unit and unit.unit_type == "worker":
                worker_action_produce(unit, gs.grid, pid, econ, bonuses)

            elif atype == "produce_unit":
                utype = act.get("unit_type", "infantry")
                city = gs.cities[pid]
                produce_unit(gs.grid, city, econ, utype, gs.units)

            elif atype == "research":
                tech_id = act.get("tech_id")
                if tech_id:
                    cost = TECH_TREE_COST.get(tech_id, (0, 0, 0))
                    if econ.can_afford(cost):
                        if tech.start_research(tech_id):
                            econ.spend(cost)

            elif atype == "destroy" and unit:
                destroy_facility(gs.grid, unit.x, unit.y)

        # 城市基础产出
        food_bonus = bonuses.get("city_food", 0)
        city_base_income(econ, food_bonus)

        # 科技研究推进
        completed = tech.tick_research()
        if completed == "C5":
            gs.winner = pid
            gs.victory_type = "construction"

    # 征服胜利检查
    for pid in (0, 1):
        opp = 1 - pid
        opp_city = gs.cities[opp]
        if opp_city.hp <= 0:
            gs.winner = pid
            gs.victory_type = "conquest"

    # 回合上限阶梯判定
    if gs.turn >= MAX_TURNS and gs.winner is None:
        _tiebreak(gs)

    # 清理死单位
    gs.dead_units.extend([u for u in gs.units if not u.alive])
    gs.units = [u for u in gs.units if u.alive]

    return {"turn": gs.turn, "winner": gs.winner, "victory_type": gs.victory_type}


def _do_move(unit: Unit, gs: GameState, dx: int, dy: int):
    """执行单位移动+可能的战斗"""
    if not unit.alive:
        return
    # 骑兵遇林检查
    dx, dy = cavalry_forest_check(unit, gs.grid, dx, dy)

    target_x = (unit.x + dx) % gs.size
    target_y = (unit.y + dy) % gs.size

    # 目标格有敌方单位？
    blocker = next((u for u in gs.units
                    if u.alive and u.player_id != unit.player_id
                    and u.x == target_x and u.y == target_y), None)

    if blocker:
        if unit.ranged:
            # 弓箭手不能移入敌方格子——只能远程攻击
            terrain_target = get_terrain(gs.grid, blocker.x, blocker.y)
            resolve_ranged(unit, blocker, terrain_target)
        else:
            # 近战——移动+战斗
            terrain_att = get_terrain(gs.grid, unit.x, unit.y)
            terrain_def = get_terrain(gs.grid, blocker.x, blocker.y)
            # 骑兵冲锋判断
            charged = (unit.unit_type == "cavalry" and
                       abs(dx) + abs(dy) == 2 and
                       get_terrain(gs.grid, unit.x, unit.y) == Terrain.PLAIN)
            result = resolve_melee(unit, blocker, terrain_att, terrain_def,
                                   attacker_just_charged=charged)
            if result["attacker_alive"] and not result["defender_alive"]:
                # 胜→占领该格
                unit.x, unit.y = target_x, target_y
                # 占领城市？
                opp_city = gs.cities[1 - unit.player_id]
                if target_x == opp_city.x and target_y == opp_city.y:
                    dmg = city_occupation_damage(unit, opp_city)
                    if dmg >= opp_city.hp:
                        opp_city.hp = 0
            elif not result["attacker_alive"]:
                pass  # 攻方已死
    else:
        # 目标格为空→直接移动
        unit.x, unit.y = target_x, target_y

    # 更新视野（lazy）
    # TODO: fow update


def _tiebreak(gs: GameState):
    """阶梯判定"""
    c0 = gs.techs[0].construction_count()
    c1 = gs.techs[1].construction_count()
    if c0 > c1:
        gs.winner, gs.victory_type = 0, "tiebreak_construction"
    elif c1 > c0:
        gs.winner, gs.victory_type = 1, "tiebreak_construction"
    elif gs.cities[0].hp > gs.cities[1].hp:
        gs.winner, gs.victory_type = 0, "tiebreak_city_hp"
    elif gs.cities[1].hp > gs.cities[0].hp:
        gs.winner, gs.victory_type = 1, "tiebreak_city_hp"
    else:
        gs.winner, gs.victory_type = 0, "tiebreak_p0"


from prototype.constants import TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}
