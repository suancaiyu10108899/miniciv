# prototype/eval_matrix.py — 并行全矩阵评估, ProcessPoolExecutor
# 用法: python -m prototype.eval_matrix --games 500 --size 15 --workers 24
import argparse, json, os, random, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from prototype.game import init_game, step_game
from prototype.eval import load_ai, AI_MODULES


def _run_one(args):
    """单局运行(独立函数, 用于进程池)"""
    seed, ai0_name, ai1_name, size, gen, max_turns = args
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    gs = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))
    return {
        "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
        "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_hp": gs.cities[0].hp, "p1_hp": gs.cities[1].hp,
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ais", default="random,greedy,aggressive")
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--output", default="eval_results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=100)
    args = parser.parse_args()

    ai_names = [a.strip() for a in args.ais.split(",")]
    workers = args.workers or min(24, os.cpu_count() or 4)
    pairs = [(a0, a1) for a0 in ai_names for a1 in ai_names]
    os.makedirs(args.output, exist_ok=True)

    print(f"=== Eval Matrix: {len(ai_names)}x{len(ai_names)} x {args.games} games ===")
    print(f"Map: {args.size}x{args.size} {args.gen}  Workers: {workers}")
    print()

    # 构建任务列表
    all_tasks = []
    for a0, a1 in pairs:
        for i in range(args.games):
            seed = args.seed + i * 1000 + hash((a0, a1)) % 100000
            all_tasks.append((seed, a0, a1, args.size, args.gen, args.max_turns))

    total = len(all_tasks)
    t0 = time.perf_counter()
    results_by_pair = {}
    completed = 0

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one, task): task for task in all_tasks}
        for fut in as_completed(futures):
            r = fut.result()
            key = (r["ai0"], r["ai1"])
            results_by_pair.setdefault(key, []).append(r)
            completed += 1
            if completed % max(1, total // 10) == 0:
                elapsed = time.perf_counter() - t0
                rate = completed / elapsed
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  {completed}/{total} ({completed/total*100:.0f}%) {rate:.0f}g/s ETA {eta:.0f}s")

    elapsed = time.perf_counter() - t0
    print(f"\nDone: {total} games in {elapsed:.0f}s ({total/elapsed:.0f} games/s)")

    # 汇总
    from prototype.constants import CITY_HP, CITY_DAMAGE
    print(f"\n=== Summary (CITY_HP={CITY_HP} CITY_DAMAGE={CITY_DAMAGE}) ===")
    header = f"{'P0':12s} {'P1':12s} {'P0win':>7s} {'P1win':>7s} {'Conq':>5s} {'Cons':>5s} {'Tie':>5s} {'AvgT':>6s} {'Dead':>5s}"
    print(header)
    print("-" * len(header))

    all_summaries = []
    for (a0, a1) in pairs:
        results = results_by_pair.get((a0, a1), [])
        n = len(results)
        p0w = sum(1 for r in results if r["winner"] == 0)
        p1w = sum(1 for r in results if r["winner"] == 1)
        cq = sum(1 for r in results if "conquest" in str(r["victory_type"]))
        cs = sum(1 for r in results if "construction" in str(r["victory_type"]))
        tie = n - cq - cs
        avg_t = sum(r["turns"] for r in results) / n if n else 0
        avg_d = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n if n else 0
        print(f"{a0:12s} {a1:12s} {p0w/n*100:6.1f}% {p1w/n*100:6.1f}% {cq:5d} {cs:5d} {tie:5d} {avg_t:6.1f} {avg_d:5.1f}")

        fname = f"{a0}_vs_{a1}.json"
        with open(os.path.join(args.output, fname), "w") as f:
            json.dump(results, f, indent=2)

        all_summaries.append({
            "ai0": a0, "ai1": a1, "n": n,
            "p0_winrate": p0w / n if n else 0,
            "p1_winrate": p1w / n if n else 0,
            "conquests": cq, "constructions": cs, "tiebreaks": tie,
            "avg_turns": avg_t, "avg_dead": avg_d,
        })

    config = {"games_per_pair": args.games, "size": args.size, "gen": args.gen}
    summary = {"config": config, "pairs": all_summaries, "total_games": total, "elapsed_s": round(elapsed, 1)}
    with open(os.path.join(args.output, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {args.output}/")


if __name__ == "__main__":
    main()
