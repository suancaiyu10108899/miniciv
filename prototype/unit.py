# prototype/unit.py — 单位/城市/设施数据类

from dataclasses import dataclass, field
from prototype.constants import UNIT_STATS, CITY_HP, CITY_DEF, CITY_BASE_FOOD


@dataclass
class Unit:
    """战斗/经济单位。纯数据容器，不含逻辑。"""
    unit_type: str       # "infantry" | "cavalry" | "archer" | "scout" | "worker"
    player_id: int       # 0 或 1
    x: int
    y: int
    hp: int
    atk: int
    def_: int            # "def" 是 Python 关键字
    move: int
    vision: int
    can_enter_mountain: bool
    ranged: bool
    range_dist: int       # 0 = 近战
    alive: bool = True
    damage_dealt: int = 0   # 累计造成伤害
    damage_taken: int = 0   # 累计承受伤害

    @classmethod
    def create(cls, unit_type: str, player_id: int, x: int, y: int) -> "Unit":
        """从兵种类型名创建单位，属性从 UNIT_STATS 读取。"""
        stats = UNIT_STATS[unit_type]
        return cls(
            unit_type=unit_type,
            player_id=player_id,
            x=x, y=y,
            hp=stats["hp"],
            atk=stats["atk"],
            def_=stats["def"],
            move=stats["move"],
            vision=stats["vision"],
            can_enter_mountain=stats["can_enter_mountain"],
            ranged=stats["ranged"],
            range_dist=stats["range_dist"],
        )

    def apply_tech_bonus(self, bonus_type: str, value: int):
        """应用科技加成。bonus_type: "atk" | "def" | "hp" """
        if bonus_type == "atk":
            self.atk += value
        elif bonus_type == "def":
            self.def_ += value
        elif bonus_type == "hp":
            self.hp += value
            # 当前HP也增加（科技生效时所有单位受益）
        # 注意：当前HP使用hp字段，apply后需外部重算


@dataclass
class City:
    """城市数据容器。"""
    player_id: int
    x: int
    y: int
    hp: int = CITY_HP
    def_: int = CITY_DEF
    base_food: int = CITY_BASE_FOOD

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class Facility:
    """设施数据容器。建在格子上，独立于单位。"""
    facility_type: str   # "farm" | "lumbermill" | "mine"
    player_id: int       # 谁建造的
    x: int
    y: int

    def output_resource(self) -> str:
        """此设施产出的资源类型."""
        return {"farm": "food", "lumbermill": "wood", "mine": "gold"}[self.facility_type]


# ─── 兵种属性查询 ─────────────────────────────────

def unit_stat(unit_type: str, stat: str):
    """快捷查询: unit_stat("cavalry", "atk") → 55"""
    return UNIT_STATS[unit_type][stat]


def unit_speed(unit_type: str) -> int:
    return UNIT_STATS[unit_type]["move"]


def unit_can_enter(unit_type: str, terrain) -> bool:
    """判断单位能否进入某地形格。terrain 是 Terrain 枚举。"""
    from prototype.terrain import terrain_passable
    return terrain_passable(terrain, unit_type, is_moving=True)
