# prototype/terrain.py — 地形枚举 + 属性查询表

from enum import Enum, auto


class Terrain(Enum):
    PLAIN = auto()
    FOREST = auto()
    MOUNTAIN = auto()
    WATER = auto()
    CITY = auto()  # 城市格——不是自然地形，但在地图网格中占一格


# ─── 属性表 ──────────────────────────────────────
# 按 Terrain 枚举索引

_TERRAIN_PROPS = {
    Terrain.PLAIN: {
        "def_bonus": 0,
        "passable": True,           # 所有单位可通过
        "blocks_projectile": False,
        "blocks_vision": False,
        "buildable": "farm",        # 可建设施类型
    },
    Terrain.FOREST: {
        "def_bonus": 10,
        "passable": True,
        "blocks_projectile": True,
        "blocks_vision": True,
        "buildable": "lumbermill",
    },
    Terrain.MOUNTAIN: {
        "def_bonus": 15,
        "passable": "restricted",   # 骑兵不可
        "blocks_projectile": True,
        "blocks_vision": True,
        "buildable": "mine",
    },
    Terrain.WATER: {
        "def_bonus": 0,
        "passable": False,          # 无人可通过
        "blocks_projectile": False, # 弹道可穿透
        "blocks_vision": False,     # 视野可穿透
        "buildable": None,
    },
    Terrain.CITY: {
        "def_bonus": 25,
        "passable": True,
        "blocks_projectile": False,
        "blocks_vision": False,
        "buildable": None,          # 城市格不建任何设施
    },
}


def terrain_def_bonus(t: Terrain) -> int:
    return _TERRAIN_PROPS[t]["def_bonus"]


def terrain_passable(t: Terrain, unit_type: str, is_moving: bool = True) -> bool:
    """单位是否能进入此地形格。is_moving=True=移动中, False=仅检查可否存在"""
    prop = _TERRAIN_PROPS[t]
    if not prop["passable"]:
        return False
    if prop["passable"] == "restricted":
        return unit_type != "cavalry"
    return True


def terrain_blocks_projectile(t: Terrain) -> bool:
    return _TERRAIN_PROPS[t]["blocks_projectile"]


def terrain_blocks_vision(t: Terrain) -> bool:
    return _TERRAIN_PROPS[t]["blocks_vision"]


def terrain_buildable(t: Terrain) -> str | None:
    return _TERRAIN_PROPS[t]["buildable"]


# ─── 地形标识字符 ──────────────────────────────
TERRAIN_CHAR = {
    Terrain.PLAIN: ".",
    Terrain.FOREST: "F",
    Terrain.MOUNTAIN: "M",
    Terrain.WATER: "~",
    Terrain.CITY: "C",
}
