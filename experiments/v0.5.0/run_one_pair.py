"""
experiments/v0.5.0/run_one_pair.py — Run a single AI pair and save result.

Usage:
  cd D:/Dev/miniciv
  python experiments/v0.5.0/run_one_pair.py <ai_a> <ai_b> [--games N] [--workers N]
"""

import json, math, os, sys, time

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "full-matrix-7x7")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GAMES = 200
SIZE = 15
MAX_TURNS = 100
SEED = 42
WORKERS = 4
MAX_PER_CHILD = 30


def _worker_run(args):
    import random as _random
    import sys as _sys
    _r = _PROJECT_ROOT
    if _r not in _sys.path:
        _sys.path.insert(0, _r)
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai

    seed, ai_a_name, ai_b_name, size, gen, max_turns = args
    ai_a = load_ai(ai_a_name)
    ai_b = load_ai(ai_b_name)

    # Game 1
    gs1 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs1.winner is None and gs1.turn < max_turns:
        step_game(gs1, ai_a(gs1, 0, rng0), ai_b(gs1, 1, rng1))

    # Game 2
    gs2 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed + 2_000_000)
    rng1 = _random.Random(seed + 2_000_001)
    while gs2.winner is None and gs2.turn < max_turns:
        step_game(gs2, ai_b(gs2, 0, rng0), ai_a(gs2, 1, rng1))

    def _ext(gs, s, a0n, a1n):
        return {"seed": s, "ai0": a0n, "ai1": a1n, "winner": gs.winner,
                "victory_type": gs.victory_type or "tiebreak", "turns": gs.turn}

    g1 = _ext(gs1, seed, ai_a_name, ai_b_name)
    g2 = _ext(gs2, seed + 1_000_000, ai_b_name, ai_a_name)
    g1a = g1["winner"] == 0
    g2a = g2["winner"] == 1

    return {"seed": seed, "ai_a": ai_a_name, "ai_b": ai_b_name,
            "game1": g1, "game2": g2,
            "ai_a_wins": (1 if g1a else 0) + (1 if g2a else 0),
            "ai_b_wins": (1 if not g1a else 0) + (1 if not g2a else 0)}


def run_pair(ai_a, ai_b):
    from multiprocessing import Pool
    tasks = [(SEED + g * 1000 + hash((ai_a, ai_b)) % 100000, ai_a, ai_b,
              SIZE, "balanced", MAX_TURNS) for g in range(GAMES)]

    results = []
    BATCH = 30
    for bs in range(0, min(30, len(tasks)), BATCH):  # Only 1 batch for now
        batch = tasks[bs:bs + BATCH]
        print(f"  Creating Pool with {WORKERS} workers...", end=" ", flush=True)
        sys.stdout.flush()
        try:
            with Pool(WORKERS, maxtasksperchild=MAX_PER_CHILD) as pool:
                for r in pool.imap_unordered(_worker_run, batch):
                    results.append(r)
            print(f"OK, {len(results)} results", flush=True)
        except Exception as e:
            print(f"FAILED: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise
    print(flush=True)

    n = len(results)
    tg = n * 2
    a_wins = sum(r["ai_a_wins"] for r in results)
    a_wr = a_wins / tg if tg else 0.5
    cq = sum(1 for r in results for g in [r["game1"],r["game2"]] if str(g["victory_type"])=="conquest")
    cs = sum(1 for r in results for g in [r["game1"],r["game2"]] if str(g["victory_type"])=="construction")
    tb = tg - cq - cs
    at = sum(t for r in results for g in [r["game1"],r["game2"]] for t in [g["turns"]]) / max(1, tg)
    p0w = sum(1 for r in results for g in [r["game1"],r["game2"]] if g["winner"]==0)
    p0wr = p0w / tg

    def ci(p, n):
        return 1.96 * math.sqrt(p*(1-p)/n) if n > 1 else 0

    return {
        "mode": "paired", "ai_a": ai_a, "ai_b": ai_b,
        "n_seeds": n, "n_games": tg,
        "ai_a_winrate": round(a_wr, 4), "ai_b_winrate": round(1-a_wr, 4),
        "p0_winrate": round(p0wr, 4),
        "p0_ci95": round(ci(p0wr, tg), 4), "ai_a_ci95": round(ci(a_wr, tg), 4),
        "ai_a_std": round(math.sqrt(sum((r["ai_a_wins"]/2 - a_wr)**2 for r in results)/(max(1,n-1))) if n>1 else 0, 4),
        "conquest_rate": round(cq/tg, 4), "construction_rate": round(cs/tg, 4),
        "tiebreak_rate": round(tb/tg, 4), "avg_turns": round(at, 2),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <ai_a> <ai_b>")
        sys.exit(1)

    ai_a, ai_b = sys.argv[1], sys.argv[2]
    out_path = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 400:
        print(f"  {ai_a} vs {ai_b} already exists")
        sys.exit(0)

    t0 = time.perf_counter()
    print(f"  Running {ai_a} vs {ai_b} ({GAMES*2} games)...", flush=True)
    data = run_pair(ai_a, ai_b)
    et = time.perf_counter() - t0

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    wr = data["ai_a_winrate"] * 100
    print(f"  Done in {et:.0f}s, A_win={wr:.1f}%", flush=True)
