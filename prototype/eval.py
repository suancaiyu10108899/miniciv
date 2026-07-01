# prototype/eval.py — 批量 AI vs AI 评估
# 用法: python -m prototype.eval --games 10 --seed 42

import argparse, json, os, random, sys
from prototype.game import init_game, step_game
from prototype.ai_rulesrandom import ai_decide


def run_one_game(seed: int, size: int = 30, generator_id: str = "balanced",
                 verbose: bool = False) -> dict:
    """跑一局 RulesRandom vs RulesRandom"""
    gs = init_game(seed=seed, size=size, generator_id=generator_id)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)

    while gs.winner is None and gs.turn < 200:  # safety limit
        actions0 = ai_decide(gs, 0, rng0)
        actions1 = ai_decide(gs, 1, rng1)
        result = step_game(gs, actions0, actions1)
        if verbose and gs.turn % 20 == 0:
            print(f"  T{gs.turn} | P0: {gs.economies[0].food}f {gs.economies[0].wood}w {gs.economies[0].gold}g"
                  f" | P1: {gs.economies[1].food}f {gs.economies[1].wood}w {gs.economies[1].gold}g"
                  f" | C0: {gs.techs[0].construction_count()} C1: {gs.techs[1].construction_count()}")

    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
        "p0_score": gs.economies[0].food + gs.economies[0].wood + gs.economies[0].gold,
        "p1_score": gs.economies[1].food + gs.economies[1].wood + gs.economies[1].gold,
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
        "p0_units": len([u for u in gs.units if u.player_id == 0 and u.alive]),
        "p1_units": len([u for u in gs.units if u.player_id == 1 and u.alive]),
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=30)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--output", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    results = []
    p0_wins = 0
    for i in range(args.games):
        seed = args.seed + i * 1000
        if args.verbose:
            print(f"Game {i+1}/{args.games} (seed={seed})")
        r = run_one_game(seed, args.size, args.gen, verbose=args.verbose)
        results.append(r)
        if r["winner"] == 0:
            p0_wins += 1

    total = args.games
    print(f"\n=== RulesRandom vs RulesRandom ({args.games} games, {args.size}x{args.size} {args.gen}) ===")
    print(f"P0 winrate: {p0_wins}/{total} ({p0_wins/total*100:.1f}%)")
    if total - p0_wins > 0:
        print(f"P1 winrate: {total-p0_wins}/{total} ({(total-p0_wins)/total*100:.1f}%)")
    avg_turns = sum(r["turns"] for r in results) / total
    print(f"Avg turns: {avg_turns:.1f}")
    conquest = sum(1 for r in results if r["victory_type"] == "conquest")
    construction = sum(1 for r in results if r["victory_type"] == "construction")
    tiebreak = sum(1 for r in results if r["victory_type"] and "tiebreak" in r["victory_type"])
    print(f"Victory: conquest={conquest} construction={construction} tiebreak={tiebreak}")
    print(f"Avg techs: P0={sum(r['p0_techs'] for r in results)/total:.1f} "
          f"P1={sum(r['p1_techs'] for r in results)/total:.1f}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
