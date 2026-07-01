# prototype/play.py — Human vs AI 命令行入口
# 用法: python -m prototype.play --human-pid 0

import argparse, random, sys
from prototype.game import init_game, step_game
from prototype.ai_rulesrandom import ai_decide
from prototype.render_ascii import render_map, render_status
from prototype.fow import init_fog, update_fog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=30)
    parser.add_argument("--gen", default="balanced")
    parser.add_argument("--human-pid", type=int, default=0)
    args = parser.parse_args()

    gs = init_game(seed=args.seed, size=args.size, generator_id=args.gen)
    fogs = init_fog(gs.size)
    update_fog(gs, fogs)
    human_pid = args.human_pid
    ai_pid = 1 - human_pid
    rng = random.Random(args.seed)

    print(f"=== miniciv — Human(P{human_pid}) vs AI(P{ai_pid}) ===")
    print(f"Map: {args.size}x{args.size} {args.gen}, seed={args.seed}")
    print(f"I=步兵 C=骑兵 A=弓 S=侦察 W=工人 (大写=P0,小写=P1)")
    print(f"f=农场 l=伐木场 m=矿山")

    while gs.winner is None and gs.turn < 100:
        print(f"\n{render_status(gs, human_pid)}")
        print(f"\n{render_map(gs, human_pid, fogs)}")

        # 人类动作
        human_actions = []
        human_units = [u for u in gs.units if u.player_id == human_pid and u.alive]
        for ui, u in enumerate(human_units):
            print(f"\n  [{_unit_label(u)}] @({u.x},{u.y}) HP={u.hp} — "
                  f"动作? wasd=移动 b=建造 p=生产 x=跳过 ")
            cmd = input("  > ").strip().lower()
            if cmd == "x" or cmd == "":
                human_actions.append({"unit_idx": ui, "type": "end_turn"})
            elif cmd in ("w", "s", "a", "d"):
                dirmap = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
                dx, dy = dirmap[cmd]
                human_actions.append({"unit_idx": ui, "type": "move", "dx": dx, "dy": dy})
            elif cmd == "b":
                human_actions.append({"unit_idx": ui, "type": "build"})
            elif cmd == "p":
                human_actions.append({"unit_idx": ui, "type": "produce"})
            else:
                human_actions.append({"unit_idx": ui, "type": "end_turn"})

        # 城市动作
        print(f"\n  城市: 资源 {gs.economies[human_pid].food}f {gs.economies[human_pid].wood}w {gs.economies[human_pid].gold}g")
        print(f"  生产? i=步兵 a=弓 c=骑 s=侦察 w=工人 回车=跳过")
        prod = input("  > ").strip().lower()
        pmap = {"i": "infantry", "a": "archer", "c": "cavalry", "s": "scout", "w": "worker"}
        if prod in pmap:
            human_actions.append({"unit_idx": -1, "type": "produce_unit", "unit_type": pmap[prod]})

        # 研究
        avail = gs.techs[human_pid].available_to_research()
        if avail and gs.techs[human_pid].researching is None:
            print(f"  可研究: {', '.join(avail)} (回车=跳过)")
            r = input("  > ").strip().upper()
            if r in avail:
                from prototype.game import TECH_TREE_COST
                cost = TECH_TREE_COST.get(r, (0, 0, 0))
                if gs.economies[human_pid].can_afford(cost):
                    human_actions.append({"unit_idx": -1, "type": "research", "tech_id": r})

        # AI 动作
        ai_actions = ai_decide(gs, ai_pid, rng)

        if human_pid == 0:
            step_game(gs, human_actions, ai_actions)
        else:
            step_game(gs, ai_actions, human_actions)

        update_fog(gs, fogs)

    # 终局
    print(f"\n{render_status(gs, human_pid)}")
    print(f"\n>>> 游戏结束: P{gs.winner} 胜 ({gs.victory_type})")


def _unit_label(u):
    t = {"infantry": "步", "cavalry": "骑", "archer": "弓",
         "scout": "侦", "worker": "工"}
    return f"P{u.player_id}{t.get(u.unit_type, '?')}"


if __name__ == "__main__":
    main()
