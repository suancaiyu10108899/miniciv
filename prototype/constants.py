# prototype/constants.py — 所有可调数值集中管理
# 改一个值不碰代码。原型阶段数值是占位符，跑数据后校准。

# ─── 棋盘 ──────────────────────────────────────────
MAP_SIZES = [15, 30, 50]
DEFAULT_SIZE = 30
MAX_TURNS = 100

# ─── 地形比例（6种生成器）────────────────────────
# 格式: (平原, 森林, 山地, 水域)
GENERATOR_RATIOS = {
    "balanced":       (0.35, 0.28, 0.22, 0.08),
    "symmetric":      (0.35, 0.28, 0.22, 0.08),
    "fertile":        (0.45, 0.30, 0.15, 0.03),
    "harsh":          (0.25, 0.25, 0.30, 0.15),
    "mountain_pass":  (0.30, 0.25, 0.30, 0.08),
    "archipelago":    (0.30, 0.28, 0.18, 0.20),
}

# 生成器聚类参数 (种子扩散距离)
GENERATOR_CLUSTER = {
    "balanced":       {"forest": (3, 8), "mountain": (2, 5), "water": (3, 6)},
    "symmetric":      {"forest": (3, 8), "mountain": (2, 5), "water": (3, 6)},
    "fertile":        {"forest": (2, 5), "mountain": (1, 3), "water": (1, 3)},
    "harsh":          {"forest": (2, 5), "mountain": (4, 10), "water": (4, 10)},
    "mountain_pass":  {"forest": (2, 4), "mountain": (6, 15), "water": (2, 5)},
    "archipelago":    {"forest": (2, 4), "mountain": (2, 4), "water": (4, 10)},
}

# ─── 兵种属性 ─────────────────────────────────────
# (hp, atk, def, move, vision, can_enter_mountain, ranged, range_dist)
UNIT_STATS = {
    "infantry":  {"hp": 100, "atk": 40, "def": 30, "move": 1, "vision": 2,
                  "can_enter_mountain": True, "ranged": False, "range_dist": 0},
    "cavalry":   {"hp": 80,  "atk": 55, "def": 15, "move": 2, "vision": 2,
                  "can_enter_mountain": False, "ranged": False, "range_dist": 0},
    "archer":    {"hp": 60,  "atk": 45, "def": 10, "move": 1, "vision": 2,
                  "can_enter_mountain": True, "ranged": True, "range_dist": 2},
    "scout":     {"hp": 40,  "atk": 10, "def": 5,  "move": 2, "vision": 3,
                  "can_enter_mountain": True, "ranged": False, "range_dist": 0},
    "worker":    {"hp": 10,  "atk": 0,  "def": 0,  "move": 1, "vision": 2,
                  "can_enter_mountain": True, "ranged": False, "range_dist": 0},
}

# (粮食花费, 木材花费, 金币花费)
UNIT_COST = {
    "infantry":  (8, 0, 0),
    "cavalry":   (8, 0, 5),
    "archer":    (5, 5, 0),
    "scout":     (5, 0, 0),
    "worker":    (5, 0, 0),
}

# ─── 地形战斗加成 ─────────────────────────────────
TERRAIN_DEF_BONUS = {"plain": 0, "forest": 5, "mountain": 8, "water": 0, "city": 15}
CAVALRY_CHARGE_BONUS = 10  # 骑兵走2格平原后攻击→额外ATK

# ─── 城市 ──────────────────────────────────────────
CITY_HP = 100
CITY_DEF = 10
CITY_DAMAGE = 20
CITY_BASE_FOOD = 1  # 城市自身每回合+1粮

# ─── 经济 ──────────────────────────────────────────
STARTING_RESOURCES = {"food": 15, "wood": 15, "gold": 15}
STARTING_UNITS = {"worker": 3, "scout": 1}
FACILITY_OUTPUT = {"farm": {"food": 3}, "lumbermill": {"wood": 3}, "mine": {"gold": 3}}

# ─── 科技 ──────────────────────────────────────────
# 科技树节点: (花费粮/木/金, 研究回合, 前置列表, 效果)
TECH_TREE = {
    "M1":  {"cost": (8, 3, 0),   "turns": 1, "requires": [],         "effect": "infantry_atk+5,archer_atk+5"},
    "M2":  {"cost": (10, 0, 8),  "turns": 1, "requires": ["M1"],     "effect": "cavalry_charge+5"},
    "M3":  {"cost": (8, 8, 3),   "turns": 1, "requires": ["M1"],     "effect": "infantry_def_forest_mountain+10"},
    "M4":  {"cost": (15, 0, 10), "turns": 2, "requires": ["M2","M3"],"effect": "all_hp+10"},
    "E1":  {"cost": (3, 0, 0),   "turns": 1, "requires": [],         "effect": "farm_food+1"},
    "E2":  {"cost": (0, 3, 0),   "turns": 1, "requires": ["E1"],     "effect": "lumbermill_wood+1"},
    "E3":  {"cost": (5, 0, 3),   "turns": 1, "requires": ["E1"],     "effect": "mine_gold+1"},
    "E4":  {"cost": (8, 8, 0),   "turns": 1, "requires": ["E2","E3"],"effect": "worker_move+1"},
    "C1":  {"cost": (10, 10, 5), "turns": 1, "requires": [],         "effect": "unlock_construction"},
    "C2":  {"cost": (8, 12, 0),  "turns": 1, "requires": ["C1"],     "effect": "city_hp+50"},
    "C3":  {"cost": (10, 10, 10),"turns": 2, "requires": ["C1"],     "effect": "research_time_half"},
    "C4":  {"cost": (12, 5, 5),  "turns": 1, "requires": ["C3","C2"],"effect": "city_food+2"},
    "C5":  {"cost": (20, 20, 20),"turns": 2, "requires": ["C3","C4"],"effect": "construction_victory"},
}

# ─── 迷雾 ──────────────────────────────────────────
VISION_RANGE = {"infantry": 2, "cavalry": 2, "archer": 2, "scout": 3, "worker": 2}
