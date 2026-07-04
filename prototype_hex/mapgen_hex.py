# prototype_hex/mapgen_hex.py — Rectangular hex grid map generation with torus
# Generates MAP_W × MAP_H hex grid with terrain distribution matching square gen.

import random as _random
from prototype.terrain import Terrain


MAP_W = 15
MAP_H = 15
HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def wrap(q, r):
    return (q % MAP_W + MAP_W) % MAP_W, (r % MAP_H + MAP_H) % MAP_H


def generate_map_hex(seed: int = 42, generator_id: str = "balanced") -> list[list[dict]]:
    """Generate a MAP_W × MAP_H hex grid. Returns grid[r][q] format.
    Each cell: {"terrain": Terrain, "facility": None}
    """
    from prototype.constants import GENERATOR_RATIOS
    ratios = GENERATOR_RATIOS.get(generator_id, GENERATOR_RATIOS["balanced"])
    plain_r, forest_r, mountain_r, water_r = ratios

    rng = _random.Random(seed)

    # Initialize with plains
    grid = [[{"terrain": Terrain.PLAIN, "facility": None}
             for _ in range(MAP_W)] for _ in range(MAP_H)]

    # Assign terrain with clustering
    # Simple approach: random assignment with terrain ratios
    total = MAP_W * MAP_H
    terrain_pool = (
        [Terrain.PLAIN] * int(total * plain_r) +
        [Terrain.FOREST] * int(total * forest_r) +
        [Terrain.MOUNTAIN] * int(total * mountain_r) +
        [Terrain.WATER] * int(total * water_r)
    )
    # Pad to total
    while len(terrain_pool) < total:
        terrain_pool.append(Terrain.PLAIN)
    terrain_pool = terrain_pool[:total]
    rng.shuffle(terrain_pool)

    idx = 0
    for r in range(MAP_H):
        for q in range(MAP_W):
            grid[r][q]["terrain"] = terrain_pool[idx]
            idx += 1

    # Place 2 cities at max torus distance
    city0_q, city0_r = 2, 2
    city1_q, city1_r = MAP_W - 3, MAP_H - 3
    grid[city0_r][city0_q]["terrain"] = Terrain.CITY
    grid[city1_r][city1_q]["terrain"] = Terrain.CITY

    # Ensure plains near cities
    for cq, cr in [(city0_q, city0_r), (city1_q, city1_r)]:
        for dq, dr in HEX_DIRS:
            nq, nr = wrap(cq + dq, cr + dr)
            if grid[nr][nq]["terrain"] == Terrain.WATER:
                grid[nr][nq]["terrain"] = Terrain.PLAIN

    return grid


def get_terrain_hex(grid, q, r):
    """Get terrain at hex coordinate."""
    return grid[r][q]["terrain"]


def get_facility_hex(grid, q, r):
    """Get facility at hex coordinate."""
    return grid[r][q].get("facility")


def set_facility_hex(grid, q, r, facility):
    """Set facility at hex coordinate."""
    grid[r][q]["facility"] = facility


def remove_facility_hex(grid, q, r):
    """Remove facility at hex coordinate."""
    grid[r][q]["facility"] = None
