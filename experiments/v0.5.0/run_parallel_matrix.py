"""
experiments/v0.5.0/run_parallel_matrix.py — 7x7 matrix with reliable parallelism

Uses multiprocessing.Pool with maxtasksperchild=1 to avoid Windows spawn memory issues.
"""

import json, math, os, random, sys, time

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "full-matrix-7x7")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AI_NAMES = ["random", "greedy", "aggressive", "flatmc", "evo", "bc", "dqn"]
GAMES = 200
SIZE = 15
MAX_TURNS = 100
SEED = 42
WORKERS = 4


def _init_worker():
    """Worker initializer: set up the path for imports."""
    import sys
    root = _PROJECT_ROOT  # captured via closure
    if root not in sys.path:
        sys.path.insert(0, root)


def _worker_run(args):
    """Run a single paired evaluation (2 games per seed) in worker process."""
    import random as _random
    import sys
    _my_root = _PROJECT_ROOT
    if _my_root not in sys.path:
        sys.path.insert(0, _my_root)
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai

    seed, ai_a_name, ai_b_name, size, gen, max_turns = args

    ai_a = load_ai(ai_a_name)
    ai_b = load_ai(ai_b_name)

    # Game 1: AI_A=P0, AI_B=P1
    gs1 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs1.winner is None and gs1.turn < max_turns:
        step_game(gs1, ai_a(gs1, 0, rng0), ai_b(gs1, 1, rng1))

    # Game 2: AI_A=P1, AI_B=P0
    gs2 = init_game(seed=seed, size=size, generator_id=gen)
    rng0 = _random.Random(seed + 2_000_000)
    rng1 = _random.Random(seed + 2_000_001)
    while gs2.winner is None and gs2.turn < max_turns:
        step_game(gs2, ai_b(gs2, 0, rng0), ai_a(gs2, 1, rng1))

    def _extract(gs, s, a0n, a1n):
        return {
            "seed": s, "ai0": a0n, "ai1": a1n,
            "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
            "turns": gs.turn,
            "p0_hp": gs.cities[0].hp, "p1_hp": gs.cities[1].hp,
            "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
            "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
            "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
            "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        }

    g1 = _extract(gs1, seed, ai_a_name, ai_b_name)
    g2 = _extract(gs2, seed + 1_000_000, ai_b_name, ai_a_name)

    g1ai_a_won = (g1["winner"] == 0)
    g2ai_a_won = (g2["winner"] == 1)

    return {
        "seed": seed,
        "ai_a": ai_a_name, "ai_b": ai_b_name,
        "game1": g1, "game2": g2,
        "ai_a_wins": (1 if g1ai_a_won else 0) + (1 if g2ai_a_won else 0),
        "ai_b_wins": (1 if not g1ai_a_won else 0) + (1 if not g2ai_a_won else 0),
        "g1_winner": g1["winner"], "g2_winner": g2["winner"],
        "g1_vtype": g1["victory_type"], "g2_vtype": g2["victory_type"],
    }


def run_pair_parallel(ai_a, ai_b):
    """Run all seeds for a single AI pair using multiple short-lived Pools."""
    from multiprocessing import Pool, get_context

    tasks = []
    for g in range(GAMES):
        seed = SEED + g * 1000 + hash((ai_a, ai_b)) % 100000
        tasks.append((seed, ai_a, ai_b, SIZE, "balanced", MAX_TURNS))

    results = []
    BATCH_SIZE = 40

    for batch_start in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[batch_start:batch_start + BATCH_SIZE]
        with Pool(processes=WORKERS, initializer=_init_worker) as pool:
            for r in pool.imap_unordered(_worker_run, batch):
                results.append(r)
        completed = len(results)
        if completed % 40 == 0 or completed == len(tasks):
            print(f"    {completed}/{len(tasks)} seeds", flush=True)

    # Aggregate
    n = len(results)
    total_games = n * 2
    ai_a_wins = sum(r["ai_a_wins"] for r in results)
    ai_b_wins = sum(r["ai_b_wins"] for r in results)
    ai_a_wr = ai_a_wins / total_games if total_games else 0.5

    conquests = sum(1 for r in results for g in [r["game1"], r["game2"]] if str(g["victory_type"]) == "conquest")
    constructions = sum(1 for r in results for g in [r["game1"], r["game2"]] if str(g["victory_type"]) == "construction")
    tiebreaks = total_games - conquests - constructions

    all_turns = []
    for r in results:
        all_turns.append(r["game1"]["turns"])
        all_turns.append(r["game2"]["turns"])
    avg_t = sum(all_turns) / len(all_turns) if all_turns else 0

    seed_rates = [r["ai_a_wins"] / 2 for r in results]
    ai_a_std = _std(seed_rates) if len(seed_rates) > 1 else 0
    p0_wins = sum(1 for r in results for g in [r["game1"], r["game2"]] if g["winner"] == 0)
    p0_wr = p0_wins / total_games if total_games else 0.5
    p0_ci = _ci95(p0_wr, total_games)
    ai_a_ci = _ci95(ai_a_wr, total_games)

    cq_rate = conquests / total_games
    cs_rate = constructions / total_games
    tie_rate = tiebreaks / total_games

    return {
        "mode": "paired",
        "ai_a": ai_a, "ai_b": ai_b,
        "n_seeds": n, "n_games": total_games,
        "ai_a_winrate": round(ai_a_wr, 4),
        "ai_b_winrate": round(1 - ai_a_wr, 4),
        "p0_winrate": round(p0_wr, 4),
        "p0_ci95": round(p0_ci, 4),
        "ai_a_ci95": round(ai_a_ci, 4),
        "ai_a_std": round(ai_a_std, 4),
        "conquest_rate": round(cq_rate, 4),
        "construction_rate": round(cs_rate, 4),
        "tiebreak_rate": round(tie_rate, 4),
        "avg_turns": round(avg_t, 2),
    }


def _std(values):
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(v)


def _ci95(p, n):
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def _compute_elo(pairs, ai_names, start_elo=1500, K=32, iterations=200):
    elo = {name: start_elo for name in ai_names}
    for it in range(iterations):
        for p in pairs:
            ai_a, ai_b = p["ai_a"], p["ai_b"]
            n_games = p["n_games"]
            a_wr = p["ai_a_winrate"]
            ea = 1.0 / (1.0 + 10.0 ** ((elo[ai_b] - elo[ai_a]) / 400.0))
            eb = 1.0 / (1.0 + 10.0 ** ((elo[ai_a] - elo[ai_b]) / 400.0))
            elo[ai_a] += K * (a_wr - ea)
            elo[ai_b] += K * ((1 - a_wr) - eb)

    import random as _rnd
    n_boot = 2000
    boot = {name: [] for name in ai_names}
    for _ in range(n_boot):
        b_elo = {name: start_elo for name in ai_names}
        for _ in range(len(pairs)):
            p = _rnd.choice(pairs)
            ai_a, ai_b = p["ai_a"], p["ai_b"]
            n_games = p["n_games"]
            a_wr = p["ai_a_winrate"]
            for _ in range(iterations // 2):
                ea = 1.0 / (1.0 + 10.0 ** ((b_elo[ai_b] - b_elo[ai_a]) / 400.0))
                eb = 1.0 / (1.0 + 10.0 ** ((b_elo[ai_a] - b_elo[ai_b]) / 400.0))
                noise_a = _rnd.gauss(0, math.sqrt(ea * (1 - ea) / max(1, n_games)))
                b_elo[ai_a] += K * (a_wr - ea + noise_a * 0.5)
                b_elo[ai_b] += K * ((1 - a_wr) - eb - noise_a * 0.5)
        for name in ai_names:
            boot[name].append(b_elo[name])

    ci = {}
    for name in ai_names:
        bvals = sorted(boot[name])
        ci[name] = {
            "elo": round(elo[name], 1),
            "ci_low": round(bvals[len(bvals) // 40], 1),
            "ci_high": round(bvals[len(bvals) * 39 // 40], 1),
        }
    return ci


def main():
    t_start = time.perf_counter()
    print("=" * 70)
    print("  MINICIV v0.5.0 — PARALLEL 7x7 PAIRED MATRIX")
    print(f"  AIs: {', '.join(AI_NAMES)}")
    print(f"  Games per pair: {GAMES} (x2 swapped = {GAMES*2} games/pair)")
    print(f"  Workers: {WORKERS} (batched 40 seeds/pool)")
    print("=" * 70)
    print()

    all_pairs = [(a, b) for a in AI_NAMES for b in AI_NAMES]
    total = len(all_pairs)
    pairs_data = []

    for idx, (ai_a, ai_b) in enumerate(all_pairs, 1):
        out_path = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 400:
            with open(out_path) as f:
                data = json.load(f)
            pairs_data.append(data)
            wr = data["ai_a_winrate"] * 100
            print(f"  [{idx}/{total}] {ai_a} vs {ai_b} — cached (A_win={wr:.1f}%)")
            continue

        t0 = time.perf_counter()
        print(f"  [{idx}/{total}] {ai_a} vs {ai_b} — running {GAMES*2} games...")
        sys.stdout.flush()

        data = run_pair_parallel(ai_a, ai_b)
        elapsed = time.perf_counter() - t0

        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

        pairs_data.append(data)
        wr = data["ai_a_winrate"] * 100
        print(f"    done ({elapsed:.0f}s, A_win={wr:.1f}%)")

    elapsed = time.perf_counter() - t_start
    print(f"\n  All {total} pairs completed in {elapsed:.0f}s")

    # Summary
    total_seeds = sum(p.get("n_seeds", 0) for p in pairs_data)
    total_games = sum(p.get("n_games", 0) for p in pairs_data)
    summary = {
        "config": {"games_per_pair": GAMES, "size": SIZE, "gen": "balanced", "paired": True, "mode": "normal"},
        "pairs": pairs_data,
        "total_seeds": total_seeds,
        "total_games": total_games,
        "elapsed_s": round(elapsed, 1),
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Elo
    print("\n  COMPUTING ELO...")
    ai_names_sorted = sorted(set(p["ai_a"] for p in pairs_data))
    elo = _compute_elo(pairs_data, ai_names_sorted)
    with open(os.path.join(OUTPUT_DIR, "elo_rankings.json"), "w") as f:
        json.dump(elo, f, indent=2)

    ranked = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    print(f"\n  {'Rank':>4s} {'AI':>12s} {'Elo':>7s} {'95% CI':>12s}")
    print(f"  {'':->4s} {'':->12s} {'':->7s} {'':->12s}")
    for rank, (name, e) in enumerate(ranked, 1):
        print(f"  {rank:>3d}. {name:>12s} {e['elo']:>7.1f} {e['ci_low']:>5.1f}-{e['ci_high']:5.1f}")

    # Report
    print("\n  GENERATING REPORT...")
    report_lines = _generate_report(summary, elo, ai_names_sorted)
    with open(os.path.join(OUTPUT_DIR, "report.md"), "w") as f:
        f.write(report_lines)
    print(f"  Report saved to {OUTPUT_DIR}/report.md")
    print("\n  ALL DONE")


def _generate_report(summary, elo, ai_names):
    pairs = summary["pairs"]
    config = summary["config"]
    L = []
    L.append("# MiniCiv v0.5.0 — AI Comparison Matrix (7x7)")
    L.append("")
    L.append(f"- **Date**: July 2026")
    L.append(f"- **AIs**: {', '.join(ai_names)}")
    L.append(f"- **Games per pair**: {config['games_per_pair']} (x2 swapped = {config['games_per_pair']*2} games/pair)")
    L.append(f"- **Total games**: {len(ai_names)}x{len(ai_names)} x {config['games_per_pair']*2} = {len(ai_names)*len(ai_names)*config['games_per_pair']*2}")
    L.append(f"- **Map**: {config['size']}x{config['size']} {config['gen']}")
    L.append(f"- **Protocol**: Paired (P0/P1 swap per seed)")
    L.append(f"- **Total games run**: {summary['total_games']}")
    L.append(f"- **Elapsed**: {summary['elapsed_s']}s")
    L.append("")

    L.append("## Winrate Matrix (Row AI vs Column AI)")
    L.append("")
    L.append("Values are Row AI's winrate as percentage (with 95% CI).")
    L.append("")
    wr = {}
    ci_lookup = {}
    for p in pairs:
        wr[(p["ai_a"], p["ai_b"])] = p["ai_a_winrate"]
        ci_lookup[(p["ai_a"], p["ai_b"])] = p["ai_a_ci95"]
    header = f"| {'AI':>8s} |"
    for name in ai_names:
        header += f" {name:>12s} |"
    L.append(header)
    sep = "|:" + "-" * 7 + ":|"
    for name in ai_names:
        sep += ":" + "-" * 11 + ":|"
    L.append(sep)
    for row_name in ai_names:
        row = f"| **{row_name:>6s}** |"
        for col_name in ai_names:
            key = (row_name, col_name)
            if key in wr:
                pct = wr[key] * 100
                the_ci = ci_lookup[key] * 100
                row += f" {pct:>5.1f}%+-{the_ci:>3.1f}% |"
            else:
                row += f" {'N/A':>12s} |"
        L.append(row)
    L.append("")

    L.append("## Elo Rankings")
    L.append("")
    L.append(f"- Starting Elo: 1500, K = 32, Iterations: 200, 95% CI via bootstrap (n=2000)")
    L.append("")
    ranked = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    L.append(f"| {'Rank':>4s} | {'AI':>12s} | {'Elo':>7s} | {'95% CI':>12s} |")
    L.append(f"|{'':-<5s}|{'':-<13s}|{'':-<8s}|{'':-<13s}|")
    for rank, (name, e) in enumerate(ranked, 1):
        L.append(f"| {rank:>3d}. | {name:>12s} | {e['elo']:>6.1f} | {e['ci_low']:>5.1f}-{e['ci_high']:>5.1f} |")
    L.append("")

    L.append("## Comparison with v0.4.0 (4x4 Matrix)")
    L.append("")
    v4_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "eval_final", "summary.json")
    if os.path.exists(v4_path):
        with open(v4_path) as f:
            v4 = json.load(f)
        v4_map = {(p["ai0"], p["ai1"]): p["p0_winrate"] for p in v4["pairs"]}
        L.append("| Matchup | v0.4.0 P0% | v0.5.0 Paired% | Delta |")
        L.append("|---|---:|---:|---:|")
        for a0, a1 in [("random","random"),("random","greedy"),("random","aggressive"),("random","flatmc"),
                        ("greedy","greedy"),("greedy","aggressive"),("greedy","flatmc"),
                        ("aggressive","aggressive"),("aggressive","flatmc"),("flatmc","flatmc")]:
            v4v = v4_map.get((a0, a1))
            v5v = None
            for p in pairs:
                if p["ai_a"] == a0 and p["ai_b"] == a1:
                    v5v = p["p0_winrate"] if a0 == a1 else p["ai_a_winrate"]
                    break
            if v4v is not None and v5v is not None:
                d = (v5v - v4v) * 100
                L.append(f"| {a0} vs {a1} | {v4v*100:.1f}% | {v5v*100:.1f}% | {d:+.1f}% |")
        L.append("")

    L.append("## Analysis")
    L.append("")
    graded = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    top_elo = graded[0][1]["elo"]
    bottom_elo = graded[-1][1]["elo"]
    spread = top_elo - bottom_elo
    L.append(f"### Overall spread: {spread:.0f} Elo points ({bottom_elo:.0f} to {top_elo:.0f})")
    L.append("")
    tiers = {"S": [], "A": [], "B": [], "C": []}
    for name, e in graded:
        pct = (e["elo"] - bottom_elo) / max(1, spread)
        if pct >= 0.8: tiers["S"].append(name)
        elif pct >= 0.5: tiers["A"].append(name)
        elif pct >= 0.2: tiers["B"].append(name)
        else: tiers["C"].append(name)
    for t in ["S", "A", "B", "C"]:
        if tiers[t]:
            L.append(f"- **Tier {t}**: {', '.join(tiers[t])}")
    L.append("")
    L.append("### Paradigm Analysis")
    L.append("")
    L.append("The 7 AIs represent 4 paradigms:")
    L.append("1. **Rule-based**: random, greedy, aggressive, flatmc")
    L.append("2. **Weight-parameterized (evolvable)**: evo")
    L.append("3. **Behavior Cloning (supervised NN)**: bc")
    L.append("4. **Reinforcement Learning (DQN)**: dqn")
    L.append("")
    rule_top = next(((n, e) for n, e in graded if n in ["random","greedy","aggressive","flatmc"]), None)
    ml_top = next(((n, e) for n, e in graded if n in ["evo","bc","dqn"]), None)
    if rule_top: L.append(f"- Best rule-based: {rule_top[0]} ({rule_top[1]['elo']:.1f} Elo)")
    if ml_top: L.append(f"- Best ML-based: {ml_top[0]} ({ml_top[1]['elo']:.1f} Elo)")
    if rule_top and ml_top:
        gap = rule_top[1]["elo"] - ml_top[1]["elo"]
        L.append(f"- {'Rule-based' if gap > 0 else 'ML-based'} leads by {abs(gap):.0f} Elo")
    L.append("")
    L.append("### First-Player Advantage (Mirror Matches)")
    L.append("")
    L.append("| AI | P0 Winrate in Mirror | 95% CI | P0 Advantage |")
    L.append("|---|---:|---:|---:|")
    for name in ai_names:
        for p in pairs:
            if p["ai_a"] == name and p["ai_b"] == name:
                adv = (p["p0_winrate"] - 0.5) * 100
                L.append(f"| {name} | {p['p0_winrate']*100:.1f}% | +-{p['p0_ci95']*100:.1f}% | {adv:+.1f}% |")
                break
    L.append("")
    L.append("### Victory Type Distribution")
    L.append("")
    avg_conq = sum(p.get("conquest_rate", 0) for p in pairs) / len(pairs) * 100
    avg_cons = sum(p.get("construction_rate", 0) for p in pairs) / len(pairs) * 100
    L.append(f"- Conquest: {avg_conq:.1f}%")
    L.append(f"- Construction: {avg_cons:.1f}%")
    L.append(f"- Tiebreak: {100-avg_conq-avg_cons:.1f}%")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
