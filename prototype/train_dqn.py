# prototype/train_dqn.py — DQN 深度 Q 网络自对弈训练
# 通过 self-play 训练 DQN agent, 然后 vs Random / Greedy 验证
#
# 用法: python -m prototype.train_dqn
#
# 流程:
#   1. DQN vs DQN 或 DQN vs Random (50% 概率) 训练 2000 盘
#   2. 经验回放 + 每 10 盘 mini-batch 训练
#   3. 保存最优权重
#   4. DQN vs Random 500 盘 / DQN vs Greedy 200 盘 验证

import json, math, os, random as _random, sys, time
from pathlib import Path

from prototype.game import init_game, step_game
from prototype.ai_dqn import DQNAgent, ai_decide as dqn_decide
from prototype.ai_dqn import _extract_features as compute_features
from prototype.ai_rulesrandom import ai_decide as random_decide
from prototype.ai_greedy import ai_decide as greedy_decide
from prototype.eval import run_one_game

# ─── 配置 ──────────────────────────────────────────
TRAINING_GAMES = 2000
EVAL_VS_RANDOM = 500
EVAL_VS_GREEDY = 200
REPLAY_CAPACITY = 2000
TRAIN_INTERVAL = 10     # 每 N 盘训练一次
BATCH_SIZE = 32
GAMMA = 0.99            # 折扣因子
LEARNING_RATE = 0.0001
SEED = 42
SIZE = 15
MAX_TURNS = 100
N_FEATURES = 25          # ai_dqn 实际输出 25 个特征
N_ACTIONS = 6

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "eval_paradigms"
BEST_WEIGHTS_PATH = OUTPUT_DIR / "dqn_best_weights.json"


def _init_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _make_dqn_decider(dqn: DQNAgent, pid: int):
    """返回一个闭包, 用 DQN agent 决策, pid 始终为 0 以便 DQN 视角固定."""
    def decider(gs, _pid, rng):
        return dqn_decide(gs, pid, rng, dqn=dqn)
    return decider


# ─── 经验回放缓冲区 ────────────────────────────────

class ReplayBuffer:
    """环形缓冲区, 存储 (state, action, reward, next_state, done) 五元组."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer = []
        self.pos = 0

    def push(self, state, action, reward, next_state, done):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.pos] = (state, action, reward, next_state, done)
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size: int):
        """随机采样 batch_size 个样本."""
        return _random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def __len__(self):
        return len(self.buffer)


# ─── 单局训练游戏 ─────────────────────────────────

def play_one_game(dqn: DQNAgent, use_selfplay: bool,
                  rng_gen: _random.Random, seed: int,
                  size: int = SIZE, max_turns: int = MAX_TURNS) -> tuple[list, int]:
    """
    DQN 作为 P0, 对手为 P1, 进行一局游戏.
    收集本局所有经验, 用 DQNAgent.store_experience 逐条存入.

    返回:
        transitions_count: 本局产生的经验条数
        winner: 0 (DQN 胜), 1 (对手胜), None (平局)
    """
    gs = init_game(seed=seed, size=size, generator_id="balanced")
    rng0 = _random.Random(seed)
    rng1 = _random.Random(seed + 1)

    # 对手决策函数
    if use_selfplay:
        opp_decider = _make_dqn_decider(dqn, 0)
    else:
        opp_decider = random_decide

    transitions_this_game = []  # 暂存本局经验

    while gs.winner is None and gs.turn < max_turns:
        state = compute_features(gs, 0)

        # DQN 决策
        raw_actions = dqn_decide(gs, 0, rng0, dqn=dqn)
        # 用 epsilon-greedy 选择 action index (用 agent 内置的 act 方法)
        action_idx = dqn.act(state, epsilon_greedy=True, legal_actions=None, rng=rng0)

        # 对手决策
        action_p1 = opp_decider(gs, 1, rng1)

        # 执行一步
        step_game(gs, raw_actions, action_p1)

        # 下一状态
        next_state = compute_features(gs, 0)

        done = gs.winner is not None or gs.turn >= max_turns
        transitions_this_game.append((state, action_idx, 0.0, next_state, done))

    winner = gs.winner

    # ─── 终局回填奖励 ───
    if winner == 0:
        game_reward = 1.0
    elif winner == 1:
        game_reward = -1.0
    else:
        game_reward = 0.0

    survival_bonus = 0.01 * gs.turn
    total_reward = game_reward + survival_bonus

    # 将所有经验存入 replay buffer (用终局奖励回填)
    for state, action, _, next_state, done in transitions_this_game:
        dqn.store_experience(state, action, total_reward, next_state, done)

    return len(transitions_this_game), winner


# ─── 训练核心 ─────────────────────────────────────

def train_dqn() -> DQNAgent:
    """主训练循环."""
    print("=" * 60)
    print("MiniCiv DQN Training")
    print(f"  Training games: {TRAINING_GAMES}")
    print(f"  Replay capacity: {REPLAY_CAPACITY}")
    print(f"  Train interval: every {TRAIN_INTERVAL} games")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Gamma: {GAMMA}")
    print(f"  LR: {LEARNING_RATE}")
    print(f"  Features: {N_FEATURES}, Actions: {N_ACTIONS}")
    print("=" * 60)

    dqn = DQNAgent(
        n_features=N_FEATURES,
        n_actions=N_ACTIONS,
        learning_rate=LEARNING_RATE,
        gamma=GAMMA,
        epsilon=0.3,
        replay_capacity=REPLAY_CAPACITY,
    )
    rng = _random.Random(SEED)

    best_winrate = 0.0
    recent_wins = []  # sliding window for tracking winrate
    games_since_train = 0

    for game_idx in range(TRAINING_GAMES):
        seed = SEED + game_idx * 1000
        use_selfplay = rng.random() < 0.5

        n_transitions, winner = play_one_game(dqn, use_selfplay, rng, seed)
        games_since_train += 1

        recent_wins.append(1 if winner == 0 else 0)
        if len(recent_wins) > 100:
            recent_wins.pop(0)

        # 每 TRAIN_INTERVAL 盘训练一次
        loss = 0.0
        if games_since_train >= TRAIN_INTERVAL and len(dqn.replay_buffer) >= BATCH_SIZE:
            loss = dqn.train(batch_size=BATCH_SIZE)
            games_since_train = 0

            # 评价当前表现（滑动窗口 ~100 盘）
            current_winrate = sum(recent_wins) / len(recent_wins)
            if current_winrate > best_winrate:
                best_winrate = current_winrate
                _save_weights(dqn, best_winrate)

            opp_label = "self" if use_selfplay else "random"
            print(
                f"Game {game_idx+1:4d}/{TRAINING_GAMES} | "
                f"opp={opp_label:6s} | "
                f"winner={'DQN' if winner == 0 else ('OPP' if winner == 1 else 'TIE'):3s} | "
                f"turns={n_transitions:2d} | "
                f"loss={loss:.4f} | "
                f"winrate100={current_winrate*100:.1f}% | "
                f"best={best_winrate*100:.1f}% | "
                f"buf={len(dqn.replay_buffer)}"
            )

    # 确保最后一轮保存
    _save_weights(dqn, best_winrate)
    print(f"\nTraining complete. Best winrate: {best_winrate*100:.1f}%")
    return dqn


def _save_weights(dqn: DQNAgent, winrate: float):
    """保存 DQN 权重到 JSON 文件, 用 DQNAgent.save + 附加 winrate."""
    _init_output_dir()
    # 先用 agent.save 存到临时文件, 再嵌入 winrate
    import tempfile
    tmp = OUTPUT_DIR / "_tmp_weights.json"
    dqn.save(str(tmp))
    with open(tmp, "r") as f:
        data = json.load(f)
    data["best_winrate"] = winrate
    with open(BEST_WEIGHTS_PATH, "w") as f:
        json.dump(data, f, indent=2)
    if tmp.exists():
        tmp.unlink()


def _load_best_weights() -> DQNAgent | None:
    """从 JSON 加载最佳权重, 返回 DQNAgent."""
    if not BEST_WEIGHTS_PATH.exists():
        return None
    dqn = DQNAgent(n_features=N_FEATURES, n_actions=N_ACTIONS)
    dqn.load(str(BEST_WEIGHTS_PATH))
    return dqn


# ─── 验证 ──────────────────────────────────────────

def _compute_stats(results: list[dict]) -> dict:
    """从 run_one_game 的结果列表中计算统计量."""
    n = len(results)
    dqn_wins = sum(1 for r in results if r["winner"] == 0)
    opp_wins = sum(1 for r in results if r["winner"] == 1)
    ties = n - dqn_wins - opp_wins
    winrate = dqn_wins / n
    # 二项分布标准差: sqrt(p*(1-p)/n)
    stddev = math.sqrt(winrate * (1 - winrate) / n) * 100  # in percentage points
    avg_turns = sum(r["turns"] for r in results) / n
    return {
        "games": n,
        "dqn_wins": dqn_wins,
        "opp_wins": opp_wins,
        "ties": ties,
        "winrate_pct": winrate * 100,
        "stddev_pct": stddev,
        "avg_turns": avg_turns,
    }


def _run_eval_series(dqn: DQNAgent, opponent_func, label: str,
                     n_games: int, rng_seed_offset: int):
    """运行一系列评估游戏, 支持 variance rule 自动翻倍."""
    dqn_decider = _make_dqn_decider(dqn, 0)
    n = n_games

    while True:
        print(f"\n--- DQN vs {label} ({n} games) ---")
        results = []
        rng = _random.Random(SEED + rng_seed_offset)
        for i in range(n):
            seed = rng.randint(0, 2_000_000_000)
            if (i + 1) % 100 == 0:
                print(f"  Game {i+1}/{n}...")
            r = run_one_game(seed, dqn_decider, opponent_func,
                             size=SIZE, max_turns=MAX_TURNS)
            results.append(r)

        stats = _compute_stats(results)
        print(f"  DQN winrate: {stats['dqn_wins']}/{stats['games']} "
              f"({stats['winrate_pct']:.1f}%)")
        print(f"  StdDev: {stats['stddev_pct']:.2f}%")
        print(f"  Avg turns: {stats['avg_turns']:.1f}")

        if stats["stddev_pct"] > 5.0:
            print(f"  StdDev > 5%, doubling games to {n * 2}")
            n *= 2
        else:
            break

    return {"stats": stats, "detailed": results}


def run_validation(dqn: DQNAgent):
    """运行验证: DQN vs Random 和 DQN vs Greedy."""
    print("\n" + "=" * 60)
    print("Validation Phase")
    print("=" * 60)

    all_results = {}

    # DQN vs Random
    vs_random = _run_eval_series(dqn, random_decide, "Random",
                                 EVAL_VS_RANDOM, rng_seed_offset=9999)
    all_results["vs_random"] = vs_random

    # DQN vs Greedy
    vs_greedy = _run_eval_series(dqn, greedy_decide, "Greedy",
                                 EVAL_VS_GREEDY, rng_seed_offset=8888)
    all_results["vs_greedy"] = vs_greedy

    # 保存验证结果摘要
    _init_output_dir()
    summary_path = OUTPUT_DIR / "dqn_eval_results.json"
    summary = {}
    for key in ("vs_random", "vs_greedy"):
        s = all_results[key]["stats"]
        summary[key] = {
            "games": s["games"],
            "dqn_wins": s["dqn_wins"],
            "opp_wins": s["opp_wins"],
            "ties": s["ties"],
            "winrate_pct": round(s["winrate_pct"], 2),
            "stddev_pct": round(s["stddev_pct"], 2),
            "avg_turns": round(s["avg_turns"], 1),
        }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nValidation results saved to: {summary_path}")

    return all_results


# ─── 主入口 ────────────────────────────────────────

def main():
    _init_output_dir()

    # 训练
    dqn = train_dqn()

    # 验证: 加载最佳权重
    best_dqn = _load_best_weights()
    if best_dqn is None:
        print("WARNING: No saved weights found, using last agent for validation.")
        best_dqn = dqn

    # 验证
    run_validation(best_dqn)

    print("\nDone!")


if __name__ == "__main__":
    main()
