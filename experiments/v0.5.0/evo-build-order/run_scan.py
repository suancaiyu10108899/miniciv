"""
C5 成本扫描 — 直接改 constants.py + 并行 eval
每个 multiplier 跑 Evo vs [Greedy, FlatMC] 各 100 paired
"""
import json, os, sys, random, time, shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

MULTIPLIERS = [1, 2, 3, 5]
OPPONENTS = ["greedy", "flatmc"]
GAMES = 100
SIZE = 15
MAX_TURNS = 100
BASE_SEED = 42
WORKERS = 8
CONSTANTS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prototype" / "constants.py"
BACKUP_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prototype" / "constants.py.bak"

OUTDIR = Path(__file__).resolve().parent

# ─── Patch C5 cost ───────────────────────────────────

def patch_c5_cost(mult):
    """Directly edit constants.py to change C5 cost."""
    content = CONSTANTS_PATH.read_text(encoding='utf-8')
    base = (3, 3, 3)
    new_cost = tuple(x * mult for x in base)
    # Find and replace the C5 line
    import re
    old_line = '"C5":  {"cost": (3, 3, 3),'
    new_line = f'"C5":  {{"cost": {new_cost},'
    content = content.replace(old_line, new_line)
    CONSTANTS_PATH.write_text(content, encoding='utf-8')
    return new_cost

def restore_constants():
    """Restore from backup."""
    if BACKUP_PATH.exists():
        shutil.copy(BACKUP_PATH, CONSTANTS_PATH)

# ─── Worker ──────────────────────────────────────────

def _play_game(args):
    """Run one paired game (2 actual games). Returns results dict."""
    seed, evo_p0_first, opp_name, c5_mult = args

    # Must import INSIDE worker (fresh process after patch)
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai

    evo = load_ai("evo")
    opp = load_ai(opp_name)

    results = []
    for role in [True, False]:  # Evo as P0, then P1
        gs_seed = seed + (0 if role else 1000000)
        gs = init_game(seed=gs_seed, size=SIZE, generator_id="balanced")
        rng0 = random.Random(gs_seed)
        rng1 = random.Random(gs_seed + 1)

        if role:
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, evo(gs, 0, rng0), opp(gs, 1, rng1))
        else:
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, opp(gs, 0, rng0), evo(gs, 1, rng1))

        evo_won = (role and gs.winner == 0) or (not role and gs.winner == 1)
        results.append({
            "evo_p0": role, "evo_won": evo_won,
            "victory_type": gs.victory_type, "turns": gs.turn,
        })

    return {
        "seed": seed, "opp": opp_name, "c5_mult": c5_mult,
        "games": results,
        "evo_wins": sum(1 for r in results if r["evo_won"]),
        "total": len(results),
    }

# ─── Run one config ──────────────────────────────────

def run_config(mult, new_cost):
    """Run all opponents for one C5 multiplier."""
    print(f"\nC5 x{mult} cost={new_cost}")
    results = []

    for opp_name in OPPONENTS:
        tasks = [(BASE_SEED + i * 1000 + mult * 100000, True, opp_name, mult)
                 for i in range(GAMES)]
        evo_total_wins = 0
        const_wins = 0
        total_games = 0

        t0 = time.time()
        with ProcessPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_play_game, t): t for t in tasks}
            for i, fut in enumerate(as_completed(futures)):
                r = fut.result()
                evo_total_wins += r["evo_wins"]
                total_games += r["total"]
                for g in r["games"]:
                    if g["evo_won"] and g["victory_type"] == "construction":
                        const_wins += 1
                if (i+1) % 20 == 0:
                    wr = evo_total_wins / total_games * 100
                    cwr = const_wins / total_games * 100
                    print(f"  {opp_name}: {i+1}/{GAMES} wr={wr:.1f}% const_wr={cwr:.1f}%")

        elapsed = time.time() - t0
        wr = evo_total_wins / total_games * 100
        cwr = const_wins / total_games * 100
        print(f"  DONE {opp_name}: wr={wr:.1f}% const_wr={cwr:.1f}% ({elapsed:.0f}s)")
        results.append({
            "c5_multiplier": mult, "c5_cost": list(new_cost),
            "opponent": opp_name, "evo_winrate": round(wr, 2),
            "construction_winrate": round(cwr, 2),
            "total_games": total_games,
        })

    return results

# ─── Main ────────────────────────────────────────────

def main():
    print("C5 Cost Sensitivity Scan")
    print(f"  Multipliers: {MULTIPLIERS}")
    print(f"  Opponents: {OPPONENTS}")
    print(f"  Games per config: {GAMES} paired ({GAMES*2} sims)")
    print(f"  Workers per config: {WORKERS}")
    print(f"  Total sims: {len(MULTIPLIERS) * len(OPPONENTS) * GAMES * 2}")

    all_results = []

    try:
        for mult in MULTIPLIERS:
            new_cost = patch_c5_cost(mult)
            config_results = run_config(mult, new_cost)
            all_results.extend(config_results)

            # Intermediate save
            with open(OUTDIR / "c5_scan_results.json", "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"  [saved partial]")
    finally:
        restore_constants()
        print("\nConstants restored from backup.")

    # Final summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'C5x':<6} {'Opp':<10} {'EvoWR':<10} {'ConstWR':<10}")
    print("-" * 36)
    for r in all_results:
        print(f"x{r['c5_multiplier']:<5} {r['opponent']:<10} {r['evo_winrate']:>6.1f}%   {r['construction_winrate']:>6.1f}%")
    print(f"\nSaved to {OUTDIR / 'c5_scan_results.json'}")

if __name__ == "__main__":
    main()
