# eval_gradient/sweep_evo_pop.py — B3: Evo population size gradient
#
# Test population sizes [20, 50, 100, 200], controlling total evaluations at 6000.
#
# Pop20: 20 gens x 20 pop x 3 opp x 5 games = 6000
# Pop50: 8  gens x 50 pop x 3 opp x 5 games = 6000
# Pop100: 4 gens x 100 pop x 3 opp x 5 games = 6000
# Pop200: 2 gens x 200 pop x 3 opp x 5 games = 6000
#
# Test each best vs Greedy 200 games.
#
# Usage: python eval_gradient/sweep_evo_pop.py

import sys, os, json, math, time, random
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

POP_CONFIGS = [
    {"pop": 20, "gens": 20},
    {"pop": 50, "gens": 8},
    {"pop": 100, "gens": 4},
    {"pop": 200, "gens": 2},
]
OPPONENTS = ["random", "greedy", "aggressive"]
GAMES_PER_MATCHUP = 5
TEST_GAMES = 200
TEST_GAMES_HIGH = 500
SIZE = 15
MAX_TURNS = 100
OUTPUT_DIR = Path(__file__).parent


def _run_one_test_evo_pop(args):
    """Top-level function for multiprocessing."""
    seed, pid_offset, weights_serialized = args
    import random as _random
    from prototype.game import init_game, step_game
    from prototype.ai_greedy import ai_decide as greedy_decide
    from prototype.ai_evo import ai_decide as evo_decide

    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    gs = init_game(seed=seed, size=SIZE, generator_id="balanced")

    def evo_ai(gs, pid, rng):
        return evo_decide(gs, pid, rng, weights=weights_serialized)

    ai0 = evo_ai if pid_offset == 0 else greedy_decide
    ai1 = greedy_decide if pid_offset == 0 else evo_ai
    evo_pid = 0 if pid_offset == 0 else 1

    while gs.winner is None and gs.turn < MAX_TURNS:
        a0 = ai0(gs, 0, rng0)
        a1 = ai1(gs, 1, rng1)
        step_game(gs, a0, a1)

    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
        "evo_won": 1 if gs.winner == evo_pid else 0,
    }


def train_population(pop_size: int, num_gens: int, label: str) -> tuple[dict, float]:
    """Train a population of pop_size for num_gens generations.
    Returns (best_weights, best_winrate).
    """
    import random as _random
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
    from prototype.train_evo import evaluate_individual

    WORKERS = min(24, os.cpu_count() or 4)

    def _create_next_gen(elites, pop_size_local, rng):
        next_gen = []
        elite_count = max(1, int(pop_size_local * 0.2))
        for i in range(min(elite_count, len(elites))):
            next_gen.append(dict(elites[i][1]))
        while len(next_gen) < pop_size_local:
            p1 = rng.choice(elites[:elite_count])[1]
            p2 = rng.choice(elites[:elite_count])[1]
            child = crossover_weights(p1, p2, rng)
            child = mutate_weights(child, rate=0.15, scale=0.2, rng=rng)
            next_gen.append(child)
        return next_gen

    rng = _random.Random(42)
    population = [random_weights(rng) for _ in range(pop_size)]
    best_winrate = 0.0
    best_weights = None

    for gen in range(num_gens):
        gen_start = time.time()
        futures = {}
        with ProcessPoolExecutor(max_workers=WORKERS) as executor:
            for i, ind in enumerate(population):
                fut = executor.submit(
                    evaluate_individual, ind, i, OPPONENTS,
                    GAMES_PER_MATCHUP, SIZE, MAX_TURNS
                )
                futures[fut] = i

            results = [None] * len(population)
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    print(f"  Worker {idx} failed: {e}")
                    results[idx] = {
                        "ind_id": idx, "winrate": -1.0, "wins": 0,
                        "games": 0, "weights": population[idx]
                    }

        results.sort(key=lambda r: r["winrate"], reverse=True)
        gen_best = results[0]
        gen_avg = sum(r["winrate"] for r in results) / len(results)

        if gen_best["winrate"] > best_winrate:
            best_winrate = gen_best["winrate"]
            best_weights = dict(gen_best["weights"])

        elites = [(r["winrate"], r["weights"]) for r in results]
        rng = _random.Random(42 + gen * 777)
        population = _create_next_gen(elites, pop_size, rng)

        elapsed = time.time() - gen_start
        print(f"  [{label}] Gen {gen+1:2d}/{num_gens} | "
              f"Best: {gen_best['winrate']*100:.1f}% "
              f"Avg: {gen_avg*100:.1f}% | "
              f"Global best: {best_winrate*100:.1f}% | "
              f"{elapsed:.1f}s")

    return best_weights, best_winrate


def test_weights(weights: dict, test_label: str, games: int) -> dict:
    """Test weights vs Greedy for N games."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import random as _random

    WORKERS = min(24, os.cpu_count() or 4)

    tasks = []
    half = games // 2
    for i in range(half):
        seed = 30000 + i * 1000 + hash(test_label) % 100000
        tasks.append((seed, 0, weights))
    for i in range(half):
        seed = 40000 + i * 1000 + hash(test_label) % 100000
        tasks.append((seed, 1, weights))

    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(_run_one_test_evo_pop, task): task for task in tasks}
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.time() - t0
    n = len(results)
    evo_wins = sum(r["evo_won"] for r in results)
    winrate = evo_wins / n if n > 0 else 0
    stddev = math.sqrt(winrate * (1 - winrate) / n) * 100 if n > 0 else 0

    avg_turns = sum(r["turns"] for r in results) / n if n > 0 else 0
    conquests = sum(1 for r in results if r.get("victory_type") == "conquest")
    constructions = sum(1 for r in results if r.get("victory_type") == "construction")
    tiebreaks = n - conquests - constructions

    return {
        "label": test_label,
        "winrate": winrate,
        "stddev_pct": stddev,
        "wins": evo_wins,
        "games": n,
        "avg_turns": avg_turns,
        "conquests": conquests,
        "constructions": constructions,
        "tiebreaks": tiebreaks,
        "elapsed_s": round(elapsed, 1),
    }


def main():
    print("=" * 60)
    print("B3: Evo Population Size Gradient Sweep")
    print(f"  Controlled total evals: 6000 per config")
    print("=" * 60)

    results = []
    total_evals_check = 0

    for cfg in POP_CONFIGS:
        pop = cfg["pop"]
        gens = cfg["gens"]
        label = f"pop{pop}_gen{gens}"
        total_evals = pop * gens * len(OPPONENTS) * GAMES_PER_MATCHUP
        total_evals_check += total_evals
        print(f"\n{'='*50}")
        print(f"Config: pop={pop} gens={gens} (total evals={total_evals})")
        print(f"{'='*50}")

        best_weights, train_best_winrate = train_population(pop, gens, label)

        print(f"  Testing {label} best vs Greedy ({TEST_GAMES} games)...")
        test_result = test_weights(best_weights, label, TEST_GAMES)

        if test_result["stddev_pct"] > 5.0:
            print(f"  Stddev {test_result['stddev_pct']:.1f}% > 5%, re-running with {TEST_GAMES_HIGH}")
            test_result = test_weights(best_weights, label + "_high", TEST_GAMES_HIGH)

        print(f"  {label}: train_best={train_best_winrate*100:.1f}% "
              f"test_vs_greedy={test_result['winrate']*100:.1f}% "
              f"stddev={test_result['stddev_pct']:.2f}% "
              f"turns={test_result['avg_turns']:.1f}")

        test_result["population"] = pop
        test_result["generations"] = gens
        test_result["total_evals"] = total_evals
        test_result["train_best_winrate"] = train_best_winrate
        results.append(test_result)

    print(f"\n{'='*60}")
    print(f"Total evals across all configs: {total_evals_check}")
    print("(should be ~24000 since each of 4 configs has 6000)")

    agg = {"b3_evo_population_gradient": results}
    with open(OUTPUT_DIR / "b3_evo_pop_results.json", "w") as f:
        json.dump(agg, f, indent=2)

    print("B3 Complete! Results saved to eval_gradient/b3_evo_pop_results.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
