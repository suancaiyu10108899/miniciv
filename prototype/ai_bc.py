# prototype/ai_bc.py — Behavior Cloning AI: 2-layer NN trained on Greedy actions
# Forward pass only: uses pre-trained weights loaded from bc_weights.json
import random as _random
import json
import os
import numpy as np
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE, UNIT_STATS
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}

# Action encoding: what actions the BC can choose from
# We encode each possible action as an integer index
_ACTION_TYPES = [
    "move_n", "move_s", "move_w", "move_e",  # 0-3: move directions
    "end_turn",                                # 4: wait
    "produce_infantry", "produce_cavalry", "produce_archer",  # 5-7: production
    "research_M1", "research_M2", "research_M3", "research_M4",  # 8-11
    "research_E1", "research_E2", "research_E3", "research_E4",  # 12-15
    "research_C1", "research_C2", "research_C3", "research_C4", "research_C5",  # 16-20
]

N_ACTIONS = len(_ACTION_TYPES)

# Feature indices for readability
F_MY_COMBAT_COUNT = 0
F_OPP_COMBAT_COUNT = 1
F_MY_CITY_HP = 2
F_OPP_CITY_HP = 3
F_MY_FOOD = 4
F_MY_WOOD = 5
F_MY_GOLD = 6
F_OPP_FOOD = 7
F_OPP_WOOD = 8
F_OPP_GOLD = 9
F_MY_TECHS = 10
F_OPP_TECHS = 11
F_TURN = 12
F_UNIT_HP_PCT = 13
F_UNIT_IS_ARCHER = 14
F_UNIT_IS_CAVALRY = 15
F_UNIT_IS_INFANTRY = 16
F_UNIT_IS_WORKER = 17
F_UNIT_IS_SCOUT = 18
F_DIST_TO_MY_CITY = 19
F_DIST_TO_OPP_CITY = 20
F_NEAREST_ENEMY_DIST = 21
F_TERRAIN_PLAIN = 22
F_TERRAIN_FOREST = 23
F_TERRAIN_MOUNTAIN = 24
F_TERRAIN_WATER = 25
F_MY_CITY_THREATENED = 26
F_HAS_FARM = 27
F_HAS_LUMBERMILL = 28
F_HAS_MINE = 29

N_FEATURES = 30


def _load_weights():
    """Load weights from bc_weights.json if available."""
    weights_path = os.path.join(os.path.dirname(__file__), "bc_weights.json")
    if os.path.exists(weights_path):
        with open(weights_path, "r") as f:
            data = json.load(f)
        # Convert lists back to numpy arrays
        return {
            "W1": np.array(data["W1"]),
            "b1": np.array(data["b1"]),
            "W2": np.array(data["W2"]),
            "b2": np.array(data["b2"]),
            "W3": np.array(data["W3"]),
            "b3": np.array(data["b3"]),
        }
    return None


# Load weights once at module level
_BC_WEIGHTS = _load_weights()


def _extract_features(gs, pid, unit_idx=None):
    """Extract 30 hand-crafted features from game state.
    If unit_idx is None, extract global features only (for production/research decisions).
    """
    opp = 1 - pid
    size = gs.size

    def td(a, b, s):
        return min(abs(b - a), s - abs(b - a))

    my_combat = [u for u in gs.units if u.player_id == pid and u.alive
                 and u.unit_type not in ("worker",)]
    opp_combat = [u for u in gs.units if u.player_id == opp and u.alive
                  and u.unit_type not in ("worker",)]

    features = np.zeros(N_FEATURES, dtype=np.float32)

    # Global features
    features[F_MY_COMBAT_COUNT] = len(my_combat) / 10.0  # Normalize
    features[F_OPP_COMBAT_COUNT] = len(opp_combat) / 10.0
    features[F_MY_CITY_HP] = gs.cities[pid].hp / 100.0
    features[F_OPP_CITY_HP] = gs.cities[opp].hp / 100.0
    features[F_MY_FOOD] = gs.economies[pid].food / 50.0
    features[F_MY_WOOD] = gs.economies[pid].wood / 50.0
    features[F_MY_GOLD] = gs.economies[pid].gold / 50.0
    features[F_OPP_FOOD] = gs.economies[opp].food / 50.0
    features[F_OPP_WOOD] = gs.economies[opp].wood / 50.0
    features[F_OPP_GOLD] = gs.economies[opp].gold / 50.0
    features[F_MY_TECHS] = len(gs.techs[pid].completed) / 10.0
    features[F_OPP_TECHS] = len(gs.techs[opp].completed) / 10.0
    features[F_TURN] = gs.turn / 100.0

    # City threatened
    my_city = gs.cities[pid]
    features[F_MY_CITY_THREATENED] = 1.0 if any(
        td(eu.x, my_city.x, size) + td(eu.y, my_city.y, size) <= 2
        for eu in opp_combat
    ) else 0.0

    # Facility counts
    facs = {"farm": 0, "lumbermill": 0, "mine": 0}
    for y in range(size):
        for x in range(size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                facs[f.facility_type] = facs.get(f.facility_type, 0) + 1
    features[F_HAS_FARM] = 1.0 if facs["farm"] > 0 else 0.0
    features[F_HAS_LUMBERMILL] = 1.0 if facs["lumbermill"] > 0 else 0.0
    features[F_HAS_MINE] = 1.0 if facs["mine"] > 0 else 0.0

    # Unit-specific features (if unit_idx is specified)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[opp]

    if unit_idx is not None and 0 <= unit_idx < len(units):
        unit = units[unit_idx]
        max_hp = UNIT_STATS[unit.unit_type]["hp"]
        features[F_UNIT_HP_PCT] = unit.hp / max_hp
        features[F_UNIT_IS_ARCHER] = 1.0 if unit.unit_type == "archer" else 0.0
        features[F_UNIT_IS_CAVALRY] = 1.0 if unit.unit_type == "cavalry" else 0.0
        features[F_UNIT_IS_INFANTRY] = 1.0 if unit.unit_type == "infantry" else 0.0
        features[F_UNIT_IS_WORKER] = 1.0 if unit.unit_type == "worker" else 0.0
        features[F_UNIT_IS_SCOUT] = 1.0 if unit.unit_type == "scout" else 0.0
        features[F_DIST_TO_MY_CITY] = td(unit.x, my_city.x, size) / 15.0 + td(unit.y, my_city.y, size) / 15.0
        features[F_DIST_TO_OPP_CITY] = td(unit.x, opp_city.x, size) / 15.0 + td(unit.y, opp_city.y, size) / 15.0

        # Nearest enemy distance
        nearest = 99
        for eu in gs.units:
            if eu.alive and eu.player_id != pid:
                d = td(eu.x, unit.x, size) + td(eu.y, unit.y, size)
                if d < nearest:
                    nearest = d
        features[F_NEAREST_ENEMY_DIST] = nearest / 15.0

        # Terrain under unit
        terrain = get_terrain(gs.grid, unit.x, unit.y)
        features[F_TERRAIN_PLAIN] = 1.0 if terrain == Terrain.PLAIN else 0.0
        features[F_TERRAIN_FOREST] = 1.0 if terrain == Terrain.FOREST else 0.0
        features[F_TERRAIN_MOUNTAIN] = 1.0 if terrain == Terrain.MOUNTAIN else 0.0
        features[F_TERRAIN_WATER] = 1.0 if terrain == Terrain.WATER else 0.0
    else:
        # No unit context (production/research decisions)
        features[F_UNIT_HP_PCT] = 0.0
        features[F_DIST_TO_MY_CITY] = 0.0
        features[F_DIST_TO_OPP_CITY] = 0.0
        features[F_NEAREST_ENEMY_DIST] = 0.0

    return features


def _forward_pass(features, weights):
    """2-layer NN forward pass with one hidden layer.
    Architecture: N_FEATURES -> 64 -> 32 -> N_ACTIONS
    """
    if weights is None:
        return np.zeros(N_ACTIONS)

    # Layer 1: input -> 64
    h1 = np.dot(features, weights["W1"]) + weights["b1"]
    h1 = np.maximum(0, h1)  # ReLU

    # Layer 2: 64 -> 32
    h2 = np.dot(h1, weights["W2"]) + weights["b2"]
    h2 = np.maximum(0, h2)  # ReLU

    # Layer 3: 32 -> N_ACTIONS (output)
    output = np.dot(h2, weights["W3"]) + weights["b3"]

    return output


def _action_to_index(action, unit_idx, gs, pid):
    """Convert an action dict to an action index for training."""
    atype = action.get("type", "end_turn")

    if atype == "move":
        dx, dy = action.get("dx", 0), action.get("dy", 0)
        if (dx, dy) == (0, -1):
            return 0
        elif (dx, dy) == (0, 1):
            return 1
        elif (dx, dy) == (-1, 0):
            return 2
        elif (dx, dy) == (1, 0):
            return 3
        return 4  # fallback
    elif atype == "end_turn":
        return 4
    elif atype == "produce_unit":
        ut = action.get("unit_type", "")
        if ut == "infantry":
            return 5
        elif ut == "cavalry":
            return 6
        elif ut == "archer":
            return 7
        return 4
    elif atype == "research":
        tech_id = action.get("tech_id", "")
        tech_map = {
            "M1": 8, "M2": 9, "M3": 10, "M4": 11,
            "E1": 12, "E2": 13, "E3": 14, "E4": 15,
            "C1": 16, "C2": 17, "C3": 18, "C4": 19, "C5": 20,
        }
        return tech_map.get(tech_id, 4)
    else:
        return 4  # default to end_turn


def _index_to_action(idx, unit_idx, gs, pid):
    """Convert an action index to an action dict for execution."""
    if idx < 4:
        # Move direction
        dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        dx, dy = dirs[idx]
        return {"unit_idx": unit_idx, "type": "move", "dx": dx, "dy": dy}
    elif idx == 4:
        return {"unit_idx": unit_idx, "type": "end_turn"}
    elif idx < 8:
        # Production
        unit_types = ["infantry", "cavalry", "archer"]
        ut = unit_types[idx - 5]
        return {"unit_idx": -1, "type": "produce_unit", "unit_type": ut}
    else:
        # Research
        tech_ids = ["M1", "M2", "M3", "M4",
                    "E1", "E2", "E3", "E4",
                    "C1", "C2", "C3", "C4", "C5"]
        tid = tech_ids[idx - 8]
        return {"unit_idx": -1, "type": "research", "tech_id": tid}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """BC AI: uses trained NN to predict actions."""
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []
    done_units = set()

    if _BC_WEIGHTS is None:
        # Fallback: random actions if no weights loaded
        for ui, u in enumerate(units):
            legal = get_single_step_moves(u, gs.grid)
            if legal and rng.random() < 0.7:
                dx, dy = rng.choice(legal)
                actions.append({"unit_idx": ui, "type": "move", "dx": dx, "dy": dy})
            else:
                actions.append({"unit_idx": ui, "type": "end_turn"})
                done_units.add(ui)
        for ut in ["infantry", "archer"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break
        return actions

    # For each unit, get action scores from NN
    for ui, u in enumerate(units):
        if ui in done_units:
            continue
        features = _extract_features(gs, pid, ui)
        scores = _forward_pass(features, _BC_WEIGHTS)
        # Filter illegal actions
        legal = get_single_step_moves(u, gs.grid)
        legal_dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]

        # Only consider move actions that are legal
        for i in range(4):
            if legal_dirs[i] not in legal:
                scores[i] = -9999  # Penalize illegal moves

        # Only consider production/research that can be afforded
        if not econ.can_afford(UNIT_COST["infantry"]):
            scores[5] = -9999
        if not econ.can_afford(UNIT_COST["cavalry"]):
            scores[6] = -9999
        if not econ.can_afford(UNIT_COST["archer"]):
            scores[7] = -9999

        if u.unit_type == "worker":
            # Workers don't do combat, but NN might suggest it
            pass  # Keep all options open

        best_idx = int(np.argmax(scores))
        act = _index_to_action(best_idx, ui, gs, pid)
        actions.append(act)
        done_units.add(ui)

    # Handle city-level actions (research if no unit would)
    if tech.researching is None:
        features_global = _extract_features(gs, pid, None)
        scores = _forward_pass(features_global, _BC_WEIGHTS)
        # Check if any research action is affordable
        for i in range(8, 21):
            tech_id = ["M1", "M2", "M3", "M4",
                      "E1", "E2", "E3", "E4",
                      "C1", "C2", "C3", "C4", "C5"][i - 8]
            if tech_id in tech.completed or not econ.can_afford(TECH_TREE_COST.get(tech_id, (99, 99, 99))):
                scores[i] = -9999

        if np.max(scores[8:]) > -100:  # Some research is affordable
            best_research = 8 + int(np.argmax(scores[8:]))
            act = _index_to_action(best_research, -1, gs, pid)
            actions.append(act)

    return actions


# Expose feature extraction for training
def get_feature_vector(gs, pid):
    """Get feature vector for training (without unit context)."""
    return _extract_features(gs, pid, None)


def get_unit_feature_vector(gs, pid, unit_idx):
    """Get feature vector with unit context for training."""
    return _extract_features(gs, pid, unit_idx)
