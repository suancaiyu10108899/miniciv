# prototype/fow.py — 三态迷雾（v1 半径视野）

from enum import Enum, auto
from prototype.terrain import Terrain


class Visibility(Enum):
    UNKNOWN = auto()    # 从未被任何单位看到
    EXPLORED = auto()   # 曾被看到，但当前无单位视野覆盖
    VISIBLE = auto()    # 当前在己方单位视野范围内


def init_fog(size: int) -> list[list[list[int]]]:
    """
    返回 per-player 迷雾状态。
    fog[pid][y][x] = Visibility enum value
    """
    return [
        [[Visibility.UNKNOWN for _ in range(size)] for _ in range(size)]
        for _ in range(2)
    ]


def update_fog(gs, fogs: list[list[list[int]]]):
    """
    每回合更新双方迷雾。
    fogs: per-player fog grids, modified in-place.
    """
    size = gs.size
    for pid in (0, 1):
        fog = fogs[pid]
        # 先将所有 VISIBLE → EXPLORED
        for y in range(size):
            for x in range(size):
                if fog[y][x] == Visibility.VISIBLE:
                    fog[y][x] = Visibility.EXPLORED

        # 所有 pid 的存活单位→其视野范围 = VISIBLE
        for u in gs.units:
            if not u.alive or u.player_id != pid:
                continue
            r = u.vision
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if abs(dx) + abs(dy) > r:  # 曼哈顿半径
                        continue
                    nx = (u.x + dx) % size
                    ny = (u.y + dy) % size
                    fog[ny][nx] = Visibility.VISIBLE


def is_visible(fogs, pid: int, x: int, y: int, size: int) -> bool:
    """检查 pid 是否能看见 (x,y)"""
    return fogs[pid][y % size][x % size] == Visibility.VISIBLE


def is_explored(fogs, pid: int, x: int, y: int, size: int) -> bool:
    return fogs[pid][y % size][x % size] in (Visibility.EXPLORED, Visibility.VISIBLE)
