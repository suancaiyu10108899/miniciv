# prototype_hex/ai_evo_hex.py — Evo AI adapted for hex grid
# Adapted from prototype/ai_evo.py: imports + distance function changed for hex

import json, os, random as _random
from prototype_hex.movement_hex import get_single_step_moves_hex as get_single_step_moves
from prototype_hex.mapgen_hex import get_terrain_hex as get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE

TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}

# ─── 自动加载最佳训练权重 ────────────────────────────
_BEST_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "evo_hex_weights.json")
_EVO_WEIGHTS = None
if os.path.exists(_BEST_WEIGHTS_PATH):
    try:
        with open(_BEST_WEIGHTS_PATH) as _f:
            _data = json.load(_f)
        _EVO_WEIGHTS = _data.get("weights", _data)
    except Exception:
        _EVO_WEIGHTS = None

# ─── 默认权重 ──────────────────────────────────────
# 每个权重有 (默认值, 最小值, 最大值, 描述)
DEFAULT_WEIGHTS = {
    # 攻击相关
    "attack_adjacent":    (1.0, 0.0, 5.0, "攻击邻格敌人的权重"),
    "rush_enemy_city":    (1.0, 0.0, 5.0, "向敌城推进的权重"),
    "defend_own_city":    (1.0, 0.0, 5.0, "防守己方城市的权重"),
    "intercept_near_city":(0.8, 0.0, 5.0, "拦截接近城市的敌人的权重"),

    # 撤退/生存
    "retreat_hp_threshold": (0.3, 0.0, 0.8, "撤退HP阈值(比例)"),
    "terrain_def_weight":   (0.15, 0.0, 1.0, "移动时看重地形防御加成的权重"),
    "retreat_terrain_bonus":(0.3, 0.0, 1.0, "撤退时额外看重防御加成"),

    # 弓手策略
    "archer_keep_distance": (1.0, 0.0, 5.0, "弓手保持最佳射程的权重"),
    "archer_prefer_high":   (0.1, 0.0, 1.0, "弓手优先占高防御地形的权重"),

    # 经济/工人
    "build_efficiency":     (1.0, 0.0, 3.0, "工人优先建造设施(vs.移动)"),
    "resource_variety":     (1.0, 0.0, 3.0, "优先补全缺失资源类型"),

    # 科技
    "research_priority":    (1.0, 0.0, 3.0, "优先研究的倾向"),
    "military_tech_bias":   (0.5, 0.0, 1.0, "军事科技(M线)相对于经济的偏向"),

    # 生产
    "cavalry_production":   (1.0, 0.0, 3.0, "生产骑兵的倾向"),
    "archer_production":    (1.0, 0.0, 3.0, "生产弓手的倾向"),
}


def random_weights(rng: _random.Random | None = None) -> dict:
    """生成随机权重向量, 每个权重在[min, max]均匀采样"""
    if rng is None:
        rng = _random.Random()
    return {
        k: rng.uniform(v[1], v[2])
        for k, v in DEFAULT_WEIGHTS.items()
    }


def mutate_weights(weights: dict, rate: float = 0.15,
                   scale: float = 0.2, rng: _random.Random | None = None) -> dict:
    """高斯变异: 每个权重以 rate 概率被扰动 scale * 范围"""
    if rng is None:
        rng = _random.Random()
    result = {}
    for k, v in weights.items():
        if rng.random() < rate:
            lo, hi = DEFAULT_WEIGHTS[k][1], DEFAULT_WEIGHTS[k][2]
            noise = rng.gauss(0, scale * (hi - lo))
            result[k] = max(lo, min(hi, v + noise))
        else:
            result[k] = v
    return result


def crossover_weights(a: dict, b: dict, rng: _random.Random | None = None) -> dict:
    """均匀交叉: 每个权重随机从父母一方继承"""
    if rng is None:
        rng = _random.Random()
    return {k: a[k] if rng.random() < 0.5 else b[k] for k in a}


def td(a: int, b: int, s: int) -> int:
    """环面曼哈顿单轴距离（保留接口兼容，实际使用 hex_distance）"""
    return min(abs(b - a), s - abs(b - a))

def _hex_dist(x1, y1, x2, y2, size):
    """六边形环面距离"""
    from prototype_hex.movement_hex import hex_distance
    return hex_distance(x1, y1, x2, y2)


def _list_my_facilities(gs, pid):
    """返回 [(x, y, type), ...]"""
    result = []
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                result.append((x, y, f.facility_type))
    return result


def _nearest_buildable(unit, gs, pid):
    """找最近可建资源格"""
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            b = terrain_buildable(get_terrain(gs.grid, x, y))
            if not b:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            d = _hex_dist(unit.x, x, unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _find_missing_resource(w, gs, pid, has_farm, has_lumb, has_mine):
    """找最近缺失资源的可建格"""
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
            d = _hex_dist(w.x, x, w.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


# ─── EVO AI 决策函数 ─────────────────────────────

def ai_decide(gs, pid: int, rng=None, weights: dict = None) -> list[dict]:
    """
    权重参数化 AI 主入口。

    参数:
        gs: GameState
        pid: 玩家 ID (0 或 1)
        rng: 随机数生成器
        weights: 权重字典 {name: float}。None 则使用默认值。
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    if weights is None:
        if _EVO_WEIGHTS is not None:
            weights = _EVO_WEIGHTS
        else:
            weights = {k: v[0] for k, v in DEFAULT_WEIGHTS.items()}

    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    my_city = gs.cities[pid]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []
    done_units = set()

    w = weights  # shorthand

    # 战术顺序: 弓手先动(站位) -> 近战单位 -> 侦察兵 -> 工人
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type not in ("archer", "worker")]
    scouts = [u for u in units if u.unit_type == "scout"]
    workers = [u for u in units if u.unit_type == "worker"]

    for u in archers + fighters + scouts:
        ui = _find_unit_index(units, u)
        if ui is None or ui in done_units:
            continue
        act = _evo_combat(u, ui, gs, pid, opp_city, my_city, w, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    for u in workers:
        ui = _find_unit_index(units, u)
        if ui is None or ui in done_units:
            continue
        act = _evo_worker(u, ui, gs, pid, w, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    # === 研究 ===
    if tech.researching is None:
        avail = tech.available_to_research()
        if avail:
            # 划分M线与E线
            m_techs = [t for t in avail if t.startswith("M")]
            e_techs = [t for t in avail if t.startswith("E")]
            c_techs = [t for t in avail if t.startswith("C")]

            # 按military_tech_bias选择优先路线
            if m_techs and e_techs:
                if rng.random() < w["military_tech_bias"]:
                    preferred = m_techs
                else:
                    preferred = e_techs
            elif m_techs:
                preferred = m_techs
            elif e_techs:
                preferred = e_techs
            else:
                preferred = avail

            preferred.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
            for t in preferred:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break

        # 偏好C线的补充检查
        if tech.researching is None:
            for t in c_techs if 'c_techs' in dir() else []:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break

    # === 生产 (研究后剩余资源) ===
    # 按权重决定生产顺序
    prod_scores = {
        "cavalry": w["cavalry_production"],
        "archer": w["archer_production"],
        "infantry": 1.0,  # 基准
    }
    ordered = sorted(prod_scores.keys(), key=lambda ut: -prod_scores[ut])
    for ut in ordered:
        if econ.can_afford(UNIT_COST[ut]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
            break

    return actions


def _find_unit_index(units, target):
    """在units列表中找target的索引"""
    for i, u in enumerate(units):
        if u is target:
            return i
    return None


def _evo_combat(u, ui, gs, pid, opp_city, my_city, w, rng):
    """权重参数化的战斗单位决策"""
    max_hp = {"infantry": 100, "cavalry": 80, "archer": 60, "scout": 40}.get(u.unit_type, 100)
    hp_pct = u.hp / max_hp

    # 残血撤退
    if hp_pct < w["retreat_hp_threshold"]:
        near_enemy = False
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _hex_dist(eu.x, u.x, eu.y, u.y, gs.size)
                if d <= 2:
                    near_enemy = True
                    break
        if near_enemy:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng,
                            terrain_weight=w["terrain_def_weight"],
                            retreat_bonus=w["retreat_terrain_bonus"])

    # === 弓手 ===
    if u.ranged:
        nearest_enemy = None
        nearest_dist = 999
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _hex_dist(eu.x, u.x, eu.y, u.y, gs.size)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_enemy = eu
        if nearest_enemy:
            if nearest_dist <= 2:
                if nearest_dist == 1:
                    return _retreat_from(u, ui, gs, nearest_enemy, rng)
                return {"unit_idx": ui, "type": "end_turn"}
            else:
                return _approach_archer(u, ui, gs, nearest_enemy, rng,
                                        dist_weight=w["archer_keep_distance"],
                                        high_ground_weight=w["archer_prefer_high"],
                                        terrain_weight=w["terrain_def_weight"])
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng,
                        terrain_weight=w["terrain_def_weight"])

    # === 非弓手战斗逻辑 ===
    # 1. 我城邻格有敌→攻击驱逐 (权重最高)
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                           if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 2. 有敌接近我城→拦截 (权重参数化)
    if w["intercept_near_city"] > 0:
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _hex_dist(eu.x, my_city.x, eu.y, my_city.y, gs.size)
                if d <= 2:
                    # 拦截概率 = weight
                    if rng.random() < w["intercept_near_city"] / 5.0:
                        return _move_to(u, ui, gs, (eu.x, eu.y), rng,
                                        terrain_weight=w["terrain_def_weight"])
                    break  # 即使不拦截, 也知道了有威胁

    # 3. 攻击邻格敌人 (权重参数化)
    if rng.random() < w["attack_adjacent"] / 5.0:
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
            target = next((eu for eu in gs.units
                           if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # 4. 防守城市 (权重参数化)
    if rng.random() < w["defend_own_city"] / 5.0:
        if _hex_dist(u.x, my_city.x, u.y, my_city.y, gs.size) > 3:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng,
                            terrain_weight=w["terrain_def_weight"])

    # 5. 向敌城推进 (权重参数化)
    if rng.random() < w["rush_enemy_city"] / 5.0:
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng,
                        terrain_weight=w["terrain_def_weight"])

    # 默认: 向敌城推进
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng,
                    terrain_weight=w["terrain_def_weight"])


def _evo_worker(wu, ui, gs, pid, w, rng):
    """权重参数化的工人决策"""
    terrain = get_terrain(gs.grid, wu.x, wu.y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[wu.y][wu.x].get("facility")

    facilities = _list_my_facilities(gs, pid)
    has_farm = any(f[2] == "farm" for f in facilities)
    has_lumb = any(f[2] == "lumbermill" for f in facilities)
    has_mine = any(f[2] == "mine" for f in facilities)
    all_types = (has_farm and has_lumb and has_mine)

    # 已有设施
    if facility and facility.player_id == pid:
        if all_types:
            return {"unit_idx": ui, "type": "produce"}
        # 不全, 是否离开找缺失?(由resource_variety控制)
        if rng.random() < w["resource_variety"] / 3.0:
            target = _find_missing_resource(wu, gs, pid, has_farm, has_lumb, has_mine)
            if target:
                return _move_to(wu, ui, gs, target, rng,
                                terrain_weight=w["terrain_def_weight"])
        return {"unit_idx": ui, "type": "produce"}

    # 可建且缺失该类型→建造
    if buildable and not facility:
        need = ((buildable == "farm" and not has_farm) or
                (buildable == "lumbermill" and not has_lumb) or
                (buildable == "mine" and not has_mine))
        if need:
            if rng.random() < w["build_efficiency"] / 3.0:
                return {"unit_idx": ui, "type": "build"}

    # 去最近缺失资源
    target = _find_missing_resource(wu, gs, pid, has_farm, has_lumb, has_mine)
    if target:
        return _move_to(wu, ui, gs, target, rng,
                        terrain_weight=w["terrain_def_weight"])

    # 找不到就生产
    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}
    return {"unit_idx": ui, "type": "end_turn"}


# ─── 移动辅助函数 ────────────────────────────────

def _retreat_from(unit, ui, gs, enemy, rng):
    """远离敌人一步"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_d = [], -1
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _hex_dist(nx, enemy.x, ny, enemy.y, gs.size)
        if d > best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _approach_archer(unit, ui, gs, target, rng, dist_weight=1.0,
                     high_ground_weight=0.1, terrain_weight=0.15):
    """弓手接近目标但保持最佳射程"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _hex_dist(nx, target.x, ny, target.y, gs.size)
        # 理想距离 = 2 (最佳射程)
        score = -abs(d - 2) * dist_weight
        t = get_terrain(gs.grid, nx, ny)
        score += terrain_def_bonus(t) * terrain_weight
        score += terrain_def_bonus(t) * high_ground_weight
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.01:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _move_to(unit, ui, gs, target, rng, terrain_weight=0.15, retreat_bonus=0.0):
    """向目标移动一步, 地形偏好权重参数化"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _hex_dist(nx, tx, ny, ty, gs.size)
        terrain = get_terrain(gs.grid, nx, ny)
        def_bonus = terrain_def_bonus(terrain)
        score = -d * 3.0 + def_bonus * terrain_weight + def_bonus * retreat_bonus  # hex: weight distance higher
        if terrain == Terrain.WATER:
            score -= 999
        if terrain == Terrain.MOUNTAIN and not unit.can_enter_mountain:
            score -= 999
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}
