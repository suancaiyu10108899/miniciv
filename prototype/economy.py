# prototype/economy.py — 经济系统（工人操作+设施+资源+生产）

from prototype.terrain import Terrain, terrain_buildable
from prototype.mapgen import get_terrain, get_facility, set_facility, remove_facility
from prototype.unit import Unit, Facility
from prototype.constants import (
    UNIT_COST, STARTING_RESOURCES, CITY_BASE_FOOD, FACILITY_OUTPUT,
)


class Economy:
    """每方独立的经济状态"""

    def __init__(self, player_id: int):
        self.pid = player_id
        self.food = STARTING_RESOURCES["food"]
        self.wood = STARTING_RESOURCES["wood"]
        self.gold = STARTING_RESOURCES["gold"]

    def can_afford(self, cost: tuple[int, int, int]) -> bool:
        f, w, g = cost
        return self.food >= f and self.wood >= w and self.gold >= g

    def spend(self, cost: tuple[int, int, int]):
        f, w, g = cost
        self.food -= f
        self.wood -= w
        self.gold -= g

    def add(self, resource: str, amount: int):
        if resource == "food":
            self.food += amount
        elif resource == "wood":
            self.wood += amount
        elif resource == "gold":
            self.gold += amount


def worker_action_move(worker: Unit, grid, dx: int, dy: int):
    """工人移动 1 格（使用 1 操作）"""
    from prototype.movement import apply_move
    apply_move(worker, grid, dx, dy)


def worker_action_build(worker: Unit, grid, pid: int) -> bool:
    """
    工人在当前位置建造设施。
    返回 True 如果建造成功。
    """
    terrain = get_terrain(grid, worker.x, worker.y)
    buildable = terrain_buildable(terrain)
    if buildable is None:
        return False
    existing = get_facility(grid, worker.x, worker.y)
    if existing is not None:
        return False  # 已有设施
    facility = Facility(buildable, pid, worker.x, worker.y)
    set_facility(grid, worker.x, worker.y, facility)
    return True


def worker_action_produce(worker: Unit, grid, pid: int, economy: Economy,
                          tech_bonuses: dict = None) -> str | None:
    """
    工人在当前位置的设施上生产。
    返回产出资源类型（"food"/"wood"/"gold"），如果无设施则返回 None。
    """
    facility = get_facility(grid, worker.x, worker.y)
    if facility is None:
        return None
    if facility.player_id != pid:
        return None  # 不是己方设施

    resource_type = facility.output_resource()
    amount = FACILITY_OUTPUT[facility.facility_type].get(resource_type, 1)

    # 科技加成
    if tech_bonuses:
        if resource_type == "food" and "farm_bonus" in tech_bonuses:
            amount += tech_bonuses["farm_bonus"]
        elif resource_type == "wood" and "lumbermill_bonus" in tech_bonuses:
            amount += tech_bonuses["lumbermill_bonus"]
        elif resource_type == "gold" and "mine_bonus" in tech_bonuses:
            amount += tech_bonuses["mine_bonus"]

    economy.add(resource_type, amount)
    return resource_type


def produce_unit(grid, city, economy: Economy, unit_type: str,
                 all_units: list) -> bool:
    """
    在城市四邻格生产单位。
    返回 True 如果生产成功。
    """
    if unit_type not in UNIT_COST:
        return False
    cost = UNIT_COST[unit_type]
    if not economy.can_afford(cost):
        return False

    # 单位类别判定
    def _is_civilian(utype): return utype == "worker"
    cat_is_civilian = _is_civilian(unit_type)
    max_per_tile = 1  # 每格最多1战斗+1平民

    H, W = len(grid), len(grid[0])
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        nx, ny = (city.x + dx) % W, (city.y + dy) % H
        terrain = get_terrain(grid, nx, ny)
        if terrain == Terrain.WATER:
            continue
        # 敌方单位占据→跳过
        if any(u.alive and u.player_id != economy.pid and u.x == nx and u.y == ny for u in all_units):
            continue
        # 己方同类别单位已达上限→跳过
        same_cat_count = sum(1 for u in all_units
                            if u.alive and u.player_id == economy.pid
                            and u.x == nx and u.y == ny
                            and _is_civilian(u.unit_type) == cat_is_civilian)
        if same_cat_count >= max_per_tile:
            continue

        economy.spend(cost)
        new_unit = Unit.create(unit_type, economy.pid, nx, ny)
        all_units.append(new_unit)
        return True
    return False


def destroy_facility(grid, x: int, y: int) -> bool:
    """摧毁目标格的设施。返回 True 如果确实有设施被摧毁。"""
    if get_facility(grid, x, y) is not None:
        remove_facility(grid, x, y)
        return True
    return False


def city_base_income(economy: Economy, food_bonus: int = 0):
    """城市基础产出"""
    economy.add("food", CITY_BASE_FOOD + food_bonus)
