# prototype/tech.py — 科技树 DAG

from prototype.constants import TECH_TREE


class TechManager:
    """管理单个玩家的科技研究状态"""

    def __init__(self, player_id: int):
        self.pid = player_id
        self.completed: set[str] = set()
        self.researching: str | None = None
        self.research_ticks: int = 0
        self.has_academy: bool = False  # C3 学院

    def available_to_research(self) -> list[str]:
        """返回当前可开启研究的科技列表"""
        available = []
        for tech_id, node in TECH_TREE.items():
            if tech_id in self.completed:
                continue
            if tech_id == self.researching:
                continue
            # 检查前置
            if self._requirements_met(tech_id):
                available.append(tech_id)
        return available

    def _requirements_met(self, tech_id: str) -> bool:
        """检查科技的所有前置是否满足"""
        requires = TECH_TREE[tech_id]["requires"]
        if not requires:
            return True
        # M4 requires M2 OR M3
        if tech_id == "M4":
            return ("M2" in self.completed) or ("M3" in self.completed)
        # C5 requires C3 AND C4
        if tech_id == "C5":
            return all(r in self.completed for r in requires)
        # C4 requires C2 OR C3
        if tech_id == "C4":
            return any(r in self.completed for r in requires)
        # E4 requires E2 OR E3
        if tech_id == "E4":
            return any(r in self.completed for r in requires)
        # 默认 AND
        return all(r in self.completed for r in requires)

    def start_research(self, tech_id: str) -> bool:
        """开启研究。返回 True 如果成功。"""
        if self.researching is not None:
            return False  # 槽位被占
        if tech_id in self.completed:
            return False
        if not self._requirements_met(tech_id):
            return False
        self.researching = tech_id
        self.research_ticks = 0
        return True

    def tick_research(self) -> str | None:
        """
        研究推进 1 回合。
        返回完成的科技 ID，或 None（研究中/无研究）。
        """
        if self.researching is None:
            return None

        # C3 学院：研究耗时减半→每回合 +2 ticks
        tick_increment = 2 if self.has_academy else 1
        self.research_ticks += tick_increment

        required = TECH_TREE[self.researching]["turns"]
        if self.research_ticks >= required:
            completed = self.researching
            self.completed.add(completed)
            self.researching = None
            self.research_ticks = 0

            # C3 学院效果
            if completed == "C3":
                self.has_academy = True
            return completed
        return None

    def get_tech_bonuses(self) -> dict:
        """返回当前已完成科技的加成汇总"""
        bonuses = {}
        if "M1" in self.completed:
            bonuses["infantry_atk"] = 5
            bonuses["archer_atk"] = 5
        if "M2" in self.completed:
            bonuses["cavalry_charge"] = 5
        if "M3" in self.completed:
            bonuses["infantry_def_forest_mountain"] = 10
        if "M4" in self.completed:
            bonuses["all_hp"] = 10
        if "E1" in self.completed:
            bonuses["farm_bonus"] = 1
        if "E2" in self.completed:
            bonuses["lumbermill_bonus"] = 1
        if "E3" in self.completed:
            bonuses["mine_bonus"] = 1
        if "E4" in self.completed:
            bonuses["worker_speed"] = 1
        if "C2" in self.completed:
            bonuses["city_hp"] = 30
        if "C4" in self.completed:
            bonuses["city_food"] = 2
        return bonuses

    def construction_count(self) -> int:
        """建设胜利科技完成数（C1-C5）"""
        return sum(1 for t in ["C1", "C2", "C3", "C4", "C5"] if t in self.completed)


def apply_tech_to_unit(unit, bonuses: dict):
    """将科技加成应用到单位属性"""
    if "all_hp" in bonuses:
        unit.hp += bonuses["all_hp"]
    if unit.unit_type == "infantry":
        if "infantry_atk" in bonuses:
            unit.atk += bonuses["infantry_atk"]
        if "infantry_def_forest_mountain" in bonuses:
            pass  # 战斗时动态应用
    elif unit.unit_type == "archer" and "archer_atk" in bonuses:
        unit.atk += bonuses["archer_atk"]
