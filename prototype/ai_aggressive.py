# prototype/ai_aggressive.py — 进攻型AI v3: 战术意识+绕路+波浪进攻
import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """进攻AI v3: 战略评估→绕路/波浪进攻/发育节奏"""
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    my_city = gs.cities[pid]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []

    # 战略评估
    assessment = _strategic_assess(gs, pid)

    # 设施统计
    facs = _count_facs(gs, pid)
    has_f, has_l, has_m = facs["farm"] > 0, facs["lumbermill"] > 0, facs["mine"] > 0

    # 优先级: 侦察→弓手→战斗单位→工人
    scouts = [u for u in units if u.unit_type == "scout"]
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type not in ("archer", "scout", "worker")]
    workers = [u for u in units if u.unit_type == "worker"]

    for u in scouts:
        act = _scout_act(u, units.index(u), gs, pid, opp_city, assessment, rng)
        if act: actions.append(act)

    for u in archers:
        act = _archer_act(u, units.index(u), gs, pid, opp_city, assessment, rng)
        if act: actions.append(act)

    for u in fighters:
        act = _fighter_act(u, units.index(u), gs, pid, opp_city, assessment, rng)
        if act: actions.append(act)

    for u in workers:
        act = _aggro_worker(u, units.index(u), gs, pid, has_f, has_l, has_m, rng)
        if act: actions.append(act)

    # === v3.4 研究: 军事优势时走C线, 否则战斗优先 ===
    military_advantage = (assessment["my_power"] > assessment["opp_power"] * 0.8)
    stalemate = (gs.turn > 45 and assessment.get("opp_frontline_count", 0) >= assessment.get("my_frontline_count", 1) * 0.8)
    c5_done = "C5" in tech.completed

    if tech.researching is None:
        # C5 available → research immediately
        avail = tech.available_to_research()
        if "C5" in avail and econ.can_afford(TECH_TREE_COST.get("C5", (99,99,99))):
            actions.append({"unit_idx": -1, "type": "research", "tech_id": "C5"})
        elif stalemate or c5_done:
            # 建设模式: C线优先
            c_avail = [t for t in avail if t.startswith("C")]
            c_avail.sort(key=lambda t: TECH_TREE_COST.get(t, (0,0,0))[0])
            for t in c_avail:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break
        else:
            # 正常: 战斗+经济+建设混合顺序
            order = ["M1", "C1", "M2", "E1", "C2", "M3", "E2", "C3", "M4", "E3", "C4", "E4", "C5"]
            for t in order:
                if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break

    # === v3.4 生产: worker补充 + 波浪进攻 ===
    n_workers = len(workers)
    n_combat = len(fighters) + len(archers)

    # Worker production: maintain 4 for economy
    if n_workers < 4 and econ.food >= 12 and n_combat >= 2:
        if econ.can_afford(UNIT_COST["worker"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "worker"})

    frontline = assessment["my_frontline_count"]
    surge = assessment["enemy_defense_strong"] and frontline < 4

    if stalemate or c5_done:
        # Construction/defense: diverse units
        if econ.can_afford(UNIT_COST["cavalry"]) and econ.gold >= 10:
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "cavalry"})
        elif econ.can_afford(UNIT_COST["archer"]) and econ.wood >= 8:
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "archer"})
        elif econ.can_afford(UNIT_COST["infantry"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})
    elif surge:
        if econ.can_afford(UNIT_COST["cavalry"]) and econ.food > 15:
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "cavalry"})
        elif econ.can_afford(UNIT_COST["infantry"]) and frontline < 3:
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})
    else:
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

    return actions


def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def _strategic_assess(gs, pid) -> dict:
    """战场战略评估"""
    my_city = gs.cities[pid]
    opp_city = gs.cities[1 - pid]
    opp = 1 - pid
    size = gs.size

    # 统计敌我兵力
    my_combat = [u for u in gs.units if u.player_id == pid and u.alive and u.unit_type not in ("worker",)]
    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive and u.unit_type not in ("worker",)]

    # 前线: 距离敌城≤6的单位
    my_frontline = [u for u in my_combat if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6]
    opp_frontline = [u for u in opp_combat if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6]

    # 敌方防线强度: 敌城周围区域的敌军密度
    opp_near_their_city = [u for u in opp_combat if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 4]

    # 找防御薄弱点: 离敌城3格内的四个方向, 哪个方向敌人最少
    weak_point = None
    min_enemies = 999
    for dx, dy in [(3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, 2), (2, -2), (-2, -2)]:
        wx, wy = (opp_city.x + dx) % size, (opp_city.y + dy) % size
        nearby = sum(1 for u in opp_combat if _td(u.x, wx, size) + _td(u.y, wy, size) <= 3)
        if nearby < min_enemies:
            min_enemies = nearby
            weak_point = (wx, wy)

    return {
        "my_frontline_count": len(my_frontline),
        "opp_frontline_count": len(opp_frontline),
        "opp_near_city_count": len(opp_near_their_city),
        "enemy_defense_strong": len(opp_near_their_city) >= 3,
        "weak_point": weak_point,
        "my_power": sum(u.atk for u in my_combat),
        "opp_power": sum(u.atk for u in opp_combat),
    }


def _scout_act(u, ui, gs, pid, opp_city, assess, rng):
    """侦察兵: 找薄弱点→标记→存活优先"""
    my_city = gs.cities[pid]
    size = gs.size

    # 如果敌人在邻格→逃跑
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        if any(eu.alive and eu.player_id != pid and eu.x == nx and eu.y == ny for eu in gs.units):
            return _retreat(u, ui, gs, rng)

    # 如果有薄弱点→去侦察
    wp = assess["weak_point"]
    if wp:
        return _move_to(u, ui, gs, wp, rng)

    # 否则绕过已知敌军区域, 迂回接近敌城
    return _flank_move(u, ui, gs, opp_city, pid, rng)


def _archer_act(u, ui, gs, pid, opp_city, assess, rng):
    """弓手: 找高地→保持距离射击"""
    size = gs.size
    # 敌人在射程内→原地射击(弓手的远程攻击在移动时自动触发)
    has_target = False
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, u.x, size) + _td(eu.y, u.y, size)
            if d <= 2:
                has_target = True
                break
    if has_target:
        # 在射程内且有敌人邻格→后退保持距离
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = (u.x + dx) % size, (u.y + dy) % size
            if any(eu.alive and eu.player_id != pid and eu.x == nx and eu.y == ny for eu in gs.units):
                return _retreat(u, ui, gs, rng)
        return {"unit_idx": ui, "type": "end_turn"}  # 安全距离射击

    # 向敌城接近但保持距离
    return _approach_ranged(u, ui, gs, opp_city, rng)


def _fighter_act(u, ui, gs, pid, opp_city, assess, rng):
    """战斗单位(步兵/骑兵): 守城>拦截>绕路进攻>波浪推进"""
    my_city = gs.cities[pid]
    size = gs.size

    # === 残血撤退 ===
    max_hp = 100 if u.unit_type == "infantry" else 80
    if u.hp < max_hp * 0.25:
        near_enemy = any(_td(eu.x, u.x, size) + _td(eu.y, u.y, size) <= 2
                        for eu in gs.units if eu.alive and eu.player_id != pid)
        if near_enemy:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng)

    # === 守城 ===
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # === 拦截接近我城的敌人 ===
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, my_city.x, size) + _td(eu.y, my_city.y, size)
            if d <= 2:
                return _move_to(u, ui, gs, (eu.x, eu.y), rng)

    # === 攻击邻格敌人 ===
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        target = next((eu for eu in gs.units if eu.alive and eu.player_id != pid
                       and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # === 波浪进攻判断 ===
    # 如果我在前线且兵力不足→等待队友
    dist_to_opp = _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size)
    if dist_to_opp <= 5 and assess["enemy_defense_strong"]:
        if assess["my_frontline_count"] < 4:
            # 兵力不足→占据有利防御地形等待
            return _hold_position(u, ui, gs, opp_city, rng)

    # === 绕路进攻 ===
    if assess["enemy_defense_strong"] and dist_to_opp <= 6:
        wp = assess["weak_point"]
        if wp:
            return _move_to(u, ui, gs, wp, rng)

    # === 直冲向敌城 ===
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _flank_move(u, ui, gs, target, pid, rng):
    """绕路移动: 优先选择远离敌方单位的路径"""
    size = gs.size
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}

    best, best_score = [], -999
    for mv in legal:
        nx, ny = (u.x + mv[0]) % size, (u.y + mv[1]) % size
        # 基础: 向目标接近
        dist = _td(nx, target.x, size) + _td(ny, target.y, size)
        score = -dist

        # 绕路: 避开有敌方单位的格子
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _td(nx, eu.x, size) + _td(ny, eu.y, size)
                if d <= 1:
                    score -= 50  # 靠近敌人=危险
                elif d <= 2:
                    score -= 10

        # 地形偏好
        terrain = get_terrain(gs.grid, nx, ny)
        if terrain == Terrain.WATER or (terrain == Terrain.MOUNTAIN and not u.can_enter_mountain):
            score -= 100
        else:
            score += terrain_def_bonus(terrain) * 0.2

        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)

    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _hold_position(u, ui, gs, target, rng):
    """占据有利地形等待援军"""
    size = gs.size
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}

    best, best_score = [], -999
    for mv in legal:
        nx, ny = (u.x + mv[0]) % size, (u.y + mv[1]) % size
        terrain = get_terrain(gs.grid, nx, ny)
        # 高防御值好, 同时不太远离目标
        dist = _td(nx, target.x, size) + _td(ny, target.y, size)
        score = terrain_def_bonus(terrain) * 2 - dist * 0.5

        if terrain == Terrain.WATER or (terrain == Terrain.MOUNTAIN and not u.can_enter_mountain):
            score -= 100

        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)

    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _retreat(u, ui, gs, rng):
    """远离所有敌方单位"""
    size = gs.size
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (u.x + mv[0]) % size, (u.y + mv[1]) % size
        # 最大化与最近敌人的距离
        min_dist = min((_td(nx, eu.x, size) + _td(ny, eu.y, size)
                       for eu in gs.units if eu.alive and eu.player_id != u.player_id), default=99)
        score = min_dist * 10
        terrain = get_terrain(gs.grid, nx, ny)
        if terrain == Terrain.WATER: score -= 100
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _approach_ranged(u, ui, gs, target, rng):
    """弓手接近目标但保持距离"""
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    size = gs.size
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (u.x + mv[0]) % size, (u.y + mv[1]) % size
        d = _td(nx, target.x, size) + _td(ny, target.y, size)
        score = -abs(d - 2) * 5  # 最优距离=2
        t = get_terrain(gs.grid, nx, ny)
        score += terrain_def_bonus(t) * 0.5
        if t == Terrain.WATER: score -= 100
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _aggro_worker(w, ui, gs, pid, has_f, has_l, has_m, rng):
    """进攻型工人 v3.4: 建缺失设施 → C5后扩展 → 生产"""
    terrain = get_terrain(gs.grid, w.x, w.y)
    buildable = terrain_buildable(terrain)
    fac = gs.grid[w.y][w.x].get("facility")
    c5_done = "C5" in gs.techs[pid].completed
    stalemate = gs.turn > 35

    # On existing facility: expand if construction mode, else produce
    if fac and fac.player_id == pid:
        if c5_done or stalemate:
            # Need more facilities for victory → find new buildable tile
            target = _nearest_any_buildable(w, gs, pid)
            if target:
                return _move_to(w, ui, gs, target, rng)
        return {"unit_idx": ui, "type": "produce"}

    # Build missing facility type first
    need = ((buildable == "farm" and not has_f) or
            (buildable == "lumbermill" and not has_l) or
            (buildable == "mine" and not has_m))
    if buildable and not fac and (need or c5_done or stalemate):
        return {"unit_idx": ui, "type": "build"}

    target = _nearest_missing(w, gs, pid, has_f, has_l, has_m)
    if not target and (c5_done or stalemate):
        target = _nearest_any_buildable(w, gs, pid)
    if target:
        return _move_to(w, ui, gs, target, rng)
    return {"unit_idx": ui, "type": "end_turn"}


def _nearest_any_buildable(unit, gs, pid):
    """Find nearest buildable tile, regardless of facility type (for expansion)."""
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            b = terrain_buildable(get_terrain(gs.grid, x, y))
            if not b:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            d = _td(unit.x, x, gs.size) + _td(unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


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
            if not b: continue
            if gs.grid[y][x].get("facility"): continue
            need = ((b == "farm" and not has_f) or
                    (b == "lumbermill" and not has_l) or
                    (b == "mine" and not has_m))
            if not need: continue
            d = td(unit.x, x, gs.size) + td(unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _move_to(unit, ui, gs, target, rng):
    """向目标移动一步, 地形偏好"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        terrain = get_terrain(gs.grid, nx, ny)
        def_bonus = terrain_def_bonus(terrain)
        score = -d + def_bonus * 0.15
        if terrain == Terrain.WATER: score -= 100
        if terrain == Terrain.MOUNTAIN and not unit.can_enter_mountain: score -= 100
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}
