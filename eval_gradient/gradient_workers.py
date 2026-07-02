# eval_gradient/gradient_workers.py — Worker functions for multiprocessing
#
# All functions here are top-level and importable, so they work with
# Windows spawn-mode ProcessPoolExecutor.

SIZE = 15
MAX_TURNS = 100
OPPONENTS = ["random", "greedy", "aggressive"]
GAMES_PER_MATCHUP = 5


# ═══ B1: FlatMC ═══════════════════════════════════════════════

def flatmc_worker(args):
    """Play one flatmc-vs-opponent game. args=(seed, rollouts, opp_name)."""
    seed, rollouts, opp_name = args
    import random as _random
    import prototype.ai_flatmc as flatmc_mod
    flatmc_mod.ROLLOUTS = rollouts
    from prototype.game import init_game, step_game
    from prototype.ai_rulesrandom import ai_decide as random_decide
    from prototype.ai_greedy import ai_decide as greedy_decide

    opp_func = random_decide if opp_name == "random" else greedy_decide
    flatmc_func = flatmc_mod.ai_decide

    is_p0 = (seed % 2 == 0)
    ai0 = flatmc_func if is_p0 else opp_func
    ai1 = opp_func if is_p0 else flatmc_func
    flatmc_pid = 0 if is_p0 else 1

    gs = init_game(seed=seed, size=SIZE, generator_id="balanced")
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)

    while gs.winner is None and gs.turn < MAX_TURNS:
        a0 = ai0(gs, 0, rng0)
        a1 = ai1(gs, 1, rng1)
        step_game(gs, a0, a1)

    return 1 if gs.winner == flatmc_pid else 0


# ═══ B2/B3: Evo workers ══════════════════════════════════════

def evo_eval_one(args):
    """Evaluate one individual vs all opponents. args=(seed_offset, weights, ind_id)."""
    seed_offset, weights_s, ind_id = args
    import random as _random
    from prototype.game import init_game, step_game
    from prototype.ai_evo import ai_decide as evo_decide
    from prototype.ai_rulesrandom import ai_decide as random_decide
    from prototype.ai_greedy import ai_decide as greedy_decide
    from prototype.ai_aggressive import ai_decide as aggressive_decide

    opp_funcs = {"random": random_decide, "greedy": greedy_decide, "aggressive": aggressive_decide}
    total_wins = 0
    total_games = 0

    for opp_name in OPPONENTS:
        opp_ai = opp_funcs[opp_name]
        for g in range(GAMES_PER_MATCHUP):
            is_p0 = (g % 2 == 0)
            seed = seed_offset + ind_id * 1000 + hash(opp_name) % 10000 + g

            def evo_ai(gs, pid, rng):
                return evo_decide(gs, pid, rng, weights=weights_s)

            ai0 = evo_ai if is_p0 else opp_ai
            ai1 = opp_ai if is_p0 else evo_ai
            evo_pid = 0 if is_p0 else 1

            gs = init_game(seed=seed, size=SIZE, generator_id="balanced")
            rng0 = _random.Random(seed)
            rng1 = _random.Random(seed + 1)

            while gs.winner is None and gs.turn < MAX_TURNS:
                a0 = ai0(gs, 0, rng0)
                a1 = ai1(gs, 1, rng1)
                step_game(gs, a0, a1)

            if gs.winner == evo_pid:
                total_wins += 1
            total_games += 1

    return total_wins / max(total_games, 1), total_wins, total_games


def evo_test_vs_greedy(args):
    """Test evo weights vs Greedy. args=(seed, pid_offset, weights_dict)."""
    seed, pid_offset, weights_s = args
    import random as _random
    from prototype.game import init_game, step_game
    from prototype.ai_greedy import ai_decide as greedy_decide
    from prototype.ai_evo import ai_decide as evo_decide

    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    gs = init_game(seed=seed, size=SIZE, generator_id="balanced")

    def evo_ai(gs, pid, rng):
        return evo_decide(gs, pid, rng, weights=weights_s)

    ai0 = evo_ai if pid_offset == 0 else greedy_decide
    ai1 = greedy_decide if pid_offset == 0 else evo_ai
    evo_pid = 0 if pid_offset == 0 else 1

    while gs.winner is None and gs.turn < MAX_TURNS:
        a0 = ai0(gs, 0, rng0)
        a1 = ai1(gs, 1, rng1)
        step_game(gs, a0, a1)

    return 1 if gs.winner == evo_pid else 0
