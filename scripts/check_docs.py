#!/usr/bin/env python
# scripts/check_docs.py — 检测 constants.py 和 GAME.md 之间的不一致
# 运行: python scripts/check_docs.py
#
# 检查项:
#   1. constants.py 中定义的关键数值是否在 GAME.md 中出现
#   2. GAME.md 中的数值是否和 constants.py 一致
#   3. GAME.md 的同步日期是否接近当前日期

import os, sys, re, json
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent

# ─── Parse constants.py ──────────────────────────────

def parse_constants():
    """从 constants.py 提取关键数值定义。返回 {name: value}。"""
    constants_file = ROOT / "prototype" / "constants.py"
    if not constants_file.exists():
        return {"_error": f"file not found: {constants_file}"}

    values = {}
    with open(constants_file, encoding="utf-8") as f:
        content = f.read()

    # Simple assignments: NAME = value
    patterns = [
        (r'^DEFAULT_SIZE\s*=\s*(\d+)', 'DEFAULT_SIZE', int),
        (r'^MAX_TURNS\s*=\s*(\d+)', 'MAX_TURNS', int),
        (r'^CITY_HP\s*=\s*(\d+)', 'CITY_HP', int),
        (r'^CITY_DEF\s*=\s*(\d+)', 'CITY_DEF', int),
        (r'^CITY_DAMAGE\s*=\s*(\d+)', 'CITY_DAMAGE', int),
        (r'^CITY_BASE_FOOD\s*=\s*(\d+)', 'CITY_BASE_FOOD', int),
        (r'^CAVALRY_CHARGE_BONUS\s*=\s*(\d+)', 'CAVALRY_CHARGE_BONUS', int),
        (r'^CONSTRUCTION_VICTORY_REQUIRE_FACILITIES\s*=\s*(\d+)',
         'CONSTRUCTION_VICTORY_REQUIRE_FACILITIES', int),
    ]

    for pattern, name, converter in patterns:
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            values[name] = converter(m.group(1))

    # STARTING_RESOURCES
    m = re.search(r'STARTING_RESOURCES\s*=\s*\{["\']food["\']:\s*(\d+),\s*["\']wood["\']:\s*(\d+),\s*["\']gold["\']:\s*(\d+)\}',
                  content)
    if m:
        values["STARTING_RESOURCES"] = {"food": int(m.group(1)), "wood": int(m.group(2)), "gold": int(m.group(3))}

    # STARTING_UNITS
    m = re.search(r'STARTING_UNITS\s*=\s*\{["\']worker["\']:\s*(\d+),\s*["\']scout["\']:\s*(\d+)\}', content)
    if m:
        values["STARTING_UNITS"] = {"worker": int(m.group(1)), "scout": int(m.group(2))}

    # FACILITY_OUTPUT
    m = re.search(r'FACILITY_OUTPUT\s*=\s*\{["\']farm["\']:\s*\{["\']food["\']:\s*(\d+)\}.*?["\']lumbermill["\']:\s*\{["\']wood["\']:\s*(\d+)\}.*?["\']mine["\']:\s*\{["\']gold["\']:\s*(\d+)\}',
                  content)
    if m:
        values["FACILITY_OUTPUT"] = {"farm_food": int(m.group(1)), "lumbermill_wood": int(m.group(2)), "mine_gold": int(m.group(3))}

    # UNIT_STATS (just check infantry exists)
    m = re.search(r'"infantry"\s*:\s*\{[^}]*"hp":\s*(\d+)[^}]*"atk":\s*(\d+)[^}]*"def":\s*(\d+)', content)
    if m:
        values["INFANTRY_HP"] = int(m.group(1))
        values["INFANTRY_ATK"] = int(m.group(2))
        values["INFANTRY_DEF"] = int(m.group(3))

    # TECH_TREE C5 cost
    m = re.search(r'"C5"\s*:\s*\{[^}]*"cost":\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
    if m:
        values["C5_COST"] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return values


# ─── Parse GAME.md ────────────────────────────────────

def parse_game_md():
    """从 GAME.md 提取关键数值。返回 {name: value_or_string}。"""
    game_md = ROOT / "docs" / "GAME.md"
    if not game_md.exists():
        return {"_error": f"file not found: {game_md}"}

    with open(game_md, encoding="utf-8") as f:
        content = f.read()

    values = {}

    # Extract sync date
    m = re.search(r'最后同步:\s*(\d{4}-\d{2}-\d{2})', content)
    if m:
        values["_sync_date"] = m.group(1)

    # Extract numeric values from tables and text
    checks = {
        "DEFAULT_SIZE": r'默认尺寸\s*\|\s*\*?\*?(\d+)\*?\*?',
        "MAX_TURNS": r'回合上限\s*\|\s*(\d+)',
        "CITY_HP": r'HP\s*\|\s*(\d+)',  # need more context
        "CITY_DEF": r'DEF\s*\|\s*(\d+)',
        "CITY_DAMAGE": r'防守伤害\s*\|\s*(\d+)',
        "CONSTRUCTION_VICTORY_REQUIRE_FACILITIES": r'[≥=]\s*`?[^`]*?`?\s*[（(]?当前[=＝]\s*(\d+)\s*[）)]?',
    }

    for name, pattern in checks.items():
        m = re.search(pattern, content)
        if m:
            try:
                values[name] = int(m.group(1))
            except ValueError:
                values[name] = m.group(1)

    # Starting resources
    m = re.search(r'初始资源\s*\|\s*粮(\d+).*?木(\d+).*?金(\d+)', content)
    if m:
        values["STARTING_RESOURCES"] = {"food": int(m.group(1)), "wood": int(m.group(2)), "gold": int(m.group(3))}

    # Starting units
    m = re.search(r'初始单位\s*\|\s*(\d+)工人.*?(\d+)侦察兵', content)
    if m:
        values["STARTING_UNITS"] = {"worker": int(m.group(1)), "scout": int(m.group(2))}

    # Facility output
    m = re.search(r'设施产出\s*\|\s*(\d+)/T', content)
    if m:
        values["FACILITY_OUTPUT_BASE"] = int(m.group(1))

    # City HP in city section
    m = re.search(r'HP\s*\|\s*(\d+)\s*\|', content)
    if m:
        values["_CITY_HP_TABLE"] = int(m.group(1))

    # C5 cost in tech tree table
    m = re.search(r'C5.*?纪念碑.*?\|\s*(\d+).*?(\d+).*?(\d+)\s*\|', content)
    if m:
        values["C5_COST"] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return values


# ─── Check consistency ────────────────────────────────

def check():
    const = parse_constants()
    game = parse_game_md()

    if "_error" in const:
        print(f"ERROR: {const['_error']}")
        return 1
    if "_error" in game:
        print(f"ERROR: {game['_error']}")
        return 1

    errors = []
    warnings = []

    # Check sync date
    sync_date = game.get("_sync_date", "")
    if sync_date:
        try:
            sd = datetime.strptime(sync_date, "%Y-%m-%d")
            days_ago = (datetime.now() - sd).days
            if days_ago > 3:
                warnings.append(f"GAME.md last synced {sync_date} ({days_ago} days ago)")
        except ValueError:
            warnings.append(f"GAME.md sync date unparseable: {sync_date}")
    else:
        warnings.append("GAME.md missing sync date")

    # Cross-check values
    checks = [
        ("DEFAULT_SIZE", "DEFAULT_SIZE"),
        ("MAX_TURNS", "MAX_TURNS"),
        ("CONSTRUCTION_VICTORY_REQUIRE_FACILITIES", "CONSTRUCTION_VICTORY_REQUIRE_FACILITIES"),
    ]

    for const_key, game_key in checks:
        cv = const.get(const_key)
        gv = game.get(game_key)
        if cv is not None and gv is not None:
            if cv != gv:
                errors.append(f"{const_key}: constants.py={cv}, GAME.md={gv}")
        elif cv is not None and gv is None:
            warnings.append(f"{const_key}: in constants.py ({cv}) but not found in GAME.md")
        elif cv is None and gv is not None:
            warnings.append(f"{const_key}: in GAME.md ({gv}) but not found in constants.py")

    # Check starting resources
    cr = const.get("STARTING_RESOURCES", {})
    gr = game.get("STARTING_RESOURCES", {})
    if cr and gr and cr != gr:
        errors.append(f"STARTING_RESOURCES: constants.py={cr}, GAME.md={gr}")

    # Check starting units
    cu = const.get("STARTING_UNITS", {})
    gu = game.get("STARTING_UNITS", {})
    if cu and gu and cu != gu:
        errors.append(f"STARTING_UNITS: constants.py={cu}, GAME.md={gu}")

    # Report
    if errors:
        print(f"\n*** {len(errors)} CONSISTENCY ERROR(S) ***")
        for e in errors:
            print(f"  [ERR] {e}")

    if warnings:
        print(f"\n{len(warnings)} WARNING(S):")
        for w in warnings:
            print(f"  [WARN] {w}")

    if not errors and not warnings:
        print("OK: constants.py and GAME.md are consistent")
        return 0

    print(f"\nTotal: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(check())
