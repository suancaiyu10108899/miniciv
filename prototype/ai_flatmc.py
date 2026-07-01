# prototype/ai_flatmc.py — FlatMC v2: 偏向进攻的rollout + 进度奖励
import random as _random, copy as _copy
from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
from prototype.economy import worker_action_build, worker_action_produce, produce_unit
from prototype.constants import TECH_TREE as _TECH_TREE, UNIT_COST, CITY_DAMAGE
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
            legal.append((0, 0))

            best_act, best_score = (0, 0), -99999
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
        if tech.researching is None:
            avail = tech.available_to_research()
            from prototype.constants import TECH_TREE as TT
            TC = {k: v["cost"] for k, v in TT.items()}
            avail.sort(key=lambda t: -sum(TC.get(t, (0, 0, 0))))
            for t in avail:
                if econ.can_afford(TC.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

        return actions


def _rollout(gs, pid, unit_idx, first_move, rng):
    """v2 rollout: 偏向进攻的模拟 + 进度奖励"""
    sim = _copy.deepcopy(gs)
    sim.rng = _random.Random(rng.randint(0, 999999))
    opp = 1 - pid
    my_city = sim.cities[pid]
    opp_city = sim.cities[opp]

    # 地图最大距离
    max_dist = sim.size * 2

    # 应用第一步
    u = None
    for i, uu in enumerate(sim.units):
        if i == unit_idx:
            u = uu
            break
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

    # 记录初始状态用于进度计算
    initial_dist = _td(u.x, opp_city.x, sim.size) + _td(u.y, opp_city.y, sim.size) if u and u.alive else max_dist
    initial_opp_hp = opp_city.hp
    progress_score = 0.0
    damage_dealt = 0

    # 偏向进攻的rollout (不是纯随机)
    sim_turns = min(sim.turn + 15, 100)
    while sim.turn < sim_turns and sim.winner is None:
        sim.turn += 1
        for p in (0, 1):
            for uu in [u for u in sim.units if u.player_id == p and u.alive]:
                legal = get_single_step_moves(uu, sim.grid)
                if not legal:
                    continue

                # 偏向进攻: 70%向敌城, 30%随机
                if sim.rng.random() < 0.7 and p != pid:
                    # 偏向进攻(对手模拟): 向我的城市推进
                    target = (sim.cities[1-p].x, sim.cities[1-p].y)
                    mv = _pick_toward(uu, legal, target, sim)
                elif sim.rng.random() < 0.7 and p == pid:
                    # 偏向进攻(我方模拟): 向敌城推进
                    mv = _pick_toward(uu, legal, (opp_city.x, opp_city.y), sim)
                else:
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
                    result = resolve_melee(uu, blocker, t_att, t_def)

                    # 追踪伤害
                    if p == pid:
                        damage_dealt += result["att_damage"]
                    else:
                        damage_dealt -= result["def_damage"]

                    if uu.alive and not blocker.alive:
                        uu.x, uu.y = nx, ny
                        for c in sim.cities:
                            if c.player_id != p and c.x == nx and c.y == ny:
                                dmg = max(1, uu.atk - c.def_)
                                c.hp -= dmg
                                if p == pid:
                                    progress_score += dmg * 5  # 对敌城造成伤害=高分
                                if c.hp <= 0:
                                    c.hp = 0
                                    sim.winner = p
                                    sim.victory_type = "conquest"
                else:
                    uu.x, uu.y = nx, ny

        # 城市防守伤害
        for p in (0, 1):
            city = sim.cities[p]
            for uu in sim.units:
                if uu.alive and uu.player_id != p and uu.x == city.x and uu.y == city.y:
                    uu.hp -= CITY_DAMAGE
                    if uu.hp <= 0:
                        uu.hp = 0
                        uu.alive = False
                    if p == pid:
                        damage_dealt += CITY_DAMAGE

        # 经济
        for p in (0, 1):
            sim.economies[p].food += 1  # city base

        sim.units = [u for u in sim.units if u.alive]

    # === 评分 ===
    if sim.winner == pid:
        return 500  # 我方胜利
    elif sim.winner == opp:
        return -500  # 敌方胜利

    # 进度分
    if u and u.alive:
        final_dist = _td(u.x, opp_city.x, sim.size) + _td(u.y, opp_city.y, sim.size)
        progress_score += (initial_dist - final_dist) * 3  # 接近敌城=正分

    # 城市伤害
    progress_score += (initial_opp_hp - opp_city.hp) * 2

    # 伤害分
    progress_score += damage_dealt * 0.5

    # 存活单位分
    my_alive = sum(1 for uu in sim.units if uu.player_id == pid and uu.alive)
    opp_alive = sum(1 for uu in sim.units if uu.player_id == opp and uu.alive)
    progress_score += (my_alive - opp_alive) * 5

    return progress_score


def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def _pick_toward(unit, legal, target, gs):
    """选最接近target的合法移动"""
    best, best_d = None, 999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = _td(nx, target[0], gs.size) + _td(ny, target[1], gs.size)
        if d < best_d:
            best_d = d
            best = mv
    return best if best else (0, 0)


_agent_cache = {}

def ai_decide(gs, pid: int, rng=None) -> list[dict]:
    sims = 25
    if sims not in _agent_cache:
        _agent_cache[sims] = FlatMCAgent(sims)
    return _agent_cache[sims].decide(gs, pid, rng)
