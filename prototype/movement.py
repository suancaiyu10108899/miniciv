# prototype/movement.py — 移动规则 + 环面 wrap

from prototype.terrain import Terrain, terrain_passable
from prototype.mapgen import get_terrain, get_facility


# 四方向
DIRS = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
DIR_LIST = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def torus_wrap(x: int, y: int, W: int, H: int) -> tuple[int, int]:
    """环面坐标 wrap"""
    return x % W, y % H


def can_enter_tile(unit, grid, x: int, y: int) -> bool:
    """
    单位能否进入目标格。
    检查: 地形可通行 + (可选：单位类型限制)
    """
    H, W = len(grid), len(grid[0])
    nx, ny = torus_wrap(x, y, W, H)
    terrain = get_terrain(grid, nx, ny)
    return terrain_passable(terrain, unit.unit_type)


def get_legal_moves(unit, grid) -> list[tuple[int, int]]:
    """
    返回单位当前可进行的合法移动方向列表。
    骑兵特殊处理：可能返回 2 格移动的中间目标。
    注意：此函数不检查目标格是否有敌方单位——那是战斗系统的事。
    """
    H, W = len(grid), len(grid[0])
    legal = []

    for dx, dy in DIR_LIST:
        nx = unit.x + dx
        ny = unit.y + dy
        if not can_enter_tile(unit, grid, nx, ny):
            continue
        legal.append((dx, dy))

    # 骑兵：如果第一格是平原，可以继续走第二格
    if unit.unit_type == "cavalry":
        extended = []
        for dx, dy in legal:
            mx = unit.x + dx
            my = unit.y + dy
            # 第一格是平原 → 可以继续
            terrain1 = get_terrain(grid, mx, my)
            if terrain1 == Terrain.PLAIN:
                for dx2, dy2 in DIR_LIST:
                    ex = mx + dx2
                    ey = my + dy2
                    if not can_enter_tile(unit, grid, ex, ey):
                        continue
                    # 第二格不能和第一格是同一个方向（同一格）
                    if (dx2, dy2) == (0, 0):
                        continue
                    # 骑兵不能连续两个反向（来回走）
                    if dx == -dx2 and dy == -dy2:
                        continue
                    # 以两步的净位移表示
                    total_dx = dx + dx2
                    total_dy = dy + dy2
                    if (total_dx, total_dy) not in extended:
                        extended.append((total_dx, total_dy))
        legal.extend(extended)

    return legal


def get_single_step_moves(unit, grid) -> list[tuple[int, int]]:
    """返回单位单步合法移动（骑兵也返回单步）"""
    legal = []
    for dx, dy in DIR_LIST:
        nx = unit.x + dx
        ny = unit.y + dy
        if can_enter_tile(unit, grid, nx, ny):
            legal.append((dx, dy))
    return legal


def apply_move(unit, grid, dx: int, dy: int):
    """应用移动：更新单位坐标（环面 wrap）"""
    H, W = len(grid), len(grid[0])
    unit.x = (unit.x + dx) % W
    unit.y = (unit.y + dy) % H


def cavalry_forest_check(unit, grid, dx: int, dy: int) -> tuple[int, int]:
    """
    骑兵移动检查：如果第一步是森林→实际只走第一步就停。
    返回实际应用的 (dx, dy)。
    """
    if unit.unit_type != "cavalry":
        return dx, dy

    H, W = len(grid), len(grid[0])
    # 分解两步移动
    # 找出第一步
    abs_dx = abs(dx)
    abs_dy = abs(dy)

    if abs_dx <= 1 and abs_dy <= 1:
        # 单步移动或零步，无需特殊处理
        return dx, dy

    # 两步移动：先走第一步
    # 第一步的符号 = 总 dx/dy 的符号
    step1_dx = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step1_dy = 1 if dy > 0 else (-1 if dy < 0 else 0)

    mx = unit.x + step1_dx
    my = unit.y + step1_dy

    terrain1 = get_terrain(grid, mx, my)
    if terrain1 == Terrain.FOREST:
        # 遇林→停，只走第一步
        return step1_dx, step1_dy

    return dx, dy
