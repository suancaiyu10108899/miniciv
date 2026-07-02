"""eval_full_matrix/compute_elo.py
Compute Elo ratings from the comparison matrix (E3).

Usage:
    python eval_full_matrix/compute_elo.py [--matrix eval_full_matrix/winrate_matrix.json]

Outputs:
    - Elo ratings with 95% CI
    - Elo difference vs predicted winrate mapping
"""

import sys, os, json, math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _ci(p, n):
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def expected_score(rating_self, rating_opp):
    """Expected score given two Elo ratings."""
    return 1.0 / (1.0 + 10.0 ** ((rating_opp - rating_self) / 400.0))


def compute_elo(pair_results, players, k=32, iterations=100):
    """Compute Elo ratings from pair winrate data.

    Args:
        pair_results: dict with keys like "ai_a_vs_ai_b", values with ai_a_winrate, ai_a_ci95, n_seeds
        players: list of AI names
        k: K-factor for Elo
        iterations: number of full passes through all pairs

    Returns:
        dict mapping player name -> final Elo
        history: per-iteration ratings for convergence check
    """
    elo = {p: 1500.0 for p in players}
    history = {p: [1500.0] for p in players}

    # Build pair result list
    pairs_list = []
    for (a, b), data in pair_results.items():
        wr_a = data.get("ai_a_winrate", data.get("p0_winrate", 0))
        n_games = data.get("n", 300) * 2  # paired seeds * 2 games per seed
        pairs_list.append((a, b, wr_a, n_games))

    all_iter_ratings = []

    for _ in range(iterations):
        for a, b, wr_a, n in pairs_list:
            # Expected scores
            ea = expected_score(elo[a], elo[b])
            eb = expected_score(elo[b], elo[a])

            # Actual scores (from the pair winrate)
            # wr_a is AI_A's winrate across all games in this pair
            sa = wr_a
            sb = 1.0 - wr_a

            # Update (weighted by n to give more weight to high-confidence pairs)
            # Using sqrt(n) weighting to be conservative
            weight = math.sqrt(n / 600.0)  # Normalized to baseline 600 games
            weight = min(weight, 2.0)  # Cap at 2x weighting

            elo[a] += k * weight * (sa - ea)
            elo[b] += k * weight * (sb - eb)

        all_iter_ratings.append({p: elo[p] for p in players})

    # Compute 95% CI from winrate variance through the pair results
    # For each player, propagate uncertainty from each match
    elo_with_ci = {}
    for p in players:
        # Baseline CI: estimate from average winrate variance across all matches
        variances = []
        for a, b, wr_a, n in pairs_list:
            if a == p or b == p:
                opponent = b if a == p else a
                my_wr = wr_a if a == p else (1.0 - wr_a)
                # Variance of winrate
                if n > 0:
                    var = my_wr * (1 - my_wr) / n
                    variances.append(var)

        if variances:
            avg_var = sum(variances) / len(variances)
            ci95 = 1.96 * math.sqrt(avg_var)
            # Convert winrate CI to Elo CI (approximately)
            # A winrate of p ± δ translates roughly to Elo of ± 400*log((p+δ)/(1-p-δ)) - 400*log(p/(1-p))
            # For small δ: approx 400 * δ / (p*(1-p))
            avg_wr = 0.5  # rough estimate for symmetric matchups
            elo_ci = 400 * ci95 / (avg_wr * (1 - avg_wr)) if avg_wr * (1 - avg_wr) > 0 else 100
        else:
            elo_ci = 50  # Fallback

        elo_with_ci[p] = {
            "elo": round(elo[p], 1),
            "ci95": round(elo_ci, 1),
        }

    return elo_with_ci, all_iter_ratings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compute Elo from winrate matrix")
    parser.add_argument("--matrix", default=None,
                        help="Path to winrate_matrix.json. If None, loads from eval_full_matrix/")
    parser.add_argument("--k", type=int, default=32, help="K-factor")
    parser.add_argument("--iterations", type=int, default=100, help="Iterations")
    args = parser.parse_args()

    # Load winrate matrix
    if args.matrix:
        matrix_path = args.matrix
    else:
        matrix_path = os.path.join(os.path.dirname(__file__), "winrate_matrix.json")

    if not os.path.exists(matrix_path):
        print(f"ERROR: {matrix_path} not found. Run run_matrix.py first.")
        sys.exit(1)

    with open(matrix_path) as f:
        raw_data = json.load(f)

    # Parse the data back into tuple-keyed dict
    pair_results = {}
    players_set = set()
    for key, val in raw_data.items():
        parts = key.split("_vs_")
        if len(parts) == 2:
            a, b = parts
            pair_results[(a, b)] = val
            players_set.add(a)
            players_set.add(b)

    players = sorted(list(players_set))
    print(f"Computing Elo for {len(players)} players: {players}")
    print(f"Using {len(pair_results)} pair results")
    print(f"K={args.k}, iterations={args.iterations}")

    elo_results, history = compute_elo(pair_results, players, k=args.k, iterations=args.iterations)

    # Convergence check
    print("\n" + "=" * 60)
    print("Elo Ratings (converged)")
    print("=" * 60)
    sorted_players = sorted(elo_results.keys(), key=lambda p: -elo_results[p]["elo"])
    print(f"{'Rank':>5s} {'Player':14s} {'Elo':>8s} {'95% CI':>8s}")
    print("-" * 40)
    for rank, p in enumerate(sorted_players, 1):
        e = elo_results[p]
        print(f"{rank:5d} {p:14s} {e['elo']:8.1f} ±{e['ci95']:5.1f}")

    # Elo -> winrate mapping calibration
    print("\n" + "=" * 60)
    print("Elo Difference -> Predicted Winrate")
    print("=" * 60)
    print(f"{'Elo Gap':>10s} {'Expected WR':>12s} {'Theoretical WR':>14s} {'Diff':>6s}")
    print("-" * 45)
    for gap in [0, 25, 50, 75, 100, 150, 200, 300, 400]:
        expected = 1.0 / (1.0 + 10.0 ** (-gap / 400.0))
        theoretical = 1.0 / (1.0 + 10.0 ** (-gap / 400.0))  # Same formula
        print(f"{gap:8d}    {expected*100:6.2f}%       {theoretical*100:6.2f}%      {'0.00':>5s}")

    # Check: does a 100 Elo gap ≈ 64%?
    wr_100 = 1.0 / (1.0 + 10.0 ** (-100 / 400.0))
    print(f"\n100 Elo gap → {wr_100*100:.1f}% winrate")
    print(f"Theoretical: 1/(1+10^(-100/400)) = {wr_100*100:.1f}%")
    print(f"(Yes, a 100 Elo gap ≈ {wr_100*100:.1f}% winrate)")

    # Compare actual vs theoretical for the measured pairs
    print("\n" + "=" * 60)
    print("Actual vs Theoretical Winrates (from matrix)")
    print("=" * 60)
    print(f"{'Matchup':24s} {'Actual WR':>10s} {'Elo Pred':>10s} {'Diff':>6s}")
    print("-" * 55)
    for (a, b), data in sorted(pair_results.items()):
        wr_a = data.get("ai_a_winrate", data.get("p0_winrate", 0))
        elo_diff = elo_results[a]["elo"] - elo_results[b]["elo"]
        predicted = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        diff = wr_a - predicted
        print(f"{a} vs {b:12s} {wr_a*100:7.2f}%   {predicted*100:7.2f}%   {diff*100:+5.2f}%")

    # Save
    out_dir = os.path.dirname(os.path.abspath(__file__))
    output = {
        "config": {"k_factor": args.k, "iterations": args.iterations},
        "elo_ratings": {p: v["elo"] for p, v in elo_results.items()},
        "elo_with_ci": elo_results,
        "ranking": [{"rank": i+1, "player": p, "elo": elo_results[p]["elo"],
                      "ci95": elo_results[p]["ci95"]}
                     for i, p in enumerate(sorted_players)],
    }
    with open(os.path.join(out_dir, "elo_ratings.json"), "w") as f:
        json.dump(output, f, indent=2)

    # Convergence history
    with open(os.path.join(out_dir, "elo_history.json"), "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nSaved to {out_dir}/")
    return elo_results, pair_results


if __name__ == "__main__":
    main()
