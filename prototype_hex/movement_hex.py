# prototype_hex/movement_hex.py — Hex grid movement (axial coords + torus)
# Replaces prototype/movement.py for hex grids.

from prototype.terrain import Terrain

# 6 hex directions in axial coordinates (q, r)
HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

# Map dimensions (same cell count as 15×15 square ≈ 225)
MAP_W = 15
MAP_H = 15


def wrap(q, r):
    """Torus wrapping for hex axial coordinates."""
    return (q % MAP_W + MAP_W) % MAP_W, (r % MAP_H + MAP_H) % MAP_H


def hex_distance(q1, r1, q2, r2):
    """Torus-aware hex distance: try 9 wrapping variants, take shortest."""
    best = 999
    for dwq in (-1, 0, 1):
        for dwr in (-1, 0, 1):
            dq = abs(q1 - (q2 + dwq * MAP_W))
            dr = abs(r1 - (r2 + dwr * MAP_H))
            ds = abs((q1 + r1) - (q2 + dwq * MAP_W + r2 + dwr * MAP_H))
            d = max(dq, dr, ds)
            if d < best:
                best = d
    return best


def get_terrain_hex(grid, q, r):
    """Get terrain at wrapped hex coordinate."""
    wq, wr = wrap(q, r)
    return grid[wr][wq]["terrain"]


def get_single_step_moves_hex(unit, grid):
    """Get legal single-step moves for a unit on hex grid.
    Returns list of (dq, dr) tuples.
    """
    moves = []
    for dq, dr in HEX_DIRS:
        nq, nr = unit.x + dq, unit.y + dr  # x=q, y=r in axial coords
        wq, wr = wrap(nq, nr)
        terrain = grid[wr][wq]["terrain"]
        if terrain == Terrain.WATER:
            continue
        if unit.unit_type == "cavalry" and terrain == Terrain.MOUNTAIN:
            continue  # cavalry can't enter mountains
        moves.append((dq, dr))
    return moves


def apply_move_hex(unit, grid, dq, dr):
    """Apply a hex move. Does NOT check legality — caller must check first.
    Does NOT handle combat — caller handles that separately.
    """
    unit.x = wrap(unit.x + dq, unit.y + dr)[0]
    unit.y = wrap(unit.x + dq, unit.y + dr)[1] if False else unit.y + dr
    # Actually simpler: wrap, then set
    nx, ny = wrap(unit.x + dq, unit.y + dr)
    unit.x = nx
    unit.y = ny


def cavalry_forest_check_hex(unit, grid, dq, dr):
    """Cavalry stops when entering forest on hex grid. Returns adjusted (dq, dr)."""
    if unit.unit_type != "cavalry":
        return dq, dr
    nq, nr = unit.x + dq, unit.y + dr
    wq, wr = wrap(nq, nr)
    if grid[wr][wq]["terrain"] == Terrain.FOREST:
        return 0, 0  # can't move into forest
    return dq, dr
