# prototype/ai_hybrid.py — 规则+参数混合AI
# 10条硬编码规则 + 5个可进化参数
# 每条规则在匹配条件下产生确定行为, 参数控制行为触发阈值

import json, os, random as _random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from prototype.movement import get_single_step_moves
from prototype.mapgen import get_terrain
from prototype.terrain import Terrain, terrain_buildable, terrain_def_bonus
from prototype.constants import UNIT_COST, TECH_TREE as _TECH_TREE

TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}

# ─── 默认参数 (各范围中点) ──────────────────────────
DEFAULT_PARAMS = {
    "retreat_threshold": 0.3,
    "defense_range": 2,
    "wave_threshold": 4,
    "patience": 50,
    "save_threshold": 25,
}

PARAM_BOUNDS = {
    "retreat_threshold": (0.1, 0.5),
    "defense_range": (1, 4),
    "wave_threshold": (2, 6),
    "patience": (20, 80),
    "save_threshold": (10, 40),
}


def random_params(rng: _random.Random | None = None) -> dict:
    """在PARAM_BOUNDS范围内均匀采样生成随机参数"""
    if rng is None:
        rng = _random.Random()
    result = {}
    for k, (lo, hi) in PARAM_BOUNDS.items():
        if isinstance(lo, int) and isinstance(hi, int):
            result[k] = rng.randint(lo, hi)
        else:
            result[k] = rng.uniform(lo, hi)
    return result


def mutate_params(params: dict, rate: float = 0.2, scale: float = 0.15,
                  rng: _random.Random | None = None) -> dict:
    """高斯变异参数"""
    if rng is None:
        rng = _random.Random()
    result = {}
    for k, v in params.items():
        if rng.random() < rate:
            lo, hi = PARAM_BOUNDS[k]
            rng_range = hi - lo
            noise = rng.gauss(0, scale * rng_range)
            if isinstance(lo, int) and isinstance(hi, int):
                result[k] = max(lo, min(hi, int(round(v + noise))))
            else:
                result[k] = max(lo, min(hi, v + noise))
        else:
            result[k] = v
    return result


def crossover_params(a: dict, b: dict, rng: _random.Random | None = None) -> dict:
    """均匀交叉: 每个参数随机从父母一方继承"""
    if rng is None:
        rng = _random.Random()
    return {k: a[k] if rng.random() < 0.5 else b[k] for k in a}


def td(a: int, b: int, s: int) -> int:
    """环面曼哈顿单轴距离"""
    return min(abs(b - a), s - abs(b - a))


def _count_enemy_ranged(gs, pid: int) -> int:
    """统计敌方远程单位数量"""
    opp = 1 - pid
    return sum(1 for u in gs.units if u.alive and u.player_id == opp and u.ranged)


def _enemies_near_my_city(gs, pid: int, dist: int) -> int:
    """统计在我城dist格范围内的敌方单位"""
    my_city = gs.cities[pid]
    opp = 1 - pid
    count = 0
    for eu in gs.units:
        if eu.alive and eu.player_id == opp:
            d = td(eu.x, my_city.x, gs.size) + td(eu.y, my_city.y, gs.size)
            if d <= dist:
                count += 1
    return count


def _my_units_near_enemy_city(gs, pid: int, dist: int) -> list:
    """返回在敌城dist格范围内的己方战斗单位"""
    opp_city = gs.cities[1 - pid]
    result = []
    for u in gs.units:
        if u.alive and u.player_id == pid and u.unit_type != "worker":
            d = td(u.x, opp_city.x, gs.size) + td(u.y, opp_city.y, gs.size)
            if d <= dist:
                result.append(u)
    return result


def _enemy_adjacent(u, gs, pid: int):
    """检查邻格是否有敌人"""
    for eu in gs.units:
        if eu.alive and eu.player_id != pid:
            d = td(eu.x, u.x, gs.size) + td(eu.y, u.y, gs.size)
            if d == 1:
                return eu
    return None


def _enemy_on_my_city(u, gs, pid: int):
    """检查敌人是否在己方城市上 (邻格检查)"""
    my_city = gs.cities[pid]
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (u.x + dx) % gs.size, (u.y + dy) % gs.size
        if nx == my_city.x and ny == my_city.y:
            target = next((eu for eu in gs.units
                           if eu.alive and eu.player_id != pid
                           and eu.x == nx and eu.y == ny), None)
            if target:
                return target
    return None


def _hp_pct(u) -> float:
    """计算单位HP比例"""
    max_hp = {"infantry": 100, "cavalry": 80, "archer": 60, "scout": 40}.get(u.unit_type, 100)
    return u.hp / max_hp


def _nearest_buildable(unit, gs, pid):
    """找最近可建资源格"""
    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            b = terrain_buildable(get_terrain(gs.grid, x, y))
            if not b:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            d = td(unit.x, x, gs.size) + td(unit.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _find_missing_resource(w, gs, pid):
    """找最近缺失资源的可建格"""
    facilities = []
    for y in range(gs.size):
        for x in range(gs.size):
            f = gs.grid[y][x].get("facility")
            if f and f.player_id == pid:
                facilities.append(f.facility_type)
    has_farm = "farm" in facilities
    has_lumb = "lumbermill" in facilities
    has_mine = "mine" in facilities

    best, best_d = None, 999
    for y in range(gs.size):
        for x in range(gs.size):
            terrain = get_terrain(gs.grid, x, y)
            buildable = terrain_buildable(terrain)
            if not buildable:
                continue
            if gs.grid[y][x].get("facility"):
                continue
            needed = ((buildable == "farm" and not has_farm) or
                      (buildable == "lumbermill" and not has_lumb) or
                      (buildable == "mine" and not has_mine))
            if not needed:
                continue
            d = td(w.x, x, gs.size) + td(w.y, y, gs.size)
            if d < best_d:
                best_d = d
                best = (x, y)
    return best


def _move_to(unit, ui, gs, target, rng):
    """向目标移动一步, 地形防御偏好 (Rule 9)"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    tx, ty = target
    best, best_score = [], -999
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, tx, gs.size) + td(ny, ty, gs.size)
        terrain = get_terrain(gs.grid, nx, ny)
        def_bonus = terrain_def_bonus(terrain)
        # Rule 9: terrain_defense_high → prefer this tile
        score = -d + def_bonus * 0.3
        if terrain == Terrain.WATER:
            score -= 100
        if terrain == Terrain.MOUNTAIN and not unit.can_enter_mountain:
            score -= 100
        if score > best_score:
            best_score = score
            best = [mv]
        elif abs(score - best_score) < 0.001:
            best.append(mv)
    mv = rng.choice(best) if best else (0, 0)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


def _retreat_from(unit, ui, gs, enemy, rng):
    """远离敌人一步"""
    legal = get_single_step_moves(unit, gs.grid)
    if not legal:
        return {"unit_idx": ui, "type": "end_turn"}
    best, best_d = [], -1
    for mv in legal:
        nx, ny = (unit.x + mv[0]) % gs.size, (unit.y + mv[1]) % gs.size
        d = td(nx, enemy.x, gs.size) + td(ny, enemy.y, gs.size)
        if d > best_d:
            best_d = d
            best = [mv]
        elif d == best_d:
            best.append(mv)
    mv = rng.choice(best)
    return {"unit_idx": ui, "type": "move", "dx": mv[0], "dy": mv[1]}


# ─── 混合AI决策函数 ────────────────────────────────

def ai_decide(gs, pid: int, rng=None, params: dict = None) -> list[dict]:
    """
    规则+参数混合AI主入口。

    参数:
        gs: GameState
        pid: 玩家ID (0或1)
        rng: random.Random实例
        params: 5个参数的字典。None则使用中点默认值。
    """
    if rng is None:
        rng = _random.Random(gs.seed + gs.turn * 1000 + pid)
    if params is None:
        params = dict(DEFAULT_PARAMS)

    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_city = gs.cities[1 - pid]
    my_city = gs.cities[pid]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    actions = []
    done_units = set()

    p = params  # shorthand

    # 战术顺序: 弓手先动(站位) -> 近战单位 -> 侦察兵 -> 工人
    archers = [u for u in units if u.unit_type == "archer"]
    fighters = [u for u in units if u.unit_type not in ("archer", "worker")]
    scouts = [u for u in units if u.unit_type == "scout"]
    workers = [u for u in units if u.unit_type == "worker"]

    for u in archers + fighters + scouts:
        ui = _find_unit_index(units, u)
        if ui is None or ui in done_units:
            continue
        act = _hybrid_combat(u, ui, gs, pid, opp_city, my_city, p, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    for u in workers:
        ui = _find_unit_index(units, u)
        if ui is None or ui in done_units:
            continue
        act = _hybrid_worker(u, ui, gs, pid, rng)
        if act:
            actions.append(act)
            done_units.add(ui)

    # === Rule 6: stalemate > patience → switch_to_construction ===
    if tech.researching is None:
        stalemate = (gs.turn > p["patience"])
        if stalemate:
            # Switch to construction: C-line techs
            avail = tech.available_to_research()
            c_avail = [t for t in avail if t.startswith("C")]
            c_avail.sort(key=lambda t: TECH_TREE_COST.get(t, (0, 0, 0))[0])
            for t in c_avail:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break

        # Rule 7: resources > save_threshold AND researching=None → research
        if tech.researching is None:
            all_above_threshold = (
                econ.food > p["save_threshold"]
                and econ.wood > p["save_threshold"]
                and econ.gold > p["save_threshold"]
            )
            if all_above_threshold:
                avail = tech.available_to_research()
                if not stalemate:
                    # Normal research order
                    order = ["M1", "C1", "M2", "E1", "C2", "M3", "E2", "C3",
                             "M4", "E3", "C4", "E4", "C5"]
                    for t in order:
                        if t in avail and econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                            actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                            break

    # === Rule 10: enemy_has_many_ranged → produce_cavalry ===
    # === Rule 8: produce elite else cheap ===
    enemy_ranged = _count_enemy_ranged(gs, pid)
    if enemy_ranged >= 2:
        # Rule 10: bias toward cavalry
        for ut in ["cavalry", "archer", "infantry"]:
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break
    else:
        # Rule 8: if can afford elite (cavalry = most expensive) produce elite, else cheap
        if econ.can_afford(UNIT_COST["cavalry"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "cavalry"})
        elif econ.can_afford(UNIT_COST["archer"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "archer"})
        elif econ.can_afford(UNIT_COST["infantry"]):
            actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"})

    return actions


def _find_unit_index(units, target):
    """在units列表中找target的索引"""
    for i, u in enumerate(units):
        if u is target:
            return i
    return None


def _hybrid_combat(u, ui, gs, pid, opp_city, my_city, p, rng):
    """规则驱动的战斗单位决策, 参数控制阈值"""
    hp = _hp_pct(u)

    # --------------------------------------------------
    # Rule 1: ENEMY_ADJACENT → attack
    # --------------------------------------------------
    enemy_adj = _enemy_adjacent(u, gs, pid)
    if enemy_adj is not None:
        # Attack the adjacent enemy
        dx = (enemy_adj.x - u.x) % gs.size
        if dx > 1:
            dx = dx - gs.size
        dy = (enemy_adj.y - u.y) % gs.size
        if dy > 1:
            dy = dy - gs.size
        return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # --------------------------------------------------
    # Rule 2: ENEMY_ON_MY_CITY → attack immediately
    # --------------------------------------------------
    enemy_on_city = _enemy_on_my_city(u, gs, pid)
    if enemy_on_city is not None:
        dx = (enemy_on_city.x - u.x) % gs.size
        if dx > 1:
            dx = dx - gs.size
        dy = (enemy_on_city.y - u.y) % gs.size
        if dy > 1:
            dy = dy - gs.size
        return {"unit_idx": ui, "type": "move", "dx": dx, "dy": dy}

    # --------------------------------------------------
    # Rule 3: HP < retreat_threshold → retreat toward city
    # --------------------------------------------------
    if hp < p["retreat_threshold"]:
        # Check if enemy is nearby (within 2 tiles)
        enemy_nearby = any(
            eu.alive and eu.player_id != pid
            and td(eu.x, u.x, gs.size) + td(eu.y, u.y, gs.size) <= 2
            for eu in gs.units
        )
        if enemy_nearby:
            return _move_to(u, ui, gs, (my_city.x, my_city.y), rng)

    # --------------------------------------------------
    # Rule 4: enemy_near_my_city < defense_range → defend
    # --------------------------------------------------
    enemies_near = _enemies_near_my_city(gs, pid, p["defense_range"])
    if enemies_near > 0:
        dist_to_my_city = td(u.x, my_city.x, gs.size) + td(u.y, my_city.y, gs.size)
        if dist_to_my_city <= p["defense_range"] + 2:
            # Unit is near city → intercept closest enemy
            closest_enemy = None
            closest_d = 999
            for eu in gs.units:
                if eu.alive and eu.player_id != pid:
                    d = td(eu.x, my_city.x, gs.size) + td(eu.y, my_city.y, gs.size)
                    if d < closest_d:
                        closest_d = d
                        closest_enemy = eu
            if closest_enemy:
                return _move_to(u, ui, gs, (closest_enemy.x, closest_enemy.y), rng)

    # --------------------------------------------------
    # Rule 5: my_units_near_enemy_city > wave_threshold → push_all
    # --------------------------------------------------
    near_enemy = _my_units_near_enemy_city(gs, pid, 6)
    if len(near_enemy) > p["wave_threshold"]:
        # Push all toward enemy city
        return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)

    # --------------------------------------------------
    # Default: move toward enemy city (prefer defense terrain per Rule 9)
    # --------------------------------------------------
    return _move_to(u, ui, gs, (opp_city.x, opp_city.y), rng)


def _hybrid_worker(wu, ui, gs, pid, rng):
    """简单的工人贪心逻辑: 建造 → 生产 → 移动"""
    terrain = get_terrain(gs.grid, wu.x, wu.y)
    buildable = terrain_buildable(terrain)
    facility = gs.grid[wu.y][wu.x].get("facility")

    # If on a facility → produce
    if facility and facility.player_id == pid:
        return {"unit_idx": ui, "type": "produce"}

    # If on a buildable tile without facility → build
    if buildable and not facility:
        return {"unit_idx": ui, "type": "build"}

    # Move to nearest buildable tile
    target = _find_missing_resource(wu, gs, pid)
    if target is None:
        target = _nearest_buildable(wu, gs, pid)
    if target:
        return _move_to(wu, ui, gs, target, rng)

    return {"unit_idx": ui, "type": "end_turn"}


# ═══════════════════════════════════════════════════
# 进化训练
# ═══════════════════════════════════════════════════

_TRAIN_CONFIG = {
    "generations": 50,
    "population_size": 30,
    "games_per": 5,
    "opponents": ["random", "greedy"],
    "size": 15,
    "max_turns": 100,
    "workers": os.cpu_count() or 4,
    "seed_offset": 42,
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "eval_paradigms"
BEST_PARAMS_PATH = OUTPUT_DIR / "hybrid_best_params.json"
CHECKPOINT_PATH = Path(__file__).parent / "hybrid_checkpoint.json"


def _import_opponent(name: str):
    """动态导入对手AI模块"""
    import importlib
    table = {
        "random": "prototype.ai_rulesrandom",
        "greedy": "prototype.ai_greedy",
        "aggressive": "prototype.ai_aggressive",
        "flatmc": "prototype.ai_flatmc",
    }
    if name not in table:
        raise ValueError(f"Unknown opponent: {name}")
    mod = importlib.import_module(table[name])
    return mod.ai_decide


def _evaluate_one(seed: int, params: dict, opponent_name: str,
                  size: int, max_turns: int, is_p0: bool) -> int:
    """运行一盘游戏, 返回1(hybrid AI赢)或0(输)"""
    from prototype.game import init_game, step_game
    opp_func = _import_opponent(opponent_name)

    def hybrid_decide(gs, p, rng):
        return ai_decide(gs, p, rng, params=params)

    ai0 = hybrid_decide if is_p0 else opp_func
    ai1 = opp_func if is_p0 else hybrid_decide

    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    hybrid_pid = 0 if is_p0 else 1

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0(gs, 0, rng0)
        a1 = ai1(gs, 1, rng1)
        step_game(gs, a0, a1)

    return 1 if gs.winner == hybrid_pid else 0


def evaluate_individual(params: dict, ind_id: int, opponents: list,
                        games_per: int, size: int, max_turns: int) -> dict:
    """评估一个个体的综合表现"""
    total_wins = 0
    total_games = 0
    rng = _random.Random(ind_id * 9999)
    seed_offset = _TRAIN_CONFIG["seed_offset"]

    for opp in opponents:
        for g in range(games_per):
            is_p0 = (g % 2 == 0)
            seed = seed_offset + ind_id * 1000 + hash(opp) % 10000 + g
            win = _evaluate_one(seed, params, opp, size, max_turns, is_p0)
            total_wins += win
            total_games += 1

    winrate = total_wins / total_games if total_games > 0 else 0.0
    return {
        "ind_id": ind_id, "winrate": winrate, "wins": total_wins,
        "games": total_games, "params": params,
    }


def create_next_generation(elites: list, pop_size: int,
                           rng: _random.Random) -> list[dict]:
    """从精英中生成下一代: 保留精英 + 交叉变异"""
    next_gen = []
    elite_count = max(1, int(pop_size * 0.2))

    # 直接保留精英 (前elite_count个)
    for i in range(min(elite_count, len(elites))):
        next_gen.append(dict(elites[i][1]))

    # 填充剩余: 交叉 + 变异
    while len(next_gen) < pop_size:
        p1 = rng.choice(elites[:elite_count])[1]
        p2 = rng.choice(elites[:elite_count])[1]
        child = crossover_params(p1, p2, rng)
        child = mutate_params(child, rate=0.2, scale=0.15, rng=rng)
        next_gen.append(child)

    return next_gen


def save_checkpoint(generation: int, population: list, best_winrate: float,
                    best_params: dict):
    """保存检查点以便中断恢复"""
    data = {
        "generation": generation,
        "best_winrate": best_winrate,
        "best_params": best_params,
        "population": population,
    }
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_checkpoint():
    """加载检查点"""
    if not CHECKPOINT_PATH.exists():
        return None
    with open(CHECKPOINT_PATH, "r") as f:
        return json.load(f)


def train_params(generations: int = 50, pop_size: int = 30,
                 games_per: int = 5) -> dict:
    """
    使用进化算法优化5个参数。

    参数:
        generations: 进化代数
        pop_size: 种群大小
        games_per: 每对局匹配的游戏数

    返回:
        最优参数字典
    """
    cfg = _TRAIN_CONFIG
    cfg["generations"] = generations
    cfg["population_size"] = pop_size
    cfg["games_per"] = games_per
    opponents = cfg["opponents"]
    workers = cfg["workers"]
    size = cfg["size"]
    max_turns = cfg["max_turns"]
    seed_offset = cfg["seed_offset"]

    total_per_gen = pop_size * len(opponents) * games_per
    total_overall = total_per_gen * generations

    print("=" * 60)
    print("MiniCiv Hybrid AI Training")
    print(f"  Population: {pop_size}")
    print(f"  Generations: {generations}")
    print(f"  Opponents: {opponents}")
    print(f"  Games per matchup: {games_per}")
    print(f"  Workers: {workers}")
    print(f"  Total games/gen: {total_per_gen}")
    print(f"  Total games: {total_overall}")
    print(f"  Params: {list(PARAM_BOUNDS.keys())}")
    print("=" * 60)

    # 尝试加载检查点
    checkpoint = load_checkpoint()
    if checkpoint:
        print(f"Resuming from generation {checkpoint['generation']}")
        population = checkpoint["population"]
        best_winrate = checkpoint["best_winrate"]
        best_params = checkpoint["best_params"]
        start_gen = checkpoint["generation"] + 1
    else:
        rng = _random.Random(seed_offset)
        population = [random_params(rng) for _ in range(pop_size)]
        best_winrate = 0.0
        best_params = None
        start_gen = 0

    global_best_winrate = best_winrate
    global_best_params = best_params

    for gen in range(start_gen, generations):
        import time
        gen_start = time.time()

        # --- 评估 ---
        futures = {}
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for i, ind in enumerate(population):
                fut = executor.submit(
                    evaluate_individual, ind, i, opponents,
                    games_per, size, max_turns
                )
                futures[fut] = i

            results = [None] * len(population)
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    print(f"  Worker {idx} failed: {e}")
                    results[idx] = {
                        "ind_id": idx, "winrate": -1.0, "wins": 0,
                        "games": 0, "params": population[idx],
                    }

        # --- 排序 ---
        results.sort(key=lambda r: r["winrate"], reverse=True)
        gen_best = results[0]
        gen_avg = sum(r["winrate"] for r in results) / len(results)

        if gen_best["winrate"] > global_best_winrate:
            global_best_winrate = gen_best["winrate"]
            global_best_params = dict(gen_best["params"])

        # --- 选择精英 ---
        elites = [(r["winrate"], r["params"]) for r in results]

        # --- 生成下一代 ---
        rng = _random.Random(seed_offset + gen * 777)
        population = create_next_generation(elites, pop_size, rng)

        elapsed = time.time() - gen_start
        print(f"Gen {gen + 1:2d}/{generations} | "
              f"Best: {gen_best['winrate'] * 100:.1f}% "
              f"(#{gen_best['ind_id']}) | "
              f"Avg: {gen_avg * 100:.1f}% | "
              f"Global best: {global_best_winrate * 100:.1f}% | "
              f"{elapsed:.1f}s")

        # --- 检查点 ---
        save_checkpoint(gen, [dict(p) for p in population],
                        global_best_winrate, global_best_params)

    # --- 完成 ---
    print("\n" + "=" * 60)
    print("Training complete!")
    print(f"Best winrate achieved: {global_best_winrate * 100:.1f}%")
    print(f"Best params: {global_best_params}")

    # 保存最优参数
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(BEST_PARAMS_PATH, "w") as f:
        json.dump({
            "best_winrate": global_best_winrate,
            "params": global_best_params,
        }, f, indent=2)
    print(f"Saved best params to: {BEST_PARAMS_PATH}")

    # 清理检查点
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    return global_best_params


if __name__ == "__main__":
    best_params = train_params()
    print("Best params:", best_params)
