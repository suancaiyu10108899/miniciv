"""
FlatMC depth scan — multi-process, paired evaluation.
Tests ROLLOUT_DEPTH = [5, 10, 20, 50] vs Random (random rollout for speed).

Fixes vs v1:
- multiprocessing.Pool + maxtasksperchild (Windows handle leak fix)
- Random rollout policy (Greedy rollout is 8x slower; we're measuring depth, not policy)
- 8 workers (conservative for Windows stability)

Usage: python experiments/v0.5.0/flatmc-depth-scan/scan.py
"""

import json, os, sys, time
from pathlib import Path
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# ─── Config ──────────────────────────────────────────
DEPTHS = [5, 10, 20, 50]
ROLLOUTS_MAP = {5: 20, 10: 10, 20: 5, 50: 2}
GAMES_PER_DEPTH = 200        # paired: 200 seeds → 400 sims
SIZE = 15
MAX_TURNS = 100
GENERATOR = "balanced"
BASE_SEED = 42
MAX_WORKERS = 8              # conservative for Windows handle stability
TASKS_PER_CHILD = 25         # recycle workers to prevent handle leak

OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════
# Worker (runs in its own process — no shared state)
# ═══════════════════════════════════════════════════════

def _worker_game(args):
    """
    Run ONE game. Patches FlatMC globals in-process (isolated).
    Uses random rollout policy for speed (scan measures depth, not policy).
    """
    seed, flatmc_is_p0, depth, rollouts = args

    import prototype.ai_flatmc as fmc
    fmc.ROLLOUT_DEPTH = depth
    fmc.ROLLOUTS = rollouts
    # Patch rollout policy to random for speed — we're scanning DEPTH, not policy
    fmc._fast_rollout = _make_fast_rollout_random()

    from prototype.eval import run_one_game
    from prototype.ai_rulesrandom import ai_decide as random_decide

    if flatmc_is_p0:
        ai0 = fmc.ai_decide
        ai1 = random_decide
    else:
        ai0 = random_decide
        ai1 = fmc.ai_decide

    result = run_one_game(
        seed=seed, ai0_func=ai0, ai1_func=ai1,
        size=SIZE, generator_id=GENERATOR, max_turns=MAX_TURNS,
    )
    result["flatmc_pid"] = 0 if flatmc_is_p0 else 1
    result["depth"] = depth
    return result


def _make_fast_rollout_random():
    """Return a _fast_rollout function that uses random-vs-random (fast)."""
    import random as _random
    from prototype.game import step_game
    from prototype.ai_rulesrandom import ai_decide as _rdecide

    def _fast_rollout(gs, pid, rng):
        rng0 = _random.Random(rng.randint(0, 2**30))
        rng1 = _random.Random(rng.randint(0, 2**30))
        import prototype.ai_flatmc as fmc
        orig_turn = gs.turn
        max_turns = orig_turn + fmc.ROLLOUT_DEPTH
        while gs.winner is None and gs.turn < max_turns:
            step_game(gs, _rdecide(gs, 0, rng0), _rdecide(gs, 1, rng1))
        if gs.winner == pid:
            return 10.0
        elif gs.winner == 1 - pid:
            return -10.0
        return fmc._rollout_score(gs, pid)

    return _fast_rollout


# ═══════════════════════════════════════════════════════
# Run one depth
# ═══════════════════════════════════════════════════════

def _run_depth(depth: int, rollouts: int) -> dict:
    """Run 200 paired games at one depth. Returns summary dict."""
    n_pairs = GAMES_PER_DEPTH
    n_tasks = n_pairs * 2
    print(f"\n{'='*50}")
    print(f"Depth={depth}, Rollouts={rollouts}, {n_pairs} paired games ({n_tasks} sims)")
    print(f"Workers={MAX_WORKERS}, TasksPerChild={TASKS_PER_CHILD}")
    print(f"{'='*50}")

    tasks = []
    for i in range(n_pairs):
        seed = BASE_SEED + i * 1000 + depth * 100000
        tasks.append((seed, True,  depth, rollouts))
        tasks.append((seed, False, depth, rollouts))

    start = time.time()
    results = []
    flatmc_wins = 0

    # Pool with maxtasksperchild → recycle workers before handle leak
    with Pool(processes=MAX_WORKERS, maxtasksperchild=TASKS_PER_CHILD) as pool:
        for i, r in enumerate(pool.imap_unordered(_worker_game, tasks)):
            results.append(r)
            if r["winner"] == r["flatmc_pid"]:
                flatmc_wins += 1

            completed = i + 1
            if completed % 80 == 0 or completed == n_tasks:
                elapsed = time.time() - start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (n_tasks - completed) / rate if rate > 0 else 0
                wr = flatmc_wins / completed * 100
                print(f"  [{completed:4d}/{n_tasks}] winrate={wr:.1f}% "
                      f"rate={rate:.1f} games/s elapsed={elapsed:.0f}s eta={eta:.0f}s")

    elapsed = time.time() - start
    n_results = len(results)
    winrate = flatmc_wins / n_results if n_results else 0.0
    avg_time = elapsed / n_results if n_results else 0.0
    conquests = sum(1 for r in results if r.get("victory_type") == "conquest")
    conquest_rate = conquests / n_results if n_results else 0.0

    # Also compute P0 advantage: FlatMC winrate when it's P0 vs P1
    p0_wins = sum(1 for r in results if r["flatmc_pid"] == 0 and r["winner"] == 0)
    p1_wins = sum(1 for r in results if r["flatmc_pid"] == 1 and r["winner"] == 1)
    p0_total = sum(1 for r in results if r["flatmc_pid"] == 0)
    p1_total = sum(1 for r in results if r["flatmc_pid"] == 1)
    p0_winrate = p0_wins / p0_total if p0_total else 0
    p1_winrate = p1_wins / p1_total if p1_total else 0

    summary = {
        "depth": depth,
        "rollouts": rollouts,
        "games_paired": n_pairs,
        "sims_completed": n_results,
        "flatmc_wins": flatmc_wins,
        "winrate": round(winrate, 4),
        "winrate_p0": round(p0_winrate, 4),
        "winrate_p1": round(p1_winrate, 4),
        "avg_time_s": round(avg_time, 3),
        "total_time_s": round(elapsed, 1),
        "conquest_rate": round(conquest_rate, 4),
        "workers": MAX_WORKERS,
        "rollout_policy": "random",
    }
    print(f"  DONE depth={depth}: winrate={winrate*100:.1f}% (P0={p0_winrate*100:.1f}% P1={p1_winrate*100:.1f}%) "
          f"avg={avg_time:.3f}s/game conquest={conquest_rate*100:.1f}%")
    return summary


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

def main():
    grand_total = len(DEPTHS) * GAMES_PER_DEPTH * 2
    print(f"FlatMC Depth Scan v2")
    print(f"  Depths: {DEPTHS}")
    print(f"  Rollout policy: random (fast — measuring depth, not policy)")
    print(f"  Workers: {MAX_WORKERS} (maxtasksperchild={TASKS_PER_CHILD})")
    print(f"  Games per depth: {GAMES_PER_DEPTH} paired")
    print(f"  Total sims: {grand_total}")
    print(f"  Output: {OUTPUT_DIR / 'results.json'}")
    print(f"  Partial: {OUTPUT_DIR / 'results_partial.json'}")

    all_summaries = []
    grand_start = time.time()

    for di, depth in enumerate(DEPTHS):
        rollouts = ROLLOUTS_MAP[depth]
        summary = _run_depth(depth, rollouts)
        all_summaries.append(summary)

        # Save intermediate after each depth
        partial_path = OUTPUT_DIR / "results_partial.json"
        with open(partial_path, "w") as f:
            json.dump(all_summaries, f, indent=2)
        print(f"  [partial save] {partial_path}")

    grand_elapsed = time.time() - grand_start

    # Final save
    results_path = OUTPUT_DIR / "results.json"
    with open(results_path, "w") as f:
        json.dump({
            "config": {
                "depths": DEPTHS,
                "rollouts_map": ROLLOUTS_MAP,
                "games_per_depth": GAMES_PER_DEPTH,
                "size": SIZE,
                "max_turns": MAX_TURNS,
                "workers": MAX_WORKERS,
                "rollout_policy": "random",
                "generator": GENERATOR,
            },
            "total_time_s": round(grand_elapsed, 1),
            "results": all_summaries,
        }, f, indent=2)

    print(f"\n{'='*60}")
    print(f"FINAL RESULTS ({grand_elapsed:.0f}s total)")
    print(f"{'='*60}")
    print(f"{'Depth':<8} {'Winrate':<10} {'P0%':<8} {'P1%':<8} {'Time(s)':<10} {'Conq%':<8}")
    print("-" * 52)
    for s in all_summaries:
        print(f"{s['depth']:<8} {s['winrate']*100:>6.1f}%    "
              f"{s['winrate_p0']*100:>5.1f}%   {s['winrate_p1']*100:>5.1f}%   "
              f"{s['avg_time_s']:>6.2f}    {s['conquest_rate']*100:>5.1f}%")
    print(f"\nResults: {results_path}")


if __name__ == "__main__":
    main()
