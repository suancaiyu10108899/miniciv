# prototype/train_selfplay.py — 自对弈训练脚本
#
# 目的: 通过多代自对弈观察 DQN 是否产生渐进式提升
# 每一代:
#   1. 创建全新 DQNAgent（随机初始权重）
#   2. 将上一代最佳权重载入固定的对手 DQN
#   3. 训练新 DQN vs 固定对手 1000 局
#   4. 保存 Gen-N 权重
#   5. 所有代训练完毕后, 每代 vs Greedy 测试 200 局
#
# 关键问题: Gen3 > Gen2 > Gen1? (自对弈产生渐进改善吗)

import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

# ── 项目根目录 ───────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.game import init_game, step_game
from prototype.ai_dqn import (
    DQNAgent,
    ai_decide as dqn_decide,
    _extract_features,
    _td,
)
from prototype.ai_greedy import ai_decide as greedy_decide
from prototype.constants import MAX_TURNS, DEFAULT_SIZE, CITY_HP, UNIT_STATS

# ── 路径 ──────────────────────────────────────────
EVAL_DIR = PROJECT_ROOT / "eval_paradigms"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── 超参数 ───────────────────────────────────────
N_FEATURES = 25       # _extract_features 输出维度
N_ACTIONS = 6         # 6种战斗动作
GAMES_PER_GEN = 1000  # 每代训练局数
TEST_GAMES = 200      # 测试局数
N_GENERATIONS = 3     # 代数
BATCH_SIZE = 64       # 训练 batch size
TRAIN_INTERVAL = 10   # 每 N 局训练一次
TRAIN_STEPS = 3       # 每次训练跑几步梯度下降

LR = 0.001
GAMMA = 0.90
EPSILON = 1.0
EPSILON_MIN = 0.05
EPSILON_DECAY = 0.997

SIZE = DEFAULT_SIZE
MAX_TURNS_LOCAL = MAX_TURNS
SEED_OFFSET = 1337


# ── 胜率统计辅助 ─────────────────────────────────


def _mean_std(values):
    """Return (mean, stddev) for a list of values."""
    n = len(values)
    if n < 2:
        return (sum(values) / n if n else 0.0, 0.0)
    m = sum(values) / n
    v = sum((x - m) ** 2 for x in values) / (n - 1)
    return (m, math.sqrt(v))


def _ci95(p, n):
    """95% confidence interval width for a proportion."""
    if n < 1:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


# ── 训练用AI包装器 ───────────────────────────────
# 在原 dqn_decide 基础上, 在每步调用时记录状态-动作-下一状态转换


class TrainingWrapper:
    """包装 DQN agent 的 ai_decide, 在游戏过程中收集经验。

    每次调用 decide() 时:
      1. 从 gs 提取状态特征
      2. 通过 dqn.act() 选择一个全局动作
      3. 记录 (state, action) 对
    游戏结束后调用 finish_game() 填充 reward/next_state/done。
    """

    def __init__(self, agent: DQNAgent, pid: int):
        self.agent = agent
        self.pid = pid
        self.transitions = []  # list of (state, action)
        self.last_state = None
        self.last_action = None

    def decide(self, gs, pid, rng):
        """决策函数, 兼容 ai_decide 接口。"""
        # 首次调用: 只记录 state, 无前一步
        state = _extract_features(gs, pid)

        # 通过 dqn.act() 选择动作
        action_id = self.agent.act(
            state,
            epsilon_greedy=True,
            legal_actions=None,
            rng=rng,
        )

        # 如果上一步有记录, 存 transition
        if self.last_state is not None:
            self.transitions.append((
                self.last_state.copy(),
                self.last_action,
                state.copy(),  # next_state (占位, 最终reward在finish时补充)
            ))

        self.last_state = state
        self.last_action = action_id

        # 将动作转换为游戏动作列表
        return self._to_game_actions(action_id, gs, pid, rng)

    def _to_game_actions(self, action_id: int, gs, pid: int,
                         rng) -> list[dict]:
        """将 DQN 动作索引转换为游戏引擎动作列表。

        动作映射 (与 ai_dqn.py 中一致):
          0: move towards enemy
          1: move towards own city
          2: attack nearest
          3: defend city
          4: hold
          5: retreat
        """
        from prototype.ai_dqn import (
            _action_move_towards_enemy, _action_move_towards_city,
            _action_attack_nearest, _action_defend_city,
            _action_hold, _action_retreat,
        )
        action_funcs = [
            _action_move_towards_enemy,
            _action_move_towards_city,
            _action_attack_nearest,
            _action_defend_city,
            _action_hold,
            _action_retreat,
        ]

        units = [u for u in gs.units if u.player_id == pid and u.alive]
        actions = []
        action_func = action_funcs[action_id] if action_id < len(action_funcs) else _action_hold

        for u in units:
            if u.unit_type == "worker":
                # 工人使用原始行为 (同 ai_dqn.py 中的 _worker_decide)
                action = self._worker_decide(u, units.index(u), gs, pid, rng)
                if action:
                    actions.append(action)
            else:
                ui = units.index(u)
                action = action_func(u, ui, gs, pid, rng)
                if action:
                    actions.append(action)

        # 研究与生产 (沿用 ai_dqn.py 的贪心策略)
        econ = gs.economies[pid]
        tech = gs.techs[pid]
        if tech.researching is None:
            avail = tech.available_to_research()
            from prototype.ai_dqn import TECH_TREE_COST, UNIT_COST
            avail.sort(key=lambda t: sum(TECH_TREE_COST.get(t, (0, 0, 0))))
            for t in avail:
                if econ.can_afford(TECH_TREE_COST.get(t, (99, 99, 99))):
                    actions.append({"unit_idx": -1, "type": "research", "tech_id": t})
                    break
        for ut in ["infantry", "archer", "cavalry"]:
            from prototype.constants import UNIT_COST
            if econ.can_afford(UNIT_COST[ut]):
                actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": ut})
                break

        return actions

    def _worker_decide(self, u, ui, gs, pid, rng):
        """工人贪心决策 (同 ai_dqn.py 中原始逻辑)。"""
        from prototype.mapgen import get_terrain
        from prototype.terrain import terrain_buildable
        terrain = get_terrain(gs.grid, u.x, u.y)
        buildable = terrain_buildable(terrain)
        facility = gs.grid[u.y][u.x].get("facility")

        if facility and facility.player_id == pid:
            return {"unit_idx": ui, "type": "produce"}
        if buildable and not facility:
            return {"unit_idx": ui, "type": "build"}

        best, best_d = None, 999
        for y in range(gs.size):
            for x in range(gs.size):
                b = terrain_buildable(get_terrain(gs.grid, x, y))
                if not b:
                    continue
                if gs.grid[y][x].get("facility"):
                    continue
                d = _td(u.x, x, gs.size) + _td(u.y, y, gs.size)
                if d < best_d:
                    best_d = d
                    best = (x, y)
        if best:
            from prototype.ai_dqn import _move_to
            return _move_to(u, ui, gs, best, rng)
        return {"unit_idx": ui, "type": "end_turn"}

    def finish_game(self, won: bool):
        """游戏结束后, 用最终奖励填充所有 transition。

        对每一步 (s,a,s'): 如果最终赢了 reward=+1, 输了 reward=-1。
        这是一种简化 (蒙特卡洛回报), 适合短游戏。
        """
        reward = 1.0 if won else -1.0
        result = []
        for state, action, next_state in self.transitions:
            result.append((state, action, reward, next_state, False))
        # 最后一步的 transition (最终状态 -> done)
        if self.last_state is not None:
            result.append((
                self.last_state.copy(),
                self.last_action,
                reward,
                None,
                True,
            ))
        self.transitions = []
        self.last_state = None
        self.last_action = None
        return result


# ── 单局游戏（训练版） ───────────────────────────


def play_training_game(agent: DQNAgent, opponent_func,
                       seed: int, size: int = SIZE,
                       max_turns: int = MAX_TURNS_LOCAL,
                       is_agent_p0: bool = True) -> tuple[bool, list]:
    """
    运行一局训练游戏, 返回 (agent_win, transitions).

    transitions: 由 TrainingWrapper 收集的 (s, a, r, s', done) 列表。
    """
    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng_agent = random.Random(seed)
    rng_opp = random.Random(seed + 1)

    # 创建训练包装器
    trainer = TrainingWrapper(agent, pid=0 if is_agent_p0 else 1)

    def agent_decide(gs, pid, rng):
        return trainer.decide(gs, pid, rng)

    while gs.winner is None and gs.turn < max_turns:
        if is_agent_p0:
            a0 = agent_decide(gs, 0, rng_agent)
            a1 = opponent_func(gs, 1, rng_opp)
        else:
            a0 = opponent_func(gs, 0, rng_opp)
            a1 = agent_decide(gs, 1, rng_agent)
        step_game(gs, a0, a1)

    agent_won = (gs.winner == (0 if is_agent_p0 else 1))
    transitions = trainer.finish_game(agent_won)
    return agent_won, transitions


# ── 单局游戏（测试版，简单） ─────────────────────


def play_test_game(ai0_func, ai1_func, seed: int, size: int = SIZE,
                   max_turns: int = MAX_TURNS_LOCAL) -> dict:
    """运行一局测试游戏, 返回结果字典"""
    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)

    while gs.winner is None and gs.turn < max_turns:
        a0 = ai0_func(gs, 0, rng0)
        a1 = ai1_func(gs, 1, rng1)
        step_game(gs, a0, a1)

    return {
        "seed": seed,
        "winner": gs.winner,
        "victory_type": gs.victory_type,
        "turns": gs.turn,
    }


# ── 测试: 对战 Greedy ─────────────────────────────


def test_vs_greedy(dqn_agent: DQNAgent, n_games: int = TEST_GAMES,
                   size: int = SIZE, max_turns: int = MAX_TURNS_LOCAL,
                   label: str = "") -> dict:
    """测试 DQN agent vs Greedy, 交替先手"""
    wins = 0
    games_played = 0
    game_results = []

    # 测试时不使用 epsilon 探索
    old_eps = dqn_agent.epsilon
    dqn_agent.epsilon = 0.0

    print(f"\n  Testing {label} vs Greedy ({n_games} games)...")

    for g in range(n_games):
        is_dqn_p0 = (g % 2 == 0)
        seed = SEED_OFFSET + 9000 + g

        def dqn_wrapper(gs, pid, rng):
            return dqn_decide(gs, pid, rng, dqn=dqn_agent)

        if is_dqn_p0:
            result = play_test_game(dqn_wrapper, greedy_decide, seed, size, max_turns)
            dqn_win = (result["winner"] == 0)
        else:
            result = play_test_game(greedy_decide, dqn_wrapper, seed, size, max_turns)
            dqn_win = (result["winner"] == 1)

        wins += 1 if dqn_win else 0
        games_played += 1
        game_results.append({
            "game": g,
            "seed": seed,
            "dqn_p0": is_dqn_p0,
            "dqn_win": dqn_win,
            "winner": result["winner"],
            "victory_type": result["victory_type"],
            "turns": result["turns"],
        })

        if (g + 1) % 50 == 0:
            wr = wins / games_played * 100
            print(f"    [{g+1}/{n_games}] current WR: {wr:.1f}%")

    # 恢复 epsilon
    dqn_agent.epsilon = old_eps

    winrate = wins / games_played
    mean, std = _mean_std([1.0 if r["dqn_win"] else 0.0 for r in game_results])
    ci = _ci95(winrate, games_played)

    print(f"  {label} vs Greedy: {wins}/{games_played} = {winrate*100:.1f}% "
          f"(std={std*100:.1f}%, CI95=+/-{ci*100:.1f}%)")

    return {
        "label": label,
        "wins": wins,
        "games": games_played,
        "winrate": winrate,
        "std": std,
        "ci95": ci,
        "results": game_results,
    }


# ── 训练一代 ─────────────────────────────────────


def train_generation(gen_id: int, opponent_func,
                     n_games: int = GAMES_PER_GEN,
                     size: int = SIZE,
                     max_turns: int = MAX_TURNS_LOCAL) -> DQNAgent:
    """
    训练第 gen_id 代 DQN.

    参数:
        gen_id: 代数 (1-based)
        opponent_func: 对手决策函数 (gs, pid, rng) -> list[dict]
        n_games: 训练局数
    """
    print(f"\n{'='*60}")
    print(f"  GENERATION {gen_id} Training")
    print(f"  Games: {n_games} | LR: {LR} | Gamma: {GAMMA}")
    print(f"  Epsilon: {EPSILON} -> {EPSILON_MIN} (decay={EPSILON_DECAY})")
    print(f"{'='*60}")

    # 创建全新 DQN agent
    agent = DQNAgent(
        n_features=N_FEATURES,
        n_actions=N_ACTIONS,
        learning_rate=LR,
        gamma=GAMMA,
        epsilon=EPSILON,
    )

    gen_start = time.time()
    total_wins = 0
    rolling_wins = []
    best_rolling_winrate = 0.0
    best_weights_path = EVAL_DIR / f"gen{gen_id}_best.json"
    total_transitions = 0

    for game_idx in range(n_games):
        # 交替先手
        is_agent_p0 = (game_idx % 2 == 0)
        seed = SEED_OFFSET + gen_id * 10000 + game_idx

        agent_won, transitions = play_training_game(
            agent, opponent_func, seed, size, max_turns, is_agent_p0,
        )

        # 将 transition 存入 agent 的回放缓冲区
        for s, a, r, ns, done in transitions:
            agent.store_experience(s, a, r, ns, done)

        total_transitions += len(transitions)
        rolling_wins.append(1.0 if agent_won else 0.0)
        if len(rolling_wins) > 100:
            rolling_wins.pop(0)
        total_wins += 1 if agent_won else 0

        # 定期训练
        if (game_idx + 1) % TRAIN_INTERVAL == 0:
            for _ in range(TRAIN_STEPS):
                agent.train(batch_size=BATCH_SIZE)

            # epsilon 衰减
            if agent.epsilon > EPSILON_MIN:
                agent.epsilon = max(EPSILON_MIN, agent.epsilon * EPSILON_DECAY)

        # 检查点保存 (按滚动胜率)
        if len(rolling_wins) >= 20:
            current_rolling = sum(rolling_wins) / len(rolling_wins)
            if current_rolling > best_rolling_winrate:
                best_rolling_winrate = current_rolling
                agent.save(str(best_weights_path))

        # 报告进度
        if (game_idx + 1) % 100 == 0:
            current_wr = total_wins / (game_idx + 1) * 100
            rolling_wr = sum(rolling_wins) / len(rolling_wins) * 100
            elapsed = time.time() - gen_start
            print(f"  Gen{gen_id} [{game_idx+1}/{n_games}] "
                  f"WR: {current_wr:.1f}% "
                  f"(roll100: {rolling_wr:.1f}%) "
                  f"eps: {agent.epsilon:.3f} "
                  f"buf: {len(agent.replay_buffer)} "
                  f"| {elapsed:.0f}s")

    # 最终训练 (多跑几步确保收敛)
    for _ in range(10):
        agent.train(batch_size=BATCH_SIZE)

    # 保存最终权重
    final_path = EVAL_DIR / f"gen{gen_id}_weights.json"
    agent.save(str(final_path))
    print(f"  Gen{gen_id} final weights saved to: {final_path}")

    gen_elapsed = time.time() - gen_start
    final_wr = total_wins / n_games * 100
    print(f"  Gen{gen_id} complete: {total_wins}/{n_games} = {final_wr:.1f}% "
          f"({gen_elapsed:.0f}s, {total_transitions} transitions)")

    return agent


# ── 对手工厂 ─────────────────────────────────────


def make_greedy_opponent():
    """返回贪心AI函数"""
    return greedy_decide


def load_dqn_opponent(weights_path: str):
    """加载 DQN 权重并返回固定对手函数"""
    opponent = DQNAgent(n_features=N_FEATURES, n_actions=N_ACTIONS)
    opponent.load(weights_path)
    # 冻结: 关闭探索
    opponent.epsilon = 0.0

    def opp_func(gs, pid, rng):
        return dqn_decide(gs, pid, rng, dqn=opponent)

    return opp_func


# ── 主流程 ───────────────────────────────────────


def main():
    print("=" * 70)
    print("  MINICIV SELF-PLAY TRAINING")
    print(f"  Generations: {N_GENERATIONS}")
    print(f"  Games per gen: {GAMES_PER_GEN}")
    print(f"  Test games per gen vs Greedy: {TEST_GAMES}")
    print(f"  Output dir: {EVAL_DIR}")
    print("=" * 70)

    all_agents = {}
    all_test_results = {}

    # ── Generation 1: Train vs Greedy ──────────────────
    print(f"\n{'#'*70}")
    print(f"  # GENERATION 1: Fresh DQN vs Greedy")
    print(f"  {'#'*70}")
    gen1_agent = train_generation(1, make_greedy_opponent(), GAMES_PER_GEN)
    all_agents[1] = gen1_agent

    gen1_weights = EVAL_DIR / "gen1_weights.json"

    # ── Generation 2: Train vs Gen1 ────────────────────
    if gen1_weights.exists():
        gen1_opponent = load_dqn_opponent(str(gen1_weights))
        print(f"\n{'#'*70}")
        print(f"  # GENERATION 2: Fresh DQN vs Gen1 (frozen)")
        print(f"  {'#'*70}")
        gen2_agent = train_generation(2, gen1_opponent, GAMES_PER_GEN)
        all_agents[2] = gen2_agent
    else:
        print(f"  ERROR: {gen1_weights} not found! Aborting Gen2.")
        return

    gen2_weights = EVAL_DIR / "gen2_weights.json"

    # ── Generation 3: Train vs Gen2 ────────────────────
    if gen2_weights.exists():
        gen2_opponent = load_dqn_opponent(str(gen2_weights))
        print(f"\n{'#'*70}")
        print(f"  # GENERATION 3: Fresh DQN vs Gen2 (frozen)")
        print(f"  {'#'*70}")
        gen3_agent = train_generation(3, gen2_opponent, GAMES_PER_GEN)
        all_agents[3] = gen3_agent
    else:
        print(f"  ERROR: {gen2_weights} not found! Aborting Gen3.")
        return

    # ── 测试所有代 vs Greedy ─────────────────────────
    print(f"\n{'='*70}")
    print(f"  FINAL EVALUATION: All Generations vs Greedy")
    print(f"  ({TEST_GAMES} games each, alternating first-move)")
    print(f"{'='*70}")

    for gen_id in [1, 2, 3]:
        agent = all_agents[gen_id]
        result = test_vs_greedy(agent, TEST_GAMES, label=f"Gen{gen_id}")
        all_test_results[gen_id] = result

    # ── 打印结果表格 ─────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print()
    print(f"  {'Generation':<14} {'Winrate':<10} {'StdDev':<10} {'CI95%':<10} {'Wins':<8} {'Games':<8}")
    print(f"  {'-'*14} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")

    for gen_id in [1, 2, 3]:
        r = all_test_results[gen_id]
        print(f"  {'Gen' + str(gen_id) + ' vs Greedy':<14} "
              f"{r['winrate']*100:<8.1f}%  "
              f"{r['std']*100:<8.1f}%  "
              f"+/-{r['ci95']*100:<7.1f}% "
              f"{r['wins']:<8} {r['games']:<8}")

    print()
    print(f"  Generation comparison (vs Greedy):")
    wr1 = all_test_results[1]["winrate"]
    wr2 = all_test_results[2]["winrate"]
    wr3 = all_test_results[3]["winrate"]
    std1 = all_test_results[1]["std"]
    std2 = all_test_results[2]["std"]
    std3 = all_test_results[3]["std"]

    print(f"    Gen1: {wr1*100:.1f}% +/-{std1*100:.1f}%")
    print(f"    Gen2: {wr2*100:.1f}% +/-{std2*100:.1f}%")
    print(f"    Gen3: {wr3*100:.1f}% +/-{std3*100:.1f}%")

    if wr3 > wr2 > wr1:
        print(f"\n  >>> VERDICT: Self-play produces progressive improvement! <<<")
        print(f"      Gen3 > Gen2 > Gen1 vs Greedy")
        print(f"      Improvement: Gen1={wr1*100:.1f}% -> Gen3={wr3*100:.1f}% "
              f"(+{(wr3-wr1)*100:+.1f}pp)")
    elif wr3 > wr2 or wr2 > wr1:
        print(f"\n  >>> PARTIAL: Some improvement, but not monotonic. <<<")
        print(f"      Gen1={wr1*100:.1f}% -> Gen2={wr2*100:.1f}% -> "
              f"Gen3={wr3*100:.1f}%")
    else:
        print(f"\n  >>> NEGATIVE: Self-play did NOT produce improvement. <<<")
        print(f"      Gen1={wr1*100:.1f}% -> Gen2={wr2*100:.1f}% -> "
              f"Gen3={wr3*100:.1f}%")
        print(f"      Later generations may be overfitting to earlier opponents.")

    # ── 保存汇总结果 ─────────────────────────────────
    summary = {
        "n_generations": N_GENERATIONS,
        "games_per_gen": GAMES_PER_GEN,
        "test_games": TEST_GAMES,
        "hyperparameters": {
            "lr": LR,
            "gamma": GAMMA,
            "epsilon_init": EPSILON,
            "epsilon_min": EPSILON_MIN,
            "epsilon_decay": EPSILON_DECAY,
            "batch_size": BATCH_SIZE,
            "train_interval": TRAIN_INTERVAL,
            "train_steps": TRAIN_STEPS,
            "n_features": N_FEATURES,
            "n_actions": N_ACTIONS,
        },
        "generations": {},
    }

    for gen_id in [1, 2, 3]:
        r = all_test_results[gen_id]
        summary["generations"][f"gen{gen_id}"] = {
            "winrate": r["winrate"],
            "std": r["std"],
            "ci95": r["ci95"],
            "wins": r["wins"],
            "games": r["games"],
        }

    summary_path = EVAL_DIR / "selfplay_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary saved to: {summary_path}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
