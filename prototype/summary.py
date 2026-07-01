# prototype/summary.py — 单局统计摘要

def summarize_game(gs, ai0_name: str = "P0_AI", ai1_name: str = "P1_AI") -> dict:
    """从终局 GameState 提取统计摘要"""
    seed = gs.seed
    turn = gs.turn
    winner = gs.winner
    vtype = gs.victory_type

    # 单位统计
    p0_units_total = sum(1 for u in gs.units + gs.dead_units if u.player_id == 0)
    p1_units_total = sum(1 for u in gs.units + gs.dead_units if u.player_id == 1)
    p0_killed = sum(1 for u in gs.dead_units if u.player_id == 0)
    p1_killed = sum(1 for u in gs.dead_units if u.player_id == 1)
    p0_workers = sum(1 for u in gs.units if u.player_id == 0 and u.alive and u.unit_type == "worker")
    p1_workers = sum(1 for u in gs.units if u.player_id == 1 and u.alive and u.unit_type == "worker")

    # 科技
    p0_techs = len(gs.techs[0].completed)
    p1_techs = len(gs.techs[1].completed)
    p0_construction = gs.techs[0].construction_count()
    p1_construction = gs.techs[1].construction_count()

    # 经济
    e0, e1 = gs.economies[0], gs.economies[1]

    # 战斗
    total_combats = sum(1 for act in gs.action_log
                        for a in act.get("p0", []) + act.get("p1", [])
                        if a.get("type") in ("move",))  # rough estimate
    first_contact = None
    for act in gs.action_log:
        for a in act.get("p0", []) + act.get("p1", []):
            if a.get("type") == "move" and a.get("dx", 0) != 0 or a.get("dy", 0) != 0:
                # rough: first turn any unit moved is "exploration started"
                if first_contact is None:
                    first_contact = act.get("turn", 0)
                break

    return {
        "matchup": {"ai0": ai0_name, "ai1": ai1_name},
        "seed": seed,
        "size": gs.size,
        "generator": gs.generator_id,
        "winner": winner,
        "victory_type": vtype,
        "turns": turn,
        "p0": {
            "techs_completed": p0_techs,
            "construction": p0_construction,
            "units_total": p0_units_total,
            "units_killed": p0_killed,
            "workers_alive": p0_workers,
            "resources": {"food": e0.food, "wood": e0.wood, "gold": e0.gold},
        },
        "p1": {
            "techs_completed": p1_techs,
            "construction": p1_construction,
            "units_total": p1_units_total,
            "units_killed": p1_killed,
            "workers_alive": p1_workers,
            "resources": {"food": e1.food, "wood": e1.wood, "gold": e1.gold},
        },
        "first_contact_approx": first_contact,
    }
