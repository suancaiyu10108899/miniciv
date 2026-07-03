# prototype/ai_greedy.py — 贪心AI v4: 战略意识+部队协调+自适应
# Built on v2's tactical code with v3 strategic awareness + v4 force coordination
import random as _random
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


# === Module-level state for opponent modeling (persists across calls) ===
_OPPONENT_HISTORY = {}  # keyed by gs.seed


def _get_opponent_model(gs):
    """Get or create opponent model for this game."""
    key = gs.seed
    if key not in _OPPONENT_HISTORY:
        _OPPONENT_HISTORY[key] = {
            "history": [],  # list of (turn, aggression_score)
            "aggression": 0.5,  # 0=passive, 1=aggressive
            "enemy_unit_types": {},  # count of enemy unit types seen
        }
    return _OPPONENT_HISTORY[key]


def _clean_opponent_history(gs):
    """Remove stale entries from opponent history."""
    global _OPPONENT_HISTORY
    # Keep only entries from the last 10 seeds to prevent memory leak
    if len(_OPPONENT_HISTORY) > 100:
        _OPPONENT_HISTORY = {k: v for k, v in list(_OPPONENT_HISTORY.items())[-50:]}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """贪心AI v4: 战略意识+部队协调+自适应对手"""
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

    # === Strategic Assessment (v3) ===
    assessment = _strategic_assess(gs, pid)

    # === Opponent Modeling (v3) ===
    opp_model = _get_opponent_model(gs)
    _update_opponent_model(opp_model, gs, pid)

    # === Adaptive Strategy Selection (v3) ===
    strategy = _select_strategy(gs, pid, assessment, opp_model)

    # === Tactical Priority ===
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type != "archer" and u.unit_type != "worker"]
    workers = [u for u in units if u.unit_type == "worker"]
    scouts = [u for u in units if u.unit_type == "scout"]

    # === Force Coordination (v4) ===
    rally_point, wave_ready = _compute_force_coordination(gs, pid, assessment)
    production_counter = _compute_adaptive_counter(gs, pid, opp_model)

    for u in archers + fighters + scouts:
        ui = units.index(u)
        if ui in done_units:
            continue
        act = _greedy_combat_v4(u, ui, gs, pid, opp_city, strategy, assessment, rally_point, wave_ready, rng)
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

    # === Research (v3: strategy-aware) ===
    if tech.researching is None:
        _do_research(gs, pid, strategy, actions)

    # === Production (v4: adaptive countering + strategy-aware) ===
    _do_production(gs, pid, strategy, production_counter, assessment, actions)

    _clean_opponent_history(gs)
    return actions


# =============================================================================
# v3: Strategic Assessment
# =============================================================================

def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def _strategic_assess(gs, pid) -> dict:
    """Comprehensive strategic assessment of the battlefield."""
    opp = 1 - pid
    size = gs.size

    # Unit counts
    my_combat = [u for u in gs.units if u.player_id == pid and u.alive
                 and u.unit_type not in ("worker",)]
    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive
                  and u.unit_type not in ("worker",)]
    my_count = len(my_combat)
    opp_count = len(opp_combat)
    unit_ratio = my_count / max(opp_count, 1)

    # Resource advantage
    my_econ = gs.economies[pid]
    opp_econ = gs.economies[opp]
    my_total_res = my_econ.food + my_econ.wood + my_econ.gold
    opp_total_res = opp_econ.food + opp_econ.wood + opp_econ.gold
    res_ratio = my_total_res / max(opp_total_res, 1)

    # Tech lead
    my_techs = len(gs.techs[pid].completed)
    opp_techs = len(gs.techs[opp].completed)
    tech_lead = my_techs - opp_techs

    # City HP
    my_city_hp = gs.cities[pid].hp
    opp_city_hp = gs.cities[opp].hp

    # Frontline: units near enemy city
    opp_city = gs.cities[opp]
    my_frontline = [u for u in my_combat
                    if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6]
    my_city = gs.cities[pid]
    opp_frontline = [u for u in opp_combat
                     if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6]

    # Enemy density around their city (for weak point detection)
    opp_near_their_city = [u for u in opp_combat
                           if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 4]

    # Find weak point: direction around enemy city with fewest enemies
    weak_point = None
    min_enemies = 999
    for dx, dy in [(3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, 2), (2, -2), (-2, -2)]:
        wx, wy = (opp_city.x + dx) % size, (opp_city.y + dy) % size
        nearby = sum(1 for u in opp_combat if _td(u.x, wx, size) + _td(u.y, wy, size) <= 3)
        if nearby < min_enemies:
            min_enemies = nearby
            weak_point = (wx, wy)

    # Power (total ATK)
    my_power = sum(u.atk for u in my_combat)
    opp_power = sum(u.atk for u in opp_combat)

    # Is city threatened?
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
    """Update opponent model based on current turn's observations."""
    opp = 1 - pid
    size = gs.size

    # Count enemy units near my city vs near their city
    my_city = gs.cities[pid]
    opp_city = gs.cities[opp]

    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive
                  and u.unit_type not in ("worker",)]

    # Enemy aggression: ratio of units near my city vs total
    near_my_city = sum(1 for u in opp_combat
                       if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6)
    near_their_city = sum(1 for u in opp_combat
                          if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6)

    total = len(opp_combat)
    if total > 0:
        # Aggression = proportion of enemy units that are forward deployed
        aggression = near_my_city / max(total, 1) - near_their_city / max(total, 1)
        aggression = max(-1, min(1, aggression))  # clamp
        aggression = (aggression + 1) / 2  # normalize to [0, 1]
    else:
        aggression = 0.5

    opp_model["history"].append((gs.turn, aggression))
    # Keep last 10 turns
    opp_model["history"] = [h for h in opp_model["history"] if h[0] > gs.turn - 10]

    # Compute rolling average
    if opp_model["history"]:
        opp_model["aggression"] = sum(h[1] for h in opp_model["history"]) / len(opp_model["history"])

    # Track enemy unit types
    for u in opp_combat:
        opp_model["enemy_unit_types"][u.unit_type] = opp_model["enemy_unit_types"].get(u.unit_type, 0) + 1


def _select_strategy(gs, pid, assessment, opp_model):
    """Select strategy based on assessment and opponent model."""
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

    # Winning militarily
    if unit_ratio > 1.3 and my_count >= 3:
        return "aggressive"

    # Only turtle if enemy actually has units near our city
    if assessment["city_threatened"] and my_count < opp_count:
        return "defensive"
    if unit_ratio < 0.6 and opp_count > 2:
        return "defensive"

    # v5: Construction triggers — require minimum game time for combat window
    # Don't allow construction before turn 20 — gives combat strategies a window
    if gs.turn < 20:
        if unit_ratio > 1.3 and my_count >= 3:
            return "aggressive"
        if assessment["city_threatened"] and my_count < opp_count:
            return "defensive"
        return "balanced"

    # 1. Already on C-line: if we have C1, continue construction path
    if "C1" in gs.techs[pid].completed:
        if gs.turn > 25:
            return "construction"

    # 2. Safe + established
    my_total_res = sum([gs.economies[pid].food, gs.economies[pid].wood, gs.economies[pid].gold])
    if gs.turn > 30 and my_total_res > 35 and not assessment.get("city_threatened", False):
        return "construction"

    # 3. Stalemate
    if gs.turn > 35 and assessment["opp_city_hp"] >= 85 and assessment["my_city_hp"] >= 85:
        return "construction"

    # Opponent modeling (only after early game stabilizes)
    if aggressiveness > 0.65 and gs.turn > 15:
        if gs.turn > 30:
            return "defensive_construction"
        return "defensive"
    elif aggressiveness < 0.35 and gs.turn > 15:
        return "aggressive"

    # Default: balanced
    return "balanced"


# =============================================================================
# v4: Force Coordination
# =============================================================================

def _compute_force_coordination(gs, pid, assessment):
    """Compute rally point near enemy city and check if wave is ready."""
    opp_city = gs.cities[1 - pid]
    size = gs.size

    # Rally point: weak_point from assessment, or directly at enemy city
    if assessment.get("weak_point") and assessment.get("opp_count", 0) >= 3:
        rally_point = assessment["weak_point"]
    else:
        rally_point = (opp_city.x, opp_city.y)

    # Count units near rally point (within 3 tiles)
    my_combat = [u for u in gs.units if u.player_id == pid and u.alive
                 and u.unit_type not in ("worker",)]
    wave_units = [u for u in my_combat
                  if _td(u.x, rally_point[0], size) + _td(u.y, rally_point[1], size) <= 4]

    wave_ready = len(wave_units) >= 2

    return rally_point, wave_ready


def _compute_adaptive_counter(gs, pid, opp_model):
    """Determine what unit type to produce based on enemy composition."""
    enemy_types = opp_model["enemy_unit_types"]
    total = sum(enemy_types.values())

    if total < 3:
        return None  # Not enough data

    archer_count = enemy_types.get("archer", 0)
    cavalry_count = enemy_types.get("cavalry", 0)
    infantry_count = enemy_types.get("infantry", 0)

    # If many archers -> produce cavalry (fast, close distance)
    if archer_count >= 2 and archer_count >= cavalry_count and archer_count >= infantry_count:
        return "cavalry"

    # If many cavalry -> produce infantry (high DEF, stand on mountains)
    if cavalry_count >= 2 and cavalry_count >= archer_count and cavalry_count >= infantry_count:
        return "infantry"

    # If building construction -> cheap infantry to stall
    if infantry_count >= 2:
        return "infantry"

    return None


# =============================================================================
# v3: Worker with strategy awareness
# =============================================================================

def _greedy_worker_v3(w, ui, gs, pid, strategy, rng):
    """Worker v5: build new facilities > produce on existing ones.
    If C5 is researched or we're in construction mode, prioritize expansion."""
    terrain = get_terrain(gs.grid, w.x, w.y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[w.y][w.x].get("facility")

    # v5: Need more facilities for construction victory → prioritize building
    c5_done = "C5" in gs.techs[pid].completed
    in_construction = strategy in ("construction", "defensive_construction")
    need_expansion = c5_done or in_construction

    if facility and facility.player_id == pid:
        if need_expansion:
            # Move to find a new buildable tile instead of staying here
            best = _nearest_buildable(w, gs, pid)
            if best:
                return _move_to(w, ui, gs, best, rng)
        return {"unit_idx": ui, "type": "produce"}
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}
    best = _nearest_buildable(w, gs, pid)
    if best:
        return _move_to(w, ui, gs, best, rng)
    return {"unit_idx": ui, "type": "end_turn"}


# =============================================================================
# v4: Combat with force coordination + strategy awareness
# =============================================================================

def _greedy_combat_v4(u, ui, gs, pid, opp_city, strategy, assessment, rally_point, wave_ready, rng):
    """Combat unit v4: strategic awareness + force coordination + tactical v2 base."""
    my_city = gs.cities[pid]
    size = gs.size
    max_hp = 100 if u.unit_type == "infantry" else (80 if u.unit_type == "cavalry" else (60 if u.unit_type == "archer" else 40))
    hp_pct = u.hp / max_hp

    # === v2: Retreat when low HP ===
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

    # === v2: Archer range discipline ===
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

    # === v2: City defense ===
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                          if eu.alive and eu.player_id != pid
                          and eu.x == nx and eu.y == ny), None)
            if target:
                return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # Intercept enemies near city
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, my_city.x, size) + _td(eu.y, my_city.y, size)
            if d <= 2:
                return _move_to(u, ui, gs, (eu.x, eu.y), rng)

    # Attack adjacent enemy
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        target = next((eu for eu in gs.units
                      if eu.alive and eu.player_id != pid
                      and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # === v3: Strategic positioning ===
    if strategy == "defensive" or strategy == "defensive_construction":
        # Turtle: stay near city, don't push far
        dist_to_my_city = _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size)
        if dist_to_my_city > 3:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng, prefer_defense=True)

    # === v4: Force coordination ===
    # If wave is ready: all units rush the enemy city
    if wave_ready:
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)

    # If close to rally point AND we have at least 2 friends nearby, wait briefly
    # otherwise keep pushing
    rpx, rpy = rally_point
    dist_to_rally = _td(u.x, rpx, size) + _td(u.y, rpy, size)
    if dist_to_rally <= 2:
        # Very close to rally point: check if there are other units nearby
        friends_nearby = 0
        for other in gs.units:
            if other.alive and other.player_id == pid and other is not u:
                if _td(other.x, u.x, size) + _td(other.y, u.y, size) <= 2:
                    friends_nearby += 1
                    if friends_nearby >= 2:
                        break
        if friends_nearby >= 2:
            # Wait for the squad to form
            return {"unit_idx": ui, "type": "end_turn"}

    # Default: push toward enemy city
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


# =============================================================================
# v3: Strategy-aware research
# =============================================================================

def _do_research(gs, pid, strategy, actions):
    """Research decision based on strategy."""
    tech = gs.techs[pid]
    econ = gs.economies[pid]
    avail = tech.available_to_research()

    # v5: C5 available → research it after combat window (turn > 20)
    # or immediately if already in construction strategy
    in_construction = strategy in ("construction", "defensive_construction")
    if "C5" in avail and econ.can_afford(TECH_TREE_COST.get("C5", (99,99,99))):
        if in_construction or gs.turn > 20:
            actions.append({"unit_idx": -1, "type": "research", "tech_id": "C5"})
            return

    if strategy == "aggressive":
        # Military priority: M-line first
        order = ["M1", "M2", "M3", "M4", "C1", "E1", "E2", "E3", "E4", "C2", "C3", "C4", "C5"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    elif strategy == "defensive" or strategy == "defensive_construction":
        # Economic priority: E-line first to catch up
        order = ["E1", "E2", "E3", "E4", "C1", "M1", "M2", "M3", "M4", "C2", "C3", "C4", "C5"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    elif strategy == "construction":
        # Construction priority: C-line first
        order = ["C1", "C2", "C3", "C4", "C5", "E1", "E2", "E3", "E4", "M1", "M2", "M3", "M4"]
        for t in order:
            if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break
    else:
        # v5 Balanced: mid-game bias toward C-line, otherwise most expensive first
        if gs.turn > 15:
            # Prioritize C-line techs to unlock construction path
            for ct in ["C2", "C3", "C4", "C5", "C1"]:
                if ct in avail and econ.can_afford(TECH_TREE_COST.get(ct, (99,99,99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": ct})
                    return
        avail.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
        for t in avail:
            if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break


# =============================================================================
# v4: Strategy-aware production with adaptive countering
# =============================================================================

def _do_production(gs, pid, strategy, production_counter, assessment, actions):
    """Production decision based on strategy and adaptive countering."""
    econ = gs.economies[pid]
    size = gs.size

    # v4: Adaptive counter production
    if production_counter:
        if econ.can_afford(UNIT_COST[production_counter]):
            # Only counter-produce if we have at least some resources
            if econ.food > 8:
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": production_counter})
                return

    if strategy == "aggressive":
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

    elif strategy == "defensive" or strategy == "defensive_construction":
        # Produce defensive units (infantry first for city defense)
        for ut in ["infantry", "archer", "cavalry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

    elif strategy == "construction":
        # v5: Diverse defense while teching — not just infantry
        my_combat = [u for u in gs.units if u.player_id == pid and u.alive
                     and u.unit_type not in ("worker",)]
        n_cav = sum(1 for u in my_combat if u.unit_type == "cavalry")
        n_arc = sum(1 for u in my_combat if u.unit_type == "archer")
        n_inf = sum(1 for u in my_combat if u.unit_type == "infantry")
        n_total = len(my_combat)

        # Produce worker if we have < 4 and economy is strong
        n_workers = sum(1 for u in gs.units if u.player_id == pid and u.alive and u.unit_type == "worker")
        if n_workers < 4 and econ.food >= 15 and n_total >= 3:
            if econ.can_afford(UNIT_COST["worker"]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "worker"})
                return

        # Cavalry if gold-rich and cavalry underrepresented
        if econ.gold >= 10 and (n_cav < n_inf or n_total <= 5):
            if econ.can_afford(UNIT_COST["cavalry"]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "cavalry"})
                return
        # Archer if wood-rich and archer underrepresented
        if econ.wood >= 8 and (n_arc < n_inf or n_total <= 5):
            if econ.can_afford(UNIT_COST["archer"]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "archer"})
                return
        # Infantry as fallback
        if econ.can_afford(UNIT_COST["infantry"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})

    else:
        # v5 Balanced: occasional worker + diverse combat units
        n_workers = sum(1 for u in gs.units if u.player_id == pid and u.alive and u.unit_type == "worker")
        n_combat = sum(1 for u in gs.units if u.player_id == pid and u.alive and u.unit_type != "worker")
        if n_workers < 4 and econ.food >= 15 and n_combat >= 3:
            if econ.can_afford(UNIT_COST["worker"]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "worker"})
                return
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break


# =============================================================================
# v2: Helper utilities (preserved from v2)
# =============================================================================

def _city_is_safe(gs, pid) -> bool:
    """Check if our city is safe (no enemies within 2 tiles)."""
    my_city = gs.cities[pid]
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, my_city.x, gs.size) + _td(eu.y, my_city.y, gs.size)
            if d <= 2:
                return False
    return True


def _retreat_from(unit, ui, gs, enemy, rng):
    """Move one step away from enemy."""
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
    """Archer approaches target keeping optimal range (2 tiles)."""
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
    """Find nearest buildable resource tile."""
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
    """Move one step toward target with terrain preference."""
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
