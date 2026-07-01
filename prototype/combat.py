# prototype/combat.py — 战斗结算（固定伤害，非随机）

from prototype.terrain import Terrain, terrain_def_bonus
from prototype.constants import CAVALRY_CHARGE_BONUS


def resolve_melee(attacker, defender, terrain_att: Terrain, terrain_def: Terrain,
                  attacker_just_charged: bool = False) -> dict:
    """
    近战结算：双方互打。
    GDD公式: damage = max(1, ATK + terrain_bonus(攻方地形) - DEF - terrain_bonus(守方地形))

    返回: {"att_damage", "def_damage", "attacker_alive", "defender_alive"}
    """
    att_bonus = terrain_def_bonus(terrain_att)
    def_bonus = terrain_def_bonus(terrain_def)

    att_damage = max(1, attacker.atk + att_bonus - defender.def_ - def_bonus)
    def_damage = max(1, defender.atk + def_bonus - attacker.def_ - att_bonus)

    # 骑兵冲锋加成
    if attacker.unit_type == "cavalry" and attacker_just_charged:
        att_damage += CAVALRY_CHARGE_BONUS

    defender.hp -= att_damage
    attacker.hp -= def_damage

    if defender.hp <= 0:
        defender.hp = 0
        defender.alive = False
    if attacker.hp <= 0:
        attacker.hp = 0
        attacker.alive = False

    return {
        "att_damage": att_damage,
        "def_damage": def_damage,
        "attacker_alive": attacker.alive,
        "defender_alive": defender.alive,
    }


def resolve_ranged(archer, target, terrain_target: Terrain) -> dict:
    """
    远程攻击：只有攻方输出。守方不还手。
    GDD公式: damage = max(1, ATK - DEF - terrain_bonus(目标地形))
    弓手自身地形不参与计算。

    返回: {"damage", "target_alive"}
    """
    if not archer.ranged:
        raise ValueError(f"{archer.unit_type} is not a ranged unit")

    def_bonus = terrain_def_bonus(terrain_target)
    damage = max(1, archer.atk - target.def_ - def_bonus)

    target.hp -= damage
    if target.hp <= 0:
        target.hp = 0
        target.alive = False

    return {"damage": damage, "target_alive": target.alive}


def can_occupy_city(unit, city) -> bool:
    """弓箭手不能占领城市"""
    if unit.ranged:
        return False
    damage = max(1, unit.atk - city.def_)
    return damage >= city.hp


def city_occupation_damage(unit, city) -> int:
    """近战入城伤害"""
    return max(1, unit.atk - city.def_)
