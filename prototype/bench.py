import argparse, time, random, multiprocessing as mp
from prototype.game import init_game, step_game
from prototype import eval as _eval

def bench_one(ai_name, games=20, size=15, max_turns=100):
    ai_func = _eval.load_ai(ai_name)
    times = []
    for i in range(games):
        seed = 42 + i * 1000
        gs = init_game(seed=seed, size=size, generator_id="balanced")
        rng0 = random.Random(seed)
        rng1 = random.Random(seed + 1)
        t0 = time.perf_counter()
        while gs.winner is None and gs.turn < max_turns:
            a0 = ai_func(gs, 0, rng0)
            a1 = ai_func(gs, 1, rng1)
            step_game(gs, a0, a1)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
    return sum(times)/len(times), min(times), max(times)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--size", type=int, default=15)
    args = parser.parse_args()
    ai_names = ["random", "greedy", "aggressive", "flatmc"]
    results = {}
    print(f"=== AI Speed Benchmark ({args.games} games, {args.size}x{args.size}) ===")
    print()
    for name in ai_names:
        print(f"  {name:12s}...", end=" ", flush=True)
        avg, lo, hi = bench_one(name, args.games, args.size)
        results[name] = {"avg": avg, "min": lo, "max": hi}
        print(f"avg={avg:.2f}s min={lo:.2f}s max={hi:.2f}s")
    workers = min(24, mp.cpu_count())
    print()
    print(f"=== Throughput (x{workers} workers) ===")
    for name in ai_names:
        r = results[name]
        ph = 3600 / r["avg"] * workers
        print(f"  {name:12s} {r['avg']:.2f}s -> {ph:.0f} games/h")
    print()
    print("=== Full Matrix Estimate (16 pairs) ===")
    ptimes = {}
    for a0 in ai_names:
        for a1 in ai_names:
            ptimes[(a0,a1)] = max(results[a0]["avg"], results[a1]["avg"])
    avgp = sum(ptimes.values()) / len(ptimes)
    for n in [100, 500, 1000]:
        total_h = 16 * n * avgp / 3600
        wall_m = total_h * 3600 / workers / 60
        print(f"  {n:4d} games/pair -> {total_h:.1f}h CPU -> ~{wall_m:.0f}min wall")
    print()
    fa = results["flatmc"]["avg"]
    print(f"FlatMC avg={fa:.2f}s/game - " + ("SLOW, reduce rollout" if fa>1.0 else "OK"))

if __name__ == "__main__":
    main()
