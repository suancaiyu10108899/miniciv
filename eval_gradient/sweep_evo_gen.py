# eval_gradient/sweep_evo_gen.py — B2: Evo generation gradient
#
# Run evolutionary training at checkpoints [5, 10, 20, 30, 50, 80, 120, 200]
# generations.  Test each checkpoint's best weights vs Greedy for 200 games.
#
# Usage: python eval_gradient/sweep_evo_gen.py

import sys, os, json, subprocess, math, time, random, copy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHECKPOINTS = [5, 10, 20, 30, 50, 80, 120, 200]
POPULATION = 60
OPPONENTS = ["random", "greedy", "aggressive"]
GAMES_PER_MATCHUP = 5
TEST_GAMES = 200
TEST_GAMES_HIGH = 500
WORKERS = 24
SIZE = 15
MAX_TURNS = 100
OUTPUT_DIR = Path(__file__).parent
CHECKPOINT_DIR = OUTPUT_DIR / "evo_checkpoints"

# We'll run training generatively: run N generations, checkpoint, then continue


def run_training_generations(start_gen: int, target_gen: int, population: list,
                              best_winrate: float, best_weights: dict) -> tuple:
    """Run training from start_gen to target_gen (exclusive), return final state."""
    import random as _random
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
    from prototype.train_evo import evaluate_individual, create_next_generation, save_checkpoint

    for gen in range(start_gen, target_gen):
        gen_start = time.time()

        # Evaluate
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
        population = create_next_generation(elites, POPULATION, rng)

        elapsed = time.time() - gen_start
        print(f"Gen {gen+1:3d}/{target_gen} | "
              f"Best: {gen_best['winrate']*100:.1f}% "
              f"(#{gen_best['ind_id']}) | "
              f"Avg: {gen_avg*100:.1f}% | "
              f"Global best: {best_winrate*100:.1f}% | "
              f"{elapsed:.1f}s")

    return population, best_winrate, best_weights


def _run_one_test_evo_gen(args):
    """Top-level function for multiprocessing: test evo weights vs Greedy."""
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


def test_weights(weights: dict, test_label: str, games: int = TEST_GAMES) -> dict:
    """Test a weight set vs Greedy for N games using parallel execution."""
    from prototype.game import init_game, step_game
    from prototype.ai_greedy import ai_decide as greedy_decide
    from prototype.ai_evo import ai_decide as evo_decide
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import random as _random

    # Build tasks: paired design — half games evo as P0, half as P1
    tasks = []
    half = games // 2
    for i in range(half):
        seed = 10000 + i * 1000 + hash(test_label) % 100000
        tasks.append((seed, 0, weights))
    for i in range(half):
        seed = 20000 + i * 1000 + hash(test_label) % 100000
        tasks.append((seed, 1, weights))

    t0 = time.time()
    results = []
    n_workers = min(WORKERS, os.cpu_count() or 4)
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        futures = {ex.submit(_run_one_test_evo_gen, task): task for task in tasks}
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.time() - t0
    n = len(results)
    evo_wins = sum(r["evo_won"] for r in results)
    winrate = evo_wins / n if n > 0 else 0

    # stddev (Bernoulli approximation)
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
    print("B2: Evo Generation Gradient Sweep")
    print(f"  Population: {POPULATION}")
    print(f"  Opponents: {OPPONENTS}")
    print(f"  Games per matchup: {GAMES_PER_MATCHUP}")
    print(f"  Checkpoints: {CHECKPOINTS}")
    print("=" * 60)

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    # Initialize population
    rng = random.Random(42)
    from prototype.ai_evo import random_weights
    population = [random_weights(rng) for _ in range(POPULATION)]
    best_winrate = 0.0
    best_weights = None
    prev_gen = 0

    checkpoint_results = []

    for target_gen in CHECKPOINTS:
        gens_to_run = target_gen - prev_gen
        print(f"\n--- Running {gens_to_run} generations (from {prev_gen} to {target_gen}) ---")

        if gens_to_run > 0:
            population, best_winrate, best_weights = run_training_generations(
                prev_gen, target_gen, population, best_winrate, best_weights
            )

        # Save checkpoint
        ckpt_path = CHECKPOINT_DIR / f"gen_{target_gen}.json"
        with open(ckpt_path, "w") as f:
            json.dump({
                "generation": target_gen,
                "best_winrate": best_winrate,
                "weights": best_weights,
            }, f, indent=2)
        print(f"  Checkpoint saved: {ckpt_path}")

        # Test vs Greedy
        print(f"  Testing gen {target_gen} best vs Greedy ({TEST_GAMES} games)...")
        result = test_weights(best_weights, f"gen_{target_gen}", TEST_GAMES)

        # Variance check
        if result["stddev_pct"] > 5.0:
            print(f"  Stddev {result['stddev_pct']:.1f}% > 5%, re-running with {TEST_GAMES_HIGH} games")
            result = test_weights(best_weights, f"gen_{target_gen}_high", TEST_GAMES_HIGH)

        print(f"  Gen {target_gen}: winrate={result['winrate']*100:.1f}% "
              f"stddev={result['stddev_pct']:.2f}% turns={result['avg_turns']:.1f}")

        # Save raw test results
        test_path = CHECKPOINT_DIR / f"test_gen_{target_gen}.json"
        with open(test_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        checkpoint_results.append({
            "generation": target_gen,
            "train_best_winrate": best_winrate,
            "test_winrate_vs_greedy": result["winrate"],
            "test_stddev_pct": result["stddev_pct"],
            "test_games": result["games"],
            "test_avg_turns": result["avg_turns"],
        })

        prev_gen = target_gen

    # Save aggregate
    agg = {"b2_evo_generation_gradient": checkpoint_results}
    with open(OUTPUT_DIR / "b2_evo_gen_results.json", "w") as f:
        json.dump(agg, f, indent=2)

    print(f"\n{'='*60}")
    print("B2 Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
