# eval_gradient/run_all.py — Run all three gradient experiments
#
# Uses eval_gradient.gradient_workers for multiprocessing-safe worker functions.
#
# Usage:  python eval_gradient/run_all.py

import sys, os, json, math, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_DIR))

OUTPUT_DIR = SCRIPT_DIR
CHECKPOINT_DIR = OUTPUT_DIR / "evo_checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

SIZE = 15
MAX_TURNS = 100
WORKERS = min(24, os.cpu_count() or 4)

from eval_gradient.gradient_workers import (
    flatmc_worker,
    evo_eval_one,
    evo_test_vs_greedy,
    OPPONENTS,
    GAMES_PER_MATCHUP,
)


# ═══ B1: FlatMC Rollout Gradient ═════════════════════════════

B1_ROLLOUTS = [3, 5, 10, 25, 50, 100]
B1_GAMES = 200
B1_GAMES_HIGH = 500


def run_b1():
    from concurrent.futures import ProcessPoolExecutor, as_completed

    print("=" * 60, flush=True)
    print("B1: FlatMC Rollout Gradient", flush=True)
    print("=" * 60, flush=True)

    b1_results = []

    for rollouts in B1_ROLLOUTS:
        for opp_name in ["random", "greedy"]:
            label = f"flatmc_r{rollouts}_vs_{opp_name}"
            print(f"\n--- {label} ({B1_GAMES} games) ---", flush=True)

            tasks = [(10000 + i * 1000 + rollouts * 100 + (0 if opp_name == "random" else 50000),
                      rollouts, opp_name) for i in range(B1_GAMES)]

            t0 = time.time()
            wins = 0
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                futures = {ex.submit(flatmc_worker, t): t for t in tasks}
                for fut in as_completed(futures):
                    wins += fut.result()
            et = time.time() - t0

            n = len(tasks)
            wr = wins / n
            std = math.sqrt(wr * (1 - wr) / n) * 100
            print(f"  -> winrate={wr*100:.1f}%  stddev={std:.2f}%  ({et:.0f}s)", flush=True)

            if std > 5.0:
                print(f"  -> High variance, rerunning {B1_GAMES_HIGH}...", flush=True)
                tasks2 = [(20000 + i * 1000 + rollouts * 100 + (0 if opp_name == "random" else 50000),
                           rollouts, opp_name) for i in range(B1_GAMES_HIGH)]
                t0 = time.time()
                wins2 = 0
                with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                    futures = {ex.submit(flatmc_worker, t): t for t in tasks2}
                    for fut in as_completed(futures):
                        wins2 += fut.result()
                et = time.time() - t0
                n = len(tasks2)
                wr = wins2 / n
                std = math.sqrt(wr * (1 - wr) / n) * 100
                print(f"  -> (rerun) winrate={wr*100:.1f}%  stddev={std:.2f}%", flush=True)

            b1_results.append({
                "rollouts": rollouts,
                "opponent": opp_name,
                "games": n,
                "winrate": wr,
                "stddev_pct": std,
                "elapsed_s": round(et, 1),
            })

    with open(OUTPUT_DIR / "b1_flatmc_results.json", "w") as f:
        json.dump({"b1_flatmc_gradient": b1_results}, f, indent=2)
    print("\nB1 Complete!\n", flush=True)
    return b1_results


# ═══ B2: Evo Generation Gradient ═════════════════════════════

B2_CHECKPOINTS = [5, 10, 20, 30, 50, 80, 120, 200]
B2_POPULATION = 60
B2_TEST_GAMES = 200
B2_TEST_GAMES_HIGH = 500


def run_b2():
    from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import random as _random

    print("=" * 60, flush=True)
    print("B2: Evo Generation Gradient", flush=True)
    print(f"  Pop={B2_POPULATION}  Checkpoints={B2_CHECKPOINTS}", flush=True)
    print("=" * 60, flush=True)

    def _next_gen(elites, pop_size, rng):
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

    rng = _random.Random(42)
    population = [random_weights(rng) for _ in range(B2_POPULATION)]
    best_wr = 0.0
    best_w = None
    prev_gen = 0
    cp_results = []

    for target_gen in B2_CHECKPOINTS:
        to_run = target_gen - prev_gen
        print(f"\n--- Running {to_run} gens (-> gen {target_gen}) ---", flush=True)

        if to_run > 0:
            for gen in range(prev_gen, target_gen):
                t0 = time.time()
                futures = {}
                with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                    for i, ind in enumerate(population):
                        fut = ex.submit(evo_eval_one, (42 + gen * 1000, ind, i))
                        futures[fut] = i
                    rl = [None] * len(population)
                    for fut in as_completed(futures):
                        idx = futures[fut]
                        try:
                            wr, w, g = fut.result()
                            rl[idx] = {"winrate": wr, "weights": population[idx]}
                        except Exception as e:
                            print(f"  Worker {idx} failed: {e}", flush=True)
                            rl[idx] = {"winrate": -1.0, "weights": population[idx]}
                rl.sort(key=lambda x: x["winrate"], reverse=True)
                gb = rl[0]
                ga = sum(x["winrate"] for x in rl) / len(rl)
                if gb["winrate"] > best_wr:
                    best_wr = gb["winrate"]
                    best_w = dict(gb["weights"])
                elites = [(x["winrate"], x["weights"]) for x in rl]
                rng = _random.Random(42 + gen * 777)
                population = _next_gen(elites, B2_POPULATION, rng)
                print(f"  Gen {gen+1:3d}/{target_gen} | Best:{gb['winrate']*100:.1f}% Avg:{ga*100:.1f}% Global:{best_wr*100:.1f}% | {time.time()-t0:.0f}s", flush=True)

            prev_gen = target_gen

        with open(CHECKPOINT_DIR / f"b2_gen_{target_gen}.json", "w") as f:
            json.dump({"gen": target_gen, "wr": best_wr, "w": best_w}, f, indent=2)

        # Test vs Greedy
        print(f"  Testing gen {target_gen} vs Greedy ({B2_TEST_GAMES} games)...", flush=True)
        half = B2_TEST_GAMES // 2
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

        if ts > 5.0:
            print(f"  High variance, rerunning {B2_TEST_GAMES_HIGH}...", flush=True)
            h2 = B2_TEST_GAMES_HIGH // 2
            tasks2 = [(30000 + i * 1000 + target_gen, 0, best_w) for i in range(h2)]
            tasks2 += [(40000 + i * 1000 + target_gen, 1, best_w) for i in range(h2)]
            t0 = time.time()
            tw2 = 0
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                futures = {ex.submit(evo_test_vs_greedy, t): t for t in tasks2}
                for fut in as_completed(futures):
                    tw2 += fut.result()
            et = time.time() - t0
            twr = tw2 / len(tasks2)
            ts = math.sqrt(twr * (1 - twr) / len(tasks2)) * 100

        print(f"  Gen {target_gen}: winrate={twr*100:.1f}%  stddev={ts:.2f}%  ({et:.0f}s)", flush=True)

        cp_results.append({
            "generation": target_gen,
            "train_best_winrate": best_wr,
            "test_winrate_vs_greedy": twr,
            "test_stddev_pct": ts,
            "test_games": len(tasks),
            "elapsed_s": round(et, 1),
        })

    with open(OUTPUT_DIR / "b2_evo_gen_results.json", "w") as f:
        json.dump({"b2_evo_generation_gradient": cp_results}, f, indent=2)
    print("\nB2 Complete!\n", flush=True)
    return cp_results


# ═══ B3: Evo Population Size Gradient ═══════════════════════

B3_POP_CONFIGS = [
    {"pop": 20, "gens": 20},
    {"pop": 50, "gens": 8},
    {"pop": 100, "gens": 4},
    {"pop": 200, "gens": 2},
]
B3_TEST_GAMES = 200
B3_TEST_GAMES_HIGH = 500


def run_b3():
    from prototype.ai_evo import random_weights, mutate_weights, crossover_weights
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import random as _random

    print("=" * 60, flush=True)
    print("B3: Evo Population Gradient (total evals=6000 each)", flush=True)
    print("=" * 60, flush=True)

    def _next_gen(elites, pop_size, rng):
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

    results = []

    for cfg in B3_POP_CONFIGS:
        pop = cfg["pop"]
        gens = cfg["gens"]
        label = f"pop{pop}_gen{gens}"
        evals = pop * gens * len(OPPONENTS) * GAMES_PER_MATCHUP
        print(f"\nPop={pop}  Gens={gens}  (evals={evals})", flush=True)

        rng = _random.Random(42)
        population = [random_weights(rng) for _ in range(pop)]
        best_wr = 0.0
        best_w = None

        for gen in range(gens):
            t0 = time.time()
            futures = {}
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                for i, ind in enumerate(population):
                    fut = ex.submit(evo_eval_one, (42 + gen * 1000, ind, i))
                    futures[fut] = i
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
            population = _next_gen(elites, pop, rng)
            print(f"  [{label}] Gen {gen+1:2d}/{gens} | Best:{gb['winrate']*100:.1f}% Avg:{ga*100:.1f}% Global:{best_wr*100:.1f}% | {time.time()-t0:.0f}s", flush=True)

        # Test vs Greedy
        print(f"  Testing vs Greedy ({B3_TEST_GAMES} games)...", flush=True)
        half = B3_TEST_GAMES // 2
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

        if ts > 5.0:
            print(f"  High variance, rerunning {B3_TEST_GAMES_HIGH}...", flush=True)
            h2 = B3_TEST_GAMES_HIGH // 2
            tasks2 = [(70000 + i * 1000 + pop, 0, best_w) for i in range(h2)]
            tasks2 += [(80000 + i * 1000 + pop, 1, best_w) for i in range(h2)]
            t0 = time.time()
            tw2 = 0
            with ProcessPoolExecutor(max_workers=WORKERS) as ex:
                futures = {ex.submit(evo_test_vs_greedy, t): t for t in tasks2}
                for fut in as_completed(futures):
                    tw2 += fut.result()
            et = time.time() - t0
            twr = tw2 / len(tasks2)
            ts = math.sqrt(twr * (1 - twr) / len(tasks2)) * 100

        print(f"  {label}: train_best={best_wr*100:.1f}%  test_vs_greedy={twr*100:.1f}%  stddev={ts:.2f}%  ({et:.0f}s)", flush=True)

        results.append({
            "population": pop, "generations": gens, "total_evals": evals,
            "train_best_winrate": best_wr,
            "test_winrate_vs_greedy": twr,
            "test_stddev_pct": ts,
            "test_games": len(tasks),
            "elapsed_s": round(et, 1),
        })

    with open(OUTPUT_DIR / "b3_evo_pop_results.json", "w") as f:
        json.dump({"b3_evo_population_gradient": results}, f, indent=2)
    print("\nB3 Complete!\n", flush=True)
    return results


# ═══ Main ════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"MiniCiv Gradient Suite | Workers={WORKERS} | Size={SIZE}x{SIZE}", flush=True)
    total_t0 = time.time()

    b1 = run_b1()
    print(f"  [B1: {(time.time()-total_t0)/60:.1f} min]", flush=True)

    b2 = run_b2()
    print(f"  [B2: {(time.time()-total_t0)/60:.1f} min]", flush=True)

    b3 = run_b3()
    print(f"  [B3: {(time.time()-total_t0)/60:.1f} min]", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"ALL DONE in {(time.time()-total_t0)/60:.1f} min", flush=True)
    print("=" * 60, flush=True)
