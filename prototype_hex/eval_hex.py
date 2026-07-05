#!/usr/bin/env python
# prototype_hex/eval_hex.py — Batch AI vs AI evaluation for hex engine
# Usage: python -m prototype_hex.eval_hex --ai0 greedy --ai1 evo --games 50

import argparse, json, os, random, sys, importlib, time
from prototype_hex.game_hex import init_game_hex, step_game_hex
import prototype.cleanup  # atexit orphan process cleanup

AI_MODULES = {
    "greedy":     "prototype_hex.ai_greedy_hex",
    "evo":        "prototype_hex.ai_evo_hex",
    "random":     "prototype_hex.ai_random_hex",
}

def load_ai(name: str):
    if name not in AI_MODULES:
        raise ValueError(f"Unknown hex AI: {name}. Options: {list(AI_MODULES.keys())}")
    mod = importlib.import_module(AI_MODULES[name])
    return mod.ai_decide

def run_one_game(seed: int, ai0_func, ai1_func, generator_id: str = "balanced",
                 verbose: bool = False, max_turns: int = 80) -> dict:
    gs = init_game_hex(seed=seed, generator_id=generator_id)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    start = time.time()

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0_func(gs, 0, rng0)
        a1 = ai1_func(gs, 1, rng1)
        step_game_hex(gs, a0, a1)
        if verbose and gs.turn % 20 == 0:
            e = gs.economies
            u0 = sum(1 for u in gs.units if u.player_id == 0 and u.alive)
            u1 = sum(1 for u in gs.units if u.player_id == 1 and u.alive)
            print(f"  T{gs.turn} | P0:{e[0].food}f{e[0].wood}w{e[0].gold}g u{u0} | "
                  f"P1:{e[1].food}f{e[1].wood}w{e[1].gold}g u{u1}")

    elapsed = time.time() - start
    return {
        "seed": seed, "winner": gs.winner, "victory_type": gs.victory_type,
        "turns": gs.turn, "elapsed": round(elapsed, 1),
        "p0_resources": {"food": gs.economies[0].food, "wood": gs.economies[0].wood,
                         "gold": gs.economies[0].gold},
        "p1_resources": {"food": gs.economies[1].food, "wood": gs.economies[1].wood,
                         "gold": gs.economies[1].gold},
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        # Per-unit-type stats
        "p0_ut_alive": _count_by_type(gs, 0, True),
        "p1_ut_alive": _count_by_type(gs, 1, True),
        "p0_ut_dead": _count_by_type(gs, 0, False),
        "p1_ut_dead": _count_by_type(gs, 1, False),
    }

def _count_by_type(gs, pid, alive):
    types = ["infantry", "cavalry", "archer", "scout", "worker"]
    units = gs.units if alive else gs.dead_units
    return {t: sum(1 for u in units if u.player_id == pid and u.unit_type == t) for t in types}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai0", default="greedy")
    parser.add_argument("--ai1", default="random")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--output", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-turns", type=int, default=80)
    args = parser.parse_args()

    print(f"=== HEX: {args.ai0} vs {args.ai1} ({args.games} games, 15x15 {args.gen}) ===")
    ai0 = load_ai(args.ai0)
    ai1 = load_ai(args.ai1)

    results = []
    p0_wins = p1_wins = 0
    conquests = constructions = tiebreaks = 0

    for i in range(args.games):
        seed = args.seed + i * 1000
        if args.verbose and i % 10 == 0:
            print(f"Game {i+1}/{args.games} (seed={seed})")
        r = run_one_game(seed, ai0, ai1, args.gen, verbose=args.verbose, max_turns=args.max_turns)
        results.append(r)
        if r["winner"] == 0: p0_wins += 1
        elif r["winner"] == 1: p1_wins += 1
        if r["victory_type"] == "conquest": conquests += 1
        elif r["victory_type"] == "construction": constructions += 1
        else: tiebreaks += 1

    n = args.games
    print(f"\n=== HEX Results ({n} games) ===")
    print(f"{args.ai0} winrate: {p0_wins}/{n} ({p0_wins/n*100:.1f}%)")
    print(f"{args.ai1} winrate: {p1_wins}/{n} ({p1_wins/n*100:.1f}%)")
    avg_t = sum(r["turns"] for r in results) / n
    print(f"Avg turns: {avg_t:.1f}")
    print(f"Victory: conquest={conquests} construction={constructions} tiebreak={tiebreaks}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        summary = {
            "config": {"ai0": args.ai0, "ai1": args.ai1, "games": n, "grid": "hex", "gen": args.gen},
            "p0_winrate": p0_wins / n,
            "avg_turns": avg_t,
            "victory_types": {"conquest": conquests, "construction": constructions, "tiebreak": tiebreaks},
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Saved: {args.output}")

if __name__ == "__main__":
    main()
