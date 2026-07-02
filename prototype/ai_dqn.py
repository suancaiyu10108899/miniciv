# prototype/ai_dqn.py — DQN AI: numpy-only Q-network with epsilon-greedy action selection
#
# Input features: ~22 hand-crafted features per state
# Network: input_dim -> 64 (ReLU) -> 32 (ReLU) -> N_actions (linear)
# Actions: 6 high-level combat actions per unit, mapped to game action dicts
#
# Usage in eval:
#   from prototype.ai_dqn import ai_decide, DQNAgent
#   dqn = DQNAgent(n_features=22, n_actions=6)
#   result = ai_decide(gs, pid, rng, dqn=dqn)

import json
import math
import random as _random
import numpy as np

from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, MAX_TURNS, TECH_TREE as _TECH_TREE

TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}
N_UNIT_TYPES = 5  # infantry, cavalry, archer, scout, worker

# ── 6 high-level actions for combat units ──
ACTION_MOVE_TOWARDS_ENEMY = 0
ACTION_MOVE_TOWARDS_CITY = 1
ACTION_ATTACK_NEAREST = 2
ACTION_DEFEND_CITY = 3
ACTION_HOLD = 4
ACTION_RETREAT = 5
N_ACTIONS = 6


# ═══════════════════════════════════════════════════════════════
# DQN Agent
# ═══════════════════════════════════════════════════════════════

class DQNAgent:
    """numpy-only DQN agent with experience replay."""

    def __init__(self, n_features: int, n_actions: int,
                 learning_rate: float = 0.001, gamma: float = 0.9,
                 epsilon: float = 0.3, replay_capacity: int = 10000):
        self.n_features = n_features
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon

        # Network: input -> 64 -> 32 -> n_actions
        self.W1 = np.random.randn(n_features, 64).astype(np.float64) * np.sqrt(2.0 / n_features)
        self.b1 = np.zeros(64, dtype=np.float64)
        self.W2 = np.random.randn(64, 32).astype(np.float64) * np.sqrt(2.0 / 64)
        self.b2 = np.zeros(32, dtype=np.float64)
        self.W3 = np.random.randn(32, n_actions).astype(np.float64) * np.sqrt(2.0 / 32)
        self.b3 = np.zeros(n_actions, dtype=np.float64)

        # Experience replay buffer
        self.replay_capacity = replay_capacity
        self.replay_buffer = []  # list of (state, action, reward, next_state, done)

    # ── Forward pass ───────────────────────────────────────

    def forward(self, state: np.ndarray) -> np.ndarray:
        """Returns Q-values for all actions. state shape: (n_features,)"""
        h1 = np.dot(state, self.W1) + self.b1       # (64,)
        h1 = np.maximum(h1, 0)                       # ReLU
        h2 = np.dot(h1, self.W2) + self.b2           # (32,)
        h2 = np.maximum(h2, 0)                       # ReLU
        q = np.dot(h2, self.W3) + self.b3            # (n_actions,)
        return q

    # ── Action selection ──────────────────────────────────

    def act(self, state: np.ndarray, epsilon_greedy: bool = True,
            legal_actions: list[int] | None = None, rng=None) -> int:
        """
        Returns action index.
        If legal_actions is given, only those indices are considered.
        """
        if rng is None:
            rng = _random.Random()
        if epsilon_greedy and rng.random() < self.epsilon:
            if legal_actions is not None:
                return rng.choice(legal_actions)
            return rng.randint(0, self.n_actions - 1)
        q = self.forward(state)
        if legal_actions is not None:
            # Mask unavailable actions
            mask = np.full(self.n_actions, -np.inf)
            for a in legal_actions:
                mask[a] = q[a]
            return int(np.argmax(mask))
        return int(np.argmax(q))

    # ── Experience replay ──────────────────────────────────

    def store_experience(self, state, action, reward, next_state, done):
        """Store a transition tuple."""
        if len(self.replay_buffer) >= self.replay_capacity:
            # Remove oldest entry
            self.replay_buffer.pop(0)
        self.replay_buffer.append(
            (np.asarray(state, dtype=np.float64),
             action,
             float(reward),
             np.asarray(next_state, dtype=np.float64) if next_state is not None else None,
             bool(done))
        )

    def train(self, batch_size: int = 32) -> float:
        """
        Sample a mini-batch and perform one step of gradient descent.
        Returns the average loss over the batch.
        """
        if len(self.replay_buffer) < batch_size:
            return 0.0

        batch = _random.sample(self.replay_buffer, batch_size)

        total_loss = 0.0

        # Accumulate gradients for each layer
        dW1 = np.zeros_like(self.W1)
        db1 = np.zeros_like(self.b1)
        dW2 = np.zeros_like(self.W2)
        db2 = np.zeros_like(self.b2)
        dW3 = np.zeros_like(self.W3)
        db3 = np.zeros_like(self.b3)

        for state, action, reward, next_state, done in batch:
            # Forward: state -> h1 -> h2 -> q
            h1 = np.dot(state, self.W1) + self.b1
            h1_act = np.maximum(h1, 0)
            h2 = np.dot(h1_act, self.W2) + self.b2
            h2_act = np.maximum(h2, 0)
            q = np.dot(h2_act, self.W3) + self.b3

            # Target Q-value
            if done or next_state is None:
                target = reward
            else:
                next_q = self.forward(next_state)
                target = reward + self.gamma * np.max(next_q)

            # Loss = 0.5 * (target - q[action])^2
            # d_loss / d_q = q[action] - target
            dq = np.zeros(self.n_actions, dtype=np.float64)
            dq[action] = q[action] - target
            total_loss += 0.5 * (target - q[action]) ** 2

            # Backprop through W3, b3
            # q = h2_act @ W3 + b3
            # dL/dW3 = h2_act^T @ dq  (outer product for each sample)
            dW3 += np.outer(h2_act, dq)
            db3 += dq

            # Backprop through h2 ReLU
            dh2 = np.dot(dq, self.W3.T)  # (32,)
            dh2[h2 <= 0] = 0

            # Backprop through W2, b2
            dW2 += np.outer(h1_act, dh2)
            db2 += dh2

            # Backprop through h1 ReLU
            dh1 = np.dot(dh2, self.W2.T)  # (64,)
            dh1[h1 <= 0] = 0

            # Backprop through W1, b1
            dW1 += np.outer(state, dh1)
            db1 += dh1

        # Average gradients
        n = float(batch_size)
        dW1 /= n
        db1 /= n
        dW2 /= n
        db2 /= n
        dW3 /= n
        db3 /= n

        # Update weights (SGD)
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W3 -= self.lr * dW3
        self.b3 -= self.lr * db3

        return float(total_loss / n)

    # ── Save / Load ───────────────────────────────────────

    def save(self, path: str):
        """Save network weights to a JSON file."""
        data = {
            "n_features": self.n_features,
            "n_actions": self.n_actions,
            "lr": self.lr,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W3": self.W3.tolist(),
            "b3": self.b3.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str):
        """Load network weights from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        self.n_features = data["n_features"]
        self.n_actions = data["n_actions"]
        self.lr = data["lr"]
        self.gamma = data["gamma"]
        self.epsilon = data["epsilon"]
        self.W1 = np.asarray(data["W1"], dtype=np.float64)
        self.b1 = np.asarray(data["b1"], dtype=np.float64)
        self.W2 = np.asarray(data["W2"], dtype=np.float64)
        self.b2 = np.asarray(data["b2"], dtype=np.float64)
        self.W3 = np.asarray(data["W3"], dtype=np.float64)
        self.b3 = np.asarray(data["b3"], dtype=np.float64)


# ═══════════════════════════════════════════════════════════════
# Feature extraction
# ═══════════════════════════════════════════════════════════════

def _td(a, b, s):
    """Torus distance component."""
    return min(abs(b - a), s - abs(b - a))


def _extract_features(gs, pid: int) -> np.ndarray:
    """
    Build ~22 feature vector for player pid.
    Order (all floats):
      0-4:  my unit counts (infantry, cavalry, archer, scout, worker)
      5-9:  enemy unit counts
      10:   my food
      11:   my wood
      12:   my gold
      13:   enemy food
      14:   enemy wood
      15:   enemy gold
      16:   my techs completed
      17:   enemy techs completed
      18:   avg dist my units -> my city
      19:   avg dist my units -> enemy city
      20:   my frontline count
      21:   enemy frontline count
      22:   my avg HP ratio
      23:   enemy avg HP ratio
      24:   turn / MAX_TURNS
    """
    opp = 1 - pid
    size = gs.size
    my_city = gs.cities[pid]
    opp_city = gs.cities[opp]

    my_units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_units = [u for u in gs.units if u.player_id == opp and u.alive]
    my_combat = [u for u in my_units if u.unit_type != "worker"]
    opp_combat = [u for u in opp_units if u.unit_type != "worker"]

    # Unit type counts for me (0-4)
    type_order = ["infantry", "cavalry", "archer", "scout", "worker"]
    feats = []
    for t in type_order:
        feats.append(float(sum(1 for u in my_units if u.unit_type == t)))
    for t in type_order:
        feats.append(float(sum(1 for u in opp_units if u.unit_type == t)))

    # Resources (10-15)
    econ = gs.economies
    feats.append(float(econ[pid].food))
    feats.append(float(econ[pid].wood))
    feats.append(float(econ[pid].gold))
    feats.append(float(econ[opp].food))
    feats.append(float(econ[opp].wood))
    feats.append(float(econ[opp].gold))

    # Tech counts (16-17)
    feats.append(float(len(gs.techs[pid].completed)))
    feats.append(float(len(gs.techs[opp].completed)))

    # Distances (18-19)
    if my_combat:
        d_to_my_city = sum(_td(u.x, my_city.x, size) + _td(u.y, my_city.y, size)
                           for u in my_combat) / len(my_combat)
        d_to_enemy_city = sum(_td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size)
                              for u in my_combat) / len(my_combat)
    else:
        d_to_my_city = _td(my_city.x, my_city.x, size) + _td(my_city.y, my_city.y, size)  # 0
        d_to_enemy_city = _td(my_city.x, opp_city.x, size) + _td(my_city.y, opp_city.y, size)
    feats.append(d_to_my_city)
    feats.append(d_to_enemy_city)

    # Frontline: combat units within 6 of enemy city (20-21)
    my_front = sum(1 for u in my_combat
                   if _td(u.x, opp_city.x, size) + _td(u.y, opp_city.y, size) <= 6)
    opp_front = sum(1 for u in opp_combat
                    if _td(u.x, my_city.x, size) + _td(u.y, my_city.y, size) <= 6)
    feats.append(float(my_front))
    feats.append(float(opp_front))

    # Avg HP ratio (22-23)
    if my_units:
        hp_sum = 0.0
        max_sum = 0.0
        for u in my_units:
            from prototype.constants import UNIT_STATS
            max_hp = UNIT_STATS[u.unit_type]["hp"]
            hp_sum += u.hp
            max_sum += max_hp
        feats.append(hp_sum / max_sum if max_sum > 0 else 1.0)
    else:
        feats.append(0.0)

    if opp_units:
        hp_sum = 0.0
        max_sum = 0.0
        for u in opp_units:
            from prototype.constants import UNIT_STATS
            max_hp = UNIT_STATS[u.unit_type]["hp"]
            hp_sum += u.hp
            max_sum += max_hp
        feats.append(hp_sum / max_sum if max_sum > 0 else 1.0)
    else:
        feats.append(0.0)

    # Turn normalised (24)
    feats.append(gs.turn / float(MAX_TURNS))

    return np.asarray(feats, dtype=np.float64)


def compute_features(gs, pid: int) -> np.ndarray:
    """Public alias for _extract_features."""
    return _extract_features(gs, pid)


# ═══════════════════════════════════════════════════════════════
# Action mapping
# ═══════════════════════════════════════════════════════════════

def _action_move_towards_enemy(u, ui, gs, pid, rng):
    """Move one step toward the enemy city."""
    opp_city = gs.cities[1 - pid]
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _action_move_towards_city(u, ui, gs, pid, rng):
    """Move one step toward own city."""
    my_city = gs.cities[pid]
    return _move_to(u, ui, gs, (my_city.x, my_city.y), rng)


def _action_attack_nearest(u, ui, gs, pid, rng):
    """Attack adjacent enemy, or move toward nearest enemy."""
    size = gs.size
    opp = 1 - pid

    # Adjacent enemy -> attack
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        target = next((eu for eu in gs.units
                       if eu.alive and eu.player_id != pid
                       and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # Move toward nearest enemy unit
    nearest = None
    nearest_d = 999
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, u.x, size) + _td(eu.y, u.y, size)
            if d < nearest_d:
                nearest_d = d
                nearest = eu
    if nearest:
        return _move_to(u, ui, gs, (nearest.x, nearest.y), rng)

    # Fallback: move toward enemy city
    opp_city = gs.cities[opp]
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _action_defend_city(u, ui, gs, pid, rng):
    """Move toward own city (defensive)."""
    my_city = gs.cities[pid]
    return _move_to(u, ui, gs, (my_city.x, my_city.y), rng, prefer_defense=True)


def _action_hold(u, ui, gs, pid, rng):
    """End turn in place (do nothing)."""
    return {"unit_idx": ui, "type": "end_turn"}


def _action_retreat(u, ui, gs, pid, rng):
    """Move away from nearest enemy."""
    size = gs.size
    legal = get_single_step_moves(u, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}

    # Find nearest enemy
    nearest = None
    nearest_d = 999
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = _td(eu.x, u.x, size) + _td(eu.y, u.y, size)
            if d < nearest_d:
                nearest_d = d
                nearest = eu

    if nearest is None:
        # No enemies visible — hold
        return {"unit_idx": ui, "type": "end_turn"}

    # Choose move that maximises distance from nearest enemy
    best, best_d = [], -1
    for mv in legal:
        nx, ny = (u.x + mv[0]) % size, (u.y + mv[1]) % size
        d = _td(nx, nearest.x, size) + _td(ny, nearest.y, size)
        terrain = get_terrain(gs.grid, nx, ny)
        if terrain == Terrain.WATER:
            continue
        if terrain == Terrain.MOUNTAIN and not u.can_enter_mountain:
            continue
        if d > best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)

    if not best:
        return {"unit_idx": ui, "type": "end_turn"}
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


# Maps action index -> function
_ACTION_FUNCS = [
    _action_move_towards_enemy,
    _action_move_towards_city,
    _action_attack_nearest,
    _action_defend_city,
    _action_hold,
    _action_retreat,
]


def _map_action(unit_idx: int, action_id: int, u, gs, pid, rng) -> dict:
    """Convert DQN action ID to a game action dict."""
    if 0 <= action_id < len(_ACTION_FUNCS):
        return _ACTION_FUNCS[action_id](u, unit_idx, gs, pid, rng)
    return {"unit_idx": unit_idx, "type": "end_turn"}


# ═══════════════════════════════════════════════════════════════
# Helper: movement
# ═══════════════════════════════════════════════════════════════

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
        score = -d + def_bonus * 0.15
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
    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


# ═══════════════════════════════════════════════════════════════
# Helper: worker logic (simple greedy)
# ═══════════════════════════════════════════════════════════════

def _worker_decide(u, ui, gs, pid, rng):
    """Simple greedy worker: build missing facility > produce > move to resource."""
    terrain = get_terrain(gs.grid, u.x, u.y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[u.y][u.x].get("facility")

    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}

    best = _nearest_buildable(u, gs, pid)
    if best:
        return _move_to(u, ui, gs, best, rng)
    return {"unit_idx": ui, "type": "end_turn"}


def _nearest_buildable(unit, gs, pid):
    """Find nearest buildable tile without a facility."""
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


# ═══════════════════════════════════════════════════════════════
# AI decide entry point
# ═══════════════════════════════════════════════════════════════

def ai_decide(gs, pid: int, rng=None, dqn: DQNAgent | None = None) -> list[dict]:
    """
    DQN-based AI decision function.

    When dqn is None, behaves like a basic greedy combat AI.
    When dqn is provided, uses the Q-network to select actions per unit.

    Compatible with eval.py interface: ai_decide(gs, pid, rng) -> list[dict]
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)

    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []

    # Compute state features once (used for all units)
    state = _extract_features(gs, pid) if dqn is not None else None

    # Separate units by type
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type not in ("archer", "scout", "worker")]
    scouts = [u for u in units if u.unit_type == "scout"]
    workers = [u for u in units if u.unit_type == "worker"]

    # Archers first, then fighters, then scouts
    for u in archers + fighters + scouts:
        ui = units.index(u)

        if dqn is not None:
            # DQN mode: select action via Q-network
            # Legal actions: all 6 are always legal in principle;
            # the action mapping handles illegal moves gracefully (end_turn fallback).
            action_id = dqn.act(state, epsilon_greedy=False, legal_actions=None, rng=rng)
            act = _map_action(ui, action_id, u, gs, pid, rng)
        else:
            # Fallback: basic greedy behaviour
            act = _greedy_combat_fallback(u, ui, gs, pid, rng)

        if act:
            actions.append(act)

    # Workers: always use simple greedy logic
    for u in workers:
        ui = units.index(u)
        act = _worker_decide(u, ui, gs, pid, rng)
        if act:
            actions.append(act)

    # Research: cheapest available tech
    if tech.researching is None:
        avail = tech.available_to_research()
        avail.sort(key=lambda t: sum(TECH_TREE_COST.get(t, (0, 0, 0))))
        for t in avail:
            if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                break

    # Production: cheapest affordable unit
    for ut in ["infantry", "archer", "cavalry"]:
        if econ.can_afford(UNIT_COST[ut]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
            break

    return actions


def _greedy_combat_fallback(u, ui, gs, pid, rng):
    """Basic greedy combat logic used when dqn is None."""
    my_city = gs.cities[pid]
    opp_city = gs.cities[1 - pid]
    size = gs.size

    # Attack adjacent enemy
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % size, (u.y + dy) % size
        target = next((eu for eu in gs.units
                       if eu.alive and eu.player_id != pid
                       and eu.x == nx and eu.y == ny), None)
        if target:
            return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # Move toward enemy city
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)
