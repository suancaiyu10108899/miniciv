# prototype/ai_rulesrandom.py — 改进的基线 AI

import random as _random
from prototype.unit import Unit
from prototype.movement import get_single_step_moves, apply_move
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE

TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def ai_decide(gs, pid: int, rng: _random.Random | None = None) -> list[dict]:
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []

    # 设施统计
    facilities = _list_my_facilities(gs, pid)
    has_farm = any(f[2] == "farm" for f in facilities)
    has_lumb = any(f[2] == "lumbermill" for f in facilities)
    has_mine = any(f[2] == "mine" for f in facilities)

    for ui, u in enumerate(units):
        if u.unit_type == "worker":
            act = _worker_ai(u, ui, gs, pid, has_farm, has_lumb, has_mine, rng)
        elif u.unit_type == "scout":
            act = _push_toward(u, ui, gs, opp_city, rng)
        else:
            act = _combat_ai(u, ui, gs, pid, opp_city, rng)
        if act:
            actions.append(act)

    # 城市生产
    if rng.random() < 0.6:
        ut = _pick_unit(econ)
        if ut:
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})

    # 研究——只在设施建成后有资源流时进行
    if tech.researching is None and (has_lumb or has_mine or gs.turn < 5):
        available = tech.available_to_research()
        available.sort(key=lambda t: sum(TECH_TREE_COST.get(t, (99, 99, 99))))
        for t in available:
            cost = TECH_TREE_COST.get(t, (99, 99, 99))
            if econ.can_afford(cost):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    return actions


def _list_my_facilities(gs, pid):
    """返回 [(x, y, type), ...]"""
    result = []
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                result.append((x, y, f.facility_type))
    return result


def _worker_ai(w, ui, gs, pid, has_farm, has_lumb, has_mine, rng):
    """工人: 优先确保三种设施各1 → 然后生产"""
    x, y = w.x, w.y
    terrain = get_terrain(gs.grid, x, y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[y][x].get("facility")

    # 已有设施且三种齐了→生产
    if facility and facility.player_id == pid:
        if has_farm and has_lumb and has_mine:
            return {"unit_idx": ui, "type": "produce"}
        # 不全→这个设施类型已有多个→离开找缺失的
        if (facility.facility_type == "farm" and has_farm) or \
           (facility.facility_type == "lumbermill" and has_lumb) or \
           (facility.facility_type == "mine" and has_mine):
            target = _find_missing_resource(w, gs, pid, has_farm, has_lumb, has_mine)
            if target:
                return _move_to(w, ui, gs, target, rng)
        return {"unit_idx": ui, "type": "produce"}

    # 可建且缺失该类型→建造
    if buildable and not facility:
        need = ((buildable == "farm" and not has_farm) or
                (buildable == "lumbermill" and not has_lumb) or
                (buildable == "mine" and not has_mine))
        if need:
            return {"unit_idx": ui, "type": "build"}

    # 去最近缺失资源
    target = _find_missing_resource(w, gs, pid, has_farm, has_lumb, has_mine)
    if target:
        return _move_to(w, ui, gs, target, rng)

    return {"unit_idx": ui, "type": "end_turn"}


def _find_missing_resource(w, gs, pid, has_farm, has_lumb, has_mine):
    """找最近缺失资源的可建格"""
    def td(a, b, s): return min(abs(b-a), s-abs(b-a))
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            terrain = get_terrain(gs.grid, x, y)
            buildable = terrain_buildable(terrain)
            if not buildable:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            needed = ((buildable == "farm" and not has_farm) or
                      (buildable == "lumbermill" and not has_lumb) or
                      (buildable == "mine" and not has_mine))
            if not needed:
                continue
            d = td(w.x, x, gs.size) + td(w.y, y, gs.size)
            if d < best_d:
                best_d = d; best = (x, y)
    return best


def _combat_ai(u, ui, gs, pid, opp_city, rng):
    """战斗单位: 向敌方城市推进，邻格有敌→攻击"""
    # 检查邻格有敌
    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        nx, ny = (u.x+dx)%gs.size, (u.y+dy)%gs.size
        enemy = next((eu for eu in gs.units
                      if eu.alive and eu.player_id != pid
                      and eu.x == nx and eu.y == ny), None)
        if enemy:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}
    # 向敌城推进
    return _push_toward(u, ui, gs, opp_city, rng)


def _push_toward(u, ui, gs, target, rng):
    """向目标格移动"""
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    def td(a, b, s): return min(abs(b-a), s-abs(b-a))
    best, best_d = [], 999
    for mv in legal:
        nx, ny = (u.x+mv[0])%gs.size, (u.y+mv[1])%gs.size
        d = td(nx, target.x, gs.size) + td(ny, target.y, gs.size)
        if d < best_d:
            best_d = d; best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _move_to(u, ui, gs, target, rng):
    """移动到目标坐标"""
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    def td(a, b, s): return min(abs(b-a), s-abs(b-a))
    best, best_d = [], 999
    for mv in legal:
        nx, ny = (u.x+mv[0])%gs.size, (u.y+mv[1])%gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        if d < best_d:
            best_d = d; best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _pick_unit(econ):
    """选能买得起的战斗单位，偏好低成本"""
    for ut in ["infantry", "archer", "cavalry"]:
        if econ.can_afford(UNIT_COST[ut]):
            return ut
    return None
