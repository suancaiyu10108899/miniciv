import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, math, json
from concurrent.futures import ProcessPoolExecutor, as_completed
from eval_gradient.gradient_workers import evo_eval_one, evo_test_vs_greedy, OPPONENTS, GAMES_PER_MATCHUP
from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
import random as _random

WORKERS = 12
CHECKPOINTS = [5, 10, 20, 30, 50, 80, 120, 200]
POPULATION = 60
TEST_GAMES = 200
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_DIR = os.path.join(OUTPUT_DIR, "evo_checkpoints")


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
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    print("B2: Evo Generation Gradient", flush=True)
    print("  Pop=%d  Checkpoints=%s" % (POPULATION, CHECKPOINTS), flush=True)

    rng = _random.Random(42)
    population = [random_weights(rng) for _ in range(POPULATION)]
    best_wr = 0.0
    best_w = None
    prev_gen = 0
    cp_results = []

    for target_gen in CHECKPOINTS:
        to_run = target_gen - prev_gen
        print("\n--- Running %d gens (-> gen %d) ---" % (to_run, target_gen), flush=True)

        if to_run > 0:
            for gen in range(prev_gen, target_gen):
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
                        except Exception as e:
                            print("  Worker %d failed: %s" % (idx, e), flush=True)
                            rl[idx] = {"winrate": -1.0, "weights": population[idx]}
                rl.sort(key=lambda x: x["winrate"], reverse=True)
                gb = rl[0]
                ga = sum(x["winrate"] for x in rl) / len(rl)
                if gb["winrate"] > best_wr:
                    best_wr = gb["winrate"]
                    best_w = dict(gb["weights"])
                elites = [(x["winrate"], x["weights"]) for x in rl]
                rng = _random.Random(42 + gen * 777)
                population = next_gen(elites, POPULATION, rng)
                elapsed = time.time() - t0
                print("  Gen %3d/%d | Best:%.1f%% Avg:%.1f%% Global:%.1f%% | %d s" % (
                    gen + 1, target_gen, gb["winrate"] * 100, ga * 100, best_wr * 100, elapsed), flush=True)

            prev_gen = target_gen

        # Save checkpoint
        ckpt_path = os.path.join(CHECKPOINT_DIR, "b2_gen_%d.json" % target_gen)
        with open(ckpt_path, "w") as f:
            json.dump({"gen": target_gen, "wr": best_wr, "w": best_w}, f, indent=2)

        # Test vs Greedy
        print("  Testing gen %d vs Greedy (%d games)..." % (target_gen, TEST_GAMES), flush=True)
        half = TEST_GAMES // 2
        tasks = [(10000 + i * 1000 + target_gen, 0, best_w) for i in range(half)]
        tasks += [(20000 + i * 1000 + target_gen, 1, best_w) for i in range(half)]
        t0 = time.time()
        tw = 0
        with ProcessPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(evo_test_vs_greedy, t): t for t in tasks}
            for fut in as_completed(futures):
                tw += fut.result()
        et = time.time() - t0
        twr = tw / len(tasks)
        ts = math.sqrt(twr * (1 - twr) / len(tasks)) * 100
        print("  Gen %d: winrate=%.1f%% stddev=%.2f%% (%d s)" % (target_gen, twr * 100, ts, et), flush=True)

        cp_results.append({
            "generation": target_gen,
            "train_best_winrate": best_wr,
            "test_winrate_vs_greedy": twr,
            "test_stddev_pct": ts,
            "test_games": len(tasks),
            "elapsed_s": round(et, 1),
        })

    with open(os.path.join(OUTPUT_DIR, "b2_evo_gen_results.json"), "w") as f:
        json.dump({"b2_evo_generation_gradient": cp_results}, f, indent=2)
    print("\nB2 Complete!", flush=True)


if __name__ == "__main__":
    main()
