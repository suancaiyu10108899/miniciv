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

    # 城市生产（偏向战斗单位，有资源就造）
    if rng.random() < 0.7:
        preferred = _prefer_combat_unit(econ, tech)
        if preferred:
            actions.append({"unit_idx": -1, "type": "produce_unit",
                           "unit_type": preferred})

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
    """工人 AI：确保三类设施各≥1 → 然后生产"""
    x, y = worker.x, worker.y
    terrain = get_terrain(gs.grid, x, y)
    facility = gs.grid[y % gs.size][x % gs.size].get("facility")
    has_farm, has_lumb, has_mine = _count_my_facilities(gs, pid)

    # 如果设施不全且当前格已有设施→离开去找缺失的
    if facility and facility.player_id == pid:
        if has_farm and has_lumb and has_mine:
            return {"unit_idx": ui, "type": "produce"}  # 齐了，生产
        # 不全→去建缺失的
        target = _find_nearest_resource(worker, gs, pid)
        if target:
            return _move_toward(worker, ui, gs, target, rng)

    # 当前格可建→只在缺少该类型时建
    buildable = terrain_buildable(terrain)
    if buildable and not facility:
        need = ((buildable == "farm" and not has_farm) or
                (buildable == "lumbermill" and not has_lumb) or
                (buildable == "mine" and not has_mine))
        if need:
            return {"unit_idx": ui, "type": "build"}

    # 去最近的新资源
    target = _find_nearest_resource(worker, gs, pid)
    if target:
        return _move_toward(worker, ui, gs, target, rng)

    return {"unit_idx": ui, "type": "end_turn"}


def _count_my_facilities(gs, pid):
    """统计pid玩家已有哪些类型的设施"""
    has_farm = has_lumb = has_mine = False
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                if f.facility_type == "farm": has_farm = True
                elif f.facility_type == "lumbermill": has_lumb = True
                elif f.facility_type == "mine": has_mine = True
    return has_farm, has_lumb, has_mine


def _move_toward(unit, ui, gs, target, rng):
    """向目标格移动一步"""
    tx, ty = target
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    # 选最接近目标的方向
    def td(a, b, s): return min(abs(b-a), s-abs(b-a))
    best = []
    best_dist = 999
    for mv in legal:
        nx = (unit.x + mv[0]) % gs.size
        ny = (unit.y + mv[1]) % gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        if d < best_dist:
            best_dist = d; best = [mv]
        elif d == best_dist:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


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
    has_farm, has_lumb, has_mine = _count_my_facilities(gs, pid)

    def td(a, b, s): return min(abs(b-a), s-abs(b-a))

    targets = []
    for y in range(gs.size):
        for x in range(gs.size):
            terrain = get_terrain(gs.grid, x, y)
            buildable = terrain_buildable(terrain)
            if buildable is None:
                continue
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                continue  # 跳过已有己方设施的格
            if f:
                continue  # 敌方设施跳过
            is_new = ((buildable == "farm" and not has_farm) or
                      (buildable == "lumbermill" and not has_lumb) or
                      (buildable == "mine" and not has_mine))
            d = td(worker.x, x, gs.size) + td(worker.y, y, gs.size)
            targets.append((d, is_new, x, y))

    if not targets:
        return None
    targets.sort(key=lambda t: (not t[1], t[0]))
    return (targets[0][2], targets[0][3])


def _prefer_combat_unit(econ, tech):
    """返回当前应生产的战斗单位。优先能买得起的，偏向多样性。"""
    # 优先顺序：骑兵(最贵但最强) > 弓箭 > 步兵(最便宜)
    order = ["cavalry", "archer", "infantry", "scout"]
    for ut in order:
        c = UNIT_COST[ut]
        if econ.can_afford(c):
            return ut
    return None
