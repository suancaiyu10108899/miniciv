"""
C5 成本精细化扫描: x1.2 ~ x1.7
"""
import json, os, sys, random, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

MULTIPLIERS = [1.2, 1.3, 1.5, 1.7]
OPPONENTS = ["greedy", "flatmc"]
GAMES = 100
SIZE = 15
MAX_TURNS = 100
BASE_SEED = 99
WORKERS = 8

CONSTANTS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "prototype" / "constants.py"
ORIGINAL = CONSTANTS_PATH.read_text(encoding='utf-8')

def patch_c5(mult):
    content = CONSTANTS_PATH.read_text(encoding='utf-8')
    nc = (round(3*mult), round(3*mult), round(3*mult))
    content = content.replace('"C5":  {"cost": (3, 3, 3),', f'"C5":  {{"cost": {nc},')
    CONSTANTS_PATH.write_text(content, encoding='utf-8')
    return nc

def _play(args):
    seed, opp_name = args
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai
    evo = load_ai("evo"); opp = load_ai(opp_name)
    results = []
    for evo_p0 in [True, False]:
        gs_seed = seed + (0 if evo_p0 else 1000000)
        gs = init_game(seed=gs_seed, size=SIZE, generator_id="balanced")
        r0, r1 = random.Random(gs_seed), random.Random(gs_seed+1)
        if evo_p0:
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, evo(gs,0,r0), opp(gs,1,r1))
        else:
            while gs.winner is None and gs.turn < MAX_TURNS:
                step_game(gs, opp(gs,0,r0), evo(gs,1,r1))
        evo_won = (evo_p0 and gs.winner==0) or (not evo_p0 and gs.winner==1)
        results.append({"evo_won": evo_won, "victory_type": gs.victory_type, "turns": gs.turn})
    return {"opp": opp_name, "evo_wins": sum(1 for r in results if r["evo_won"]),
            "const_wins": sum(1 for r in results if r["evo_won"] and r["victory_type"]=="construction"),
            "total": len(results), "avg_turns": sum(r["turns"] for r in results)/len(results)}

all_results = []
OUTDIR = Path(__file__).resolve().parent

for mult in MULTIPLIERS:
    new_cost = patch_c5(mult)
    print(f"\nC5 x{mult} cost={new_cost}")
    for opp_name in OPPONENTS:
        tasks = [(BASE_SEED + i*1000 + int(mult*100000), opp_name) for i in range(GAMES)]
        evo_wins = 0; const_wins = 0; total = 0
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_play, t): t for t in tasks}
            for i, fut in enumerate(as_completed(futures)):
                r = fut.result()
                evo_wins += r["evo_wins"]; const_wins += r["const_wins"]; total += r["total"]
                if (i+1) % 25 == 0:
                    print(f"  {opp_name}: {i+1}/{GAMES} wr={evo_wins/total*100:.1f}% const={const_wins/total*100:.1f}%")
        wr = evo_wins/total*100; cwr = const_wins/total*100
        print(f"  DONE {opp_name}: wr={wr:.1f}% const={cwr:.1f}% ({time.time()-t0:.0f}s)")
        all_results.append({"c5_mult": mult, "c5_cost": list(new_cost), "opponent": opp_name,
                           "evo_winrate": round(wr,1), "construction_winrate": round(cwr,1)})
    # Save intermediate
    with open(OUTDIR / "c5_scan_fine.json", "w") as f:
        json.dump(all_results, f, indent=2)

# Restore
CONSTANTS_PATH.write_text(ORIGINAL, encoding='utf-8')

print(f"\n=== FINE SCAN RESULTS ===")
for r in all_results:
    print(f"x{r['c5_mult']} {r['opponent']:<10} EvoWR={r['evo_winrate']:>5.1f}% ConstWR={r['construction_winrate']:>5.1f}%")
print(f"\nSaved to {OUTDIR / 'c5_scan_fine.json'}")
