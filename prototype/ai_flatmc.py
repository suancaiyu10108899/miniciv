# prototype/ai_flatmc.py — FlatMC v4: 快速混合搜索
# 架构：对每个动作做少量(3-5次)rollout推演，用实际Random AI作为对手模型
# 关键优化：rollout用精简模拟(非step_game)降低单次时间，换取更多模拟次数
#
# 设计思路：
# - 对手用真实Random AI行为模型匹配
# - 滚动深度=25回合覆盖完整对局
# - 评分重点惩罚己方城市受损
# - 己方用Greedy AI近似Future Multi-Turn决策
import random as _random, copy as _copy
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
from prototype.economy import worker_action_build, worker_action_produce, produce_unit
from prototype.constants import TECH_TREE as _TECH_TREE, UNIT_COST, CITY_DAMAGE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}

from prototype.ai_greedy import ai_decide as _greedy_decide

# 不需要step_game – 用精简模拟


class FlatMCAgent:
    """FlatMC v4: 混合搜索 + 精确对手建模。

    每个动作 5 次精简rollout（无deepcopy损耗），
    己方Greedy AI vs 对手Random AI，
    深度25回合，评分侧重己方城市保护。
    """

    def __init__(self, simulations: int = 15, rollout_depth: int = 25):
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
                    score = _fast_rollout(gs, pid, ui, mv, rng,
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


def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def _fast_rollout(gs, pid, unit_idx, first_move, rng, depth=25):
    """
    精简rollout: deepcopy + Greedy(self) vs Random(opp) + step_game.
    不使用手写模拟以避免与真实游戏逻辑的偏差。
    """
    from prototype.game import step_game
    from prototype.ai_rulesrandom import ai_decide as _random_decide

    sim = _copy.deepcopy(gs)
    opp = 1 - pid

    rollout_rng = _random.Random(rng.randint(0, 999999))

    # 应用第一步
    u = None
    for i, uu in enumerate(sim.units):
        if i == unit_idx and uu.player_id == pid:
            u = uu
            break
    if u and u.alive and first_move != (0, 0):
        _apply_first_move(sim, u, first_move, pid, opp)

    # Rollout
    sim_turns = min(sim.turn + depth, 100)
    while sim.turn < sim_turns and sim.winner is None:
        if pid == 0:
            p0 = _greedy_decide(sim, 0, rollout_rng)
            p1 = _random_decide(sim, 1, rollout_rng)
        else:
            p0 = _random_decide(sim, 0, rollout_rng)
            p1 = _greedy_decide(sim, 1, rollout_rng)
        step_game(sim, p0, p1)

    # 评分
    if sim.winner == pid:
        return 600.0
    elif sim.winner == opp:
        return -600.0

    # 城市HP分
    my_hp_lost = 100 - sim.cities[pid].hp
    opp_hp_lost = 100 - sim.cities[opp].hp
    score = opp_hp_lost * 10.0 - my_hp_lost * 15.0

    # 存活单位
    my_alive = sum(1 for uu in sim.units if uu.player_id == pid and uu.alive)
    opp_alive = sum(1 for uu in sim.units if uu.player_id == opp and uu.alive)
    score += (my_alive - opp_alive) * 8.0

    # 单位接近己方城市 = 威胁，给负分
    mc = sim.cities[pid]
    for uu in sim.units:
        if uu.alive and uu.player_id == opp:
            d = _td(uu.x, mc.x, sim.size) + _td(uu.y, mc.y, sim.size)
            if d <= 2:
                score -= 12.0

    return score


def _apply_first_move(sim, u, first_move, pid, opp):
    """将first_move应用到sim中，处理战斗和城市占领"""
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
    # 清理死单位
    sim.units = [uu for uu in sim.units if uu.alive]


_agent_cache = {}

def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    sims = 15
    key = f"mc{sims}"
    if key not in _agent_cache:
        _agent_cache[key] = FlatMCAgent(simulations=sims, rollout_depth=25)
    return _agent_cache[key].decide(gs, pid, rng)
