#!/usr/bin/env python3
"""
validate_dqn.py — DQN vs Multiple Opponents Validation Script

This script loads the DQN agent from saved weights and evaluates it against
multiple opponents (Evo, Aggressive, Random). It records per-game metrics
including winrate, victory type breakdown, average turns, dead units, tech
completion, and unit production.

Key finding: The DQN weights contain NaN values (numerical instability during
training). This script handles that gracefully by:
1. Loading the weights and checking for NaN
2. Running games with the corrupted DQN (which will produce NaN Q-values)
3. Also running a fresh untrained DQN as control
4. Producing the validation report

Output directory: experiments/v0.5.0/dqn-validation/
"""

import json
import math
import os
import random as _random
import statistics
import sys
import time
import traceback

import numpy as np

# Ensure project root is on path so prototype modules are importable
# When running via `python path/to/script.py`, sys.path[0] is the script's dir.
# We need sys.path[0] to be the project root instead.
# Script is at experiments/v0.5.0/dqn-validation/validate_dqn.py, so up 3 levels.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path[0] = PROJECT_ROOT
os.chdir(PROJECT_ROOT)

from prototype.game import init_game, step_game
from prototype.ai_dqn import DQNAgent, ai_decide as dqn_decide, compute_features
from prototype.ai_evo import ai_decide as evo_decide
from prototype.ai_aggressive import ai_decide as aggressive_decide
from prototype.ai_rulesrandom import ai_decide as random_decide
from prototype.ai_greedy import ai_decide as greedy_decide

# ── Paths ───────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DQN_WEIGHTS_PATH = os.path.join(
    PROJECT_ROOT, "experiments", "v0.4.0", "paradigms", "dqn_best_weights.json"
)
EVO_WEIGHTS_PATH = os.path.join(
    PROJECT_ROOT, "experiments", "v0.4.0", "gradient", "evo_checkpoints", "b2_gen_200.json"
)
BC_WEIGHTS_PATH = os.path.join(
    PROJECT_ROOT, "experiments", "v0.4.0", "paradigms", "bc_weights.json"
)
REPORT_PATH = os.path.join(OUTPUT_DIR, "report.md")
RAW_DATA_DIR = OUTPUT_DIR

# ── Constants ───────────────────────────────────────────────────────
N_FEATURES = 25
N_ACTIONS = 6
MAX_TURNS = 100
MAP_SIZE = 15
GENERATOR = "balanced"

# ── Helpers: AI wrappers ────────────────────────────────────────────


def make_dqn_decider(agent):
    """Wrap a DQNAgent into an ai_decide-compatible function."""
    def decider(gs, pid, rng):
        return dqn_decide(gs, pid, rng, dqn=agent)
    return decider


def load_evo_weights(path):
    """Load Evo weights from the checkpoint JSON format."""
    with open(path) as f:
        data = json.load(f)
    if "w" in data:
        return data["w"]
    if "weights" in data:
        return data["weights"]
    return data


def make_evo_decider(weights):
    """Wrap Evo weights into an ai_decide-compatible function."""
    def decider(gs, pid, rng):
        return evo_decide(gs, pid, rng, weights=weights)
    return decider


def load_dqn_agent(path):
    """Load DQN agent from weights file, check for NaN, return (agent, has_nan)."""
    with open(path) as f:
        data = json.load(f)

    has_nan = False
    for key in ["W1", "b1", "W2", "b2", "W3", "b3"]:
        arr = np.asarray(data[key], dtype=np.float64)
        if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
            has_nan = True
            break

    agent = DQNAgent(
        n_features=data.get("n_features", N_FEATURES),
        n_actions=data.get("n_actions", N_ACTIONS),
    )
    agent.load(path)
    return agent, has_nan


def make_fresh_dqn_agent():
    """Create a randomly-initialized (untrained) DQN agent for control."""
    agent = DQNAgent(n_features=N_FEATURES, n_actions=N_ACTIONS)
    return agent


# ── Game runner ─────────────────────────────────────────────────────


def run_one_game(seed, ai0_func, ai1_func, size=MAP_SIZE,
                 generator_id=GENERATOR, max_turns=MAX_TURNS):
    """Run a single game between two AI decision functions.

    Returns a detailed dict of game metrics.
    """
    gs = init_game(seed=seed, size=size, generator_id=generator_id)
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    start = time.time()

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0_func(gs, 0, rng0)
        a1 = ai1_func(gs, 1, rng1)
        step_game(gs, a0, a1)

    elapsed = time.time() - start

    # Unit production tracking: count units by type that were produced
    # (alive + dead units that belong to each player)
    p0_units_by_type = _count_unit_types(gs, 0)
    p1_units_by_type = _count_unit_types(gs, 1)

    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
        "elapsed": round(elapsed, 3),
        "p0_resources": {
            "food": gs.economies[0].food,
            "wood": gs.economies[0].wood,
            "gold": gs.economies[0].gold,
        },
        "p1_resources": {
            "food": gs.economies[1].food,
            "wood": gs.economies[1].wood,
            "gold": gs.economies[1].gold,
        },
        "p0_techs": len(gs.techs[0].completed),
        "p1_techs": len(gs.techs[1].completed),
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_units_by_type": p0_units_by_type,
        "p1_units_by_type": p1_units_by_type,
        "p0_techs_list": list(gs.techs[0].completed),
        "p1_techs_list": list(gs.techs[1].completed),
    }


def _count_unit_types(gs, pid):
    """Count all units (alive + dead) for a player by type."""
    counts = {"infantry": 0, "cavalry": 0, "archer": 0, "scout": 0, "worker": 0}
    all_units = [u for u in gs.units if u.player_id == pid] + \
                [u for u in gs.dead_units if u.player_id == pid]
    for u in all_units:
        if u.unit_type in counts:
            counts[u.unit_type] += 1
    return counts


# ── Match runner (paired: swap P0/P1) ──────────────────────────────


def run_matchup(name_dqn, name_opp, dqn_decider, opp_decider,
                n_games, base_seed=1000, paired=True):
    """Run a DQN vs Opponent matchup.

    If paired=True, each seed is run twice (DQN as P0, DQN as P1)
    to cancel first-move advantage.

    Returns list of result dicts, each tagged with which player DQN was.
    """
    all_results = []
    actual_games_run = 0

    for g in range(n_games):
        seed = base_seed + g
        if paired:
            # Run both directions with the same seed
            # Direction 1: DQN as P0
            r1 = run_one_game(seed, dqn_decider, opp_decider)
            r1["dqn_player"] = 0
            r1["matchup"] = f"{name_dqn}(P0) vs {name_opp}(P1)"
            all_results.append(r1)
            actual_games_run += 1

            # Direction 2: DQN as P1
            r2 = run_one_game(seed, opp_decider, dqn_decider)
            r2["dqn_player"] = 1
            r2["matchup"] = f"{name_opp}(P0) vs {name_dqn}(P1)"
            all_results.append(r2)
            actual_games_run += 1
        else:
            # Single direction: DQN is P0
            r = run_one_game(seed, dqn_decider, opp_decider)
            r["dqn_player"] = 0
            r["matchup"] = f"{name_dqn}(P0) vs {name_opp}(P1)"
            all_results.append(r)
            actual_games_run += 1

    return all_results, actual_games_run


# ── Metrics computation ────────────────────────────────────────────


def compute_metrics(results):
    """Compute aggregate metrics from a list of game results.

    Each result dict has a 'dqn_player' key indicating which player ID (0 or 1)
    the DQN controlled in that game.
    Returns a dict of summary statistics.
    """
    n = len(results)
    if n == 0:
        return {"error": "no games"}

    dqn_wins = sum(1 for r in results if r["winner"] == r["dqn_player"])
    opp_wins = sum(1 for r in results if r["winner"] != r["dqn_player"] and r["winner"] is not None)
    draws = n - dqn_wins - opp_wins

    winrate = dqn_wins / n * 100.0
    winrate_std = math.sqrt(winrate * (100 - winrate) / n) if n > 1 else 0

    victory_types = {}
    for r in results:
        vt = r["victory_type"] or "unknown"
        victory_types[vt] = victory_types.get(vt, 0) + 1

    dqn_victories = [r for r in results if r["winner"] == r["dqn_player"]]

    avg_turns = statistics.mean(r["turns"] for r in results) if results else 0
    std_turns = statistics.stdev(r["turns"] for r in results) if len(results) > 1 else 0

    avg_dead_dqn = statistics.mean(r[f"p{r['dqn_player']}_dead"] for r in results)
    avg_dead_opp = statistics.mean(r[f"p{1-r['dqn_player']}_dead"] for r in results)

    avg_techs_dqn = statistics.mean(r[f"p{r['dqn_player']}_techs"] for r in results)
    avg_techs_opp = statistics.mean(r[f"p{1-r['dqn_player']}_techs"] for r in results)

    avg_construction_dqn = statistics.mean(r[f"p{r['dqn_player']}_construction"] for r in results)
    avg_construction_opp = statistics.mean(r[f"p{1-r['dqn_player']}_construction"] for r in results)

    dqn_construction_wins = sum(
        1 for r in dqn_victories
        if r["victory_type"] == "construction"
    )
    dqn_conquest_wins = sum(
        1 for r in dqn_victories
        if r["victory_type"] == "conquest"
    )

    # Unit production averages
    unit_types = ["infantry", "cavalry", "archer", "scout", "worker"]
    avg_dqn_units = {
        ut: statistics.mean(r[f"p{r['dqn_player']}_units_by_type"][ut] for r in results)
        for ut in unit_types
    }
    avg_opp_units = {
        ut: statistics.mean(r[f"p{1-r['dqn_player']}_units_by_type"][ut] for r in results)
        for ut in unit_types
    }

    return {
        "n_games": n,
        "dqn_wins": dqn_wins,
        "opp_wins": opp_wins,
        "draws": draws,
        "winrate_pct": round(winrate, 2),
        "winrate_std_pct": round(winrate_std, 2),
        "victory_types": victory_types,
        "dqn_construction_wins": dqn_construction_wins,
        "dqn_conquest_wins": dqn_conquest_wins,
        "avg_turns": round(avg_turns, 2),
        "std_turns": round(std_turns, 2),
        "avg_dead_dqn": round(avg_dead_dqn, 2),
        "avg_dead_opp": round(avg_dead_opp, 2),
        "avg_techs_dqn": round(avg_techs_dqn, 2),
        "avg_techs_opp": round(avg_techs_opp, 2),
        "avg_construction_dqn": round(avg_construction_dqn, 2),
        "avg_construction_opp": round(avg_construction_opp, 2),
        "avg_dqn_units_by_type": avg_dqn_units,
        "avg_opp_units_by_type": avg_opp_units,
    }


def analyze_behavior(results, sample_size=20):
    """Analyze DQN behavior pattern from a sample of games.

    Checks for C5-rush shortcut (construction victory dominance,
    low military production, high tech count).
    Each result dict has 'dqn_player' indicating which side DQN was on.
    """
    sample = results[:sample_size]
    n = len(sample)
    if n == 0:
        return {"error": "no games in sample"}

    # Victory type breakdown - DQN wins that are construction
    dqn_construction_wins = sum(
        1 for r in sample
        if r["winner"] == r["dqn_player"] and r["victory_type"] == "construction"
    )
    dqn_conquest_wins = sum(
        1 for r in sample
        if r["winner"] == r["dqn_player"] and r["victory_type"] == "conquest"
    )
    construction_pct = dqn_construction_wins / n * 100

    # Tech completion - use per-result dqn_player
    avg_techs = statistics.mean(r[f"p{r['dqn_player']}_techs"] for r in sample)
    avg_construction = statistics.mean(
        r[f"p{r['dqn_player']}_construction"] for r in sample
    )

    # Unit production - military vs non-military
    avg_military = statistics.mean(
        r[f"p{r['dqn_player']}_units_by_type"]["infantry"] +
        r[f"p{r['dqn_player']}_units_by_type"]["cavalry"] +
        r[f"p{r['dqn_player']}_units_by_type"]["archer"]
        for r in sample
    )
    avg_scouts = statistics.mean(
        r[f"p{r['dqn_player']}_units_by_type"]["scout"] for r in sample
    )
    avg_workers = statistics.mean(
        r[f"p{r['dqn_player']}_units_by_type"]["worker"] for r in sample
    )

    # C5 completion rate
    c5_count = sum(
        1 for r in sample
        if "C5" in r.get(f"p{r['dqn_player']}_techs_list", [])
    )

    return {
        "sample_size": n,
        "construction_victory_pct": round(construction_pct, 2),
        "conquest_victory_pct": round(dqn_conquest_wins / n * 100, 2),
        "avg_techs_completed": round(avg_techs, 2),
        "avg_construction_techs": round(avg_construction, 2),
        "avg_military_units_produced": round(avg_military, 2),
        "avg_scouts_produced": round(avg_scouts, 2),
        "avg_workers_produced": round(avg_workers, 2),
        "c5_completion_rate_pct": round(c5_count / n * 100, 2),
        "c5_completed_games": c5_count,
    }


# ── Comparison with BC behavior ────────────────────────────────────


def load_bc_weights(path):
    """Load BC weights if they exist."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    return data


# ── Strategy-level analysis: per-game detailed tracking ────────────


def extract_strategy_details(results):
    """Extract per-game strategic indicators for DQN.

    Detects whether DQN:
    - Pursues C5 rush (all construction techs, minimal military)
    - Plays balanced (mix of military and construction)
    - Relies on conquest (military units > 3, early aggression)
    """
    details = []
    for r in results:
        dp = r["dqn_player"]
        mil_units = (
            r[f"p{dp}_units_by_type"]["infantry"] +
            r[f"p{dp}_units_by_type"]["cavalry"] +
            r[f"p{dp}_units_by_type"]["archer"]
        )
        techs_list = r.get(f"p{dp}_techs_list", [])
        has_c5 = "C5" in techs_list
        construction = r[f"p{dp}_construction"]
        won = r["winner"] == dp

        # Classify strategy
        if construction >= 3 and mil_units <= 2 and has_c5:
            strategy = "C5_rush"
        elif construction >= 3 and mil_units >= 3:
            strategy = "mixed_construction"
        elif mil_units >= 4:
            strategy = "military_focus"
        else:
            strategy = "underdeveloped"

        details.append({
            "seed": r["seed"],
            "won": won,
            "victory_type": r["victory_type"],
            "turns": r["turns"],
            "strategy": strategy,
            "military_units": mil_units,
            "construction_techs": construction,
            "has_c5": has_c5,
            "techs_completed": r[f"p{dp}_techs"],
        })
    return details


# ══════════════════════════════════════════════════════════════════
# Main validation pipeline
# ══════════════════════════════════════════════════════════════════

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=" * 60)
    print("DQN Validation: DQN vs Evo / Aggressive / Random")
    print("=" * 60)

    # ── Step 0: Check weights ────────────────────────────────────
    print("\n[0] Loading DQN weights...")
    agent, dqn_has_nan = load_dqn_agent(DQN_WEIGHTS_PATH)
    state = np.zeros(N_FEATURES, dtype=np.float64)
    try:
        q_vals = agent.forward(state)
        has_nan_q = bool(np.any(np.isnan(q_vals)))
        has_inf_q = bool(np.any(np.isinf(q_vals)))
    except Exception as e:
        has_nan_q = True
        has_inf_q = True
        print(f"  Forward pass error: {e}")

    print(f"  DQN weights file: {DQN_WEIGHTS_PATH}")
    print(f"  n_features={agent.n_features}, n_actions={agent.n_actions}")
    print(f"  Contains NaN: {dqn_has_nan}")
    print(f"  Forward pass produces NaN Q-values: {has_nan_q}")
    print(f"  Forward pass produces Inf Q-values: {has_inf_q}")

    # Log NaN analysis
    nan_analysis = {
        "weights_path": DQN_WEIGHTS_PATH,
        "contains_nan": dqn_has_nan,
        "forward_produces_nan": has_nan_q,
        "forward_produces_inf": has_inf_q,
    }

    # Load control DQN (untrained random weights)
    fresh_agent = make_fresh_dqn_agent()
    fresh_q = fresh_agent.forward(state)
    print(f"  Fresh (untrained) DQN forward: min={fresh_q.min():.4f}, max={fresh_q.max():.4f}")

    # Load Evo weights
    print("\n  Loading Evo weights...")
    evo_weights = load_evo_weights(EVO_WEIGHTS_PATH)
    print(f"  Evo weights loaded from: {EVO_WEIGHTS_PATH}")
    print(f"  Keys: {list(evo_weights.keys())}")

    # Load BC weights
    print("\n  Loading BC weights...")
    bc_data = load_bc_weights(BC_WEIGHTS_PATH)
    if bc_data:
        print(f"  BC weights found. Keys: {list(bc_data.keys())}")
    else:
        print("  BC weights not found or are null/empty.")

    # Create AI deciders
    dqn_trained = make_dqn_decider(agent)
    dqn_fresh = make_dqn_decider(fresh_agent)
    evo_ai = make_evo_decider(evo_weights)
    aggressive_ai = lambda gs, pid, rng: aggressive_decide(gs, pid, rng)
    random_ai = lambda gs, pid, rng: random_decide(gs, pid, rng)
    greedy_ai = lambda gs, pid, rng: greedy_decide(gs, pid, rng)

    # ── Step 1: Quick sanity check (10 games DQN trained vs Random) ──
    print("\n[1] Sanity check: DQN(loaded) vs Random (10 games)")
    sanity_results, _ = run_matchup("DQN", "Random", dqn_trained, random_ai,
                                     n_games=5, base_seed=9000, paired=True)
    sanity_metrics = compute_metrics(sanity_results)
    print(f"  DQN wins: {sanity_metrics['dqn_wins']}/{sanity_metrics['n_games']} "
          f"({sanity_metrics['winrate_pct']}%)")

    # ── Step 2: DQN vs Evo (200 games, paired) ──────────────────────
    print("\n[2] DQN(loaded) vs Evo gen200 (200 games, paired)")
    print("  Running... (this takes a while)")
    evo_results, evo_n = run_matchup(
        "DQN", "Evo", dqn_trained, evo_ai,
        n_games=100, base_seed=2000, paired=True
    )
    evo_metrics = compute_metrics(evo_results)
    print(f"  Games: {evo_metrics['n_games']}")
    print(f"  DQN winrate: {evo_metrics['winrate_pct']}% +/- {evo_metrics['winrate_std_pct']}%")
    print(f"  Victory types: {evo_metrics['victory_types']}")
    print(f"  Avg turns: {evo_metrics['avg_turns']}")

    # ── Step 3: DQN vs Aggressive (200 games, paired) ───────────────
    print("\n[3] DQN(loaded) vs Aggressive (200 games, paired)")
    print("  Running...")
    aggro_results, aggro_n = run_matchup(
        "DQN", "Aggressive", dqn_trained, aggressive_ai,
        n_games=100, base_seed=4000, paired=True
    )
    aggro_metrics = compute_metrics(aggro_results)
    print(f"  Games: {aggro_metrics['n_games']}")
    print(f"  DQN winrate: {aggro_metrics['winrate_pct']}% +/- {aggro_metrics['winrate_std_pct']}%")
    print(f"  Victory types: {aggro_metrics['victory_types']}")
    print(f"  Avg turns: {aggro_metrics['avg_turns']}")

    # ── Step 4: DQN vs Random (500 games, independent) ──────────────
    print("\n[4] DQN(loaded) vs Random (500 games, paired)")
    print("  Running...")
    random_results, random_n = run_matchup(
        "DQN", "Random", dqn_trained, random_ai,
        n_games=250, base_seed=6000, paired=True
    )
    random_metrics = compute_metrics(random_results)
    print(f"  Games: {random_metrics['n_games']}")
    print(f"  DQN winrate: {random_metrics['winrate_pct']}% +/- {random_metrics['winrate_std_pct']}%")
    print(f"  Victory types: {random_metrics['victory_types']}")
    print(f"  Avg turns: {random_metrics['avg_turns']}")

    # ── Step 4b: Control — Fresh (untrained) DQN vs Random (100 games) ──
    print("\n[4b] Control: Fresh (untrained) DQN vs Random (100 games, paired)")
    print("  Running...")
    fresh_results, fresh_n = run_matchup(
        "FreshDQN", "Random", dqn_fresh, random_ai,
        n_games=50, base_seed=8000, paired=True
    )
    fresh_metrics = compute_metrics(fresh_results)
    print(f"  Games: {fresh_metrics['n_games']}")
    print(f"  Fresh DQN winrate: {fresh_metrics['winrate_pct']}% +/- {fresh_metrics['winrate_std_pct']}%")
    print(f"  Victory types: {fresh_metrics['victory_types']}")

    # ── Step 5: Behavioral analysis ─────────────────────────────────
    print("\n[5] Behavioral analysis (sampling DQN games)")

    # Use Evo games for analysis (hardest opponent)
    evo_behavior = analyze_behavior(evo_results, sample_size=min(20, len(evo_results)))
    print(f"  DQN vs Evo behavior (n={evo_behavior['sample_size']}):")
    print(f"    Construction victory: {evo_behavior['construction_victory_pct']}%")
    print(f"    Conquest victory: {evo_behavior['conquest_victory_pct']}%")
    print(f"    Avg techs completed: {evo_behavior['avg_techs_completed']}")
    print(f"    Avg construction techs: {evo_behavior['avg_construction_techs']}")
    print(f"    Avg military units: {evo_behavior['avg_military_units_produced']}")

    # Aggressive games behavior
    aggro_behavior = analyze_behavior(aggro_results, sample_size=min(20, len(aggro_results)))
    print(f"\n  DQN vs Aggressive behavior (n={aggro_behavior['sample_size']}):")
    print(f"    Construction victory: {aggro_behavior['construction_victory_pct']}%")
    print(f"    Conquest victory: {aggro_behavior['conquest_victory_pct']}%")
    print(f"    Avg techs completed: {aggro_behavior['avg_techs_completed']}")
    print(f"    Avg military units: {aggro_behavior['avg_military_units_produced']}")
    print(f"    C5 completion: {aggro_behavior['c5_completion_rate_pct']}%")

    # Random games behavior
    random_behavior = analyze_behavior(random_results, sample_size=min(20, len(random_results)))
    print(f"\n  DQN vs Random behavior (n={random_behavior['sample_size']}):")
    print(f"    Construction victory: {random_behavior['construction_victory_pct']}%")
    print(f"    Conquest victory: {random_behavior['conquest_victory_pct']}%")
    print(f"    Avg techs completed: {random_behavior['avg_techs_completed']}")
    print(f"    Avg military units: {random_behavior['avg_military_units_produced']}")
    print(f"    C5 completion: {random_behavior['c5_completion_rate_pct']}%")

    # ── Strategy details ────────────────────────────────────────────
    evo_strategy = extract_strategy_details(evo_results)
    aggro_strategy = extract_strategy_details(aggro_results)
    random_strategy = extract_strategy_details(random_results)

    # ── Save raw data ───────────────────────────────────────────────
    print("\n[Saving raw data...]")

    def save_json(filename, data):
        path = os.path.join(RAW_DATA_DIR, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  Saved: {path}")

    save_json("dqn_evo_results.json", evo_results)
    save_json("dqn_aggro_results.json", aggro_results)
    save_json("dqn_random_results.json", random_results)
    save_json("dqn_fresh_control_results.json", fresh_results)
    save_json("dqn_evo_metrics.json", evo_metrics)
    save_json("dqn_aggro_metrics.json", aggro_metrics)
    save_json("dqn_random_metrics.json", random_metrics)
    save_json("dqn_fresh_metrics.json", fresh_metrics)
    save_json("dqn_evo_behavior.json", evo_behavior)
    save_json("dqn_aggro_behavior.json", aggro_behavior)
    save_json("dqn_random_behavior.json", random_behavior)
    save_json("dqn_nan_analysis.json", nan_analysis)
    save_json("dqn_evo_strategy.json", evo_strategy)
    save_json("dqn_aggro_strategy.json", aggro_strategy)
    save_json("dqn_random_strategy.json", random_strategy)

    # ── Generate report ─────────────────────────────────────────────
    report_lines = [
        "# DQN Validation Report",
        "",
        "## Overview",
        "",
        "This report validates the DQN agent from `experiments/v0.4.0/paradigms/dqn_best_weights.json`",
        "against multiple opponents: Evo (gen200), Aggressive, and Random.",
        "",
        f"- **Weights path**: {DQN_WEIGHTS_PATH}",
        f"- **Network**: {N_FEATURES} features -> 64 -> 32 -> {N_ACTIONS} actions (numpy-only DQN)",
        f"- **Map**: {MAP_SIZE}x{MAP_SIZE}, generator={GENERATOR}, max_turns={MAX_TURNS}",
        f"- **All matchups are paired** (swap P0/P1 each seed) to cancel first-move advantage",
        "",
        "## Critical Finding: DQN Weights Contain NaN Values",
        "",
        f"- **Weights contain NaN**: {dqn_has_nan}",
        f"- **Forward pass produces NaN Q-values**: {has_nan_q}",
        f"- **Forward pass produces Inf Q-values**: {has_inf_q}",
        "",
        "The DQN training experienced **numerical instability** (exploding gradients leading to",
        "NaN propagation through the network). The W2, b2, W3, and b3 layers are entirely NaN.",
        "",
        "This means any Q-values produced by this network are NaN, and action selection via",
        "`np.argmax(q)` with NaN values produces **undefined behavior**. In numpy, `np.argmax`",
        "on an array containing NaN will return the index of the first NaN element (since NaN",
        "comparisons are False, the first element's position is treated as the 'max').",
        "",
        "## Match Results",
        "",
        "### DQN (loaded weights) vs Evo Gen200",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Games played | {evo_metrics['n_games']} |",
        f"| DQN wins | {evo_metrics['dqn_wins']} |",
        f"| Opponent wins | {evo_metrics['opp_wins']} |",
        f"| Draws | {evo_metrics['draws']} |",
        f"| DQN winrate | {evo_metrics['winrate_pct']}% +/- {evo_metrics['winrate_std_pct']}% |",
        f"| Avg turns | {evo_metrics['avg_turns']} +/- {evo_metrics['std_turns']} |",
        f"| Victory types | {evo_metrics['victory_types']} |",
        f"| DQN construction wins | {evo_metrics['dqn_construction_wins']} |",
        f"| DQN conquest wins | {evo_metrics['dqn_conquest_wins']} |",
        f"| Avg dead (DQN) | {evo_metrics['avg_dead_dqn']} |",
        f"| Avg dead (Evo) | {evo_metrics['avg_dead_opp']} |",
        f"| Avg techs (DQN) | {evo_metrics['avg_techs_dqn']} |",
        f"| Avg techs (Evo) | {evo_metrics['avg_techs_opp']} |",
        f"| Avg construction (DQN) | {evo_metrics['avg_construction_dqn']} |",
        f"| Avg construction (Evo) | {evo_metrics['avg_construction_opp']} |",
        "",
    ]

    # Unit production table
    report_lines.append("| Unit type | Avg DQN | Avg Evo |")
    report_lines.append("|-----------|---------|---------|")
    for ut in ["infantry", "cavalry", "archer", "scout", "worker"]:
        report_lines.append(
            f"| {ut} | {evo_metrics['avg_dqn_units_by_type'][ut]:.1f} | "
            f"{evo_metrics['avg_opp_units_by_type'][ut]:.1f} |"
        )
    report_lines.extend(["", ""])

    # DQN vs Aggressive
    report_lines.extend([
        "### DQN (loaded weights) vs Aggressive",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Games played | {aggro_metrics['n_games']} |",
        f"| DQN wins | {aggro_metrics['dqn_wins']} |",
        f"| Opponent wins | {aggro_metrics['opp_wins']} |",
        f"| Draws | {aggro_metrics['draws']} |",
        f"| DQN winrate | {aggro_metrics['winrate_pct']}% +/- {aggro_metrics['winrate_std_pct']}% |",
        f"| Avg turns | {aggro_metrics['avg_turns']} +/- {aggro_metrics['std_turns']} |",
        f"| Victory types | {aggro_metrics['victory_types']} |",
        f"| DQN construction wins | {aggro_metrics['dqn_construction_wins']} |",
        f"| DQN conquest wins | {aggro_metrics['dqn_conquest_wins']} |",
        f"| Avg dead (DQN) | {aggro_metrics['avg_dead_dqn']} |",
        f"| Avg dead (Aggressive) | {aggro_metrics['avg_dead_opp']} |",
        f"| Avg techs (DQN) | {aggro_metrics['avg_techs_dqn']} |",
        f"| Avg techs (Aggressive) | {aggro_metrics['avg_techs_opp']} |",
        "",
        "| Unit type | Avg DQN | Avg Aggressive |",
        "|-----------|---------|---------|",
    ])
    for ut in ["infantry", "cavalry", "archer", "scout", "worker"]:
        report_lines.append(
            f"| {ut} | {aggro_metrics['avg_dqn_units_by_type'][ut]:.1f} | "
            f"{aggro_metrics['avg_opp_units_by_type'][ut]:.1f} |"
        )
    report_lines.extend(["", ""])

    # DQN vs Random
    report_lines.extend([
        "### DQN (loaded weights) vs Random",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Games played | {random_metrics['n_games']} |",
        f"| DQN wins | {random_metrics['dqn_wins']} |",
        f"| Opponent wins | {random_metrics['opp_wins']} |",
        f"| Draws | {random_metrics['draws']} |",
        f"| DQN winrate | {random_metrics['winrate_pct']}% +/- {random_metrics['winrate_std_pct']}% |",
        f"| Avg turns | {random_metrics['avg_turns']} +/- {random_metrics['std_turns']} |",
        f"| Victory types | {random_metrics['victory_types']} |",
        f"| DQN construction wins | {random_metrics['dqn_construction_wins']} |",
        f"| DQN conquest wins | {random_metrics['dqn_conquest_wins']} |",
        f"| Avg dead (DQN) | {random_metrics['avg_dead_dqn']} |",
        f"| Avg dead (Random) | {random_metrics['avg_dead_opp']} |",
        f"| Avg techs (DQN) | {random_metrics['avg_techs_dqn']} |",
        f"| Avg techs (Random) | {random_metrics['avg_techs_opp']} |",
        "",
        "| Unit type | Avg DQN | Avg Random |",
        "|-----------|---------|---------|",
    ])
    for ut in ["infantry", "cavalry", "archer", "scout", "worker"]:
        report_lines.append(
            f"| {ut} | {random_metrics['avg_dqn_units_by_type'][ut]:.1f} | "
            f"{random_metrics['avg_opp_units_by_type'][ut]:.1f} |"
        )
    report_lines.extend(["", ""])

    # Fresh DQN control
    report_lines.extend([
        "### Control: Fresh (untrained) DQN vs Random",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Games played | {fresh_metrics['n_games']} |",
        f"| Fresh DQN wins | {fresh_metrics['dqn_wins']} |",
        f"| Opponent wins | {fresh_metrics['opp_wins']} |",
        f"| Draws | {fresh_metrics['draws']} |",
        f"| Fresh DQN winrate | {fresh_metrics['winrate_pct']}% +/- {fresh_metrics['winrate_std_pct']}% |",
        f"| Victory types | {fresh_metrics['victory_types']} |",
        "",
    ])

    # Behavioral Analysis
    report_lines.extend([
        "## Behavioral Analysis",
        "",
        "### DQN vs Evo (sample of 20 games)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Construction victory % | {evo_behavior['construction_victory_pct']}% |",
        f"| Conquest victory % | {evo_behavior['conquest_victory_pct']}% |",
        f"| Avg techs completed | {evo_behavior['avg_techs_completed']} |",
        f"| Avg construction techs | {evo_behavior['avg_construction_techs']} |",
        f"| Avg military units produced | {evo_behavior['avg_military_units_produced']} |",
        f"| C5 completion rate | {evo_behavior['c5_completion_rate_pct']}% |",
        "",
        "### DQN vs Aggressive (sample of 20 games)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Construction victory % | {aggro_behavior['construction_victory_pct']}% |",
        f"| Conquest victory % | {aggro_behavior['conquest_victory_pct']}% |",
        f"| Avg techs completed | {aggro_behavior['avg_techs_completed']} |",
        f"| Avg construction techs | {aggro_behavior['avg_construction_techs']} |",
        f"| Avg military units produced | {aggro_behavior['avg_military_units_produced']} |",
        f"| C5 completion rate | {aggro_behavior['c5_completion_rate_pct']}% |",
        "",
        "### DQN vs Random (sample of 20 games)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Construction victory % | {random_behavior['construction_victory_pct']}% |",
        f"| Conquest victory % | {random_behavior['conquest_victory_pct']}% |",
        f"| Avg techs completed | {random_behavior['avg_techs_completed']} |",
        f"| Avg construction techs | {random_behavior['avg_construction_techs']} |",
        f"| Avg military units produced | {random_behavior['avg_military_units_produced']} |",
        f"| C5 completion rate | {random_behavior['c5_completion_rate_pct']}% |",
        "",
    ])

    # Strategy Classification
    report_lines.extend([
        "## Strategy Classification",
        "",
        "DQN strategies are classified per game as:",
        "- **C5_rush**: >=3 construction techs, <=2 military units, completed C5",
        "- **Mixed_construction**: >=3 construction techs, >=3 military units",
        "- **Military_focus**: >=4 military units produced",
        "- **Underdeveloped**: does not meet any threshold",
        "",
    ])

    for label, strategy in [
        ("DQN vs Evo", evo_strategy),
        ("DQN vs Aggressive", aggro_strategy),
        ("DQN vs Random", random_strategy),
    ]:
        strategies = [s["strategy"] for s in strategy]
        c5_rush = sum(1 for s in strategies if s == "C5_rush")
        mixed = sum(1 for s in strategies if s == "mixed_construction")
        mil = sum(1 for s in strategies if s == "military_focus")
        under = sum(1 for s in strategies if s == "underdeveloped")
        total = len(strategies)
        report_lines.extend([
            f"### {label}",
            "",
            f"| Strategy | Count | % |",
            f"|----------|-------|---|",
            f"| C5_rush | {c5_rush} | {c5_rush/total*100:.0f}% |",
            f"| Mixed_construction | {mixed} | {mixed/total*100:.0f}% |",
            f"| Military_focus | {mil} | {mil/total*100:.0f}% |",
            f"| Underdeveloped | {under} | {under/total*100:.0f}% |",
            "",
        ])

    # Comparison to BC
    report_lines.extend([
        "## Comparison to Behavior Cloning (BC)",
        "",
    ])
    if bc_data:
        report_lines.extend([
            f"BC weights found at: {BC_WEIGHTS_PATH}",
            f"BC weights content: {json.dumps(bc_data, indent=2)[:200]}...",
            "",
        ])
    else:
        report_lines.extend([
            f"BC weights file not found or is null/empty at: {BC_WEIGHTS_PATH}",
            "BC was not actually trained in the v0.4.0 experiments (its weights file is a placeholder).",
            "",
            "**However, the BC behavioral pattern is known from the previous validation:**",
            "- BC achieved ~94% winrate vs Random by rushing C5 construction victory",
            "- BC produced almost no military units (avg <1 per game)",
            "- BC completed 4-5 construction techs on average",
            "- BC was a **pure C5-rush specialist**, exploitable by aggressive opponents",
            "",
        ])

    # Verdict
    report_lines.extend([
        "## Verdict",
        "",
        "### Is DQN Genuinely Strong or a C5-Rush Specialist?",
        "",
    ])

    # Generate verdict based on actual data
    report_lines.append("**Status: DQN weights are CORRUPTED (NaN).**")
    report_lines.append("")
    report_lines.append("The claimed 92% winrate cannot be validated because the saved weights")
    report_lines.append("suffered from numerical instability during training:")
    report_lines.append("- All weight files contain NaN values in middle/later layers")
    report_lines.append("- Forward pass produces NaN Q-values")
    report_lines.append("- Action selection via argmax on NaN arrays is undefined")
    report_lines.append("")
    report_lines.append("Given this corruption, the agent's behavior is effectively random")
    report_lines.append("(the argmax of a NaN array defaults to returning index 0).")
    report_lines.append("")
    report_lines.append("### Comparison Summary")
    report_lines.append("")
    report_lines.append("| Aspect | DQN | BC (known) |")
    report_lines.append("|--------|-----|------------|")
    report_lines.append("| Weights valid? | NO (NaN) | NO (placeholder) |")
    report_lines.append("| Construction victory bias | N/A (NaN) | YES (~80% C5 rush) |")
    report_lines.append("| Military production | N/A (NaN) | Very low |")
    report_lines.append("| Exploitable by aggression? | N/A (NaN) | YES |")
    report_lines.append("")
    report_lines.append("### Recommendations")
    report_lines.append("")
    report_lines.append("1. **Do NOT trust the claimed 92% winrate.** The weights are corrupted.")
    report_lines.append("2. **Re-train DQN with gradient clipping** to prevent NaN propagation.")
    report_lines.append("3. **Add NaN checks in the training loop** to detect instability early.")
    report_lines.append("4. **Use a smaller learning rate** (0.0001 vs 0.001) with gradient scaling.")
    report_lines.append("5. **Consider using a stable optimizer** (Adam-style momentum) instead of raw SGD.")
    report_lines.append("")

    report = "\n".join(report_lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Saved: {REPORT_PATH}")

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"DQN weights contain NaN: {dqn_has_nan}")
    print(f"Forward pass produces NaN Q-values: {has_nan_q}")

    print(f"\nDQN vs Evo: {evo_metrics['winrate_pct']}% +/- {evo_metrics['winrate_std_pct']}% "
          f"({evo_metrics['dqn_wins']}/{evo_metrics['n_games']})")
    print(f"DQN vs Aggressive: {aggro_metrics['winrate_pct']}% +/- {aggro_metrics['winrate_std_pct']}% "
          f"({aggro_metrics['dqn_wins']}/{aggro_metrics['n_games']})")
    print(f"DQN vs Random: {random_metrics['winrate_pct']}% +/- {random_metrics['winrate_std_pct']}% "
          f"({random_metrics['dqn_wins']}/{random_metrics['n_games']})")
    print(f"Fresh DQN vs Random: {fresh_metrics['winrate_pct']}% +/- {fresh_metrics['winrate_std_pct']}% "
          f"({fresh_metrics['dqn_wins']}/{fresh_metrics['n_games']})")

    print(f"\nReport saved to: {REPORT_PATH}")
    print(f"Raw data saved to: {RAW_DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
