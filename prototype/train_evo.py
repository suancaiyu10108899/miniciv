# prototype/train_evo.py — 进化算法训练脚本
# 对 ai_evo.py 的权重参数进行进化优化
# 每一代: 种群50, 锦标赛, top20% 选择, 交叉+变异

import json, os, random, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import prototype.cleanup  # atexit orphan process cleanup

from prototype.game import init_game, step_game
from prototype.ai_evo import ai_decide, random_weights, mutate_weights, crossover_weights, DEFAULT_WEIGHTS

# ─── 配置 ─────────────────────────────────────────
POPULATION_SIZE = 60
ELITE_RATIO = 0.2          # 前20%入选
GENERATIONS = 50
OPPONENTS = ["random", "greedy", "aggressive"]  # 对手AI
GAMES_PER_MATCHUP = 5       # 每局配对玩5盘 (交替先手)
SEED_OFFSET = 42
SIZE = 15
MAX_TURNS = 100

# 并行worker数
WORKERS = os.cpu_count() or 4

OUTPUT_PATH = Path(__file__).parent / "evo_best_weights.json"
CHECKPOINT_PATH = Path(__file__).parent / "evo_checkpoint.json"


def _import_opponent(name: str):
    """动态导入对手 AI 模块"""
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


def _evaluate_one(seed: int, weights: dict, opponent_name: str,
                  size: int, max_turns: int, is_p0: bool) -> int:
    """
    运行一盘游戏, 返回 1 (evo AI 赢) 或 0 (输).
    is_p0: True 表示 evo AI 执先手, False 表示执后手.
    """
    opp_func = _import_opponent(opponent_name)

    def evo_decide(gs, pid, rng):
        return ai_decide(gs, pid, rng, weights=weights)

    ai0 = evo_decide if is_p0 else opp_func
    ai1 = opp_func if is_p0 else evo_decide

    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)
    evo_pid = 0 if is_p0 else 1

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0(gs, 0, rng0)
        a1 = ai1(gs, 1, rng1)
        step_game(gs, a0, a1)

    return 1 if gs.winner == evo_pid else 0


def evaluate_individual(individual: dict, ind_id: int, opponents: list,
                        games_per: int, size: int, max_turns: int) -> dict:
    """
    评估一个个体的综合表现.
    对每个对手: 玩 games_per 盘 (P0先手 |P1先手 各一半), 统计胜率.
    """
    total_wins = 0
    total_games = 0
    rng = random.Random(ind_id * 9999)

    for opp in opponents:
        for g in range(games_per):
            # 交替先手
            is_p0 = (g % 2 == 0)
            seed = SEED_OFFSET + ind_id * 1000 + hash(opp) % 10000 + g
            win = _evaluate_one(seed, individual, opp, size, max_turns, is_p0)
            total_wins += win
            total_games += 1

    winrate = total_wins / total_games if total_games > 0 else 0.0
    return {"ind_id": ind_id, "winrate": winrate, "wins": total_wins,
            "games": total_games, "weights": individual}


def create_next_generation(elites: list, pop_size: int,
                           rng: random.Random) -> list[dict]:
    """
    从精英中生成下一代: 保留精英 + 交叉变异.
    elites: [(winrate, weights_dict), ...]
    """
    next_gen = []
    elite_count = max(1, int(pop_size * ELITE_RATIO))

    # 直接保留精英 (前 elite_count 个)
    for i in range(min(elite_count, len(elites))):
        next_gen.append(dict(elites[i][1]))

    # 填充剩余: 交叉 + 变异
    while len(next_gen) < pop_size:
        p1 = rng.choice(elites[:elite_count])[1]
        p2 = rng.choice(elites[:elite_count])[1]
        child = crossover_weights(p1, p2, rng)
        child = mutate_weights(child, rate=0.15, scale=0.2, rng=rng)
        next_gen.append(child)

    return next_gen


def save_checkpoint(generation: int, population: list, best_winrate: float,
                    best_weights: dict):
    """保存检查点以便中断恢复"""
    data = {
        "generation": generation,
        "best_winrate": best_winrate,
        "best_weights": best_weights,
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


def main():
    print("=" * 60)
    print("MiniCiv EVO Training")
    print(f"  Population: {POPULATION_SIZE}")
    print(f"  Generations: {GENERATIONS}")
    print(f"  Opponents: {OPPONENTS}")
    print(f"  Games per matchup: {GAMES_PER_MATCHUP}")
    print(f"  Workers: {WORKERS}")
    print(f"  Total games/gen: {POPULATION_SIZE * len(OPPONENTS) * GAMES_PER_MATCHUP}")
    print(f"  Total games: {POPULATION_SIZE * len(OPPONENTS) * GAMES_PER_MATCHUP * GENERATIONS}")
    print("=" * 60)

    # 尝试加载检查点
    checkpoint = load_checkpoint()
    if checkpoint:
        print(f"Resuming from generation {checkpoint['generation']}")
        population = checkpoint["population"]
        best_winrate = checkpoint["best_winrate"]
        best_weights = checkpoint["best_weights"]
        start_gen = checkpoint["generation"] + 1
    else:
        rng = random.Random(SEED_OFFSET)
        population = [random_weights(rng) for _ in range(POPULATION_SIZE)]
        best_winrate = 0.0
        best_weights = None
        start_gen = 0

    global_best_winrate = best_winrate
    global_best_weights = best_weights

    for gen in range(start_gen, GENERATIONS):
        gen_start = time.time()

        # --- 评估 ---
        futures = {}
        with ProcessPoolExecutor(max_workers=WORKERS) as executor:
            for i, ind in enumerate(population):
                fut = executor.submit(
                    evaluate_individual, ind, i, OPPONENTS,
                    GAMES_PER_MATCHUP, SIZE, MAX_TURNS
                )
                futures[fut] = i

            results = [None] * len(population)
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    print(f"  Worker {idx} failed: {e}")
                    # 给失败个体默认-1分
                    results[idx] = {
                        "ind_id": idx, "winrate": -1.0, "wins": 0,
                        "games": 0, "weights": population[idx]
                    }

        # --- 排序 ---
        results.sort(key=lambda r: r["winrate"], reverse=True)
        gen_best = results[0]
        gen_avg = sum(r["winrate"] for r in results) / len(results)

        if gen_best["winrate"] > global_best_winrate:
            global_best_winrate = gen_best["winrate"]
            global_best_weights = dict(gen_best["weights"])

        # --- 选择精英 ---
        elites = [(r["winrate"], r["weights"]) for r in results]

        # --- 生成下一代 ---
        rng = random.Random(SEED_OFFSET + gen * 777)
        population = create_next_generation(elites, POPULATION_SIZE, rng)

        elapsed = time.time() - gen_start
        print(f"Gen {gen+1:2d}/{GENERATIONS} | "
              f"Best: {gen_best['winrate']*100:.1f}% "
              f"(#{gen_best['ind_id']}) | "
              f"Avg: {gen_avg*100:.1f}% | "
              f"Global best: {global_best_winrate*100:.1f}% | "
              f"{elapsed:.1f}s")

        # --- 检查点 ---
        save_checkpoint(gen, population, global_best_winrate, global_best_weights)

    # --- 完成 ---
    print("\n" + "=" * 60)
    print(f"Training complete!")
    print(f"Best winrate achieved: {global_best_winrate*100:.1f}%")
    print(f"Saving best weights to: {OUTPUT_PATH}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump({
            "best_winrate": global_best_winrate,
            "weights": global_best_weights,
        }, f, indent=2)
    print(f"Saved!")

    # 清理检查点
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    return global_best_winrate, global_best_weights


if __name__ == "__main__":
    main()
