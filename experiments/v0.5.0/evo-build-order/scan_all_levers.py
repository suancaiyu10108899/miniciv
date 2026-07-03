"""
Test all balance levers: asymmetric costs, research turns, construction requirement.
Each config: 50 paired games vs Greedy, quick directional scan.
"""
import json, sys, random, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

GAMES = 50
BASE_SEED = 777

# ── Configs to test ──
CONFIGS = [
    # Baseline
    {"name": "baseline", "c5_cost": (3,3,3), "c5_turns": 2, "require_construction": 0},
    # Asymmetric +1
    {"name": "C5_food+1", "c5_cost": (4,3,3), "c5_turns": 2, "require_construction": 0},
    {"name": "C5_wood+1", "c5_cost": (3,4,3), "c5_turns": 2, "require_construction": 0},
    {"name": "C5_gold+1", "c5_cost": (3,3,4), "c5_turns": 2, "require_construction": 0},
    # Asymmetric +2
    {"name": "C5_food+2", "c5_cost": (5,3,3), "c5_turns": 2, "require_construction": 0},
    {"name": "C5_gold+2", "c5_cost": (3,3,5), "c5_turns": 2, "require_construction": 0},
    # Turns
    {"name": "C5_turns=4", "c5_cost": (3,3,3), "c5_turns": 4, "require_construction": 0},
    {"name": "C5_turns=6", "c5_cost": (3,3,3), "c5_turns": 6, "require_construction": 0},
    # Construction requirement
    {"name": "need_C1-C3", "c5_cost": (3,3,3), "c5_turns": 2, "require_construction": 3},
    # Combined
    {"name": "C5(4,3,3)+turns4", "c5_cost": (4,3,3), "c5_turns": 4, "require_construction": 0},
    {"name": "C5(3,3,4)+turns4+needC3", "c5_cost": (3,3,4), "c5_turns": 4, "require_construction": 3},
]

# ── Import and patch ──
import prototype.constants as c

def apply_config(cfg):
    """Apply config to constants module, then clear cached imports."""
    c.TECH_TREE["C5"] = {
        "cost": cfg["c5_cost"],
        "turns": cfg["c5_turns"],
        "requires": ["C3","C4"],
        "effect": "construction_victory",
    }
    # Also store construction requirement in module for game.py to check
    c.C5_REQUIRE_CONSTRUCTION = cfg["require_construction"]
    for mod in list(sys.modules):
        if 'prototype' in mod and mod != 'prototype.constants':
            del sys.modules[mod]

# Add construction check to game loop (monkey-patch)
def _patch_game_loop():
    """If C5_REQUIRE_CONSTRUCTION > 0, add facility check to victory condition."""
    import prototype.game as g
    orig_step = g.step_game
    def patched_step(gs, a0, a1):
        result = orig_step(gs, a0, a1)
        if result and result.get("victory_type") == "construction":
            winner = result["winner"]
            req = getattr(c, 'C5_REQUIRE_CONSTRUCTION', 0)
            if req > 0 and gs.techs[winner].construction_count() < req:
                # Undo victory — C5 researched but not enough facilities
                gs.winner = None
                gs.victory_type = None
                return {"turn": gs.turn, "winner": None, "victory_type": None}
        return result
    g.step_game = patched_step

all_results = []

for cfg in CONFIGS:
    apply_config(cfg)

    # Clear and reimport
    for mod in list(sys.modules):
        if 'prototype' in mod and mod != 'prototype.constants':
            del sys.modules[mod]
    import prototype.game as game
    import prototype.eval as ev
    if cfg["require_construction"] > 0:
        _patch_game_loop()

    evo = ev.load_ai("evo")
    greedy = ev.load_ai("greedy")
    evo_wins, const_wins, total = 0, 0, 0

    for i in range(GAMES):
        seed = BASE_SEED + i * 1000 + hash(cfg["name"]) % 100000
        for evo_p0 in [True, False]:
            gs_seed = seed if evo_p0 else seed + 1000000
            gs = game.init_game(seed=gs_seed, size=15, generator_id="balanced")
            r0, r1 = random.Random(gs_seed), random.Random(gs_seed + 1)
            if evo_p0:
                while gs.winner is None and gs.turn < 100:
                    game.step_game(gs, evo(gs, 0, r0), greedy(gs, 1, r1))
            else:
                while gs.winner is None and gs.turn < 100:
                    game.step_game(gs, greedy(gs, 0, r0), evo(gs, 1, r1))
            evo_won = (evo_p0 and gs.winner == 0) or (not evo_p0 and gs.winner == 1)
            total += 1
            if evo_won:
                evo_wins += 1
                if gs.victory_type == "construction":
                    const_wins += 1

    wr = evo_wins / total * 100
    cwr = const_wins / total * 100
    print(f"{cfg['name']:<25} wr={wr:>5.1f}% const={cwr:>5.1f}%")
    all_results.append({**cfg, "evo_winrate": round(wr,1), "construction_winrate": round(cwr,1)})

# Save
OUTDIR = Path(__file__).resolve().parent
with open(OUTDIR / "all_levers_scan.json", "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\nSaved to {OUTDIR / 'all_levers_scan.json'}")
