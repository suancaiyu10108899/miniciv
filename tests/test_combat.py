# tests/test_combat.py — 战斗系统测试

import pytest
from prototype.unit import Unit, City
from prototype.combat import (
    resolve_melee, resolve_ranged, can_occupy_city, city_occupation_damage,
)
from prototype.terrain import Terrain


def make(utype: str, pid=0, x=0, y=0) -> Unit:
    return Unit.create(utype, pid, x, y)


# ─── GDD 关键对战验证 ────────────────────────────

class TestGDDExamples:
    """验证 GDD 中列出的典型对战数值"""

    def test_cavalry_charge_vs_plains_infantry(self):
        """骑兵冲锋 vs 平原步兵: 40 伤 → ~3 刀杀"""
        a = make("cavalry")
        d = make("infantry")
        # 公式: max(1, 60+0 - 30 - 0) + 10 = 30 + 10 = 40
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN,
                               attacker_just_charged=True)
        assert result["att_damage"] == 40
        assert d.hp == 60  # 100 - 40

    def test_cavalry_vs_mountain_infantry(self):
        """骑兵(平原) vs 步兵山地上: 几乎打不动"""
        a = make("cavalry")
        d = make("infantry")
        # 实际值依赖当前 TERRAIN_DEF_BONUS[mountain]
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.MOUNTAIN)
        assert result["att_damage"] == 15   # 骑兵打山上步兵
        assert result["def_damage"] == 45   # 山上步兵反击

    def test_archer_vs_plains_cavalry(self):
        """弓箭 vs 平原骑兵: 35 伤 → ~3 箭杀"""
        a = make("archer")
        d = make("cavalry")
        # max(1, 50 - 15 - 0) = 35
        result = resolve_ranged(a, d, Terrain.PLAIN)
        assert result["damage"] == 35

    def test_archer_vs_mountain_infantry(self):
        """弓箭 vs 山地步兵: 5 伤 → 刮痧"""
        a = make("archer")
        d = make("infantry")
        # max(1, 50 - 30 - 15) = max(1, 5) = 5
        result = resolve_ranged(a, d, Terrain.MOUNTAIN)
        assert result["damage"] == 5  # 打不太动

    def test_infantry_vs_infantry_plains(self):
        """步兵 vs 步兵 平原: 15 伤 → ~7T杀"""
        a = make("infantry")
        d = make("infantry")
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN)
        # max(1, 45+0 - 30 - 0) = 15
        assert result["att_damage"] == 15
        assert result["def_damage"] == 15


# ─── 地形效果 ─────────────────────────────────────

class TestTerrainEffects:
    def test_forest_defender_takes_less(self):
        """守方在森林→攻方伤害减少"""
        a = make("infantry")
        d = make("infantry")
        result_plain = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN)
        a2 = make("infantry"); d2 = make("infantry")
        result_forest = resolve_melee(a2, d2, Terrain.PLAIN, Terrain.FOREST)
        # 攻方打森林守方: max(1, 40+0 - 30 - 10) = 0 → 1
        assert result_forest["att_damage"] < result_plain["att_damage"]

    def test_mountain_attacker_hits_harder(self):
        """攻方在山地→攻方伤害增加"""
        a = make("infantry")
        d = make("cavalry")
        # 山地步打平原骑: 实际值依赖 terrain_def
        result = resolve_melee(a, d, Terrain.MOUNTAIN, Terrain.PLAIN)
        assert result["att_damage"] == 45

    def test_city_defense_strong(self):
        """城市 DEF 25 → 守城方很肉"""
        a = make("cavalry")
        d = make("infantry")
        # 骑打城市步兵: max(1, 60+0 - 30 - 25) = 5
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.CITY)
        assert result["att_damage"] == 5

    def test_city_attacker_hits_harder(self):
        """攻方站在城市上攻平原→加成"""
        a = make("cavalry")
        d = make("infantry")
        # 骑(城市)打平原步: max(1, 60+25 - 30 - 0) = 55
        result = resolve_melee(a, d, Terrain.CITY, Terrain.PLAIN)
        assert result["att_damage"] == 55


# ─── 边界条件 ─────────────────────────────────────

class TestEdgeCases:
    def test_min_one_damage(self):
        a = make("worker")   # ATK 0
        d = make("infantry") # DEF 30
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN)
        assert result["att_damage"] == 1  # 保底

    def test_kill_worker(self):
        a = make("cavalry")
        d = make("worker")  # HP 10
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN)
        # max(1, 55 - 0 - 0) = 55 → 10 HP 死
        assert result["defender_alive"] is False
        assert d.hp == 0

    def test_mutual_kill(self):
        """双方同时死"""
        a = make("worker")
        a.hp = 1
        d = make("worker")
        d.hp = 1
        result = resolve_melee(a, d, Terrain.PLAIN, Terrain.PLAIN)
        assert result["attacker_alive"] is False
        assert result["defender_alive"] is False


# ─── 远程 ─────────────────────────────────────────

class TestRanged:
    def test_no_counterattack(self):
        a = make("archer")
        d = make("cavalry")
        initial = a.hp
        resolve_ranged(a, d, Terrain.PLAIN)
        assert a.hp == initial

    def test_non_ranged_cant(self):
        with pytest.raises(ValueError):
            resolve_ranged(make("infantry"), make("infantry"), Terrain.PLAIN)


# ─── 城市 ─────────────────────────────────────────

class TestCityOccupation:
    def test_archer_cannot(self):
        assert can_occupy_city(make("archer"), City(1, 0, 0)) is False

    def test_infantry_can(self):
        c = City(1, 0, 0)
        c.hp = 10
        assert can_occupy_city(make("infantry"), c) is True

    def test_damage(self):
        c = City(1, 0, 0)
        # 骑(ATK 60) - 城(DEF 10) = 50
        assert city_occupation_damage(make("cavalry"), c) == 50
