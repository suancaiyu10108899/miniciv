# prototype/ai_greedy_v3.py — 贪心AI v3: 战略意识+自适应策略
# Builds on v2 tactical code, adds strategic assessment + opponent modeling
import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


# === Module-level state for opponent modeling ===
_OPPONENT_HISTORY = {}


def _get_opponent_model(gs):
    key = gs.seed
    if key not in _OPPONENT_HISTORY:
        _OPPONENT_HISTORY[key] = {
            "history": [],
            "aggression": 0.5,
            "enemy_unit_types": {},
        }
    return _OPPONENT_HISTORY[key]


def _clean_opponent_history(gs):
    global _OPPONENT_HISTORY
    if len(_OPPONENT_HISTORY) > 100:
        _OPPONENT_HISTORY = {k: v for k, v in list(_OPPONENT_HISTORY.items())[-50:]}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """贪心AI v3: 战略意识+自适应策略（无部队协调）"""
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

    # Strategic assessment
    assessment = _strategic_assess(gs, pid)

    # Opponent modeling
    opp_model = _get_opponent_model(gs)
    _update_opponent_model(opp_model, gs, pid)

    # Adaptive strategy selection
    strategy = _select_strategy(gs, pid, assessment, opp_model)

    # Tactical priority
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type != "archer" and u.unit_type != "worker"]
    workers = [u for u in units if u.unit_type == "worker"]
    scouts = [u for u in units if u.unit_type == "scout"]

    for u in archers + fighters + scouts:
        ui = units.index(u)
        if ui in done_units:
            continue
        act = _greedy_combat_v3(u, ui, gs, pid, opp_city, strategy, assessment, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    for u in workers:
        ui = units.index(u)
        if ui in done_units:
            continue
        act = _greedy_worker_v3(u, ui, gs, pid, strategy, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    # Research (strategy-aware)
    if tech.researching is None:
        _do_research_v3(gs, pid, strategy, actions)

    # Production (strategy-aware)
    _do_production_v3(gs, pid, strategy, assessment, actions)

    _clean_opponent_history(gs)
    return actions


# =============================================================================
# Strategic Assessment
# =============================================================================

def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def _strategic_assess(gs, pid) -> dict:
    opp = 1 - pid
    size = gs.size

    my_combat = [u for u in gs.units if u.player_id == pid and u.alive
                 and u.unit_type not in ("worker",)]
    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive
                  and u.unit_type not in ("worker",)]
    my_count = len(my_combat)
    opp_count = len(opp_combat)
    unit_ratio = my_count / max(opp_count, 1)

    my_econ = gs.economies[pid]
    opp_econ = gs.economies[opp]
    my_total_res = my_econ.food + my_econ.wood + my_econ.gold
    opp_total_res = opp_econ.food + opp_econ.wood + opp_econ.gold
    res_ratio = my_total_res / max(opp_total_res, 1)

    my_techs = len(gs.techs[pid].completed)
    opp_techs = len(gs.techs[opp].completed)
    tech_lead = my_techs - opp_techs

    my_city_hp = gs.cities[pid].hp
    opp_city_hp = gs.cities[opp].hp

    opp_city = gs.cities[opp]
    my_frontline = [u for u in my_combat
                    if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6]
    my_city = gs.cities[pid]
    opp_frontline = [u for u in opp_combat
                     if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6]

    opp_near_their_city = [u for u in opp_combat
                           if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 4]

    weak_point = None
    min_enemies = 999
    for dx, dy in [(3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, 2), (2, -2), (-2, -2)]:
        wx, wy = (opp_city.x + dx) % size, (opp_city.y + dy) % size
        nearby = sum(1 for u in opp_combat if _td(u.x, wx, size) + _td(u.y, wy, size) <= 3)
        if nearby < min_enemies:
            min_enemies = nearby
            weak_point = (wx, wy)

    my_power = sum(u.atk for u in my_combat)
    opp_power = sum(u.atk for u in opp_combat)
    city_threatened = any(
        _td(eu.x, my_city.x, size) + _td(eu.y, my_city.y, size) <= 2
        for eu in opp_combat
    )

    return {
        "my_count": my_count,
        "opp_count": opp_count,
        "unit_ratio": unit_ratio,
        "res_ratio": res_ratio,
        "tech_lead": tech_lead,
        "my_city_hp": my_city_hp,
        "opp_city_hp": opp_city_hp,
        "my_frontline": my_frontline,
        "opp_frontline": opp_frontline,
        "my_frontline_count": len(my_frontline),
        "opp_frontline_count": len(opp_frontline),
        "opp_near_city_count": len(opp_near_their_city),
        "enemy_defense_strong": len(opp_near_their_city) >= 3,
        "weak_point": weak_point,
        "my_power": my_power,
        "opp_power": opp_power,
        "city_threatened": city_threatened,
    }


def _update_opponent_model(opp_model, gs, pid):
    opp = 1 - pid
    size = gs.size
    my_city = gs.cities[pid]
    opp_city = gs.cities[opp]

    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive
                  and u.unit_type not in ("worker",)]

    near_my_city = sum(1 for u in opp_combat
                       if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6)
    near_their_city = sum(1 for u in opp_combat
                          if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6)

    total = len(opp_combat)
    if total > 0:
        aggression = near_my_city / max(total, 1) - near_their_city / max(total, 1)
        aggression = max(-1, min(1, aggression))
        aggression = (aggression + 1) / 2
    else:
        aggression = 0.5

    opp_model["history"].append((gs.turn, aggression))
    opp_model["history"] = [h for h in opp_model["history"] if h[0] > gs.turn - 10]

    if opp_model["history"]:
        opp_model["aggression"] = sum(h[1] for h in opp_model["history"]) / len(opp_model["history"])

    for u in opp_combat:
        opp_model["enemy_unit_types"][u.unit_type] = opp_model["enemy_unit_types"].get(u.unit_type, 0) + 1


def _select_strategy(gs, pid, assessment, opp_model):
    unit_ratio = assessment["unit_ratio"]
    my_count = assessment["my_count"]
    opp_count = assessment["opp_count"]
    aggressiveness = opp_model["aggression"]

    # Early game: always balanced, let economy build up
    if gs.turn < 8:
        return "balanced"

    # Both sides have no combat units yet
    if my_count == 0 and opp_count == 0:
        return "balanced"

    if unit_ratio > 1.3 and my_count >= 3:
        return "aggressive"
    # Only turtle if enemy actually has units near our city
    if assessment["city_threatened"] and my_count < opp_count:
        return "defensive"
    if unit_ratio < 0.6 and opp_count > 2:
        return "defensive"
    if gs.turn > 50 and assessment["opp_city_hp"] >= 95 and assessment["my_city_hp"] >= 95:
        return "construction"
    if aggressiveness > 0.65 and gs.turn > 15:
        if gs.turn > 30:
            return "defensive_construction"
        return "defensive"
    elif aggressiveness < 0.35 and gs.turn > 15:
        return "aggressive"
    return "balanced"


# =============================================================================
# v2 preserved helpers + v3 strategy-aware combat
# =============================================================================

def _greedy_worker_v3(w, ui, gs, pid, strategy, rng):
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


def _greedy_combat_v3(u, ui, gs, pid, opp_city, strategy, assessment, rng):
    """v2 tactical combat + v3 strategic awareness."""
    my_city = gs.cities[pid]
    size = gs.size
    max_hp = 100 if u.unit_type == "infantry" else (80 if u.unit_type == "cavalry" else (60 if u.unit_type == "archer" else 40))
    hp_pct = u.hp / max_hp

    # v2: Retreat when low HP
    if hp_pct < 0.3:
        near_enemy = False
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _td(eu.x, u.x, size) + _td(eu.y, u.y, size)
                if d <= 2:
                    near_enemy = True
                    break
        if near_enemy:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng, prefer_defense=True)

    # v2: Archer range discipline
    if u.ranged:
        nearest_enemy = None
        nearest_dist = 999
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = _td(eu.x, u.x, size) + _td(eu.y, u.y, size)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_enemy = eu
        if nearest_enemy:
            if nearest_dist <= 2:
                if nearest_dist == 1:
                    return _retreat_from(u, ui, gs, nearest_enemy, rng)
                return {"unit_idx": ui, "type": "end_turn"}
            else:
                return _approach_archer(u, ui, gs, nearest_enemy, rng)
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)

    # v2: City defense
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                          if eu.alive and eu.player_id != pid
                          and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, my_city.x, size) + _td(eu.y, my_city.y, size)
            if d <= 2:
                return _move_to(u, ui, gs, (eu.x, eu.y), rng)

    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        target = next((eu for eu in gs.units
                      if eu.alive and eu.player_id != pid
                      and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # v3: Strategic positioning
    if strategy == "defensive" or strategy == "defensive_construction":
        dist_to_my_city = _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size)
        if dist_to_my_city > 3:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng, prefer_defense=True)

    # Push toward enemy city
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


# =============================================================================
# v3: Strategy-aware research
# =============================================================================

def _do_research_v3(gs, pid, strategy, actions):
    tech = gs.techs[pid]
    econ = gs.economies[pid]
    avail = tech.available_to_research()

    if strategy == "aggressive":
        order = ["M1", "M2", "M3", "M4", "C1", "E1", "E2", "E3", "E4", "C2", "C3", "C4", "C5"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    elif strategy == "defensive" or strategy == "defensive_construction":
        order = ["E1", "E2", "E3", "E4", "C1", "M1", "M2", "M3", "M4", "C2", "C3", "C4", "C5"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    elif strategy == "construction":
        order = ["C1", "C2", "C3", "C4", "C5", "E1", "E2", "E3", "E4", "M1", "M2", "M3", "M4"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    else:
        # Balanced: v2-style, pick most expensive available
        avail.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
        for t in avail:
            if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break


# =============================================================================
# v3: Strategy-aware production
# =============================================================================

def _do_production_v3(gs, pid, strategy, assessment, actions):
    econ = gs.economies[pid]

    if strategy == "aggressive":
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break
    elif strategy == "defensive" or strategy == "defensive_construction":
        for ut in ["infantry", "archer", "cavalry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break
    elif strategy == "construction":
        if econ.can_afford(UNIT_COST["infantry"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})
    else:
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break


# =============================================================================
# v2 Helper utilities
# =============================================================================

def _retreat_from(unit, ui, gs, enemy, rng):
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_d = [], -1
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _td(nx, enemy.x, gs.size) + _td(ny, enemy.y, gs.size)
        if d > best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _approach_archer(unit, ui, gs, target, rng):
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _td(nx, target.x, gs.size) + _td(ny, target.y, gs.size)
        score = -abs(d - 2)
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


def _move_to(unit, ui, gs, target, rng, prefer_defense=False):
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _td(nx, tx, gs.size) + _td(ny, ty, gs.size)
        terrain = get_terrain(gs.grid, nx, ny)
        def_bonus = terrain_def_bonus(terrain)
        score = -d
        score += def_bonus * 0.15
        if prefer_defense:
            score += def_bonus * 0.3
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
