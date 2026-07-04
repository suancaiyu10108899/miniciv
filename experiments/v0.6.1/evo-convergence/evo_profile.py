#!/usr/bin/env python
"""Evo Convergence Profile — 测量Evo训练胜率随代数变化曲线。

回答三个问题:
1. 多少代收敛? (爬坡期长度)
2. 收敛后胜率多少? (平台期高度)
3. 什么代数性价比最高? (快速迭代用 vs 严肃验证用)

方法: 200代 × 种群60, 每2代存档一次checkpoint + 评估 vs 3个对手。
"""

import json, os, sys, time, random, copy
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from prototype.game import init_game, step_game
from prototype.eval import load_ai
from prototype.ai_evo import ai_decide, DEFAULT_WEIGHTS, random_weights
import prototype.cleanup

# ─── Config ──────────────────────────────────────
GENERATIONS = 200
POPULATION = 60
ELITE_RATIO = 0.2
EVAL_OPPONENTS = ["random", "greedy", "aggressive"]
EVAL_GAMES_PER_OPPONENT = 10  # paired games per checkpoint
CHECKPOINT_EVERY = 5           # generations between checkpoints
SIZE = 15
OUTPUT_DIR = Path(__file__).parent
WORKERS = 20

EVO_WEIGHT_BOUNDS = {k: (v[1], v[2]) for k, v in DEFAULT_WEIGHTS.items()}


class EvoAgent:
    def __init__(self, w): self.w = w
    def decide(self, gs, pid, rng):
        return ai_decide(gs, pid, rng, weights=self.w)


def evaluate_weights(weights, opponent, games):
    """Paired evaluation: returns winrate."""
    agent = EvoAgent(weights)
    opp = load_ai(opponent)
    wins = 0
    total = games * 2
    for s in range(games):
        gs = init_game(seed=s * 1000 + 1, size=SIZE)
        rng0 = random.Random(s * 1000 + 1)
        rng1 = random.Random(s * 1000 + 2)
        while gs.winner is None and gs.turn < 100:
            step_game(gs, agent.decide(gs, 0, rng0), opp(gs, 1, rng1))
        if gs.winner == 0: wins += 1
        gs = init_game(seed=s * 1000 + 2, size=SIZE)
        rng0 = random.Random(s * 1000 + 2)
        rng1 = random.Random(s * 1000 + 1)
        while gs.winner is None and gs.turn < 100:
            step_game(gs, opp(gs, 0, rng0), agent.decide(gs, 1, rng1))
        if gs.winner == 1: wins += 1
    return wins / total


def evaluate_full(weights, checkpoint_id):
    """Full evaluation vs all opponents."""
    results = {}
    for opp in EVAL_OPPONENTS:
        wr = evaluate_weights(weights, opp, EVAL_GAMES_PER_OPPONENT)
        results[opp] = wr
    return results


def mutate(w, rng):
    child = {}
    for key, (lo, hi) in EVO_WEIGHT_BOUNDS.items():
        v = w.get(key, (lo + hi) / 2)
        v += rng.gauss(0, (hi - lo) * 0.08)
        child[key] = max(lo, min(hi, v))
    return child


def crossover(a, b, rng):
    child = {}
    for key in EVO_WEIGHT_BOUNDS:
        child[key] = a[key] if rng.random() < 0.5 else b[key]
    return child


def main():
    print("=" * 60)
    print("Evo Convergence Profile")
    print(f"Generations: {GENERATIONS}, Pop: {POPULATION}")
    print(f"Checkpoints every {CHECKPOINT_EVERY} gens, vs {EVAL_OPPONENTS}")
    print("=" * 60)

    rng = random.Random(42)
    pop = [random_weights(rng) for _ in range(POPULATION)]
    best_overall = None
    best_overall_wr = 0
    history = []

    t0 = time.time()

    for gen in range(GENERATIONS + 1):  # +1 to evaluate gen 0
        # Evaluate population (parallel)
        with ProcessPoolExecutor(max_workers=WORKERS) as ex:
            futures = {}
            for i, w in enumerate(pop):
                fut = ex.submit(evaluate_weights, w, "greedy", 5)
                futures[fut] = (i, w)

            scores = []
            for fut in as_completed(futures):
                i, w = futures[fut]
                wr = fut.result()
                scores.append((wr, i, w))

        scores.sort(key=lambda x: -x[0])
        best_wr, best_i, best_w = scores[0]
        avg_wr = sum(s[0] for s in scores) / len(scores)

        if best_wr > best_overall_wr:
            best_overall_wr = best_wr
            best_overall = copy.deepcopy(best_w)

        elapsed = time.time() - t0
        marker = ""
        if gen % CHECKPOINT_EVERY == 0:
            # Full evaluation vs all opponents
            full_eval = evaluate_full(best_w, gen)
            checkpoint = {
                "gen": gen,
                "best_wr_vs_greedy": best_wr,
                "avg_wr": avg_wr,
                "overall_best_wr": best_overall_wr,
                "vs_opponents": full_eval,
                "weights": best_w,
                "elapsed_s": elapsed,
            }
            history.append(checkpoint)

            avg_vs_opp = sum(full_eval.values()) / len(full_eval)
            marker = (f"  vs R={full_eval['random']:.1%} "
                      f"G={full_eval['greedy']:.1%} "
                      f"A={full_eval['aggressive']:.1%} "
                      f"avg={avg_vs_opp:.1%}")

        print(f"Gen {gen:3d}: best={best_wr:.1%} avg={avg_wr:.1%} "
              f"overall={best_overall_wr:.1%} ({elapsed:.0f}s){marker}")

        if gen >= GENERATIONS:
            break

        # Breed next generation
        n_elite = max(2, int(POPULATION * ELITE_RATIO))
        elite = [s[2] for s in scores[:n_elite]]
        new_pop = list(elite)
        while len(new_pop) < POPULATION:
            a = elite[rng.randint(0, len(elite) - 1)]
            b = elite[rng.randint(0, len(elite) - 1)]
            child = crossover(a, b, rng)
            child = mutate(child, rng)
            new_pop.append(child)
        pop = new_pop[:POPULATION]

    # ─── Save ───
    total_time = time.time() - t0
    profile = {
        "config": {
            "generations": GENERATIONS, "population": POPULATION,
            "elite_ratio": ELITE_RATIO, "checkpoint_every": CHECKPOINT_EVERY,
            "eval_opponents": EVAL_OPPONENTS,
        },
        "total_time_s": total_time,
        "history": history,
    }
    with open(OUTPUT_DIR / "evo_profile.json", "w") as f:
        json.dump(profile, f, indent=2)

    # Summary table
    print(f"\n{'='*60}")
    print(f"CONVERGENCE PROFILE (total: {total_time:.0f}s)")
    print(f"{'Gen':>5}  {'vs_R':>6} {'vs_G':>6} {'vs_A':>6} {'Avg':>6}  Notes")
    print("-" * 50)
    for h in history:
        vs = h["vs_opponents"]
        avg = sum(vs.values()) / len(vs)
        notes = ""
        if h["gen"] == 0:
            notes = "baseline (random weights)"
        elif h["gen"] == history[-1]["gen"]:
            notes = "final"
        elif len(history) >= 3:
            # Detect plateau start
            idx = history.index(h)
            if idx >= 2:
                prev_avg = sum(history[idx-1]["vs_opponents"].values()) / len(history[idx-1]["vs_opponents"])
                delta = avg - prev_avg
                if delta < 0.02 and prev_avg > 0.5:
                    notes = f"plateau? (+{delta:.1%})"
        print(f"{h['gen']:>5}  {vs['random']:>5.1%} {vs['greedy']:>5.1%} {vs['aggressive']:>5.1%} {avg:>5.1%}  {notes}")

    # Analysis
    print(f"\nAnalysis:")
    # Find where improvement drops below 2% per checkpoint
    for i in range(1, len(history)):
        prev_avg = sum(history[i-1]["vs_opponents"].values()) / len(history[i-1]["vs_opponents"])
        curr_avg = sum(history[i]["vs_opponents"].values()) / len(history[i]["vs_opponents"])
        delta = curr_avg - prev_avg
        if delta < 0.02 and curr_avg > 0.6:
            print(f"  Plateau begins around gen {history[i]['gen']} (delta={delta:.1%})")
            print(f"  Fast-iteration sweet spot: gen {history[i-1]['gen']}")
            print(f"  Benchmark sweet spot: gen {history[-1]['gen']}")
            break
    else:
        print(f"  No clear plateau — still improving at gen {history[-1]['gen']}")

    print(f"\nProfile saved: {OUTPUT_DIR / 'evo_profile.json'}")


if __name__ == "__main__":
    main()
