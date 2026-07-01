# prototype/ai_flatmc.py — Flat Monte Carlo AI
# 对每个合法动作做N次随机rollout，选平均分最高的

import random as _random, copy as _copy
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
from prototype.economy import worker_action_build, worker_action_produce, produce_unit
from prototype.constants import TECH_TREE as _TECH_TREE, UNIT_COST, CITY_BASE_FOOD
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}


class FlatMCAgent:
    def __init__(self, simulations: int = 25):
        self.sims = simulations

    def decide(self, gs, pid: int, rng=None) -> list[dict]:
        if rng is None:
            rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
        units = [u for u in gs.units if u.player_id == pid and u.alive]
        actions = []

        for ui, u in enumerate(units):
            legal = get_single_step_moves(u, gs.grid)
            if not legal:
                actions.append({"unit_idx": ui, "type": "end_turn"})
                continue
            legal.append((0, 0))  # stay

            best_act, best_score = (0, 0), -999
            for mv in legal:
                total = 0.0
                sims_per = max(1, self.sims // len(legal))
                for _ in range(sims_per):
                    score = _rollout(gs, pid, ui, mv, rng)
                    total += score
                avg = total / sims_per
                if avg > best_score:
                    best_score = avg
                    best_act = mv

            actions.append({"unit_idx": ui, "type": "move",
                           "dx": best_act[0], "dy": best_act[1]})

        # 生产+研究
        econ = gs.economies[pid]
        tech = gs.techs[pid]
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break
        if tech.researching is None:
            avail = tech.available_to_research()
            for t in ["M1", "E1", "C1"]:
                if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break

        return actions


def _rollout(gs, pid, unit_idx, first_move, rng):
    """模拟：应用first_move后，双方随机移动直到终局。返回pid的分数。"""
    sim = _copy.deepcopy(gs)
    sim.rng = _random.Random(rng.randint(0, 999999))
    opp = 1 - pid

    # 应用第一步
    u = sim.units[unit_idx] if unit_idx < len(sim.units) else None
    if u and u.alive and first_move != (0, 0):
        nx, ny = (u.x + first_move[0]) % sim.size, (u.y + first_move[1]) % sim.size
        blocker = next((eu for eu in sim.units
                        if eu.alive and eu.player_id != pid
                        and eu.x == nx and eu.y == ny), None)
        if blocker:
            t_att = get_terrain(sim.grid, u.x, u.y)
            t_def = get_terrain(sim.grid, blocker.x, blocker.y)
            resolve_melee(u, blocker, t_att, t_def)
            if u.alive and not blocker.alive:
                u.x, u.y = nx, ny
        else:
            u.x, u.y = nx, ny

    # 随机rollout
    max_t = min(gs.turn + 30, 100)
    while sim.turn < max_t and sim.winner is None:
        sim.turn += 1
        for p in (0, 1):
            for uu in [u for u in sim.units if u.player_id == p and u.alive]:
                legal = get_single_step_moves(uu, sim.grid)
                if not legal:
                    continue
                mv = sim.rng.choice(legal + [(0, 0)])
                if mv == (0, 0):
                    continue
                nx, ny = (uu.x + mv[0]) % sim.size, (uu.y + mv[1]) % sim.size
                blocker = next((eu for eu in sim.units
                                if eu.alive and eu.player_id != p
                                and eu.x == nx and eu.y == ny), None)
                if blocker:
                    t_att = get_terrain(sim.grid, uu.x, uu.y)
                    t_def = get_terrain(sim.grid, blocker.x, blocker.y)
                    resolve_melee(uu, blocker, t_att, t_def)
                    if uu.alive and not blocker.alive:
                        uu.x, uu.y = nx, ny
                        # 占城？
                        for c in sim.cities:
                            if c.player_id != p and c.x == nx and c.y == ny:
                                dmg = max(1, uu.atk - c.def_)
                                if dmg >= c.hp:
                                    c.hp = 0
                                    sim.winner = p
                                    sim.victory_type = "conquest"
                else:
                    uu.x, uu.y = nx, ny

        # 简单经济（只做基础产出）
        for p in (0, 1):
            sim.economies[p].food += CITY_BASE_FOOD

        # 清理死单位
        sim.units = [u for u in sim.units if u.alive]

    # 终局分数：pid分差
    score_diff = sim.economies[pid].food + sim.economies[pid].wood + sim.economies[pid].gold
    opp_diff = sim.economies[opp].food + sim.economies[opp].wood + sim.economies[opp].gold
    if sim.winner == pid:
        return 1000
    elif sim.winner == opp:
        return -1000
    return (score_diff - opp_diff) / 10.0


# 统一接口
_agent_cache = {}


def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    sims = 25
    key = sims
    if key not in _agent_cache:
        _agent_cache[key] = FlatMCAgent(sims)
    return _agent_cache[key].decide(gs, pid, rng)
