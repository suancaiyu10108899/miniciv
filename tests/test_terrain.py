# tests/test_terrain.py — 地形属性测试

from prototype.terrain import (
    Terrain, terrain_def_bonus, terrain_passable,
    terrain_blocks_projectile, terrain_blocks_vision,
    terrain_buildable, TERRAIN_CHAR,
)


class TestTerrainProperties:
    def test_plain(self):
        assert terrain_def_bonus(Terrain.PLAIN) == 0
        assert terrain_passable(Terrain.PLAIN, "cavalry") is True
        assert terrain_passable(Terrain.PLAIN, "infantry") is True
        assert terrain_passable(Terrain.PLAIN, "worker") is True
        assert terrain_blocks_projectile(Terrain.PLAIN) is False
        assert terrain_buildable(Terrain.PLAIN) == "farm"

    def test_forest(self):
        assert terrain_def_bonus(Terrain.FOREST) == 10
        assert terrain_passable(Terrain.FOREST, "cavalry") is True
        assert terrain_passable(Terrain.FOREST, "infantry") is True
        assert terrain_blocks_projectile(Terrain.FOREST) is True
        assert terrain_buildable(Terrain.FOREST) == "lumbermill"

    def test_mountain_infantry_ok_cavalry_no(self):
        assert terrain_passable(Terrain.MOUNTAIN, "infantry") is True
        assert terrain_passable(Terrain.MOUNTAIN, "cavalry") is False
        assert terrain_def_bonus(Terrain.MOUNTAIN) == 15
        assert terrain_buildable(Terrain.MOUNTAIN) == "mine"

    def test_water_nobody_passable(self):
        assert terrain_passable(Terrain.WATER, "infantry") is False
        assert terrain_passable(Terrain.WATER, "cavalry") is False
        assert terrain_passable(Terrain.WATER, "scout") is False
        # 水域不阻断弹道和视野
        assert terrain_blocks_projectile(Terrain.WATER) is False
        assert terrain_blocks_vision(Terrain.WATER) is False

    def test_city(self):
        assert terrain_def_bonus(Terrain.CITY) == 25
        assert terrain_passable(Terrain.CITY, "infantry") is True
        assert terrain_buildable(Terrain.CITY) is None  # 城市格不能建设施


class TestTerrainChar:
    def test_all_have_char(self):
        for t in Terrain:
            assert t in TERRAIN_CHAR, f"Missing char for {t}"
