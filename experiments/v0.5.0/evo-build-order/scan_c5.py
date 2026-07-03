"""
建设胜利平衡扫描：C5 成本对 Evo 胜率的影响
C5 cost 倍数: x1, x2, x3, x5
每个配置: Evo vs Greedy/DQN/FlatMC, 200局 paired
"""
import json, os, sys, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from prototype.game import init_game, step_game
from prototype.eval import load_ai, run_one_game

# ─── Config ──────────────────────────────────────────
C5_MULTIPLIERS = [(1, 200), (2, 200), (3, 200), (5, 200)]  # (mult, games)
OPPONENTS = ["greedy", "flatmc"]
SIZE = 15
MAX_TURNS = 100
BASE_SEED = 42

OUTDIR = Path(__file__).resolve().parent
OUTDIR.mkdir(parents=True, exist_ok=True)

# ─── Override C5 cost ────────────────────────────────

def set_c5_multiplier(mult):
    """Monkey-patch C5 cost in constants module."""
    import prototype.constants as c
    import importlib
    base = (3, 3, 3)
    c.TECH_TREE["C5"]["cost"] = tuple(x * mult for x in base)
    # Reload game module so step_game picks up changes
    import prototype.game as g
    importlib.reload(g)
    # Re-patch game's import of TECH_TREE
    import prototype.tech as t
    importlib.reload(t)
    import prototype.ai_evo as evo
    importlib.reload(evo)
    import prototype.eval as e
    importlib.reload(e)
    # Reload AI modules that cache TECH_TREE
    for mod_name in ["ai_greedy", "ai_flatmc", "ai_evo"]:
        mod = __import__(f"prototype.{mod_name}", fromlist=[""])
        importlib.reload(mod)

# ─── Main ────────────────────────────────────────────

all_results = []

for mult, games in C5_MULTIPLIERS:
    print(f"\n{'='*60}")
    print(f"C5 multiplier: x{mult} (cost={tuple(x*mult for x in (3,3,3))})")
    print(f"{'='*60}")

    set_c5_multiplier(mult)

    # Re-load AIs after patch
    evo_decide = load_ai("evo")

    for opp_name in OPPONENTS:
        opp_decide = load_ai(opp_name)
        print(f"  Evo vs {opp_name}: {games} paired games...", end=" ", flush=True)

        results = []
        evo_wins = 0
        const_wins = 0
        t0 = time.time()

        for i in range(games):
            seed = BASE_SEED + i * 1000 + mult * 100000
            # Evo as P0
            gs = init_game(seed=seed, size=SIZE, generator_id="balanced")
            rng0 = random.Random(seed)
            rng1 = random.Random(seed + 1)
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, evo_decide(gs, 0, rng0), opp_decide(gs, 1, rng1))
            g1_evo_win = gs.winner == 0
            g1_const = gs.victory_type == "construction"
            if g1_evo_win: evo_wins += 1
            if g1_evo_win and g1_const: const_wins += 1
            results.append({
                "seed": seed, "evo_p0": True,
                "winner": gs.winner, "victory_type": gs.victory_type,
                "turns": gs.turn,
                "evo_construction": gs.techs[0].construction_count() if gs.winner == 0 else gs.techs[1].construction_count(),
            })

            # Evo as P1 (swapped)
            seed2 = seed + 1_000_000
            gs = init_game(seed=seed2, size=SIZE, generator_id="balanced")
            rng0 = random.Random(seed2)
            rng1 = random.Random(seed2 + 1)
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, opp_decide(gs, 0, rng0), evo_decide(gs, 1, rng1))
            g2_evo_win = gs.winner == 1
            if g2_evo_win: evo_wins += 1
            results.append({
                "seed": seed2, "evo_p0": False,
                "winner": gs.winner, "victory_type": gs.victory_type,
                "turns": gs.turn,
            })

        total = games * 2
        wr = evo_wins / total * 100
        cwr = const_wins / total * 100
        elapsed = time.time() - t0
        print(f"wr={wr:.1f}% const_wr={cwr:.1f}% ({elapsed:.0f}s)")

        all_results.append({
            "c5_multiplier": mult,
            "c5_cost": tuple(x*mult for x in (3,3,3)),
            "opponent": opp_name,
            "games": games,
            "total_games": total,
            "evo_winrate": round(wr, 2),
            "construction_winrate": round(cwr, 2),
        })

# ─── Save ────────────────────────────────────────────

with open(OUTDIR / "c5_scan_results.json", "w") as f:
    json.dump(all_results, f, indent=2)

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"{'C5x':<6} {'Opp':<10} {'EvoWR':<10} {'ConstWR':<10}")
print("-" * 36)
for r in all_results:
    print(f"x{r['c5_multiplier']:<5} {r['opponent']:<10} {r['evo_winrate']:>6.1f}%   {r['construction_winrate']:>6.1f}%")
print(f"\nSaved to {OUTDIR / 'c5_scan_results.json'}")
