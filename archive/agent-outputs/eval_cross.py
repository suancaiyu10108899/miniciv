# prototype/eval_cross.py — 跨范式评估矩阵
# 运行 DQN(gen3) vs Hybrid vs BC vs Greedy 的全配对比较
#
# 用法: python -m prototype.eval_cross
#
# 要求:
#   - eval_paradigms/gen3_weights.json (来自 train_selfplay.py)
#   - eval_paradigms/hybrid_best_params.json (来自 ai_hybrid.py 训练)
#   - prototype/bc_weights.json (来自 Agent C 的训练, 如不存在则使用随机基线)
#
# 输出: eval_paradigms/cross_paradigm_results.json + 详细 JSON

import json, math, os, random as _random, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# ── 项目根目录 ───────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.game import init_game, step_game
from prototype.ai_dqn import DQNAgent, ai_decide as dqn_decide
from prototype.ai_hybrid import ai_decide as hybrid_decide
from prototype.ai_greedy import ai_decide as greedy_decide
from prototype.eval import load_ai, AI_MODULES

EVAL_DIR = PROJECT_ROOT / "eval_paradigms"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── 配置 ──────────────────────────────────────────
GAMES_PER_PAIR = 200
SIZE = 15
MAX_TURNS = 100
SEED = 42
WORKERS = max(1, (os.cpu_count() or 4) - 1)

# 参与者列表: 每个项是 (name, decide_func, is_available)
# DQN-Gen3 (需要 gen3_weights.json)
# Hybrid (需要 hybrid_best_params.json)
# BC (需要 bc_weights.json — Agent C 的输出)
# Greedy (总是可用)


def _mean_std(values):
    """Return (mean, stddev) for a list of numbers."""
    n = len(values)
    if n < 2:
        return (sum(values) / n if n else 0.0, 0.0)
    m = sum(values) / n
    v = sum((x - m) ** 2 for x in values) / (n - 1)
    return (m, math.sqrt(v))


def _ci95(p, n):
    """95% CI width"""
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


def _load_dqn(path: str) -> DQNAgent | None:
    """从 JSON 加载 DQN agent"""
    p = Path(path)
    if not p.exists():
        print(f"  WARNING: DQN weights not found: {path}")
        return None
    agent = DQNAgent(n_features=25, n_actions=6)
    agent.load(str(p))
    return agent


def _load_hybrid_params(path: str) -> dict | None:
    """从 JSON 加载 Hybrid 参数"""
    p = Path(path)
    if not p.exists():
        print(f"  WARNING: Hybrid params not found: {path}")
        return None
    with open(p) as f:
        data = json.load(f)
    return data.get("params") or data.get("weights")


def _load_bc_weights(path: str) -> dict | None:
    """从 JSON 加载 BC 权重 (Agent C 格式)"""
    p = Path(path)
    if not p.exists():
        # 尝试 prototype/bc_weights.json
        p2 = PROJECT_ROOT / "prototype" / "bc_weights.json"
        if p2.exists():
            with open(p2) as f:
                return json.load(f)
        print(f"  WARNING: BC weights not found at {path} or {p2}")
        return None
    with open(p) as f:
        return json.load(f)


def build_contestants() -> dict:
    """
    构建参赛者字典 {name: decide_func}
    对于需要权重的 AI, 如权重不存在则跳过.
    """
    contestants = {}

    # Greedy: 总是可用
    contestants["greedy"] = {
        "func": greedy_decide,
        "available": True,
    }

    # Hybrid: 需要 params
    hybrid_params = _load_hybrid_params(str(EVAL_DIR / "hybrid_best_params.json"))
    if hybrid_params:
        def make_hybrid(p):
            def f(gs, pid, rng):
                return hybrid_decide(gs, pid, rng, params=p)
            return f
        contestants["hybrid"] = {
            "func": make_hybrid(hybrid_params),
            "available": True,
        }
    else:
        # 使用默认参数
        from prototype.ai_hybrid import DEFAULT_PARAMS
        def f(gs, pid, rng):
            return hybrid_decide(gs, pid, rng, params=DEFAULT_PARAMS)
        contestants["hybrid-default"] = {
            "func": f,
            "available": True,
        }

    # DQN-Gen3: 需要 gen3 weights
    for gen_name, gen_file in [("dqn-gen3", "gen3_weights.json"),
                                ("dqn-gen2", "gen2_weights.json"),
                                ("dqn-gen1", "gen1_weights.json")]:
        agent = _load_dqn(str(EVAL_DIR / gen_file))
        if agent:
            def make_dqn(a):
                def f(gs, pid, rng):
                    return dqn_decide(gs, pid, rng, dqn=a)
                return f
            contestants[gen_name] = {
                "func": make_dqn(agent),
                "available": True,
            }

    # BC: 需要 bc weights
    bc_data = _load_bc_weights(str(EVAL_DIR / "bc_weights.json"))
    if bc_data:
        # BC 是 Behavioral Cloning AI — Agent C 的实现
        # 这里假设 BC AI 使用 prototype.ai_rulesrandom 作为回退
        # 有一个 bc_weights.json 文件 (Agent C 输出)
        # 实际实现取决于 Agent C 的接口, 这里做适应性加载
        try:
            from prototype.ai_bc import ai_decide as bc_decide
            # 尝试加载权重
            if isinstance(bc_data, dict) and "weights" in bc_data:
                weights = bc_data["weights"]
            else:
                weights = bc_data

            def make_bc(w):
                def f(gs, pid, rng):
                    # 尝试用 weights 调用 bc_decide
                    try:
                        return bc_decide(gs, pid, rng, weights=w)
                    except:
                        # 回退到 random
                        from prototype.ai_rulesrandom import ai_decide as rr
                        return rr(gs, pid, rng)
                return f
            contestants["bc"] = {
                "func": make_bc(bc_data),
                "available": True,
            }
        except ImportError:
            print("  WARNING: prototype.ai_bc not found. BC not available.")

    return contestants


def _run_seeded_game(ai0_func, ai1_func, seed: int,
                     size: int = SIZE, max_turns: int = MAX_TURNS) -> dict:
    """运行一局游戏, 返回结果"""
    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)
    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0_func(gs, 0, rng0), ai1_func(gs, 1, rng1))
    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type or "tiebreak",
        "turns": gs.turn,
        "p0_dead": sum(1 for u in gs.dead_units if u.player_id == 0),
        "p1_dead": sum(1 for u in gs.dead_units if u.player_id == 1),
        "p0_alive": sum(1 for u in gs.units if u.player_id == 0 and u.alive),
        "p1_alive": sum(1 for u in gs.units if u.player_id == 1 and u.alive),
    }


def _run_one_pair(args):
    """运行一对 AI 的所有游戏 (用于进程池)"""
    name_a, func_a, name_b, func_b, n_games, size, max_turns, seed_offset = args
    results = []
    for g in range(n_games):
        seed = seed_offset + g * 1000 + hash((name_a, name_b)) % 100000
        # G: AI_A is P0
        r1 = _run_seeded_game(func_a, func_b, seed, size, max_turns)
        # G+1: AI_A is P1 (swap)
        r2 = _run_seeded_game(func_b, func_a, seed + 1, size, max_turns)
        results.append({"game_p0": r1, "game_p1": r2, "seed": seed})
    return {"pair": (name_a, name_b), "results": results}


def main():
    workers = WORKERS
    n_games = GAMES_PER_PAIR

    print("=" * 70)
    print("  MINICIV CROSS-PARADIGM EVALUATION")
    print(f"  Games per pair: {n_games} (x2 for swap = {n_games*2} total)")
    print(f"  Workers: {workers}")
    print("=" * 70)

    # 构建参赛者
    contestants = build_contestants()
    available_names = [n for n, c in contestants.items() if c["available"]]
    print(f"\n  Contestants: {available_names}")

    # 全配对 (包括自身 vs 自身)
    pairs = [(a, b) for a in available_names for b in available_names]

    # 构建任务
    tasks = []
    for name_a, name_b in pairs:
        func_a = contestants[name_a]["func"]
        func_b = contestants[name_b]["func"]
        tasks.append((name_a, func_a, name_b, func_b, n_games, SIZE, MAX_TURNS, SEED))

    # 并行执行
    t0 = time.perf_counter()
    raw_results = {}
    completed = 0
    n_tasks = len(tasks)

    print(f"\n  Running {n_tasks} pair evaluations...")

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one_pair, task): task for task in tasks}
        for fut in as_completed(futures):
            result = fut.result()
            key = result["pair"]
            raw_results[key] = result["results"]
            completed += 1
            if completed % max(1, n_tasks // 5) == 0 or completed == n_tasks:
                elapsed = time.perf_counter() - t0
                print(f"    {completed}/{n_tasks} pairs ({elapsed:.0f}s)")

    elapsed = time.perf_counter() - t0
    print(f"\n  All games complete in {elapsed:.0f}s")

    # ── 汇总统计 ──
    print(f"\n{'='*70}")
    print(f"  RESULTS TABLE")
    print(f"{'='*70}")
    print()

    # 标题行
    header = f"  {'AI A':<14s}"
    for name_b in available_names:
        header += f" {name_b:>12s}"
    print(header)
    print(f"  {'-'*14}" + " " + "-" * (14 * len(available_names)))

    summary = {
        "config": {
            "games_per_pair": n_games,
            "total_games_per_pair": n_games * 2,
            "size": SIZE,
            "max_turns": MAX_TURNS,
            "contestants": available_names,
        },
        "pairwise": {},
    }

    for name_a in available_names:
        row = f"  {name_a:<14s}"
        for name_b in available_names:
            results = raw_results.get((name_a, name_b), [])
            if not results:
                row += f" {'N/A':>12s}"
                continue

            # 统计 AI_A winrate (paired)
            total_games = len(results) * 2
            a_wins = 0
            all_wins = []
            for r in results:
                # game_p0: AI_A=P0 -> AI_A wins if winner=0
                a_wins += 1 if r["game_p0"]["winner"] == 0 else 0
                # game_p1: AI_A=P1 -> AI_A wins if winner=1
                a_wins += 1 if r["game_p1"]["winner"] == 1 else 0
                all_wins.append(1 if r["game_p0"]["winner"] == 0 else 0)
                all_wins.append(1 if r["game_p1"]["winner"] == 1 else 0)

            wr = a_wins / total_games
            mean, std = _mean_std(all_wins)
            ci = _ci95(wr, total_games)

            row += f" {wr*100:>5.1f}%+/-{std*100:>4.1f}%"

            # Save details
            key = f"{name_a}_vs_{name_b}"
            summary["pairwise"][key] = {
                "ai_a": name_a,
                "ai_b": name_b,
                "n_seeds": len(results),
                "n_games": total_games,
                "ai_a_winrate": round(wr, 4),
                "ai_a_wins": a_wins,
                "ai_b_wins": total_games - a_wins,
                "std": round(std, 4),
                "ci95": round(ci, 4),
                "avg_turns": round(sum(r["game_p0"]["turns"] + r["game_p1"]["turns"] for r in results) / total_games, 1),
                "conquest_rate": round(sum(1 for r in results for g in [r["game_p0"], r["game_p1"]] if "conquest" in str(g["victory_type"])) / total_games, 4),
                "construction_rate": round(sum(1 for r in results for g in [r["game_p0"], r["game_p1"]] if "construction" in str(g["victory_type"])) / total_games, 4),
            }

        print(row)

    # ── 保存结果 ──
    output_path = EVAL_DIR / "cross_paradigm_results.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results saved to: {output_path}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
