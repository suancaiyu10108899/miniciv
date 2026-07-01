# tests/test_movement.py — 移动规则测试

import pytest
from prototype.unit import Unit
from prototype.movement import (
    get_legal_moves, get_single_step_moves, apply_move,
    cavalry_forest_check, torus_wrap, can_enter_tile, DIR_LIST,
)
from prototype.terrain import Terrain, terrain_passable


def make(utype: str, x=5, y=5) -> Unit:
    return Unit.create(utype, 0, x, y)


# ─── 环面 wrap ────────────────────────────────────

class TestTorusWrap:
    def test_normal(self):
        assert torus_wrap(3, 5, 30, 30) == (3, 5)

    def test_overflow(self):
        assert torus_wrap(30, 5, 30, 30) == (0, 5)
        assert torus_wrap(5, 30, 30, 30) == (5, 0)

    def test_negative(self):
        assert torus_wrap(-1, 0, 30, 30) == (29, 0)


# ─── 单位能否进入地形 ─────────────────────────────

class TestCanEnterTile:
    def test_infantry_all_passable(self, balanced_map_30):
        grid = balanced_map_30
        # 找个平原
        for y in range(30):
            for x in range(30):
                t = grid[y][x]["terrain"]
                if t == Terrain.PLAIN:
                    assert can_enter_tile(make("infantry", x, y), grid, x, y)
                    return

    def test_cavalry_cannot_mountain(self, balanced_map_30):
        grid = balanced_map_30
        for y in range(30):
            for x in range(30):
                if grid[y][x]["terrain"] == Terrain.MOUNTAIN:
                    assert can_enter_tile(make("cavalry", 5, 5), grid, x, y) is False
                    return

    def test_nobody_enters_water(self, balanced_map_30):
        grid = balanced_map_30
        for y in range(30):
            for x in range(30):
                if grid[y][x]["terrain"] == Terrain.WATER:
                    for utype in ["infantry", "cavalry", "archer", "scout", "worker"]:
                        assert can_enter_tile(make(utype, 5, 5), grid, x, y) is False
                    return

    def test_scout_enters_mountain(self, balanced_map_30):
        grid = balanced_map_30
        for y in range(30):
            for x in range(30):
                if grid[y][x]["terrain"] == Terrain.MOUNTAIN:
                    assert can_enter_tile(make("scout", 5, 5), grid, x, y) is True
                    return


# ─── 合法移动 ─────────────────────────────────────

class TestGetLegalMoves:
    def test_all_on_plains(self, balanced_map_30):
        """平原上：3×3中心→4方向都可走"""
        grid = balanced_map_30
        for y in range(1, 29):
            for x in range(1, 29):
                terrain = grid[y][x]["terrain"]
                # 找一块周围都是平原的
                if terrain != Terrain.PLAIN:
                    continue
                neighbors_ok = all(
                    grid[(y+dy)%30][(x+dx)%30]["terrain"] == Terrain.PLAIN
                    for dx, dy in DIR_LIST
                )
                if neighbors_ok:
                    u = make("infantry", x, y)
                    legal = get_legal_moves(u, grid)
                    assert len(legal) == 4, f"Expected 4 moves at ({x},{y}), got {len(legal)}"
                    return
        pytest.skip("No all-plains area found")

    def test_water_blocks(self, balanced_map_30):
        """水域方向不可走"""
        grid = balanced_map_30
        for y in range(1, 29):
            for x in range(1, 29):
                if grid[y][x]["terrain"] != Terrain.PLAIN:
                    continue
                # 找一个方向是水域的平原格
                for dx, dy in DIR_LIST:
                    nx, ny = (x+dx)%30, (y+dy)%30
                    if grid[ny][nx]["terrain"] == Terrain.WATER:
                        u = make("infantry", x, y)
                        legal = get_legal_moves(u, grid)
                        assert (dx, dy) not in legal, \
                            f"Should not allow move into water at ({x},{y})→({nx},{ny})"
                        return
        pytest.skip("No water-adjacent plains found")

    def test_cavalry_double_plains(self):
        """骑兵在两格连续平原→可以走2格"""
        # 手工构造一个全是平原的地图
        W, H = 30, 30
        grid = [[{"terrain": Terrain.PLAIN, "facility": None} for _ in range(W)] for _ in range(H)]
        u = make("cavalry", 10, 10)
        legal = get_legal_moves(u, grid)
        # 单步: 4个方向
        # 两步: 每个方向可以继续走1-2格
        assert len(legal) >= 4


# ─── 骑兵遇林停 ──────────────────────────────────

class TestCavalryForest:
    def test_first_step_forest_stops(self):
        """第一格是森林→只走第一格"""
        u = make("cavalry", 0, 0)
        W, H = 30, 30
        grid = [[{"terrain": Terrain.PLAIN, "facility": None} for _ in range(W)] for _ in range(H)]
        grid[0][1]["terrain"] = Terrain.FOREST  # x=1,y=0 是森林
        # 骑兵向右 2 格→第一步是森林→停
        result = cavalry_forest_check(u, grid, 2, 0)
        assert result == (1, 0)  # 只走第一步

    def test_all_plains_goes_full(self):
        u = make("cavalry", 0, 0)
        W, H = 30, 30
        grid = [[{"terrain": Terrain.PLAIN, "facility": None} for _ in range(W)] for _ in range(H)]
        result = cavalry_forest_check(u, grid, 2, 0)
        assert result == (2, 0)

    def test_non_cavalry_ignored(self):
        u = make("infantry", 0, 0)
        W, H = 30, 30
        grid = [[{"terrain": Terrain.PLAIN, "facility": None} for _ in range(W)] for _ in range(H)]
        grid[0][1]["terrain"] = Terrain.FOREST
        result = cavalry_forest_check(u, grid, 2, 0)
        assert result == (2, 0)  # 步兵力小，不做检查


# ─── apply_move ──────────────────────────────────

class TestApplyMove:
    def test_normal(self):
        u = make("infantry", 5, 5)
        grid = [[None]*30 for _ in range(30)]
        apply_move(u, grid, 1, 0)
        assert (u.x, u.y) == (6, 5)

    def test_wrap(self):
        u = make("infantry", 29, 5)
        grid = [[None]*30 for _ in range(30)]
        apply_move(u, grid, 1, 0)
        assert (u.x, u.y) == (0, 5)
