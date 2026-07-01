# tests/test_mapgen.py — 地图生成器测试

import pytest
from prototype.mapgen import (
    generate_map, _torus_delta, _torus_neighbors, _torus_dist,
    _bfs_connected, get_terrain,
)
from prototype.terrain import Terrain
from prototype.constants import GENERATOR_RATIOS, MAP_SIZES, DEFAULT_SIZE


# ─── 环面工具函数 ─────────────────────────────────

class TestTorus:
    def test_delta_positive(self):
        assert _torus_delta(0, 5, 30) == 5

    def test_delta_wrap_left(self):
        # 从 0 到 29 → 往左绕 1 步
        assert _torus_delta(0, 29, 30) == -1

    def test_delta_wrap_right(self):
        assert _torus_delta(29, 0, 30) == 1

    def test_delta_halfway(self):
        # 刚好一半→保持正值
        assert _torus_delta(0, 15, 30) == 15

    def test_neighbors_corner(self):
        n = _torus_neighbors(0, 0, 30, 30)
        assert (1, 0) in n
        assert (29, 0) in n   # 左 wrap
        assert (0, 1) in n
        assert (0, 29) in n   # 上 wrap

    def test_dist_normal(self):
        assert _torus_dist(0, 0, 5, 5, 30, 30) == 10

    def test_dist_wrap(self):
        # (0,0) 到 (29,29) 环面最短 = 绕 1+1=2
        assert _torus_dist(0, 0, 29, 29, 30, 30) == 2


# ─── 地图生成 ─────────────────────────────────────

class TestGenerateMap:
    def test_default_size(self, balanced_map_30):
        grid = balanced_map_30
        assert len(grid) == 30
        assert len(grid[0]) == 30

    def test_15_size(self, small_map_15):
        assert len(small_map_15) == 15
        assert len(small_map_15[0]) == 15

    def test_50_size(self):
        grid = generate_map(seed=42, size=50, generator_id="balanced")
        assert len(grid) == 50

    @pytest.mark.parametrize("size", MAP_SIZES)
    def test_all_sizes(self, size):
        grid = generate_map(seed=1, size=size, generator_id="balanced")
        assert len(grid) == size
        assert len(grid[0]) == size

    @pytest.mark.parametrize("gen_id", list(GENERATOR_RATIOS.keys()))
    def test_all_generators(self, gen_id):
        grid = generate_map(seed=42, size=15, generator_id=gen_id)
        assert grid is not None
        # 每种生成器都能产出合法地图
        assert len(grid) == 15

    def test_reproducibility(self):
        g1 = generate_map(seed=42, size=30, generator_id="balanced")
        g2 = generate_map(seed=42, size=30, generator_id="balanced")
        # 相同 seed→相同地图
        for y in range(30):
            for x in range(30):
                assert g1[y][x]["terrain"] == g2[y][x]["terrain"]

    def test_different_seed_different(self):
        g1 = generate_map(seed=42, size=15, generator_id="balanced")
        g2 = generate_map(seed=999, size=15, generator_id="balanced")
        # 大概率不同。只要不崩溃即可
        same = sum(1 for y in range(15) for x in range(15)
                   if g1[y][x]["terrain"] == g2[y][x]["terrain"])
        assert same < 225  # 不可能完全相同


# ─── 地形比例 ─────────────────────────────────────

class TestTerrainRatios:
    @pytest.mark.parametrize("gen_id", list(GENERATOR_RATIOS.keys()))
    def test_ratio_rough(self, gen_id):
        """检查各地形比例误差 < 10%"""
        grid = generate_map(seed=42, size=30, generator_id=gen_id)
        W, H = 30, 30
        total = W * H
        target = GENERATOR_RATIOS[gen_id]

        counts = {Terrain.PLAIN: 0, Terrain.FOREST: 0,
                  Terrain.MOUNTAIN: 0, Terrain.WATER: 0}
        for y in range(H):
            for x in range(W):
                t = grid[y][x]["terrain"]
                if t in counts:
                    counts[t] += 1

        # 城市占 2 格，不影响统计量级
        for i, t in enumerate([Terrain.FOREST, Terrain.MOUNTAIN, Terrain.WATER]):
            actual = counts[t] / total
            target_ratio = target[i + 1]  # skip plain ratio
            assert abs(actual - target_ratio) < 0.10, \
                f"{gen_id}: {t.name} ratio {actual:.2f} vs target {target_ratio:.2f}"


# ─── 连通性 ─────────────────────────────────────

class TestConnectivity:
    def test_bfs_reachable(self, balanced_map_30):
        """P0 城市可到达 P1 城市"""
        grid = balanced_map_30
        W = H = 30
        # 找到两个城市位置
        cities = []
        for y in range(H):
            for x in range(W):
                if grid[y][x]["terrain"] == Terrain.CITY:
                    cities.append((x, y))
        assert len(cities) == 2
        assert _bfs_connected(grid, cities[0][0], cities[0][1],
                              cities[1][0], cities[1][1], W, H)

    def test_city_4_neighbors_plain(self, balanced_map_30):
        """城市四正方向必须是平原"""
        grid = balanced_map_30
        W = H = 30
        for y in range(H):
            for x in range(W):
                if grid[y][x]["terrain"] == Terrain.CITY:
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = (x + dx) % W, (y + dy) % H
                        assert grid[ny][nx]["terrain"] == Terrain.PLAIN, \
                            f"City at ({x},{y}) has {grid[ny][nx]['terrain']} at ({nx},{ny})"


# ─── 对称 ─────────────────────────────────────────

class TestSymmetric:
    def test_symmetric_mirror(self, symmetric_map_30):
        """对称生成器：左右半图镜像（排除城市 3×3 保护区）"""
        grid = symmetric_map_30
        W = H = 30
        # 找到城市位置
        cities = []
        for y in range(H):
            for x in range(W):
                if grid[y][x]["terrain"] == Terrain.CITY:
                    cities.append((x, y))
        # 保护区域 = 城市 3×3
        protected = set()
        for cx, cy in cities:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    protected.add(((cx + dx) % W, (cy + dy) % H))
        for y in range(H):
            for x in range(W // 2):
                mirror_x = W - 1 - x
                if (x, y) in protected or (mirror_x, y) in protected:
                    continue
                t1 = grid[y][x]["terrain"]
                t2 = grid[y][mirror_x]["terrain"]
                assert t1 == t2, \
                    f"Symmetry broken at ({x},{y}): {t1} vs ({mirror_x},{y}): {t2}"


# ─── get_terrain ──────────────────────────────────

class TestGetTerrain:
    def test_wrap(self, balanced_map_30):
        """get_terrain 支持环面 wrap"""
        grid = balanced_map_30
        t1 = get_terrain(grid, 0, 0)
        t2 = get_terrain(grid, 30, 0)  # x wrap
        t3 = get_terrain(grid, 0, 30)  # y wrap
        assert t1 == t2 == t3
