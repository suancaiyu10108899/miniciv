# prototype/ai_flatmc.py — FlatMC v14: lightweight rollout-based Monte Carlo agent
#
# FlatMC evaluates each unit's legal moves by running N fast rollouts
# (random-vs-random), scoring each, and picking the highest-scoring action.
# Only the first combat unit with multiple legal moves is evaluated;
# everything else delegates to Greedy.
#
# Rollout count is controlled by module-level ROLLOUTS so sweep scripts
# can patch it without touching constants.py.

import copy as _copy
import random as _random
from prototype.movement import get_single_step_moves

ROLLOUTS = 10  # patch from outside before calling ai_decide
ROLLOUT_DEPTH = 10      # how many turns to simulate in each rollout


def _rollout_score(gs, pid: int) -> float:
    """Score a game state from pid's perspective."""
    opp = 1 - pid
    hp_diff = (gs.cities[pid].hp - gs.cities[opp].hp) / 100.0
    my_alive = sum(1 for u in gs.units if u.player_id == pid and u.alive)
    opp_alive = sum(1 for u in gs.units if u.player_id == opp and u.alive)
    unit_diff = (my_alive - opp_alive) / 5.0
    return hp_diff + unit_diff


def _fast_rollout(gs, pid: int, rng: _random.Random) -> float:
    """Fast random-vs-random rollout from gs. Returns a score for pid.
    Does NOT deepcopy internally -- caller is responsible for that.
    """
    from prototype.game import step_game
    from prototype.ai_rulesrandom import ai_decide as _rdecide

    rng0 = _random.Random(rng.randint(0, 2**30))
    rng1 = _random.Random(rng.randint(0, 2**30))
    orig_turn = gs.turn
    max_turns = orig_turn + ROLLOUT_DEPTH

    while gs.winner is None and gs.turn < max_turns:
        a0 = _rdecide(gs, 0, rng0)
        a1 = _rdecide(gs, 1, rng1)
        step_game(gs, a0, a1)

    if gs.winner == pid:
        return 10.0
    elif gs.winner == 1 - pid:
        return -10.0
    return _rollout_score(gs, pid)


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    """FlatMC agent.  Finds the first combat unit with >1 legal move,
    evaluates each candidate via ROLLOUTS random-vs-random playouts,
    picks the best, and returns a full action list.
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)

    from prototype.ai_greedy import ai_decide as _greedy_decide
    greedy_actions = _greedy_decide(gs, pid, rng)

    units = [u for u in gs.units if u.player_id == pid and u.alive]
    fighters = [u for u in units if u.unit_type not in ("worker",)]

    if not fighters:
        return greedy_actions

    found_flatmc = False

    for u in fighters:
        if found_flatmc:
            break
        legal = get_single_step_moves(u, gs.grid)
        if not legal:
            continue
        candidates = [None] + legal  # None = end_turn
        if len(candidates) <= 1:
            continue

        found_flatmc = True
        best_score = -float("inf")
        best_candidate = candidates[0]
        ui = units.index(u)

        # Pre-build opponent "end turn" actions
        opp_units = [eu for eu in gs.units if eu.player_id == 1 - pid and eu.alive]
        opp_endturn = [{"unit_idx": i, "type": "end_turn"} for i in range(len(opp_units))]

        for cand in candidates:
            scores = []
            for _rep in range(ROLLOUTS):
                # One deepcopy per rollout
                sim = _copy.deepcopy(gs)

                # Build action list for this turn
                test_actions = list(greedy_actions)
                for i, a in enumerate(test_actions):
                    if a.get("unit_idx") == ui:
                        if cand is None:
                            test_actions[i] = {"unit_idx": ui, "type": "end_turn"}
                        else:
                            test_actions[i] = {"unit_idx": ui, "type": "move",
                                               "dx": cand[0], "dy": cand[1]}
                        break

                from prototype.game import step_game
                if pid == 0:
                    step_game(sim, test_actions, opp_endturn)
                else:
                    step_game(sim, opp_endturn, test_actions)

                if sim.winner is not None:
                    scores.append(10.0 if sim.winner == pid else -10.0)
                else:
                    scores.append(_fast_rollout(sim, pid, rng))

            avg = sum(scores) / len(scores)
            if avg > best_score:
                best_score = avg
                best_candidate = cand

        # Replace the greedy action for our unit
        if best_candidate is None:
            flatmc_action = {"unit_idx": ui, "type": "end_turn"}
        else:
            flatmc_action = {"unit_idx": ui, "type": "move",
                             "dx": best_candidate[0], "dy": best_candidate[1]}

        for i, a in enumerate(greedy_actions):
            if a.get("unit_idx") == ui:
                greedy_actions[i] = flatmc_action
                break

    return greedy_actions
