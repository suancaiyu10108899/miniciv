# prototype/eval.py — 批量 AI vs AI 评估（多AI支持）
# 用法: python -m prototype.eval --ai0 greedy --ai1 aggressive --games 50 --size 15

import argparse, json, os, random, sys, importlib, time
from prototype.game import init_game, step_game


AI_MODULES = {
    "random":     "prototype.ai_rulesrandom",
    "greedy":     "prototype.ai_greedy",
    "aggressive": "prototype.ai_aggressive",
    "flatmc":     "prototype.ai_flatmc",
}


def load_ai(name: str):
    if name not in AI_MODULES:
        raise ValueError(f"Unknown AI: {name}. Options: {list(AI_MODULES.keys())}")
    mod = importlib.import_module(AI_MODULES[name])
    return mod.ai_decide


def run_one_game(seed: int, ai0_func, ai1_func, size: int = 15,
                 generator_id: str = "balanced", verbose: bool = False,
                 max_turns: int = 100) -> dict:
    gs = init_game(seed=seed, size=size, generator_id=generator_id)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    start = time.time()

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0_func(gs, 0, rng0)
        a1 = ai1_func(gs, 1, rng1)
        step_game(gs, a0, a1)
        if verbose and gs.turn % 20 == 0:
            e = gs.economies
            u0 = sum(1 for u in gs.units if u.player_id == 0 and u.alive)
            u1 = sum(1 for u in gs.units if u.player_id == 1 and u.alive)
            d0 = sum(1 for u in gs.dead_units if u.player_id == 0)
            d1 = sum(1 for u in gs.dead_units if u.player_id == 1)
            print(f"  T{gs.turn} | P0:{e[0].food}f{e[0].wood}w{e[0].gold}g u{u0} d{d0} | "
                  f"P1:{e[1].food}f{e[1].wood}w{e[1].gold}g u{u1} d{d1}")

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
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai0", default="greedy")
    parser.add_argument("--ai1", default="aggressive")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--output", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-turns", type=int, default=100)
    args = parser.parse_args()

    print(f"=== {args.ai0} vs {args.ai1} ({args.games} games, {args.size}x{args.size} {args.gen}) ===")
    ai0 = load_ai(args.ai0)
    ai1 = load_ai(args.ai1)

    results = []
    p0_wins = p1_wins = 0
    conquests = constructions = tiebreaks = 0

    for i in range(args.games):
        seed = args.seed + i * 1000
        if args.verbose:
            print(f"\nGame {i+1}/{args.games} (seed={seed})")
        r = run_one_game(seed, ai0, ai1, args.size, args.gen,
                        verbose=args.verbose, max_turns=args.max_turns)
        results.append(r)
        if r["winner"] == 0:
            p0_wins += 1
        elif r["winner"] == 1:
            p1_wins += 1
        if r["victory_type"] == "conquest":
            conquests += 1
        elif r["victory_type"] == "construction":
            constructions += 1
        else:
            tiebreaks += 1

    n = args.games
    print(f"\n=== Results ({n} games) ===")
    print(f"{args.ai0} winrate: {p0_wins}/{n} ({p0_wins/n*100:.1f}%)")
    print(f"{args.ai1} winrate: {p1_wins}/{n} ({p1_wins/n*100:.1f}%)")
    avg_t = sum(r["turns"] for r in results) / n
    print(f"Avg turns: {avg_t:.1f}")
    print(f"Victory: conquest={conquests} construction={constructions} tiebreak={tiebreaks}")
    avg_dead = sum(r["p0_dead"] + r["p1_dead"] for r in results) / n
    print(f"Avg dead units/game: {avg_dead:.1f}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
