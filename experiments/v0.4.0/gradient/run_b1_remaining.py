import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, math, json
from concurrent.futures import ProcessPoolExecutor, as_completed
from eval_gradient.gradient_workers import flatmc_worker

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # Load partial results
    with open(os.path.join(OUTPUT_DIR, "b1_partial.json")) as f:
        results = json.load(f)

    rollouts_list = [10, 25, 50, 100]

    for rollouts in rollouts_list:
        for opp in ["random", "greedy"]:
            label = "flatmc_r%d_vs_%s" % (rollouts, opp)
            print("--- %s (200 games) ---" % label, flush=True)
            base_seed = 10000 + rollouts * 100 + (0 if opp == "random" else 50000)
            tasks = [(base_seed + i * 1000, rollouts, opp) for i in range(200)]
            t0 = time.time()
            wins = 0
            with ProcessPoolExecutor(max_workers=12) as ex:
                futures = {ex.submit(flatmc_worker, t): t for t in tasks}
                for fut in as_completed(futures):
                    wins += fut.result()
            et = time.time() - t0
            wr = wins / len(tasks)
            std = math.sqrt(wr * (1 - wr) / len(tasks)) * 100
            print("  -> winrate=%.1f%%  stddev=%.2f%%  (%d s)" % (wr * 100, std, et), flush=True)
            results.append({
                "rollouts": rollouts,
                "opponent": opp,
                "games": len(tasks),
                "winrate": wr,
                "stddev_pct": std,
                "elapsed_s": round(et, 1),
            })

    with open(os.path.join(OUTPUT_DIR, "b1_flatmc_results.json"), "w") as f:
        json.dump({"b1_flatmc_gradient": results}, f, indent=2)
    print("\nB1 Complete!", flush=True)


if __name__ == "__main__":
    main()
