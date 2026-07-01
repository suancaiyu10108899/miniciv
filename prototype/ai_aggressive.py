# prototype/ai_aggressive.py — 进攻型AI：优先攻击+暴兵

import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """进攻AI：工人只建必需品，全力暴兵+推进"""
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []

    # 设施统计
    facs = _count_facs(gs, pid)
    has_f, has_l, has_m = facs["farm"] > 0, facs["lumbermill"] > 0, facs["mine"] > 0

    for ui, u in enumerate(units):
        if u.unit_type == "worker":
            act = _aggro_worker(u, ui, gs, pid, has_f, has_l, has_m, rng)
        elif u.unit_type == "scout":
            act = _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)
        else:
            act = _aggro_combat(u, ui, gs, pid, opp_city, rng)
        if act:
            actions.append(act)

    # 暴兵
    for ut in ["cavalry", "archer", "infantry"]:
        if econ.can_afford(UNIT_COST[ut]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
            break

    # 研究：优先战斗线
    if tech.researching is None:
        avail = tech.available_to_research()
        order = ["M1", "M2", "M3", "E1", "E2", "E3", "M4", "C1"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    return actions


def _aggro_worker(w, ui, gs, pid, has_f, has_l, has_m, rng):
    """进攻型工人：只建还没的设施，之后生产"""
    terrain = get_terrain(gs.grid, w.x, w.y)
    buildable = terrain_buildable(terrain)
    fac = gs.grid[w.y][w.x].get("facility")

    if fac and fac.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}

    # 缺啥建啥
    need = ((buildable == "farm" and not has_f) or
            (buildable == "lumbermill" and not has_l) or
            (buildable == "mine" and not has_m))
    if buildable and not fac and need:
        return {"unit_idx": ui, "type": "build"}

    # 找缺失资源
    target = _nearest_missing(w, gs, pid, has_f, has_l, has_m)
    if target:
        return _move_to(w, ui, gs, target, rng)
    return {"unit_idx": ui, "type": "end_turn"}


def _aggro_combat(u, ui, gs, pid, opp_city, rng):
    """战斗单位：攻敌→冲城。骑兵敢死队"""
    # 邻格有敌→攻击
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        target = next((eu for eu in gs.units
                       if eu.alive and eu.player_id != pid
                       and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 冲城！
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _count_facs(gs, pid):
    counts = {"farm": 0, "lumbermill": 0, "mine": 0}
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                counts[f.facility_type] = counts.get(f.facility_type, 0) + 1
    return counts


def _nearest_missing(unit, gs, pid, has_f, has_l, has_m):
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            b = terrain_buildable(get_terrain(gs.grid, x, y))
            if not b:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            need = ((b == "farm" and not has_f) or
                    (b == "lumbermill" and not has_l) or
                    (b == "mine" and not has_m))
            if not need:
                continue
            d = td(unit.x, x, gs.size) + td(unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _move_to(unit, ui, gs, target, rng):
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_d = [], 999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        if d < best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}
