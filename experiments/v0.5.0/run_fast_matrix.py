"""
experiments/v0.5.0/run_fast_matrix.py — Fast 7x7 matrix with zero queue saturation

Uses ThreadPoolExecutor (no pickling) + batch-submits to a fixed-size ProcessPool.
Each batch is one AI-pair's games at a time.

Usage:
  cd D:/Dev/miniciv
  python experiments/v0.5.0/run_fast_matrix.py
"""

import json, math, os, random, sys, time

# Ensure project root is in path
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
WORKERS = 8


def run_pair_batched(ai_a, ai_b):
    """Run all seeds for one AI pair sequentially on a local process pool, one seed at a time."""
    from prototype.eval import load_ai
    from prototype.game import init_game, step_game
    from concurrent.futures import ProcessPoolExecutor, as_completed

    results = []
    all_tasks = []

    for g in range(GAMES):
        seed = SEED + g * 1000 + hash((ai_a, ai_b)) % 100000
        # Game 1: ai_a=P0, ai_b=P1
        t1 = (seed, ai_a, ai_b, SIZE, "balanced", MAX_TURNS)
        all_tasks.append(t1)
        # Game 2: ai_a=P1, ai_b=P0
        t2 = (seed + 2_000_000, ai_b, ai_a, SIZE, "balanced", MAX_TURNS)
        all_tasks.append(t2)

    # Run in parallel (single-seed tasks are small)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(_run_single, t): t for t in all_tasks}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)

    # Aggregate paired results
    seeds_dict = {}
    for r in results:
        s = r["base_seed"] if "base_seed" in r else (r["seed"] if r.get("ai0") == ai_a else r["seed"] - 2_000_000)
        base = s if s % 2_000_000 != 1_000_000 else s - 1_000_000
        # Simplify: just use the raw seed
        seeds_dict.setdefault(r["seed"], []).append(r)

    # Build paired stats
    n_seeds = GAMES  # Each original seed produces 2 games
    paired_results = []
    for g in range(GAMES):
        seed = SEED + g * 1000 + hash((ai_a, ai_b)) % 100000
        game1 = _find_result(results, seed, ai_a, ai_b)
        game2 = _find_result(results, seed + 2_000_000, ai_b, ai_a)
        if game1 and game2:
            paired_results.append({
                "seed": seed,
                "game1": game1, "game2": game2,
                "ai_a_wins": (1 if game1["winner"] == 0 else 0) + (1 if game2["winner"] == 1 else 0),
                "ai_b_wins": (1 if game1["winner"] == 1 else 0) + (1 if game2["winner"] == 0 else 0),
            })

    # Compute stats
    n = len(paired_results)
    total_games = n * 2
    ai_a_wins = sum(r["ai_a_wins"] for r in paired_results)
    ai_b_wins = sum(r["ai_b_wins"] for r in paired_results)
    ai_a_wr = ai_a_wins / total_games if total_games else 0.5

    conquests = sum(1 for r in paired_results for g in [r["game1"], r["game2"]] if str(g["victory_type"]) == "conquest")
    constructions = sum(1 for r in paired_results for g in [r["game1"], r["game2"]] if str(g["victory_type"]) == "construction")
    tiebreaks = total_games - conquests - constructions

    all_turns = []
    for r in paired_results:
        all_turns.append(r["game1"]["turns"])
        all_turns.append(r["game2"]["turns"])
    avg_t = sum(all_turns) / len(all_turns) if all_turns else 0

    seed_rates = [r["ai_a_wins"] / 2 for r in paired_results]
    ai_a_std = _std(seed_rates) if len(seed_rates) > 1 else 0
    p0_wins = sum(1 for r in paired_results for g in [r["game1"], r["game2"]] if g["winner"] == 0)
    p0_wr = p0_wins / total_games if total_games else 0.5
    p0_ci = _ci95(p0_wr, total_games)
    ai_a_ci = _ci95(ai_a_wr, total_games)

    cq_rate = conquests / total_games
    cs_rate = constructions / total_games
    tie_rate = tiebreaks / total_games

    raw_data = {
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

    return raw_data


def _find_result(results, seed, ai0, ai1):
    """Find a game result matching seed and AI names."""
    for r in results:
        if r["seed"] == seed and r.get("ai0") == ai0 and r.get("ai1") == ai1:
            return r
    return None


def _run_single(args):
    """Run a single game. args: (seed, ai0_name, ai1_name, size, gen, max_turns)"""
    import sys
    _root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from prototype.game import init_game, step_game
    from prototype.eval import load_ai
    seed, ai0_name, ai1_name, size, gen, max_turns = args
    gs = init_game(seed=seed, size=size, generator_id=gen)
    ai0 = load_ai(ai0_name)
    ai1 = load_ai(ai1_name)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0(gs, 0, rng0), ai1(gs, 1, rng1))
    return {
        "seed": seed, "ai0": ai0_name, "ai1": ai1_name,
        "winner": gs.winner, "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_hp": gs.cities[0].hp, "p1_hp": gs.cities[1].hp,
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
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

    # Bootstrap CI
    n_boot = 2000
    import random as _rnd
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
    print("  MINICIV v0.5.0 — FAST 7x7 PAIRED MATRIX")
    print(f"  AIs: {', '.join(AI_NAMES)}")
    print(f"  Games per pair: {GAMES} (x2 swapped = {GAMES*2} games/pair)")
    print(f"  Workers per batch: {WORKERS}")
    print("=" * 70)
    print()

    all_pairs = [(a, b) for a in AI_NAMES for b in AI_NAMES]
    total = len(all_pairs)
    pairs_data = []

    for idx, (ai_a, ai_b) in enumerate(all_pairs, 1):
        out_path = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")
        if os.path.exists(out_path):
            with open(out_path) as f:
                data = json.load(f)
            pairs_data.append(data)
            print(f"  [{idx}/{total}] {ai_a} vs {ai_b} — loaded from cache")
            continue

        t0 = time.perf_counter()
        print(f"  [{idx}/{total}] {ai_a} vs {ai_b} — running {GAMES*2} games...", end=" ")
        sys.stdout.flush()

        data = run_pair_batched(ai_a, ai_b)
        elapsed = time.perf_counter() - t0

        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)

        # Also copy the pair data to cache in main dir
        main_out = os.path.join(OUTPUT_DIR, f"paired_{ai_a}_vs_{ai_b}.json")
        with open(main_out, "w") as f:
            json.dump(data, f, indent=2)

        pairs_data.append(data)

        wr = data["ai_a_winrate"] * 100
        print(f"done ({elapsed:.0f}s, A_win={wr:.1f}%)")

    elapsed = time.perf_counter() - t_start
    print(f"\n  All {total} pairs completed in {elapsed:.0f}s")

    # Build summary
    total_seeds = sum(p.get("n_seeds", 0) for p in pairs_data)
    total_games = sum(p.get("n_games", 0) for p in pairs_data)
    summary = {
        "config": {
            "games_per_pair": GAMES,
            "size": SIZE,
            "gen": "balanced",
            "paired": True,
            "mode": "normal",
        },
        "pairs": pairs_data,
        "total_seeds": total_seeds,
        "total_games": total_games,
        "elapsed_s": round(elapsed, 1),
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Elo
    print("\n" + "=" * 70)
    print("  ELO RANKINGS")
    print("=" * 70)
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
    print("\n" + "=" * 70)
    print("  GENERATING REPORT")
    print("=" * 70)
    report = _generate_report(summary, elo, ai_names_sorted)
    with open(os.path.join(OUTPUT_DIR, "report.md"), "w") as f:
        f.write(report)
    print(f"  Report saved to {OUTPUT_DIR}/report.md")
    print("\n  ALL DONE")


def _generate_report(summary, elo, ai_names):
    pairs = summary["pairs"]
    config = summary["config"]
    lines = []
    lines.append("# MiniCiv v0.5.0 — AI Comparison Matrix (7x7)")
    lines.append("")
    lines.append(f"- **Date**: July 2026")
    lines.append(f"- **AIs**: {', '.join(ai_names)}")
    lines.append(f"- **Games per pair**: {config['games_per_pair']} (x2 swapped = {config['games_per_pair']*2} games/pair)")
    lines.append(f"- **Total games**: {len(ai_names)}x{len(ai_names)} x {config['games_per_pair']*2} = {len(ai_names)*len(ai_names)*config['games_per_pair']*2}")
    lines.append(f"- **Map**: {config['size']}x{config['size']} {config['gen']}")
    lines.append(f"- **Protocol**: Paired (P0/P1 swap per seed)")
    lines.append(f"- **Total games run**: {summary['total_games']}")
    lines.append(f"- **Elapsed**: {summary['elapsed_s']}s")
    lines.append("")

    # Winrate matrix
    lines.append("## Winrate Matrix (Row AI vs Column AI)")
    lines.append("")
    lines.append("Values are Row AI's winrate as percentage (with 95% CI).")
    lines.append("")
    wr = {}
    ci_lookup = {}
    for p in pairs:
        wr[(p["ai_a"], p["ai_b"])] = p["ai_a_winrate"]
        ci_lookup[(p["ai_a"], p["ai_b"])] = p["ai_a_ci95"]

    header = f"| {'AI':>8s} |"
    for name in ai_names:
        header += f" {name:>12s} |"
    lines.append(header)
    sep = "|:" + "-" * 7 + ":|"
    for name in ai_names:
        sep += ":" + "-" * 11 + ":|"
    lines.append(sep)

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
        lines.append(row)
    lines.append("")

    # Elo ranking
    lines.append("## Elo Rankings")
    lines.append("")
    lines.append(f"- Starting Elo: 1500")
    lines.append(f"- K = 32")
    lines.append(f"- Iterations: 200")
    lines.append(f"- 95% CI via bootstrap (n=2000)")
    lines.append("")
    ranked = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    lines.append(f"| {'Rank':>4s} | {'AI':>12s} | {'Elo':>7s} | {'95% CI':>12s} |")
    lines.append(f"|{'':-<5s}|{'':-<13s}|{'':-<8s}|{'':-<13s}|")
    for rank, (name, e) in enumerate(ranked, 1):
        lines.append(f"| {rank:>3d}. | {name:>12s} | {e['elo']:>6.1f} | {e['ci_low']:>5.1f}-{e['ci_high']:>5.1f} |")
    lines.append("")

    # Compare with v0.4.0
    lines.append("## Comparison with v0.4.0 (4x4 Matrix)")
    lines.append("")
    v4_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "eval_final", "summary.json")
    if os.path.exists(v4_path):
        with open(v4_path) as f:
            v4 = json.load(f)
        v4_pairs_map = {(p["ai0"], p["ai1"]): p["p0_winrate"] for p in v4["pairs"]}
        lines.append("| Matchup | v0.4.0 P0% | v0.5.0 Paired% | Delta |")
        lines.append("|---|---:|---:|---:|")
        matchups = [
            ("random", "random"), ("random", "greedy"), ("random", "aggressive"), ("random", "flatmc"),
            ("greedy", "greedy"), ("greedy", "aggressive"), ("greedy", "flatmc"),
            ("aggressive", "aggressive"), ("aggressive", "flatmc"), ("flatmc", "flatmc"),
        ]
        for a0, a1 in matchups:
            v4_val = v4_pairs_map.get((a0, a1))
            v5_val = None
            for p in pairs:
                if p["ai_a"] == a0 and p["ai_b"] == a1:
                    v5_val = p["p0_winrate"] if a0 == a1 else p["ai_a_winrate"]
                    break
            if v4_val is not None and v5_val is not None:
                delta = (v5_val - v4_val) * 100
                lines.append(f"| {a0} vs {a1} | {v4_val*100:.1f}% | {v5_val*100:.1f}% | {delta:+.1f}% |")
        lines.append("")

    # Analysis
    lines.append("## Analysis")
    lines.append("")
    graded = sorted(elo.items(), key=lambda x: -x[1]["elo"])
    top_elo = graded[0][1]["elo"]
    bottom_elo = graded[-1][1]["elo"]
    spread = top_elo - bottom_elo
    lines.append(f"### Overall spread: {spread:.0f} Elo points ({bottom_elo:.0f} to {top_elo:.0f})")
    lines.append("")

    tiers = {"S": [], "A": [], "B": [], "C": []}
    for name, e in graded:
        pct = (e["elo"] - bottom_elo) / max(1, spread)
        if pct >= 0.8: tiers["S"].append(name)
        elif pct >= 0.5: tiers["A"].append(name)
        elif pct >= 0.2: tiers["B"].append(name)
        else: tiers["C"].append(name)
    for tier in ["S", "A", "B", "C"]:
        if tiers[tier]:
            lines.append(f"- **Tier {tier}**: {', '.join(tiers[tier])}")
    lines.append("")

    lines.append("### Paradigm Analysis")
    lines.append("")
    lines.append("The 7 AIs represent 4 paradigms:")
    lines.append("")
    lines.append("1. **Rule-based**: random, greedy, aggressive, flatmc")
    lines.append("2. **Weight-parameterized (evolvable)**: evo")
    lines.append("3. **Behavior Cloning (supervised NN)**: bc")
    lines.append("4. **Reinforcement Learning (DQN)**: dqn")
    lines.append("")

    rule_names = ["random", "greedy", "aggressive", "flatmc"]
    ml_names = ["evo", "bc", "dqn"]
    rule_top = next(((n, e) for n, e in graded if n in rule_names), None)
    ml_top = next(((n, e) for n, e in graded if n in ml_names), None)
    if rule_top:
        lines.append(f"- Best rule-based: {rule_top[0]} ({rule_top[1]['elo']:.1f} Elo)")
    if ml_top:
        lines.append(f"- Best ML-based: {ml_top[0]} ({ml_top[1]['elo']:.1f} Elo)")
    if rule_top and ml_top:
        gap = rule_top[1]["elo"] - ml_top[1]["elo"]
        lines.append(f"- {'Rule-based' if gap > 0 else 'ML-based'} leads by {abs(gap):.0f} Elo")
    lines.append("")

    lines.append("### First-Player Advantage (Mirror Matches)")
    lines.append("")
    lines.append("| AI | P0 Winrate in Mirror | 95% CI | P0 Advantage |")
    lines.append("|---|---:|---:|---:|")
    for name in ai_names:
        for p in pairs:
            if p["ai_a"] == name and p["ai_b"] == name:
                p0_wr = p["p0_winrate"]
                p0_ci = p["p0_ci95"]
                adv = (p0_wr - 0.5) * 100
                lines.append(f"| {name} | {p0_wr*100:.1f}% | +-{p0_ci*100:.1f}% | {adv:+.1f}% |")
                break
    lines.append("")

    lines.append("### Victory Type Distribution")
    lines.append("")
    avg_conq = sum(p.get("conquest_rate", 0) for p in pairs) / len(pairs) * 100
    avg_cons = sum(p.get("construction_rate", 0) for p in pairs) / len(pairs) * 100
    avg_tie = 100 - avg_conq - avg_cons
    lines.append(f"- Conquest: {avg_conq:.1f}%")
    lines.append(f"- Construction: {avg_cons:.1f}%")
    lines.append(f"- Tiebreak (max turns): {avg_tie:.1f}%")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
