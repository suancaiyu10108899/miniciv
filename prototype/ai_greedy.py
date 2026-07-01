# prototype/ai_greedy.py — 贪心AI v2: 战术意识+建设倾向
import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """贪心AI v2: 研究优先, 建设倾向, 战术意识"""
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

    # 战术优先级: 弓手最先行动(站位), 然后步兵/骑兵
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type != "archer" and u.unit_type != "worker"]
    workers = [u for u in units if u.unit_type == "worker"]
    scouts = [u for u in units if u.unit_type == "scout"]

    for u in archers + fighters + scouts:
        ui = units.index(u)
        if ui in done_units:
            continue
        act = _greedy_combat(u, ui, gs, pid, opp_city, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    for u in workers:
        ui = units.index(u)
        if ui in done_units:
            continue
        act = _greedy_worker(u, ui, gs, pid, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    # === 研究优先 (先研究再生产) ===
    if tech.researching is None:
        avail = tech.available_to_research()
        avail.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
        for t in avail:
            if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    # === 生产 (研究后剩余资源) ===
    for ut in ["cavalry", "archer", "infantry"]:
        if econ.can_afford(UNIT_COST[ut]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
            break

    return actions


def _city_is_safe(gs, pid) -> bool:
    """检查己方城市是否安全(2格内无敌军)"""
    my_city = gs.cities[pid]
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = td(eu.x, my_city.x, gs.size) + td(eu.y, my_city.y, gs.size)
            if d <= 2:
                return False
    return True


def _greedy_worker(w, ui, gs, pid, rng):
    """工人：建缺失设施 > 生产 > 移动找资源"""
    terrain = get_terrain(gs.grid, w.x, w.y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[w.y][w.x].get("facility")

    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}
    best = _nearest_buildable(w, gs, pid)
    if best:
        return _move_to(w, ui, gs, best, rng)
    return {"unit_idx": ui, "type": "end_turn"}


def _greedy_combat(u, ui, gs, pid, opp_city, rng):
    """战斗单位 v2: 残血撤退 > 守城 > 弓手射程 > 攻击邻敌 > 推进"""
    my_city = gs.cities[pid]
    max_hp = 100 if u.unit_type == "infantry" else (80 if u.unit_type == "cavalry" else (60 if u.unit_type == "archer" else 40))
    hp_pct = u.hp / max_hp

    # 残血撤退: HP<30% 且附近有敌人→向己方城市撤退
    if hp_pct < 0.3:
        def td(a, b, s): return min(abs(b - a), s - abs(b - a))
        near_enemy = False
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = td(eu.x, u.x, gs.size) + td(eu.y, u.y, gs.size)
                if d <= 2:
                    near_enemy = True
                    break
        if near_enemy:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng, prefer_defense=True)

    # === 弓手射程纪律 ===
    if u.ranged:
        def td(a, b, s): return min(abs(b - a), s - abs(b - a))
        # 找最近敌方单位
        nearest_enemy = None
        nearest_dist = 999
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = td(eu.x, u.x, gs.size) + td(eu.y, u.y, gs.size)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_enemy = eu
        if nearest_enemy:
            if nearest_dist <= 2:
                # 敌人在射程内, 保持距离射击(不移动, 或找高地)
                # 如果敌人就在邻格→后退
                if nearest_dist == 1:
                    return _retreat_from(u, ui, gs, nearest_enemy, rng)
                return {"unit_idx": ui, "type": "end_turn"}  # 原地射击
            else:
                # 接近目标但保持距离
                return _approach_archer(u, ui, gs, nearest_enemy, rng)
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)

    # === 守城逻辑 ===
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    # 敌人在我城邻格→攻击驱逐
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                           if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 有敌接近我城(距离≤2)→拦截
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


def _retreat_from(unit, ui, gs, enemy, rng):
    """远离敌人一步"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_d = [], -1
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, enemy.x, gs.size) + td(ny, enemy.y, gs.size)
        if d > best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _approach_archer(unit, ui, gs, target, rng):
    """弓手接近目标但保持射击距离(2格)"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, target.x, gs.size) + td(ny, target.y, gs.size)
        score = -abs(d - 2)  # 最优距离=2
        # 地形偏好
        t = get_terrain(gs.grid, nx, ny)
        score += terrain_def_bonus(t) * 0.1
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.01:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


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


def _move_to(unit, ui, gs, target, rng, prefer_defense=False):
    """向目标移动一步, 可选地形偏好"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        # 地形偏好: 防御加成高的格子更优
        terrain = get_terrain(gs.grid, nx, ny)
        def_bonus = terrain_def_bonus(terrain)
        # 基础分: 距离越近越好
        score = -d
        # 地形加分
        score += def_bonus * 0.15
        # 撤退模式: 防御加成权重更高
        if prefer_defense:
            score += def_bonus * 0.3
        # 避免撞到障碍物
        if terrain == Terrain.WATER:
            score -= 100
        if terrain == Terrain.MOUNTAIN and not unit.can_enter_mountain:
            score -= 100
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}
