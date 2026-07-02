"""
experiments/v0.5.0/map-size-comparison/run.py
地图尺寸对比实验: 15×15 vs 30×30
同一组 AI 在两个尺寸上对比，判断尺寸对游戏深度的影响。

指标: AI Elo spread, 征服/建设/阶梯比例, 平均回合, P0胜率
"""
import json, math, os, random, sys, time

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 实验参数
SIZES = [15, 30]
GAMES_PER_PAIR = 500
AI_PAIRS = [
    ("random", "random"),     # 先手基线
    ("random", "greedy"),     # 能力区分
    ("greedy", "greedy"),     # 镜像深度
]
GEN = "balanced"
MAX_TURNS = 100
BASE_SEED = 42

from prototype.game import init_game, step_game
from prototype.eval import load_ai


def _td(a, b, s):
    return min(abs(b - a), s - abs(b - a))


def run_paired(ai_a_name, ai_b_name, size, games, start_seed):
    """Paired 评估: 每个 seed 两局(P0/P1交换), 返回汇总。"""
    ai_a = load_ai(ai_a_name)
    ai_b = load_ai(ai_b_name)

    a_wins = 0
    p0_wins = 0
    conquests = 0
    constructions = 0
    all_turns = []
    game_count = games * 2

    print(f"    {ai_a_name} vs {ai_b_name} {size}x{size} ({games} seeds)...", end=" ", flush=True)
    t0 = time.perf_counter()

    for g in range(games):
        seed = start_seed + g * 1000
        rng0 = random.Random(seed)
        rng1 = random.Random(seed + 1)

        # Game 1: ai_a=P0, ai_b=P1
        gs = init_game(seed=seed, size=size, generator_id=GEN)
        while gs.winner is None and gs.turn < MAX_TURNS:
            step_game(gs, ai_a(gs, 0, rng0), ai_b(gs, 1, rng1))
        all_turns.append(gs.turn)
        if gs.winner == 0:
            a_wins += 1
            p0_wins += 1
        elif gs.winner == 1:
            pass  # b wins
        if gs.victory_type == "conquest":
            conquests += 1
        elif gs.victory_type == "construction":
            constructions += 1

        # Game 2: ai_a=P1, ai_b=P0
        rng0_2 = random.Random(seed + 2_000_000)
        rng1_2 = random.Random(seed + 2_000_001)
        gs2 = init_game(seed=seed, size=size, generator_id=GEN)
        while gs2.winner is None and gs2.turn < MAX_TURNS:
            step_game(gs2, ai_b(gs2, 0, rng0_2), ai_a(gs2, 1, rng1_2))
        all_turns.append(gs2.turn)
        if gs2.winner == 1:
            a_wins += 1
        if gs2.winner == 0:
            p0_wins += 1
        if gs2.victory_type == "conquest":
            conquests += 1
        elif gs2.victory_type == "construction":
            constructions += 1

    elapsed = time.perf_counter() - t0
    a_wr = a_wins / game_count
    p0_wr = p0_wins / game_count
    tiebreaks = game_count - conquests - constructions

    result = {
        "ai_a": ai_a_name, "ai_b": ai_b_name,
        "size": size,
        "seeds": games, "games": game_count,
        "ai_a_winrate": round(a_wr, 4),
        "ai_b_winrate": round(1 - a_wr, 4),
        "p0_winrate": round(p0_wr, 4),
        "conquest_rate": round(conquests / game_count, 4),
        "construction_rate": round(constructions / game_count, 4),
        "tiebreak_rate": round(tiebreaks / game_count, 4),
        "avg_turns": round(sum(all_turns) / len(all_turns), 1),
        "elapsed_s": round(elapsed, 1),
        "games_per_second": round(game_count / elapsed, 1) if elapsed > 0 else 0,
    }
    print(f"{elapsed:.0f}s (a_wr={a_wr*100:.1f}%, p0={p0_wr*100:.1f}%)")
    return result


def main():
    total_pairs = len(SIZES) * len(AI_PAIRS)
    pair_idx = 0
    all_results = []

    print("=" * 70)
    print("  MAP SIZE COMPARISON: 15x15 vs 30x30")
    print(f"  Pairs: {len(AI_PAIRS)} x {len(SIZES)} sizes = {total_pairs} runs")
    print(f"  Games per run: {GAMES_PER_PAIR} seeds x2 (paired) = {GAMES_PER_PAIR * 2}")
    print(f"  Total: {total_pairs * GAMES_PER_PAIR * 2} games")
    print("=" * 70)
    print()

    for size in SIZES:
        print(f"[{size}x{size}]")
        for ai_a, ai_b in AI_PAIRS:
            pair_idx += 1
            print(f"  [{pair_idx}/{total_pairs}]", end="")
            r = run_paired(ai_a, ai_b, size, GAMES_PER_PAIR,
                          BASE_SEED + pair_idx * 10000)
            all_results.append(r)

            # 中间保存
            with open(os.path.join(OUTPUT_DIR, "results.json"), "w") as f:
                json.dump(all_results, f, indent=2)
        print()

    # 汇总报告
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    for size in SIZES:
        size_results = [r for r in all_results if r["size"] == size]
        print(f"\n## {size}x{size}")
        print(f"{'Matchup':>20s} | {'A_WR':>7s} | {'P0_WR':>7s} | {'Conq':>6s} | {'Cons':>6s} | {'Tie':>6s} | {'Turns':>6s} | {'Spd':>7s}")
        print("-" * 90)
        for r in size_results:
            print(f"  {r['ai_a'] + ' vs ' + r['ai_b']:>18s} | "
                  f"{r['ai_a_winrate']*100:>6.1f}% | "
                  f"{r['p0_winrate']*100:>6.1f}% | "
                  f"{r['conquest_rate']*100:>5.1f}% | "
                  f"{r['construction_rate']*100:>5.1f}% | "
                  f"{r['tiebreak_rate']*100:>5.1f}% | "
                  f"{r['avg_turns']:>5.1f} | "
                  f"{r['games_per_second']:>5.1f}/s")

    # 生成 report.md
    lines = []
    lines.append("# 地图尺寸对比实验")
    lines.append("")
    lines.append(f"**日期**: 2026-07-02")
    lines.append(f"**每对**: {GAMES_PER_PAIR} seeds × 2 (paired)")
    lines.append(f"**总游戏数**: {total_pairs * GAMES_PER_PAIR * 2}")
    lines.append("")

    for size in SIZES:
        size_results = [r for r in all_results if r["size"] == size]
        lines.append(f"## {size}×{size}")
        lines.append("")
        lines.append("| Matchup | A Winrate | P0 Winrate | Conquest | Construction | Tiebreak | Avg Turns |")
        lines.append("|---------|-----------|------------|----------|-------------|----------|-----------|")
        for r in size_results:
            lines.append(f"| {r['ai_a']} vs {r['ai_b']} | "
                        f"{r['ai_a_winrate']*100:.1f}% | "
                        f"{r['p0_winrate']*100:.1f}% | "
                        f"{r['conquest_rate']*100:.1f}% | "
                        f"{r['construction_rate']*100:.1f}% | "
                        f"{r['tiebreak_rate']*100:.1f}% | "
                        f"{r['avg_turns']:.1f} |")
        lines.append("")

    # 对比分析
    lines.append("## 对比分析")
    lines.append("")
    for ai_a, ai_b in AI_PAIRS:
        r15 = next(r for r in all_results if r["size"] == 15 and r["ai_a"] == ai_a and r["ai_b"] == ai_b)
        r30 = next(r for r in all_results if r["size"] == 30 and r["ai_a"] == ai_a and r["ai_b"] == ai_b)
        lines.append(f"### {ai_a} vs {ai_b}")
        lines.append("")
        lines.append(f"| 指标 | 15×15 | 30×30 | 变化 |")
        lines.append(f"|------|-------|-------|------|")
        for key, label in [("conquest_rate", "征服率"), ("construction_rate", "建设率"),
                           ("tiebreak_rate", "阶梯率"), ("avg_turns", "平均回合"),
                           ("p0_winrate", "P0胜率"), ("ai_a_winrate", f"{ai_a}胜率")]:
            v15 = r15[key] * 100 if "rate" in key else r15[key]
            v30 = r30[key] * 100 if "rate" in key else r30[key]
            delta = v30 - v15
            lines.append(f"| {label} | {v15:.1f}{'%' if 'rate' in key else ''} | "
                        f"{v30:.1f}{'%' if 'rate' in key else ''} | "
                        f"{delta:+.1f}{'pp' if 'rate' in key else ''} |")
        lines.append("")

    lines.append("## 结论")
    lines.append("")
    lines.append("(实验运行后填写)")
    lines.append("")

    with open(os.path.join(OUTPUT_DIR, "report.md"), "w") as f:
        f.write("\n".join(lines))

    print(f"\nResults saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
