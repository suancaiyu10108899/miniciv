import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, math, json
from concurrent.futures import ProcessPoolExecutor, as_completed
from eval_gradient.gradient_workers import evo_eval_one, evo_test_vs_greedy, OPPONENTS, GAMES_PER_MATCHUP
from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
import random as _random

WORKERS = 12
pop_configs = [{"pop": 20, "gens": 20}, {"pop": 50, "gens": 8}, {"pop": 100, "gens": 4}, {"pop": 200, "gens": 2}]


def next_gen(elites, pop_size, rng):
    nxt = []
    ec = max(1, int(pop_size * 0.2))
    for i in range(min(ec, len(elites))):
        nxt.append(dict(elites[i][1]))
    while len(nxt) < pop_size:
        p1 = rng.choice(elites[:ec])[1]
        p2 = rng.choice(elites[:ec])[1]
        child = crossover_weights(p1, p2, rng)
        child = mutate_weights(child, rate=0.15, scale=0.2, rng=rng)
        nxt.append(child)
    return nxt


def main():
    results = []
    for cfg in pop_configs:
        pop = cfg["pop"]
        gens = cfg["gens"]
        label = "pop%d_gen%d" % (pop, gens)
        evals = pop * gens * len(OPPONENTS) * GAMES_PER_MATCHUP
        print("\nPop=%d  Gens=%d  (evals=%d)" % (pop, gens, evals), flush=True)

        rng = _random.Random(42)
        population = [random_weights(rng) for _ in range(pop)]
        best_wr = 0.0
        best_w = None

        for gen in range(gens):
            t0 = time.time()
            futures = {}
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                for i, ind in enumerate(population):
                    futures[ex.submit(evo_eval_one, (42 + gen * 1000, ind, i))] = i
                rl = [None] * len(population)
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        wr, w, g = fut.result()
                        rl[idx] = {"winrate": wr, "weights": population[idx]}
                    except:
                        rl[idx] = {"winrate": -1.0, "weights": population[idx]}
            rl.sort(key=lambda x: x["winrate"], reverse=True)
            gb = rl[0]
            ga = sum(x["winrate"] for x in rl) / len(rl)
            if gb["winrate"] > best_wr:
                best_wr = gb["winrate"]
                best_w = dict(gb["weights"])
            elites = [(x["winrate"], x["weights"]) for x in rl]
            rng = _random.Random(42 + gen * 777)
            population = next_gen(elites, pop, rng)
            elapsed = time.time() - t0
            print("  [%s] Gen %2d/%d | Best:%.1f%% Avg:%.1f%% Global:%.1f%% | %d s" % (
                label, gen + 1, gens, gb["winrate"] * 100, ga * 100, best_wr * 100, elapsed), flush=True)

        # Test vs Greedy
        test_games = 200
        print("  Testing vs Greedy (%d games)..." % test_games, flush=True)
        half = test_games // 2
        tasks = [(50000 + i * 1000 + pop, 0, best_w) for i in range(half)]
        tasks += [(60000 + i * 1000 + pop, 1, best_w) for i in range(half)]
        t0 = time.time()
        tw = 0
        with ProcessPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(evo_test_vs_greedy, t): t for t in tasks}
            for fut in as_completed(futures):
                tw += fut.result()
        et = time.time() - t0
        twr = tw / len(tasks)
        ts = math.sqrt(twr * (1 - twr) / len(tasks)) * 100
        print("  %s: train=%.1f%% test=%.1f%% stddev=%.2f%% (%d s)" % (
            label, best_wr * 100, twr * 100, ts, et), flush=True)

        results.append({
            "population": pop, "generations": gens, "total_evals": evals,
            "train_best_winrate": best_wr,
            "test_winrate_vs_greedy": twr,
            "test_stddev_pct": ts,
        })

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "b3_evo_pop_results.json"), "w") as f:
        json.dump({"b3_evo_population_gradient": results}, f, indent=2)
    print("\nB3 Complete!", flush=True)


if __name__ == "__main__":
    main()
