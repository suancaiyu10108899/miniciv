# tests/test_unit.py — 单位/城市/设施数据类测试

import pytest
from prototype.unit import Unit, City, Facility, unit_stat, unit_speed, unit_can_enter
from prototype.terrain import Terrain
from prototype.constants import UNIT_STATS, CITY_HP, CITY_DEF, CITY_BASE_FOOD


class TestUnitCreate:
    def test_create_infantry(self):
        u = Unit.create("infantry", 0, 3, 5)
        assert u.unit_type == "infantry"
        assert u.player_id == 0
        assert u.x == 3 and u.y == 5
        assert u.hp == 100
        assert u.atk == 40
        assert u.def_ == 30
        assert u.move == 1
        assert u.vision == 2
        assert u.can_enter_mountain is True
        assert u.ranged is False

    def test_create_cavalry(self):
        u = Unit.create("cavalry", 0, 0, 0)
        assert u.hp == 80
        assert u.atk == 55
        assert u.def_ == 15
        assert u.move == 2
        assert u.can_enter_mountain is False

    def test_create_archer(self):
        u = Unit.create("archer", 1, 0, 0)
        assert u.hp == 60
        assert u.ranged is True
        assert u.range_dist == 2

    def test_create_scout(self):
        u = Unit.create("scout", 0, 0, 0)
        assert u.vision == 3
        assert u.move == 2
        assert u.can_enter_mountain is True

    def test_create_worker(self):
        u = Unit.create("worker", 0, 0, 0)
        assert u.hp == 10
        assert u.atk == 0
        assert u.def_ == 0

    @pytest.mark.parametrize("utype", list(UNIT_STATS.keys()))
    def test_all_types_create(self, utype):
        u = Unit.create(utype, 0, 0, 0)
        assert u.unit_type == utype
        assert u.alive is True
        assert u.hp > 0


class TestUnitStatQuery:
    def test_unit_stat(self):
        assert unit_stat("cavalry", "atk") == 55
        assert unit_stat("infantry", "hp") == 100

    def test_unit_speed(self):
        assert unit_speed("cavalry") == 2
        assert unit_speed("infantry") == 1

    def test_unit_can_enter(self):
        assert unit_can_enter("cavalry", Terrain.MOUNTAIN) is False
        assert unit_can_enter("infantry", Terrain.MOUNTAIN) is True
        assert unit_can_enter("scout", Terrain.MOUNTAIN) is True
        assert unit_can_enter("cavalry", Terrain.FOREST) is True


class TestCity:
    def test_create(self):
        c = City(0, 5, 10)
        assert c.player_id == 0
        assert c.x == 5 and c.y == 10
        assert c.hp == CITY_HP
        assert c.def_ == CITY_DEF
        assert c.base_food == CITY_BASE_FOOD
        assert c.alive is True

    def test_dead_when_hp_zero(self):
        c = City(0, 0, 0)
        c.hp = 0
        assert c.alive is False


class TestFacility:
    def test_create(self):
        f = Facility("farm", 0, 3, 4)
        assert f.facility_type == "farm"
        assert f.player_id == 0

    def test_output_resource(self):
        assert Facility("mine", 0, 0, 0).output_resource() == "gold"
        assert Facility("farm", 0, 0, 0).output_resource() == "food"
        assert Facility("lumbermill", 0, 0, 0).output_resource() == "wood"
