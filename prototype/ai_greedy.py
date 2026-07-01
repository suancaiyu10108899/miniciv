# prototype/ai_greedy.py — 贪心AI：每步选当前最优动作

import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """贪心AI：每个单位+城市选评分最高的动作"""
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    my_city = gs.cities[pid]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []
    done_units = set()

    for ui, u in enumerate(units):
        if ui in done_units:
            continue
        if u.unit_type == "worker":
            act = _greedy_worker(u, ui, gs, pid, rng)
        else:
            act = _greedy_combat(u, ui, gs, pid, opp_city, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    # 生产：有资源就造
    for ut in ["cavalry", "archer", "infantry"]:
        if econ.can_afford(UNIT_COST[ut]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
            break

    # 研究：选买得起的最贵的
    if tech.researching is None:
        avail = tech.available_to_research()
        avail.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
        for t in avail:
            if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    return actions


def _greedy_worker(w, ui, gs, pid, rng):
    """工人：建缺失设施 > 生产 > 移动找资源"""
    x, y = w.x, w.y
    terrain = get_terrain(gs.grid, x, y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[y][x].get("facility")

    # 已有设施→生产
    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}

    # 可建→建造
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}

    # 移动找最近的资源
    best = _nearest_buildable(w, gs, pid)
    if best:
        return _move_to(w, ui, gs, best, rng)
    return {"unit_idx": ui, "type": "end_turn"}


def _greedy_combat(u, ui, gs, pid, opp_city, rng):
    """战斗单位：守城 > 攻击邻敌 > 向敌城推进"""
    my_city = gs.cities[pid]

    # 优先: 敌人在我城邻格→攻击驱逐
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                           if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 有敌接近我城(距离≤2)→拦截
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = td(eu.x, my_city.x, gs.size) + td(eu.y, my_city.y, gs.size)
            if d <= 2:
                return _move_to(u, ui, gs, (eu.x, eu.y), rng)

    # 攻击邻格敌人
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        target = next((eu for eu in gs.units
                       if eu.alive and eu.player_id != pid
                       and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 向敌城推进
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _nearest_buildable(unit, gs, pid):
    """找最近可建资源格"""
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            b = terrain_buildable(get_terrain(gs.grid, x, y))
            if not b:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            d = td(unit.x, x, gs.size) + td(unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _move_to(unit, ui, gs, target, rng):
    """贪心向目标移动一步"""
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
