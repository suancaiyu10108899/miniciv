#!/usr/bin/env python
"""Facility threshold scan — find sweet spot where construction victory is achievable but not dominant.
Tests facility ∈ {3,4,5,6} with Greedy mirror and Evo vs Greedy.
"""
import json, os, sys, time, random, importlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import prototype.constants as c
from prototype.game import init_game, step_game
from prototype.eval import load_ai

SIZE = 15
MAX_TURNS = 100
SEEDS = 100  # paired seeds per test
OUTPUT_DIR = Path(__file__).parent


def run_paired_test(ai_a, ai_b, facility_req, n_seeds):
    """Run paired test with a specific facility requirement.
    Patches constants.py temporarily.
    """
    orig = c.CONSTRUCTION_VICTORY_REQUIRE_FACILITIES
    c.CONSTRUCTION_VICTORY_REQUIRE_FACILITIES = facility_req

    ai0_fn = load_ai(ai_a)
    ai1_fn = load_ai(ai_b)
    results = []

    for seed in range(n_seeds):
        # Forward: ai_a = P0
        gs = init_game(seed=seed, size=SIZE)
        rng0 = random.Random(seed)
        rng1 = random.Random(seed + 1)
        while gs.winner is None and gs.turn < MAX_TURNS:
            step_game(gs, ai0_fn(gs, 0, rng0), ai1_fn(gs, 1, rng1))
        results.append(_extract(gs, seed, ai_a, ai_b, "forward"))

        # Backward: ai_b = P0
        gs = init_game(seed=seed, size=SIZE)
        rng0 = random.Random(seed + 1)
        rng1 = random.Random(seed)
        while gs.winner is None and gs.turn < MAX_TURNS:
            step_game(gs, ai1_fn(gs, 0, rng0), ai0_fn(gs, 1, rng1))
        results.append(_extract(gs, seed, ai_b, ai_a, "backward"))

    c.CONSTRUCTION_VICTORY_REQUIRE_FACILITIES = orig
    return results


def _extract(gs, seed, ai0_name, ai1_name, tag):
    from prototype.mapgen import get_facility
    fc = {0: 0, 1: 0}
    for y in range(gs.size):
        for x in range(gs.size):
            f = get_facility(gs.grid, x, y)
            if f is not None:
                fc[f.player_id] += 1

    def _cu(units, pid, ut, alive=True):
        if alive:
            return sum(1 for u in units if u.player_id == pid and u.alive and u.unit_type == ut)
        return sum(1 for u in units if u.player_id == pid and u.unit_type == ut)

    utypes = ["infantry", "cavalry", "archer", "scout", "worker"]
    r = {
        "seed": seed, "winner": gs.winner, "victory_type": gs.victory_type,
        "turns": gs.turn,
        "p0_construction": gs.techs[0].construction_count(),
        "p1_construction": gs.techs[1].construction_count(),
        "p0_facilities": fc[0], "p1_facilities": fc[1],
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "_ai0": ai0_name, "_ai1": ai1_name, "_tag": tag,
    }
    for ut in utypes:
        r[f"p0_{ut}_alive"] = _cu(gs.units, 0, ut, True)
        r[f"p1_{ut}_alive"] = _cu(gs.units, 1, ut, True)
        r[f"p0_{ut}_dead"] = _cu(gs.dead_units, 0, ut, False)
        r[f"p1_{ut}_dead"] = _cu(gs.dead_units, 1, ut, False)
    return r


def summarize(ai_a, ai_b, results):
    """Paired summary."""
    fwd = [r for r in results if r["_tag"] == "forward"]
    bwd = [r for r in results if r["_tag"] == "backward"]
    n = len(results)

    a_wins = sum(1 for r in fwd if r["winner"] == 0) + sum(1 for r in bwd if r["winner"] == 1)
    b_wins = sum(1 for r in fwd if r["winner"] == 1) + sum(1 for r in bwd if r["winner"] == 0)
    p0_wins = sum(1 for r in results if r["winner"] == 0)

    vtypes = [r.get("victory_type") or "" for r in results]
    cq = sum(1 for v in vtypes if v == "conquest")
    cs = sum(1 for v in vtypes if v == "construction")
    tie = sum(1 for v in vtypes if v and v.startswith("tiebreak"))

    utypes = ["infantry", "cavalry", "archer", "scout", "worker"]
    a_ut = {}
    b_ut = {}
    for ut in utypes:
        a_alive = sum(r.get(f"p0_{ut}_alive",0) if r["_tag"]=="forward" else r.get(f"p1_{ut}_alive",0) for r in results)
        a_dead = sum(r.get(f"p0_{ut}_dead",0) if r["_tag"]=="forward" else r.get(f"p1_{ut}_dead",0) for r in results)
        b_alive = sum(r.get(f"p1_{ut}_alive",0) if r["_tag"]=="forward" else r.get(f"p0_{ut}_alive",0) for r in results)
        b_dead = sum(r.get(f"p1_{ut}_dead",0) if r["_tag"]=="forward" else r.get(f"p0_{ut}_dead",0) for r in results)
        a_ut[ut] = (a_alive/n, a_dead/n)
        b_ut[ut] = (b_alive/n, b_dead/n)

    a_facs = sum(r.get("p0_facilities",0) if r["_tag"]=="forward" else r.get("p1_facilities",0) for r in results) / n
    b_facs = sum(r.get("p1_facilities",0) if r["_tag"]=="forward" else r.get("p0_facilities",0) for r in results) / n

    return {
        "ai_a": ai_a, "ai_b": ai_b, "n": n,
        "ai_a_wr": round(a_wins/n, 4), "ai_b_wr": round(b_wins/n, 4),
        "p0_wr": round(p0_wins/n, 4),
        "conquest": round(cq/n, 4), "construction": round(cs/n, 4), "tiebreak": round(tie/n, 4),
        "avg_turns": round(sum(r["turns"] for r in results)/n, 1),
        "ai_a_facs": round(a_facs, 2), "ai_b_facs": round(b_facs, 2),
        "ai_a_units": {ut: {"alive": round(v[0],2), "dead": round(v[1],2)} for ut, v in a_ut.items()},
        "ai_b_units": {ut: {"alive": round(v[0],2), "dead": round(v[1],2)} for ut, v in b_ut.items()},
    }


def main():
    facilities = [3, 4, 5, 6]
    pairs = [("greedy", "greedy"), ("evo", "greedy")]
    all_results = {}

    print("=" * 70)
    print("Facility Threshold Scan")
    print(f"Testing facility in {facilities}, {SEEDS} paired seeds each")
    print(f"Pairs: {[f'{a} vs {b}' for a,b in pairs]}")
    print("=" * 70)

    total_start = time.time()
    configs_tested = 0

    for fac in facilities:
        for ai_a, ai_b in pairs:
            label = f"fac={fac} {ai_a} vs {ai_b}"
            t0 = time.time()
            results = run_paired_test(ai_a, ai_b, fac, SEEDS)
            s = summarize(ai_a, ai_b, results)
            elapsed = time.time() - t0

            # Save raw
            fname = f"fac{fac}_{ai_a}_vs_{ai_b}.json"
            with open(OUTPUT_DIR / fname, "w") as f:
                json.dump(results, f, indent=2)

            key = f"fac{fac}"
            if key not in all_results:
                all_results[key] = []
            all_results[key].append(s)

            print(f"\n  {label} ({elapsed:.0f}s):")
            print(f"    WR: {ai_a}={s['ai_a_wr']:.1%} {ai_b}={s['ai_b_wr']:.1%} P0={s['p0_wr']:.1%}")
            print(f"    Victory: Conq={s['conquest']:.1%} Const={s['construction']:.1%} Tie={s['tiebreak']:.1%} T={s['avg_turns']:.0f}")
            print(f"    Facilities: {ai_a}={s['ai_a_facs']} {ai_b}={s['ai_b_facs']}")
            print(f"    Units ({ai_a}): I={s['ai_a_units']['infantry']['alive']}/{s['ai_a_units']['infantry']['dead']} "
                  f"C={s['ai_a_units']['cavalry']['alive']}/{s['ai_a_units']['cavalry']['dead']} "
                  f"A={s['ai_a_units']['archer']['alive']}/{s['ai_a_units']['archer']['dead']}")
            configs_tested += 1

    # Save summary
    summary = {
        "experiment": "facility-scan",
        "date": "2026-07-04",
        "config": {"sizes": [15], "seeds_per_test": SEEDS, "paired": True},
        "results_by_facility": all_results,
    }
    with open(OUTPUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"SCAN COMPLETE: {configs_tested} configs in {total_elapsed:.0f}s")

    # Summary table
    print(f"\n{'Fac':>4} {'Pair':>22} {'A_WR':>7} {'B_WR':>7} {'Conq':>6} {'Const':>6} {'Tie':>6} {'T':>5} {'FacA':>5} {'FacB':>5}")
    print("-" * 85)
    for fac in facilities:
        key = f"fac{fac}"
        for s in all_results.get(key, []):
            print(f"{fac:>4} {s['ai_a']+' vs '+s['ai_b']:>22} {s['ai_a_wr']:>6.1%} {s['ai_b_wr']:>6.1%} "
                  f"{s['conquest']:>5.1%} {s['construction']:>5.1%} {s['tiebreak']:>5.1%} "
                  f"{s['avg_turns']:>5.0f} {s['ai_a_facs']:>5.1f} {s['ai_b_facs']:>5.1f}")

    # Analysis
    print(f"\nAnalysis:")
    for fac in facilities:
        key = f"fac{fac}"
        results = all_results.get(key, [])
        for s in results:
            if s['ai_a'] == 'greedy' and s['ai_b'] == 'greedy':
                cs_rate = s['construction']
                if cs_rate == 0:
                    status = "UNREACHABLE"
                elif cs_rate < 0.10:
                    status = "TOO RARE"
                elif cs_rate > 0.50:
                    status = "TOO DOMINANT"
                else:
                    status = "SWEET SPOT"
                print(f"  fac={fac}: construction={cs_rate:.1%} → {status}")
            if s['ai_a'] == 'evo' and s['ai_b'] == 'greedy':
                evo_wr = s['ai_a_wr']
                if evo_wr > 0.80:
                    status = "EVO DOMINANT"
                elif evo_wr > 0.65:
                    status = "EVO STRONG"
                else:
                    status = "BALANCED"
                print(f"  fac={fac}: Evo WR={evo_wr:.1%} → {status}")


if __name__ == "__main__":
    main()
