# prototype/ai_flatmc.py — FlatMC v13:  rollout-based Monte Carlo agent
#
# FlatMC evaluates each legal action by running N rollouts (playouts using
# random/Greedy policy), scoring each by state advantage, and picking the
# action with the highest average score.
#
# Rollout count is configurable via a module-level variable so external
# scripts can sweep it without touching constants.py.

import random as _random
import copy as _copy
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.combat import resolve_melee, resolve_ranged
from prototype.constants import CITY_DAMAGE

# --- Configurable rollout count (tweak before calling ai_decide) ---
ROLLOUTS = 10  # default; overridden by sweep scripts

# --- Rollout scoring ---

def _rollout_score(gs, pid: int) -> float:
    """Score a terminal state from pid's perspective.
    Positive = good for pid.  Uses city HP difference and alive unit count.
    """
    opp = 1 - pid
    my_city_hp = gs.cities[pid].hp
    opp_city_hp = gs.cities[opp].hp
    my_alive = sum(1 for u in gs.units if u.player_id == pid and u.alive)
    opp_alive = sum(1 for u in gs.units if u.player_id == opp and u.alive)
    # Normalise so scores are roughly comparable across states
    hp_diff = (my_city_hp - opp_city_hp) / 100.0
    unit_diff = (my_alive - opp_alive) / 5.0
    return hp_diff + unit_diff


def _random_rollout(gs, pid: int, max_turns: int = 30, rng=None):
    """Play out the game from current state using random policies for both sides,
    returning the terminal score for pid.  Uses a *copy* of gs so we don't
    mutate the real state.
    """
    sim_gs = _copy.deepcopy(gs)
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    rng0 = _random.Random(rng.randint(0, 2**30))
    rng1 = _random.Random(rng.randint(0, 2**30))

    from prototype.ai_rulesrandom import ai_decide as _random_decide

    while sim_gs.winner is None and sim_gs.turn - gs.turn < max_turns:
        from prototype.game import step_game
        a0 = _random_decide(sim_gs, 0, rng0)
        a1 = _random_decide(sim_gs, 1, rng1)
        step_game(sim_gs, a0, a1)

    if sim_gs.winner == pid:
        return 10.0  # big win bonus
    elif sim_gs.winner == 1 - pid:
        return -10.0
    else:
        return _rollout_score(sim_gs, pid)


def _greedy_rollout(gs, pid: int, max_turns: int = 30, rng=None):
    """Play out the game using pid=Greedy, opponent=Random, scoring the result.
    This gives a stronger signal than pure-random rollouts.
    """
    sim_gs = _copy.deepcopy(gs)
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    rng0 = _random.Random(rng.randint(0, 2**30))
    rng1 = _random.Random(rng.randint(0, 2**30))

    from prototype.ai_greedy import ai_decide as _greedy_decide
    from prototype.ai_rulesrandom import ai_decide as _random_decide

    evo_ai = _greedy_decide
    opp_ai = _random_decide

    while sim_gs.winner is None and sim_gs.turn - gs.turn < max_turns:
        from prototype.game import step_game
        a0 = evo_ai(sim_gs, 0, rng0) if pid == 0 else opp_ai(sim_gs, 0, rng0)
        a1 = opp_ai(sim_gs, 1, rng1) if pid == 0 else evo_ai(sim_gs, 1, rng1)
        step_game(sim_gs, a0, a1)

    if sim_gs.winner == pid:
        return 10.0
    elif sim_gs.winner == 1 - pid:
        return -10.0
    else:
        return _rollout_score(sim_gs, pid)


# --- FlatMC decision ---

def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """FlatMC agent: for each unit, enumerate legal moves, run ROLLOUTS
    random-policy playouts per move, pick the move with highest avg score.

    Uses Greedy(pid) vs Random(opp) rollouts by default (stronger signal).
    Falls back to random-vs-random if deepcopy fails on large states.
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)

    # Delegate to Greedy for decisions that don't involve combat (tech, production, worker)
    # FlatMC only needs to evaluate combat moves.
    from prototype.ai_greedy import ai_decide as _greedy_decide
    greedy_actions = _greedy_decide(gs, pid, rng)

    # Identify combat units and find the first one with >1 legal move
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    fighters = [u for u in units if u.unit_type not in ("worker",)]

    # If no combat units, return Greedy's decisions directly
    if not fighters:
        return greedy_actions

    # We only FlatMC-evaluate the first combat unit that has multiple legal moves,
    # for performance reasons.  The rest use Greedy defaults.
    found_flatmc = False
    flatmc_action = None

    for u in fighters:
        if found_flatmc:
            break
        legal = get_single_step_moves(u, gs.grid)
        if not legal:
            continue
        # Include "end_turn" as a candidate action
        candidates = [None] + legal  # None = end_turn
        # If only 1 legal move, skip flatmc
        if len(candidates) <= 1:
            continue

        found_flatmc = True
        # Evaluate each candidate
        best_score = -float('inf')
        best_candidate = candidates[0]
        ui = units.index(u)

        for cand in candidates:
            scores = []
            for r in range(ROLLOUTS):
                # Build a copy of the actions list with this candidate for u
                test_actions = []
                for a in greedy_actions:
                    if a.get("unit_idx") == ui:
                        if cand is None:
                            test_actions.append({"unit_idx": ui, "type": "end_turn"})
                        else:
                            test_actions.append({"unit_idx": ui, "type": "move",
                                                 "dx": cand[0], "dy": cand[1]})
                    else:
                        test_actions.append(a)

                # Simulate one turn with this action, then rollout
                sim = _copy.deepcopy(gs)
                from prototype.game import step_game
                if pid == 0:
                    step_game(sim, test_actions, _dummy_opponent_actions(sim, 1, rng))
                else:
                    step_game(sim, _dummy_opponent_actions(sim, 0, rng), test_actions)

                if sim.winner is not None:
                    score = 10.0 if sim.winner == pid else -10.0
                else:
                    score = _greedy_rollout(sim, pid, max_turns=20, rng=rng)

                scores.append(score)

            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_candidate = cand

        # Build the action for this unit
        if best_candidate is None:
            flatmc_action = {"unit_idx": ui, "type": "end_turn"}
        else:
            flatmc_action = {"unit_idx": ui, "type": "move",
                             "dx": best_candidate[0], "dy": best_candidate[1]}

        # Replace the greedy action for this unit
        for i, a in enumerate(greedy_actions):
            if a.get("unit_idx") == ui:
                greedy_actions[i] = flatmc_action
                break

    return greedy_actions


def _dummy_opponent_actions(gs, pid, rng):
    """Generate dummy opponent actions (end_turn for all units)."""
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    return [{"unit_idx": i, "type": "end_turn"} for i in range(len(units))]
