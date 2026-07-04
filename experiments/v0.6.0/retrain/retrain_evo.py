#!/usr/bin/env python
"""Retrain Evo under new v0.6.0 rules (stacking limit + facility=5).
Compares old weights vs new weights."""
import json, os, sys, time, random, copy
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from prototype.game import init_game, step_game
from prototype.eval import load_ai
from prototype.ai_evo import ai_decide as evo_decide, DEFAULT_WEIGHTS, random_weights as evo_random_weights

# Build bounds dict from DEFAULT_WEIGHTS
EVO_WEIGHT_BOUNDS = {k: (v[1], v[2]) for k, v in DEFAULT_WEIGHTS.items()}

class EvoAgent:
    """Wrapper for ai_decide with fixed weights."""
    def __init__(self, weights):
        self.weights = weights
    def decide(self, gs, pid, rng):
        return evo_decide(gs, pid, rng, weights=self.weights)

GENERATIONS = 200
POPULATION = 50
EVAL_GAMES = 30  # games per fitness eval
SIZE = 15
OUTPUT_DIR = Path(__file__).parent


def evaluate_weights(weights, opponent="greedy", games=EVAL_GAMES):
    """Evaluate a set of weights against an opponent. Returns winrate."""
    agent = EvoAgent(weights)
    opp_fn = load_ai(opponent)
    wins = 0
    total = 0

    for s in range(games):
        # Forward: evo = P0
        gs = init_game(seed=s * 1000 + 1, size=SIZE)
        rng0 = random.Random(s * 1000 + 1)
        rng1 = random.Random(s * 1000 + 2)
        while gs.winner is None and gs.turn < 100:
            step_game(gs, agent.decide(gs, 0, rng0), opp_fn(gs, 1, rng1))
        if gs.winner == 0: wins += 1
        total += 1

        # Backward: evo = P1
        gs = init_game(seed=s * 1000 + 2, size=SIZE)
        rng0 = random.Random(s * 1000 + 2)
        rng1 = random.Random(s * 1000 + 1)
        while gs.winner is None and gs.turn < 100:
            step_game(gs, opp_fn(gs, 0, rng0), agent.decide(gs, 1, rng1))
        if gs.winner == 1: wins += 1
        total += 1

    return wins / total if total > 0 else 0


def mutate(parent_weights, rng):
    """Gaussian mutation within bounds."""
    child = {}
    for key, (low, high) in EVO_WEIGHT_BOUNDS.items():
        val = parent_weights.get(key, (low + high) / 2)
        val += rng.gauss(0, (high - low) * 0.1)
        child[key] = max(low, min(high, val))
    return child


def crossover(a, b, rng):
    """Uniform crossover."""
    child = {}
    for key in EVO_WEIGHT_BOUNDS:
        child[key] = a[key] if rng.random() < 0.5 else b[key]
    return child


def main():
    print("=" * 60)
    print("Evo Retraining — v0.6.0 Rules (facility=5, stacking limit)")
    print(f"Generations: {GENERATIONS}, Population: {POPULATION}")
    print("=" * 60)

    # Load old weights for comparison
    old_weights_path = ROOT / "prototype" / "evo_best_weights.json"
    old_weights = None
    if old_weights_path.exists():
        with open(old_weights_path) as f:
            old_weights = json.load(f)
        old_wr = evaluate_weights(old_weights, "greedy", EVAL_GAMES)
        print(f"\nOld Evo weights vs Greedy: {old_wr:.1%}")

    # Initialize population
    rng = random.Random(42)
    population = []
    for i in range(POPULATION):
        w = {}
        for key, (low, high) in EVO_WEIGHT_BOUNDS.items():
            w[key] = rng.uniform(low, high)
        population.append(w)

    best_overall = None
    best_overall_wr = 0
    history = []

    t0 = time.time()
    for gen in range(GENERATIONS):
        # Evaluate
        scores = []
        for i, w in enumerate(population):
            wr = evaluate_weights(w, "greedy", EVAL_GAMES)
            scores.append((wr, i, w))

        scores.sort(key=lambda x: -x[0])
        best_wr, best_idx, best_w = scores[0]
        avg_wr = sum(s[0] for s in scores) / len(scores)

        if best_wr > best_overall_wr:
            best_overall_wr = best_wr
            best_overall = copy.deepcopy(best_w)

        elapsed = time.time() - t0
        print(f"  Gen {gen:3d}: best={best_wr:.1%} avg={avg_wr:.1%} "
              f"overall_best={best_overall_wr:.1%} ({elapsed:.0f}s)")

        history.append({"gen": gen, "best": best_wr, "avg": avg_wr, "overall_best": best_overall_wr})

        if gen == GENERATIONS - 1:
            break

        # Select top 20%
        n_elite = max(2, POPULATION // 5)
        elite = [s[2] for s in scores[:n_elite]]

        # Breed next generation
        new_pop = list(elite)  # elitism
        while len(new_pop) < POPULATION:
            a = elite[rng.randint(0, len(elite) - 1)]
            b = elite[rng.randint(0, len(elite) - 1)]
            child = crossover(a, b, rng)
            child = mutate(child, rng)
            new_pop.append(child)
        population = new_pop[:POPULATION]

    total_time = time.time() - t0

    # ─── Results ───
    print(f"\n{'='*60}")
    print(f"Training complete: {total_time:.0f}s")
    print(f"Best WR: {best_overall_wr:.1%}")

    # Save new weights
    new_weights_path = OUTPUT_DIR / "evo_v06_weights.json"
    with open(new_weights_path, "w") as f:
        json.dump(best_overall, f, indent=2)
    print(f"Weights saved: {new_weights_path}")

    # Compare old vs new
    if old_weights:
        old_wr_vs_new = evaluate_weights(old_weights, "greedy", 50)
        new_wr_vs_old = evaluate_weights(best_overall, "greedy", 50)
        # Head-to-head: old evo vs new evo
        old_agent = EvoAgent(old_weights)
        new_agent = EvoAgent(best_overall)
        h2h_wins_old = 0
        h2h_wins_new = 0
        for s in range(50):
            gs = init_game(seed=s, size=SIZE)
            rng0 = random.Random(s)
            rng1 = random.Random(s+1)
            while gs.winner is None and gs.turn < 100:
                step_game(gs, old_agent.decide(gs, 0, rng0), new_agent.decide(gs, 1, rng1))
            if gs.winner == 0: h2h_wins_old += 1
            elif gs.winner == 1: h2h_wins_new += 1
            # Backward
            gs = init_game(seed=s+1000, size=SIZE)
            rng0 = random.Random(s+1000)
            rng1 = random.Random(s+1001)
            while gs.winner is None and gs.turn < 100:
                step_game(gs, new_agent.decide(gs, 0, rng0), old_agent.decide(gs, 1, rng1))
            if gs.winner == 0: h2h_wins_new += 1
            elif gs.winner == 1: h2h_wins_old += 1

        print(f"\nComparison (50 paired seeds each):")
        print(f"  Old Evo vs Greedy: {old_wr_vs_new:.1%}")
        print(f"  New Evo vs Greedy: {new_wr_vs_old:.1%}")
        print(f"  Old Evo vs New Evo (h2h): old={h2h_wins_old/100:.1%} new={h2h_wins_new/100:.1%}")

    # Save history
    with open(OUTPUT_DIR / "evo_train_history.json", "w") as f:
        json.dump({"generations": GENERATIONS, "population": POPULATION,
                   "best_wr": best_overall_wr, "total_time_s": total_time,
                   "history": history}, f, indent=2)
    print(f"History saved: {OUTPUT_DIR / 'evo_train_history.json'}")


if __name__ == "__main__":
    main()
