# prototype/ai_rulesrandom.py — 最低合理基线 AI
# 不会自杀。不会乱走。不会随机研究然后取消。

import random as _random
from prototype.unit import Unit, City
from prototype.movement import get_single_step_moves, apply_move
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable
from prototype.constants import UNIT_COST


def ai_decide(gs, pid: int, rng: _random.Random | None = None) -> list[dict]:
    """
    为 pid 玩家的所有单位 + 城市决策本回合动作。
    返回: [{"unit_idx": N, "type": "...", ...}, ...] ——每个单位的动作。

    决策优先级:
    - 工人: 最近无设施资源格→走过去建。有设施→生产。已建完→找下一个。
    - 侦察兵: 探索未访问区域（随机合法方向，偏向未见过地形）
    - 其他: 向对方城市移动。邻格有敌→攻击。
    - 城市: 50%概率造最便宜单位（资源够时）
    - 研究: 槽位空→研究最便宜可用科技
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)

    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []
    assigned = set()  # 本回合已分配动作的单位 idx

    for ui, u in enumerate(units):
        if ui in assigned:
            continue

        if u.unit_type == "worker":
            act = _worker_action(u, ui, gs, pid, econ, rng)
        elif u.unit_type == "scout":
            act = _scout_action(u, ui, gs, rng)
        else:
            act = _combat_action(u, ui, gs, pid, opp_city, rng)

        if act:
            actions.append(act)
            assigned.add(ui)

    # 城市生产
    if rng.random() < 0.5:
        cheapest = _cheapest_affordable(econ)
        if cheapest:
            actions.append({"unit_idx": -1, "type": "produce_unit",
                           "unit_type": cheapest})

    # 研究
    if tech.researching is None:
        available = tech.available_to_research()
        # 按总花费排序，选第一个买得起的
        available.sort(key=lambda t: sum(TECH_TREE_COST.get(t, (99, 99, 99))))
        for t in available:
            cost = TECH_TREE_COST.get(t, (99, 99, 99))
            if econ.can_afford(cost):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    return actions


from prototype.constants import TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def _worker_action(worker, ui, gs, pid, econ, rng):
    """工人 AI"""
    x, y = worker.x, worker.y
    terrain = get_terrain(gs.grid, x, y)

    # 1. 当前格已有己方设施→生产
    facility = gs.grid[y % gs.size][x % gs.size].get("facility")
    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}

    # 2. 当前格可建且未建→建造
    buildable = terrain_buildable(terrain)
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}

    # 3. 移动到最近的可建/可生产格
    target = _find_nearest_resource(worker, gs, pid)
    if target:
        tx, ty = target
        dx = 1 if tx > x else (-1 if tx < x else 0)
        dy = 1 if ty > y else (-1 if ty < y else 0)
        # 简单：只走一步
        legal = get_single_step_moves(worker, gs.grid)
        if (dx, dy) in legal:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}
        # 尝试任意合法方向
        if legal:
            mv = rng.choice(legal)
            return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}

    return {"unit_idx": ui, "type": "end_turn"}


def _scout_action(scout, ui, gs, rng):
    """侦察兵 AI：随机探索"""
    legal = get_single_step_moves(scout, gs.grid)
    if legal:
        mv = rng.choice(legal)
        return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}
    return {"unit_idx": ui, "type": "end_turn"}


def _combat_action(unit, ui, gs, pid, opp_city, rng):
    """战斗单位 AI：向敌城推进 + 攻击相邻敌人"""
    x, y = unit.x, unit.y

    # 检查相邻是否有敌（一格内）
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (x + dx) % gs.size, (y + dy) % gs.size
        enemy = next((u for u in gs.units
                      if u.alive and u.player_id != pid
                      and u.x == nx and u.y == ny), None)
        if enemy:
            if unit.ranged:
                return {"unit_idx": ui, "type": "move", "dx": 0, "dy": 0}
                # 弓箭手射程 2，即使不在邻格也能射。简化：如果邻格有敌→射它
                # 实际 ranged 的 target 通过 resolve_ranged，这里先通过 move 触发战斗
            # 近战：移动过去（战斗自动触发）
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 向对方城市移动
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}

    # 选减少到对方城市距离的方向
    best = []
    best_dist = 999
    for mv in legal:
        nx, ny = (x + mv[0]) % gs.size, (y + mv[1]) % gs.size
        # torus distance
        def td(a, b, s): return min(abs(b-a), s-abs(b-a))
        nd = td(nx, opp_city.x, gs.size) + td(ny, opp_city.y, gs.size)
        if nd < best_dist:
            best_dist = nd
            best = [mv]
        elif nd == best_dist:
            best.append(mv)

    mv = rng.choice(best) if best else rng.choice(legal)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _find_nearest_resource(worker, gs, pid):
    """找最近的可建资源格。优先还没有己方设施的资源类型。"""
    # 检查已有设施覆盖了哪些资源类型
    has_farm = has_lumbermill = has_mine = False
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                if f.facility_type == "farm": has_farm = True
                elif f.facility_type == "lumbermill": has_lumbermill = True
                elif f.facility_type == "mine": has_mine = True

    def td(a, b, s): return min(abs(b-a), s-abs(b-a))

    # 优先找还没覆盖的资源类型
    targets = []
    for y in range(gs.size):
        for x in range(gs.size):
            terrain = get_terrain(gs.grid, x, y)
            buildable = terrain_buildable(terrain)
            if buildable is None:
                continue
            # 跳过已有己方设施的格
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                continue
            # 跳过被敌方设施占的格
            if f:
                continue
            # 标记是否是新资源类型
            is_new = ((buildable == "farm" and not has_farm) or
                      (buildable == "lumbermill" and not has_lumbermill) or
                      (buildable == "mine" and not has_mine))
            d = td(worker.x, x, gs.size) + td(worker.y, y, gs.size)
            targets.append((d, is_new, x, y))

    if not targets:
        return None
    # 新资源类型优先，同类型取最近
    targets.sort(key=lambda t: (not t[1], t[0]))
    return (targets[0][2], targets[0][3])


def _cheapest_affordable(econ):
    """返回当前可买的最便宜战斗单位"""
    combat_units = ["infantry", "archer", "cavalry", "scout"]
    affordable = []
    for ut in combat_units:
        c = UNIT_COST[ut]
        if econ.can_afford(c):
            affordable.append((ut, c))
    if not affordable:
        return None
    # 按总花费排序
    affordable.sort(key=lambda x: sum(x[1]))
    return affordable[0][0]
