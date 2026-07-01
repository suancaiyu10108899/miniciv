# prototype/ai_flash.py — DeepSeek Flash AI 对战 + 思考可见
# 每步调用 Flash API，返回决策 + 思考过程

import json, urllib.request, os

FLASH_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic") + "/v1/messages"
FLASH_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
FLASH_MODEL = "deepseek-v4-flash"


def _call_api(messages: list, max_tokens: int = 200, no_think: bool = False) -> dict:
    """调用 Flash API"""
    payload = {
        "model": FLASH_MODEL,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if no_think:
        payload["thinking"] = {"type": "disabled"}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(FLASH_URL, data=body,
        headers={"Content-Type": "application/json", "x-api-key": FLASH_KEY},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def ai_flash_decide(gs, pid: int, rng=None) -> list[dict]:
    """
    Flash AI 决策——每回合调用一次 API，为所有单位+城市决策。
    返回动作列表 + 可选的思考日志。
    """
    units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp = 1 - pid
    econ = gs.economies[pid]
    tech = gs.techs[pid]

    # 构建游戏状态
    state = {
        "you": f"P{pid}",
        "turn": gs.turn, "max_turns": 100,
        "resources": {"food": econ.food, "wood": econ.wood, "gold": econ.gold},
        "city_hp": gs.cities[pid].hp,
        "opponent_city_hp": gs.cities[opp].hp,
        "techs_completed": sorted(list(tech.completed)),
        "researching": tech.researching,
        "construction_progress": tech.construction_count(),
        "your_units": [
            {"idx": i, "type": u.unit_type, "x": u.x, "y": u.y, "hp": u.hp,
             "atk": u.atk, "def": u.def_}
            for i, u in enumerate(units)
        ],
        "enemy_units": [
            {"type": u.unit_type, "x": u.x, "y": u.y, "hp": u.hp}
            for u in gs.units if u.player_id == opp and u.alive
        ],
        "available_techs": tech.available_to_research(),
    }

    prompt = f"""You are playing miniciv, a turn-based strategy game. You are P{pid}.

## Game State
{json.dumps(state, indent=2)}

## Rules
- Each of your units can take ONE action this turn
- Valid actions per unit: {{"unit_idx": N, "type": "move", "dx":-1|0|1, "dy":-1|0|1}}
  Or: {{"unit_idx": N, "type": "build"}} (worker on buildable terrain, builds farm/lumbermill/mine)
  Or: {{"unit_idx": N, "type": "produce"}} (worker on existing facility)
  Or: {{"unit_idx": N, "type": "end_turn"}} (skip this unit)
- Workers (W): build facilities on matching terrain (plain→farm, forest→lumbermill, mountain→mine), then produce. Prioritize building all 3 facility types first.
- Scouts (S): explore toward enemy territory
- Combat units (I/C/A): move toward enemy city, attack adjacent enemies
- City production: {{"unit_idx": -1, "type": "produce_unit", "unit_type": "infantry"|"archer"|"cavalry"}}
- Research: {{"unit_idx": -1, "type": "research", "tech_id": "E1"|"M1"|...}}
- Infantry (I) cost food, Archer (A) cost food+wood, Cavalry (C) cost food+gold
- You can issue actions for ALL units plus ONE city action and ONE research action.

## Tech Tree
M1(+5ATK inf/arch)→M2(cav charge+5)/M3(inf def forest/mountain+10)→M4(all HP+10)
E1(farm food+1)→E2(lumbermill wood+1)/E3(mine gold+1)→E4(worker speed+1)
C1(unlock construction)→C2(city+100HP)/C3(research speed x2)→C4(city+2food)→C5(★construction victory)

Reply ONLY with JSON: {{"actions": [action_dicts...], "reasoning": "brief explanation of your strategy"}}"""

    messages = [
        {"role": "user", "content": prompt + "\n\n用中文回复。在JSON的reasoning字段中写出你的策略思考(≤300字)，actions字段列出所有动作。只输出JSON，不要其他内容。"},
    ]

    # 重试最多 3 次（API 可能返回不完整 JSON）
    for attempt in range(3):
        try:
            resp = _call_api(messages, max_tokens=500, no_think=True)
            # 提取 text（JSON 动作）和 thinking（思考过程）
            thinking = ""
            text = ""
            for c in resp.get("content", []):
                if c.get("type") == "thinking":
                    thinking += c.get("thinking", "")
                elif c.get("type") == "text":
                    text += c.get("text", "")

            tokens = resp.get("usage", {})
            # 只用 text 字段提取 JSON（thinking 里可能有 JSON 示例会干扰）
            source = text.strip()
            if not source:
                return {"actions": [], "reasoning": thinking[:500],
                       "_thinking": thinking, "_tokens": tokens,
                       "_raw_response": "(no text output)"}

            # 提取 JSON
            if "```json" in source:
                source = source.split("```json")[1].split("```")[0]
            elif "```" in source:
                parts = source.split("```")
                source = parts[1] if len(parts) > 1 else source
            brace_start = source.find("{")
            brace_end = source.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                source = source[brace_start:brace_end + 1]
            import re
            source = re.sub(r',\s*}', '}', source)
            source = re.sub(r',\s*]', ']', source)

            try:
                result = json.loads(source.strip())
            except json.JSONDecodeError:
                return {"actions": [], "reasoning": f"JSON parse fail: {source[:200]}",
                       "_thinking": thinking, "_tokens": tokens, "_raw_response": text}

            result["_tokens"] = tokens
            result["_thinking"] = thinking
            result["_raw_response"] = text.strip()
            return result


        except (json.JSONDecodeError, KeyError, IndexError) as e:
            if attempt == 2:
                return {"actions": [], "reasoning": f"API error: {e}", "_tokens": {}}
            continue

    return {"actions": [], "reasoning": "failed"}


def ai_flash_decide_simple(gs, pid: int, rng=None) -> list[dict]:
    """
    简化版——只返回动作列表（兼容现有 game loop）。
    思考过程通过 _last_flash_log 访问。
    """
    result = ai_flash_decide(gs, pid, rng)
    # 保存完整日志供回放
    if not hasattr(ai_flash_decide_simple, '_log'):
        ai_flash_decide_simple._log = []
    ai_flash_decide_simple._log.append({
        "turn": gs.turn,
        "pid": pid,
        "tokens": result.get("_tokens", {}),
        "reasoning": result.get("reasoning", ""),
        "raw": result.get("_raw_response", ""),
    })
    return result.get("actions", [])


def get_flash_log():
    """返回 Flash AI 决策日志"""
    return getattr(ai_flash_decide_simple, '_log', [])


def clear_flash_log():
    ai_flash_decide_simple._log = []
