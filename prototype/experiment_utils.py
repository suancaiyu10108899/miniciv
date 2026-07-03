# prototype/experiment_utils.py — 实验工具函数
# 自动注入参数快照、格式验证、标准指标计算

import json, os, math
from collections import defaultdict


def inject_config_snapshot() -> dict:
    """从 constants.py 自动抓取完整参数快照。
    返回 {"source": "...", "values": {...}}。
    调用时机：实验脚本运行开始时。
    """
    from prototype import constants as c
    values = {}

    # 棋盘
    values["MAP_SIZES"] = list(c.MAP_SIZES)
    values["DEFAULT_SIZE"] = c.DEFAULT_SIZE
    values["MAX_TURNS"] = c.MAX_TURNS

    # 地形比例（只取 balanced 的值）
    if "balanced" in c.GENERATOR_RATIOS:
        ratios = c.GENERATOR_RATIOS["balanced"]
        values["GENERATOR_RATIOS"] = {
            "plain": ratios[0], "forest": ratios[1],
            "mountain": ratios[2], "water": ratios[3]
        }

    # 城市
    values["CITY_HP"] = c.CITY_HP
    values["CITY_DEF"] = c.CITY_DEF
    values["CITY_DAMAGE"] = c.CITY_DAMAGE
    values["CITY_BASE_FOOD"] = c.CITY_BASE_FOOD

    # 经济
    values["STARTING_RESOURCES"] = dict(c.STARTING_RESOURCES)
    values["STARTING_UNITS"] = dict(c.STARTING_UNITS)
    values["FACILITY_OUTPUT"] = {
        k: dict(v) for k, v in c.FACILITY_OUTPUT.items()
    }

    # 科技
    values["CONSTRUCTION_VICTORY_REQUIRE_FACILITIES"] = c.CONSTRUCTION_VICTORY_REQUIRE_FACILITIES

    # 战斗
    values["CAVALRY_CHARGE_BONUS"] = c.CAVALRY_CHARGE_BONUS

    return {"source": "auto-injected from prototype/constants.py", "values": values}


def validate_experiment_output(data: dict) -> list[str]:
    """检查实验输出是否符合 EXPERIMENT-FORMAT v1.0。
    返回错误列表。空列表 = 合规。
    """
    errors = []

    # schema_version
    if "schema_version" not in data:
        errors.append("missing schema_version")
    elif data["schema_version"] != "1.0":
        errors.append(f"unknown schema_version: {data['schema_version']}")

    # experiment
    exp = data.get("experiment", {})
    if "id" not in exp:
        errors.append("missing experiment.id")
    if "date" not in exp:
        errors.append("missing experiment.date")

    # config_snapshot
    if "config_snapshot" not in data:
        errors.append("missing config_snapshot")
    elif "values" not in data.get("config_snapshot", {}):
        errors.append("config_snapshot missing values")

    # results
    results = data.get("results", {})
    if "summary" not in results:
        errors.append("missing results.summary")
    if "_fields" not in results:
        errors.append("missing results._fields (self-describing field metadata)")
    else:
        # Check that summary keys are described in _fields
        fields = results["_fields"]
        for key in results.get("summary", {}):
            if key not in fields and key not in ("total_games",):
                errors.append(f"results.summary.{key} not described in _fields")

    # per_game is optional but if present, check it
    if "per_game" in results and results["per_game"]:
        pg0 = results["per_game"][0]
        for key in pg0:
            if key not in results.get("_fields", {}):
                errors.append(f"results.per_game[0].{key} not described in _fields")

    return errors


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def compute_standard_metrics(results: list[dict], ai_names: list[str] | None = None) -> dict:
    """计算 L1 + L2 标准指标。

    results: list of per-game result dicts. Each must have:
        - winner: int | None
        - victory_type: str | None
        - turns: int
        - p0_dead: int, p1_dead: int
        - p0_facilities: int, p1_facilities: int
        - p0_construction: int, p1_construction: int
        - _tag: "forward" | "backward" (for paired analysis)
        - _ai0: str, _ai1: str

    Returns dict with L1 and L2 metrics plus _fields metadata.
    """
    n = len(results)
    if n == 0:
        return {"summary": {}, "_fields": {}}

    forward = [r for r in results if r.get("_tag") == "forward"]
    back = [r for r in results if r.get("_tag") == "backward"]

    # ─── L1: Core metrics ───
    p0_wins = sum(1 for r in results if r["winner"] == 0)
    p0_wr = p0_wins / n

    # P0 CI95
    if n > 0:
        p0_std = _stddev([1.0 if r["winner"] == 0 else 0.0 for r in results])
        p0_ci95 = 1.96 * p0_std / math.sqrt(n)
    else:
        p0_std = 0.0
        p0_ci95 = 0.0

    vtypes = [r.get("victory_type", "") or "" for r in results]
    conquest = sum(1 for v in vtypes if v == "conquest")
    construction = sum(1 for v in vtypes if v == "construction")
    tiebreak = sum(1 for v in vtypes if v and v.startswith("tiebreak"))
    avg_turns = sum(r["turns"] for r in results) / n

    # ─── AI-specific winrates ───
    ai_wins = defaultdict(int)
    ai_games = defaultdict(int)
    if ai_names:
        for tag, ai0, ai1 in [(r.get("_tag"), r.get("_ai0"), r.get("_ai1")) for r in results]:
            if tag == "forward":
                if r["winner"] == 0:
                    ai_wins[ai0] += 1
                elif r["winner"] == 1:
                    ai_wins[ai1] += 1
                ai_games[ai0] += 1
                ai_games[ai1] += 1
            elif tag == "backward":
                if r["winner"] == 0:
                    ai_wins[ai1] += 1
                elif r["winner"] == 1:
                    ai_wins[ai0] += 1
                ai_games[ai0] += 1
                ai_games[ai1] += 1

    # ─── L2: Standard metrics ───
    avg_dead = sum(r.get("p0_dead", 0) + r.get("p1_dead", 0) for r in results) / n

    # Per-P0 and Per-P1 averages
    p0_facs = [r.get("p0_facilities", 0) for r in results]
    p1_facs = [r.get("p1_facilities", 0) for r in results]
    p0_cons = [r.get("p0_construction", 0) for r in results]
    p1_cons = [r.get("p1_construction", 0) for r in results]

    summary = {
        "total_games": n,
        "p0_winrate": round(p0_wr, 4),
        "p0_std": round(p0_std, 4),
        "p0_ci95": round(p0_ci95, 4),
        "conquest_rate": round(conquest / n, 4),
        "construction_rate": round(construction / n, 4),
        "tiebreak_rate": round(tiebreak / n, 4),
        "avg_turns": round(avg_turns, 1),
        "avg_dead": round(avg_dead, 1),
        "avg_facilities_P0": round(sum(p0_facs) / n, 2) if n else 0,
        "avg_facilities_P1": round(sum(p1_facs) / n, 2) if n else 0,
        "avg_construction_P0": round(sum(p0_cons) / n, 2) if n else 0,
        "avg_construction_P1": round(sum(p1_cons) / n, 2) if n else 0,
    }

    # Per-AI winrates
    for ai_name in (ai_names or []):
        if ai_games[ai_name] > 0:
            summary[f"winrate_{ai_name}"] = round(ai_wins[ai_name] / ai_games[ai_name], 4)

    # ─── _fields metadata ───
    _fields = {
        "total_games":     {"level": "L1", "type": "int", "description": "总局数", "source": "auto-computed"},
        "p0_winrate":      {"level": "L1", "type": "float", "range": [0.0, 1.0], "description": "P0胜率 (paired模式下P0偏差)", "source": "auto-computed"},
        "p0_std":          {"level": "L1", "type": "float", "description": "P0胜率标准差", "source": "auto-computed"},
        "p0_ci95":         {"level": "L1", "type": "float", "description": "P0胜率95%置信区间半宽", "source": "auto-computed"},
        "conquest_rate":   {"level": "L1", "type": "float", "range": [0.0, 1.0], "description": "征服胜利占比", "source": "computed from victory_type"},
        "construction_rate": {"level": "L1", "type": "float", "range": [0.0, 1.0], "description": "建设胜利占比", "source": "computed from victory_type"},
        "tiebreak_rate":   {"level": "L1", "type": "float", "range": [0.0, 1.0], "description": "阶梯判定占比", "source": "computed from victory_type"},
        "avg_turns":       {"level": "L1", "type": "float", "description": "平均回合数", "source": "auto-computed"},
        "avg_dead":        {"level": "L2", "type": "float", "description": "平均死亡单位数(双方合计)", "source": "computed from p0_dead + p1_dead"},
        "avg_facilities_P0":{"level": "L2", "type": "float", "description": "P0平均设施数", "source": "computed from p0_facilities"},
        "avg_facilities_P1":{"level": "L2", "type": "float", "description": "P1平均设施数", "source": "computed from p1_facilities"},
        "avg_construction_P0":{"level": "L2", "type": "float", "description": "P0平均建设科技数", "source": "computed from p0_construction"},
        "avg_construction_P1":{"level": "L2", "type": "float", "description": "P1平均建设科技数", "source": "computed from p1_construction"},
    }

    for ai_name in (ai_names or []):
        key = f"winrate_{ai_name}"
        if key in summary:
            _fields[key] = {"level": "L2", "type": "float", "range": [0.0, 1.0],
                          "description": f"{ai_name}的配对胜率", "source": "auto-computed"}

    return {"summary": summary, "_fields": _fields}


def merge_experiments(experiments: list[dict]) -> dict:
    """跨实验聚合。读取每个实验的 _fields 做字段匹配。
    只聚合两个实验都有的 L1/L2 字段，L3 字段跳过。
    """
    if not experiments:
        return {}

    # Collect common L1/L2 fields
    common_fields = None
    for exp in experiments:
        fields = set()
        fmeta = exp.get("results", {}).get("_fields", {})
        for name, meta in fmeta.items():
            if meta.get("level") in ("L1", "L2"):
                fields.add(name)
        if common_fields is None:
            common_fields = fields
        else:
            common_fields &= fields

    if not common_fields:
        return {"error": "no common L1/L2 fields across experiments"}

    merged = {}
    for field in sorted(common_fields):
        values = []
        weights = []
        for exp in experiments:
            val = exp.get("results", {}).get("summary", {}).get(field)
            n = exp.get("results", {}).get("summary", {}).get("total_games", 0)
            if val is not None and n > 0:
                values.append(val)
                weights.append(n)
        if values:
            # Weighted average by number of games
            merged[field] = round(sum(v * w for v, w in zip(values, weights)) / sum(weights), 4)

    return merged
