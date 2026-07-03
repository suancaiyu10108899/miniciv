#!/usr/bin/env python
# scripts/save_replays.py — 从实验结果中选代表性对局，重新运行并保存 GameReplay JSON
#
# 用法:
#   python scripts/save_replays.py experiments/v0.5.0/facility-8-verify --per-pair 3
#
# 行为:
#   1. 读实验目录下的 paired_*.json 或 summary.json
#   2. 每对 AI 选 N 个代表性 seed（胜/负/中位回合）
#   3. 重新运行这些 seed 并收集 turn_snapshots
#   4. 保存 GameReplay JSON 到 replays/ 子目录
#   5. 生成 _index.json

import argparse, json, os, sys, random, time
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from prototype.game import init_game, step_game, export_replay
from prototype.eval import load_ai


def pick_representative_seeds(results, n_per_pair=3):
    """从一组 paired 结果中选代表性 seed。
    每个 seed 有 2 局（forward + backward），选 seed 而非单局。

    策略：
    1. 一个 ai_a 赢的 seed（ai_a_wins >= 1）
    2. 一个 ai_b 赢的 seed（ai_b_wins >= 1）
    3. 一个最接近中位回合数的 seed

    如果某种不存在，跳过。返回 [(seed, forward_result, backward_result), ...]
    """
    # Group by seed
    forward = [r for r in results if r.get("_tag") == "forward"]
    backward = [r for r in results if r.get("_tag") == "backward"]

    # Build seed -> (forward, backward) map
    seed_map = {}
    for r in forward:
        seed_map[r["seed"]] = {"forward": r}
    for r in backward:
        if r["seed"] in seed_map:
            seed_map[r["seed"]]["backward"] = r

    seeds = []
    for seed, data in seed_map.items():
        fwd = data.get("forward")
        bwd = data.get("backward")
        if fwd is None or bwd is None:
            continue
        # Determine who "won" this seed
        fwd_winner = fwd.get("winner")
        bwd_winner = bwd.get("winner")
        avg_turns = (fwd.get("turns", 0) + bwd.get("turns", 0)) / 2
        seeds.append({
            "seed": seed,
            "fwd_winner": fwd_winner,
            "bwd_winner": bwd_winner,
            "avg_turns": avg_turns,
            "ai_a_name": fwd.get("_ai0", "?"),
            "ai_b_name": fwd.get("_ai1", "?"),
        })

    if not seeds:
        return []

    ai_a_name = seeds[0]["ai_a_name"]
    ai_b_name = seeds[0]["ai_b_name"]

    selected = []
    used_seeds = set()

    # 1. ai_a winning seed (ai_a wins as P0 in forward OR as P1 in backward)
    ai_a_wins = [s for s in seeds
                 if (s["fwd_winner"] == 0) or (s["bwd_winner"] == 1)]
    if ai_a_wins:
        # Pick the one with median turns among ai_a wins
        ai_a_wins.sort(key=lambda s: s["avg_turns"])
        pick = ai_a_wins[len(ai_a_wins) // 2]
        selected.append(pick)
        used_seeds.add(pick["seed"])

    # 2. ai_b winning seed
    ai_b_wins = [s for s in seeds
                 if (s["fwd_winner"] == 1) or (s["bwd_winner"] == 0)]
    ai_b_wins = [s for s in ai_b_wins if s["seed"] not in used_seeds]
    if ai_b_wins:
        ai_b_wins.sort(key=lambda s: s["avg_turns"])
        pick = ai_b_wins[len(ai_b_wins) // 2]
        selected.append(pick)
        used_seeds.add(pick["seed"])

    # 3. Median turns overall
    remaining = [s for s in seeds if s["seed"] not in used_seeds]
    if remaining:
        remaining.sort(key=lambda s: s["avg_turns"])
        pick = remaining[len(remaining) // 2]
        selected.append(pick)
        used_seeds.add(pick["seed"])

    return selected[:n_per_pair]


def run_and_save_replay(ai_a, ai_b, seed, output_dir, size=15, gen="balanced", max_turns=100):
    """Run a game with turn snapshots and save as GameReplay JSON.
    Runs forward game (ai_a=P0, ai_b=P1).
    """
    gs = init_game(seed=seed, size=size, generator_id=gen)
    ai0_fn = load_ai(ai_a)
    ai1_fn = load_ai(ai_b)
    rng0 = random.Random(seed)
    rng1 = random.Random(seed + 1)

    while gs.winner is None and gs.turn < max_turns:
        step_game(gs, ai0_fn(gs, 0, rng0), ai1_fn(gs, 1, rng1))

    replay = export_replay(gs, seed=seed)

    # Filename with metadata
    winner_str = f"P{gs.winner}" if gs.winner is not None else "draw"
    vt = gs.victory_type or "unknown"
    fname = f"paired_{ai_a}_vs_{ai_b}_seed{seed}_{winner_str}_{vt}_t{gs.turn}.json"
    filepath = os.path.join(output_dir, fname)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(replay, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(filepath)
    return {
        "file": fname,
        "ai_a": ai_a, "ai_b": ai_b,
        "seed": seed,
        "winner": f"P{gs.winner}" if gs.winner is not None else "draw",
        "victory_type": vt,
        "turns": gs.turn,
        "size_kb": round(file_size / 1024, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_dir", help="Path to experiment directory with paired_*.json files")
    parser.add_argument("--per-pair", type=int, default=3, help="Replays per AI pair (default: 3)")
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--gen", default="balanced")
    args = parser.parse_args()

    exp_dir = Path(args.experiment_dir)
    if not exp_dir.exists():
        print(f"ERROR: directory not found: {exp_dir}")
        return 1

    # Find paired JSON files
    paired_files = sorted(exp_dir.glob("paired_*.json"))
    if not paired_files:
        print(f"ERROR: no paired_*.json files found in {exp_dir}")
        return 1

    # Filter out non-result files (like summary.json)
    paired_files = [f for f in paired_files if f.name != "summary.json"]

    # Create replays directory
    replays_dir = exp_dir / "replays"
    replays_dir.mkdir(exist_ok=True)

    index_entries = []
    total_start = time.time()

    for pf in paired_files:
        # Parse AI names from filename
        stem = pf.name.replace("paired_", "").replace(".json", "")
        parts = stem.split("_vs_")
        if len(parts) != 2:
            print(f"  SKIP {pf.name}: cannot parse AI names")
            continue
        ai_a, ai_b = parts[0], parts[1]

        # Load results
        with open(pf) as f:
            results = json.load(f)

        if not results:
            print(f"  SKIP {ai_a} vs {ai_b}: no results")
            continue

        # Pick representative seeds
        picks = pick_representative_seeds(results, args.per_pair)
        if not picks:
            print(f"  SKIP {ai_a} vs {ai_b}: cannot select representative seeds")
            continue

        print(f"  {ai_a} vs {ai_b}: saving {len(picks)} replays...")
        for pick in picks:
            entry = run_and_save_replay(
                ai_a, ai_b, pick["seed"],
                str(replays_dir),
                size=args.size, gen=args.gen
            )
            index_entries.append(entry)
            vt = entry["victory_type"]
            print(f"    seed={pick['seed']} {entry['winner']} {vt} "
                  f"t{entry['turns']} ({entry['size_kb']}KB)")

    # Save _index.json
    index_path = replays_dir / "_index.json"
    index_data = {
        "experiment_dir": str(exp_dir),
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "replays": index_entries,
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    total_elapsed = time.time() - total_start
    print(f"\nDone: {len(index_entries)} replays saved to {replays_dir}")
    print(f"Index: {index_path}")
    print(f"Time: {total_elapsed:.0f}s")

    # Quick stats
    victory_types = defaultdict(int)
    for e in index_entries:
        victory_types[e["victory_type"]] += 1
    print(f"Victory types: {dict(victory_types)}")


if __name__ == "__main__":
    main()
