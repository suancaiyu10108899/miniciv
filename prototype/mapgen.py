# prototype/mapgen.py — 地图生成器（6种）
# 环面拓扑。BFS 连通性验证。种子可复现。

import random
from collections import deque
from prototype.constants import (
    MAP_SIZES, DEFAULT_SIZE, GENERATOR_RATIOS, GENERATOR_CLUSTER,
)
from prototype.terrain import Terrain


def _torus_delta(a: int, b: int, size: int) -> int:
    """环面上 a 到 b 的最短距离（单轴）"""
    d = b - a
    if d > size // 2:
        d -= size
    elif d < -size // 2:
        d += size
    return d


def _torus_neighbors(x: int, y: int, W: int, H: int) -> list[tuple[int, int]]:
    """环面四邻"""
    return [
        ((x + 1) % W, y),
        ((x - 1) % W, y),
        (x, (y + 1) % H),
        (x, (y - 1) % H),
    ]


def _torus_dist(x1: int, y1: int, x2: int, y2: int, W: int, H: int) -> int:
    """环面曼哈顿距离"""
    return abs(_torus_delta(x1, x2, W)) + abs(_torus_delta(y1, y2, H))


# ─── 核心生成 ────────────────────────────────────────

def generate_map(seed: int, size: int = DEFAULT_SIZE,
                 generator_id: str = "balanced") -> list[list[dict]]:
    """
    生成 size×size 环面地图。
    返回: grid[y][x] = {"terrain": Terrain, "facility": None}
    """
    if generator_id not in GENERATOR_RATIOS:
        raise ValueError(f"未知生成器: {generator_id}. 可用: {list(GENERATOR_RATIOS.keys())}")

    rng = random.Random(seed)
    W, H = size, size
    ratios = GENERATOR_RATIOS[generator_id]
    clusters = GENERATOR_CLUSTER[generator_id]

    # 1. 全平原
    grid = [[{"terrain": Terrain.PLAIN, "facility": None} for _ in range(W)] for _ in range(H)]

    # 2. 城市位置
    if generator_id == "symmetric":
        # 对称模式：P0 随机，P1 = 对角线镜像
        cx0 = rng.randint(0, W - 1)
        cy0 = rng.randint(0, H - 1)
        cx1 = (W - 1 - cx0) % W
        cy1 = (H - 1 - cy0) % H
    else:
        cx0 = rng.randint(0, W - 1)
        cy0 = rng.randint(0, H - 1)
        cx1 = (cx0 + W // 2) % W
        cy1 = (cy0 + H // 2) % H

    # 城市初始 3×3 布局
    _place_city_3x3(grid, cx0, cy0, W, H, mirror=False)
    _place_city_3x3(grid, cx1, cy1, W, H, mirror=(generator_id == "symmetric"))

    # 保护区域：城市 3×3 范围（9+9=18格），防止地形覆盖城市四邻
    protected = set()
    for cx, cy in [(cx0, cy0), (cx1, cy1)]:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                protected.add(((cx + dx) % W, (cy + dy) % H))

    # 3. 对称模式：只生成半场 + mirror
    if generator_id == "symmetric":
        _generate_half_and_mirror(grid, rng, W, H, ratios, clusters, protected)
    else:
        _generate_terrain(grid, rng, W, H, ratios, clusters, protected)

    # 4. 连通性验证
    if not _bfs_connected(grid, cx0, cy0, cx1, cy1, W, H):
        # 换 seed 重试
        return generate_map(seed + 1, size, generator_id)

    return grid


def _place_city_3x3(grid, cx, cy, W, H, mirror=False):
    """城市 + 3×3 布局：四正=平原，对角=山/林交替。
    mirror=True 时对角方向反转（用于对称地图的镜像城市）"""
    grid[cy][cx]["terrain"] = Terrain.CITY
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (cx + dx) % W, (cy + dy) % H
        if grid[ny][nx]["terrain"] != Terrain.CITY:
            grid[ny][nx]["terrain"] = Terrain.PLAIN
    # 对角。mirror 时交换山/林位置以实现对称
    corners = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for i, (dx, dy) in enumerate(corners):
        nx, ny = (cx + dx) % W, (cy + dy) % H
        if grid[ny][nx]["terrain"] not in (Terrain.CITY,):
            if mirror:
                # 镜像：前两个对角=林，后两个=山（与默认相反）
                if i < 2:
                    grid[ny][nx]["terrain"] = Terrain.FOREST
                else:
                    grid[ny][nx]["terrain"] = Terrain.MOUNTAIN
            else:
                if i < 2:
                    grid[ny][nx]["terrain"] = Terrain.MOUNTAIN
                else:
                    grid[ny][nx]["terrain"] = Terrain.FOREST


def _generate_terrain(grid, rng, W, H, ratios, clusters, protected):
    """通用地形生成：种子扩散"""
    total = W * H
    city_count = sum(1 for row in grid for c in row if c["terrain"] == Terrain.CITY)
    available = total - city_count

    target_water = max(1, int(available * ratios[3]))
    target_mountain = max(1, int(available * ratios[2]))
    target_forest = max(1, int(available * ratios[1]))

    _place_clustered(grid, rng, W, H, Terrain.WATER, target_water,
                     clusters["water"], protected)
    _place_clustered(grid, rng, W, H, Terrain.MOUNTAIN, target_mountain,
                     clusters["mountain"], protected)
    _place_clustered(grid, rng, W, H, Terrain.FOREST, target_forest,
                     clusters["forest"], protected)


def _generate_half_and_mirror(grid, rng, W, H, ratios, clusters, protected):
    """对称生成：随机生成左半，右半镜像"""
    half_w = W // 2
    half_count = half_w * H
    target_water = max(1, int(half_count * ratios[3]))
    target_mountain = max(1, int(half_count * ratios[2]))
    target_forest = max(1, int(half_count * ratios[1]))

    _place_clustered_half(grid, rng, W, H, half_w, Terrain.WATER,
                          target_water, clusters["water"], protected)
    _place_clustered_half(grid, rng, W, H, half_w, Terrain.MOUNTAIN,
                          target_mountain, clusters["mountain"], protected)
    _place_clustered_half(grid, rng, W, H, half_w, Terrain.FOREST,
                          target_forest, clusters["forest"], protected)


def _place_clustered_half(grid, rng, W, H, half_w, terrain_type, target,
                          cluster_range, protected):
    """在半场放置地形，然后镜像到另一半"""
    placed = 0
    attempts = 0
    min_c, max_c = cluster_range

    while placed < target and attempts < target * 3:
        attempts += 1
        sx = rng.randint(0, half_w - 1)
        sy = rng.randint(0, H - 1)
        if (sx, sy) in protected:
            continue
        if grid[sy][sx]["terrain"] != Terrain.PLAIN:
            continue

        cluster_size = rng.randint(min_c, max_c)
        for px, py in _bfs_spread(sx, sy, W, H, cluster_size, rng, grid,
                                  terrain_type, is_half=True, half_w=half_w,
                                  protected=protected):
            if placed >= target:
                break
            placed += 1

    # 镜像：将左半的地形复制到右半（跳过保护区）
    for y in range(H):
        for x in range(half_w):
            mirror_x = W - 1 - x
            if (mirror_x, y) in protected:
                continue
            t = grid[y][x]["terrain"]
            if t not in (Terrain.CITY, Terrain.PLAIN):
                grid[y][mirror_x]["terrain"] = t
    # 反向：右半也可能有未镜像的非平原，跳过保护
    for y in range(H):
        for x in range(W - 1, W - half_w - 1, -1):
            mirror_x = W - 1 - x
            if (mirror_x, y) in protected:
                continue
            t = grid[y][x]["terrain"]
            if t not in (Terrain.CITY, Terrain.PLAIN):
                grid[y][mirror_x]["terrain"] = t


def _place_clustered(grid, rng, W, H, terrain_type, target, cluster_range,
                     protected):
    """聚类放置地形"""
    placed = 0
    attempts = 0
    min_c, max_c = cluster_range

    while placed < target and attempts < target * 3:
        attempts += 1
        sx = rng.randint(0, W - 1)
        sy = rng.randint(0, H - 1)
        if (sx, sy) in protected:
            continue
        if grid[sy][sx]["terrain"] != Terrain.PLAIN:
            continue

        cluster_size = rng.randint(min_c, max_c)

        for px, py in _bfs_spread(sx, sy, W, H, cluster_size, rng, grid,
                                  terrain_type, is_half=False,
                                  protected=protected):
            if (px, py) in protected:
                continue
            if placed >= target:
                break
            placed += 1


def _bfs_spread(sx, sy, W, H, max_size, rng, grid, terrain_type,
                is_half=False, half_w=0, protected=None):
    """BFS 扩散——从种子向外放置同种地形"""
    if protected is None:
        protected = set()
    q = deque([(sx, sy)])
    visited = {(sx, sy)}
    placed = 0
    order = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while q and placed < max_size:
        x, y = q.popleft()
        if is_half and x >= half_w:
            continue
        if (x, y) in protected:
            continue
        if grid[y][x]["terrain"] == Terrain.PLAIN:
            grid[y][x]["terrain"] = terrain_type
            placed += 1
            yield (x, y)

        rng.shuffle(order)
        for dx, dy in order:
            nx, ny = (x + dx) % W, (y + dy) % H
            if (nx, ny) not in visited:
                visited.add((nx, ny))
                q.append((nx, ny))


def _bfs_connected(grid, x0, y0, x1, y1, W, H) -> bool:
    """BFS: 从城市 A 能否走到城市 B（只走可行地形）"""
    q = deque([(x0, y0)])
    visited = {(x0, y0)}

    while q:
        x, y = q.popleft()
        if (x, y) == (x1, y1):
            return True
        for nx, ny in _torus_neighbors(x, y, W, H):
            if (nx, ny) in visited:
                continue
            t = grid[ny][nx]["terrain"]
            if t == Terrain.WATER:
                continue
            visited.add((nx, ny))
            q.append((nx, ny))
    return False


# ─── 查询函数 ────────────────────────────────────────

def get_terrain(grid, x: int, y: int) -> Terrain:
    """环面 safe get"""
    H, W = len(grid), len(grid[0])
    return grid[y % H][x % W]["terrain"]


def get_facility(grid, x: int, y: int):
    """环面 safe get"""
    H, W = len(grid), len(grid[0])
    return grid[y % H][x % W].get("facility")


def set_facility(grid, x: int, y: int, facility):
    """设置设施"""
    H, W = len(grid), len(grid[0])
    grid[y % H][x % W]["facility"] = facility


def remove_facility(grid, x: int, y: int):
    """移除设施"""
    H, W = len(grid), len(grid[0])
    grid[y % H][x % W]["facility"] = None
