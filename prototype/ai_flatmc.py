# prototype/ai_flatmc.py — FlatMC v3: 精确对手建模
# 核心思路：
# 1. rolloute中己方用Greedy AI（近似Future FlatMC行为）
# 2. 对手用实际Random AI(ai_rulesrandom)，使推演对手行为匹配真实对局
# 3. 评分聚焦城市HP差和防守
import random as _random, copy as _copy
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
from prototype.economy import worker_action_build, worker_action_produce, produce_unit
from prototype.constants import TECH_TREE as _TECH_TREE, UNIT_COST, CITY_DAMAGE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}

from prototype.ai_greedy import ai_decide as _greedy_decide
from prototype.ai_rulesrandom import ai_decide as _random_decide
from prototype.game import step_game


class FlatMCAgent:
    """FlatMC Agent with exact opponent modeling.

    对每个合法动作运行多次rollout:
    -己方(Greedy AI) vs 对手(Random AI)
    -评分器聚焦城市HP差和防守
    -depth=20覆盖完整对局长度
    """

    def __init__(self, simulations: int = 15, rollout_depth: int = 20):
        self.sims = simulations
        self.rollout_depth = rollout_depth

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
            legal.append((0, 0))

            best_act, best_score = (0, 0), -99999
            for mv in legal:
                total = 0.0
                sims_per = max(2, self.sims // len(legal))
                for _ in range(sims_per):
                    score = _rollout_mirror(gs, pid, ui, mv, rng,
                                            self.rollout_depth)
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
        if tech.researching is None:
            avail = tech.available_to_research()
            avail.sort(key=lambda t: -sum(TECH_TREE_COST.get(t, (0, 0, 0))))
            for t in avail:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

        return actions


def _rollout_mirror(gs, pid, unit_idx, first_move, rng, depth):
    """
    Mirror rollout: 己方用Greedy AI，对手用实际Random AI。
    推演结果用于评估first_move的质量。
    """
    sim = _copy.deepcopy(gs)
    opp = 1 - pid

    rollout_rng = _random.Random(rng.randint(0, 999999))

    # 应用第一步 = 强制指定单位按给定方向移动
    u = None
    for i, uu in enumerate(sim.units):
        if i == unit_idx and uu.player_id == pid:
            u = uu
            break
    if u and u.alive and first_move != (0, 0):
        nx = (u.x + first_move[0]) % sim.size
        ny = (u.y + first_move[1]) % sim.size
        blocker = next((eu for eu in sim.units
                        if eu.alive and eu.player_id != pid
                        and eu.x == nx and eu.y == ny), None)
        if blocker:
            t_att = get_terrain(sim.grid, u.x, u.y)
            t_def = get_terrain(sim.grid, blocker.x, blocker.y)
            result = resolve_melee(u, blocker, t_att, t_def)
            if u.alive and not blocker.alive:
                u.x, u.y = nx, ny
                opp_city = sim.cities[opp]
                if nx == opp_city.x and ny == opp_city.y:
                    dmg = max(1, u.atk - opp_city.def_)
                    opp_city.hp -= dmg
                    if opp_city.hp <= 0:
                        opp_city.hp = 0
                        sim.winner = pid
                        sim.victory_type = "conquest"
        else:
            u.x, u.y = nx, ny
            opp_city = sim.cities[opp]
            if nx == opp_city.x and ny == opp_city.y:
                dmg = max(1, u.atk - opp_city.def_)
                opp_city.hp -= dmg
                if opp_city.hp <= 0:
                    opp_city.hp = 0
                    sim.winner = pid
                    sim.victory_type = "conquest"

    # Rollout循环: 己方Greedy AI, 对手Random AI
    sim_turns = min(sim.turn + depth, 100)
    while sim.turn < sim_turns and sim.winner is None:
        if pid == 0:
            p0_actions = _greedy_decide(sim, 0, rollout_rng)
            p1_actions = _random_decide(sim, 1, rollout_rng)
        else:
            p0_actions = _random_decide(sim, 0, rollout_rng)
            p1_actions = _greedy_decide(sim, 1, rollout_rng)
        step_game(sim, p0_actions, p1_actions)

    # === 评分 ===
    if sim.winner == pid:
        return 500.0
    elif sim.winner == opp:
        return -500.0

    # 未分胜负时的评分（重点防守）
    my_city_hp = sim.cities[pid].hp
    opp_city_hp = sim.cities[opp].hp

    # 城市HP差: 对我方城市HP的保留给予高分，对敌方城市HP减少也给予高分
    score = 0.0
    score -= (100 - my_city_hp) * 12.0  # 己方城市每掉1HP = -12
    score += (100 - opp_city_hp) * 8.0  # 敌方城市每掉1HP = +8

    # 单位优势
    my_alive = sum(1 for uu in sim.units if uu.player_id == pid and uu.alive)
    opp_alive = sum(1 for uu in sim.units if uu.player_id == opp and uu.alive)
    score += (my_alive - opp_alive) * 10.0

    # 城郊防御: 接近己方城市的敌方单位给负分
    def td(a, b, s): return min(abs(b - a), s - abs(b - a))
    for uu in sim.units:
        if uu.alive and uu.player_id == opp:
            d = td(uu.x, my_city_hp if False else sim.cities[pid].x, sim.size) + \
                td(uu.y, sim.cities[pid].y, sim.size)
            if d <= 2:
                score -= 15.0  # 敌人靠近城市 = 负分

    return score


_agent_cache = {}

def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    sims = 15
    key = f"mc{sims}"
    if key not in _agent_cache:
        _agent_cache[key] = FlatMCAgent(simulations=sims, rollout_depth=20)
    return _agent_cache[key].decide(gs, pid, rng)
