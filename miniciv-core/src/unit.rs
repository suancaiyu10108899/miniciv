// 单位 / 城市 / 设施 — Phase 4
// 翻译自 prototype/unit.py (98行)
//
// 纯数据容器。不含游戏逻辑(战斗公式在 combat.rs，移动在 movement.rs)。
//
// Rust 新概念:
//   #[derive(...)]              — 自动生成 trait 实现(≈ C++ 代码生成器)
//   impl Unit { fn create() }   — 关联函数(≈ C++ 静态工厂方法，不是构造函数)
//   Self                        — 在 impl 块内指代"当前类型"(≈ C++ 的 className)
//   pub 字段                     — Rust 默认私有，pub 才公开(和 C++ 相反)

use serde::{Deserialize, Serialize};

// ─── 单位类型 ────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum UnitType {
    Infantry,  // 步兵
    Cavalry,   // 骑兵
    Archer,    // 弓手
    Scout,     // 侦察兵
    Worker,    // 工人
}

// ─── 设施类型 ────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum FacilityType {
    Farm,        // 农场 — 产出粮食
    Lumbermill,  // 伐木场 — 产出木材
    Mine,        // 矿山 — 产出金币
}

// ─── 单位属性表 ─────────────────────────────────────
// 来自 prototype/constants.py UNIT_STATS
// 格式: (hp, atk, def, move_speed, vision, can_enter_mountain, ranged, range_dist)

struct UnitStats {
    hp: i32,
    atk: i32,
    def: i32,
    move_speed: u8,
    vision: u8,
    can_enter_mountain: bool,
    ranged: bool,
    range_dist: u8,
}

// 查找表——用 match 替代 Python 的 UNIT_STATS[unit_type] 字典
fn get_stats(ut: UnitType) -> UnitStats {
    match ut {
        UnitType::Infantry => UnitStats { hp: 100, atk: 45, def: 30, move_speed: 1, vision: 2, can_enter_mountain: true,  ranged: false, range_dist: 0 },
        UnitType::Cavalry  => UnitStats { hp: 80,  atk: 60, def: 15, move_speed: 2, vision: 2, can_enter_mountain: false, ranged: false, range_dist: 0 },
        UnitType::Archer   => UnitStats { hp: 60,  atk: 50, def: 10, move_speed: 1, vision: 2, can_enter_mountain: true,  ranged: true,  range_dist: 2 },
        UnitType::Scout    => UnitStats { hp: 40,  atk: 15, def: 5,  move_speed: 2, vision: 3, can_enter_mountain: true,  ranged: false, range_dist: 0 },
        UnitType::Worker   => UnitStats { hp: 10,  atk: 0,  def: 0,  move_speed: 1, vision: 2, can_enter_mountain: true,  ranged: false, range_dist: 0 },
    }
}

// ─── 单位 ────────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Unit {
    pub unit_type: UnitType,
    pub player_id: u8,          // 0 或 1
    pub q: i32, pub r: i32,    // 轴向坐标(六边形)
    pub hp: i32,
    pub atk: i32,
    pub def: i32,               // "def" 不是 Rust 关键字，不需要像 Python 那样加下划线
    pub move_speed: u8,
    pub vision: u8,
    pub can_enter_mountain: bool,
    pub ranged: bool,
    pub range_dist: u8,         // 0 = 近战，2 = 射程2格
    pub alive: bool,
    pub damage_dealt: i32,      // 累计造成伤害（统计数据）
    pub damage_taken: i32,      // 累计承受伤害（统计数据）
    pub build_ticks: u8,        // P1.5深度: 建造剩余回合(0=空闲)
}

impl Unit {
    /// 工厂方法——从兵种类型名创建单位。
    /// 属性从 UnitStats 查找表读取。
    ///
    /// `Self` 在 impl Unit 块内 = Unit。
    /// 这和 C++ 在类内部用 `ClassName` 引用自身是一样的。
    pub fn create(unit_type: UnitType, player_id: u8, q: i32, r: i32) -> Self {
        let s = get_stats(unit_type);
        Self {
            unit_type,
            player_id,
            q, r,
            hp: s.hp,
            atk: s.atk,
            def: s.def,
            move_speed: s.move_speed,
            vision: s.vision,
            can_enter_mountain: s.can_enter_mountain,
            ranged: s.ranged,
            range_dist: s.range_dist,
            alive: true,
            damage_dealt: 0,
            damage_taken: 0,
            build_ticks: 0,
        }
    }

    /// 应用科技加成。
    /// `&mut self` ≈ C++ 的非 const 成员函数——可以修改成员。
    pub fn apply_tech_bonus(&mut self, bonus_type: &str, value: i32) {
        match bonus_type {
            "atk" => self.atk += value,
            "def" => self.def += value,
            "hp"  => self.hp += value,
            _ => {}  // 未知加成类型，忽略
        }
    }
}

// ─── 城市 ────────────────────────────────────────────
// 来自 prototype/constants.py: CITY_HP=80, CITY_DEF=5, CITY_BASE_FOOD=1

use crate::constants::{CITY_HP, CITY_DEF, CITY_BASE_FOOD};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct City {
    pub player_id: u8,
    pub q: i32, pub r: i32,
    pub hp: i32,
    pub def: i32,
    pub base_food: i32,
}

impl City {
    pub fn new(player_id: u8, q: i32, r: i32) -> Self {
        Self {
            player_id, q, r,
            hp: CITY_HP,
            def: CITY_DEF,
            base_food: CITY_BASE_FOOD,
        }
    }

    /// 城市是否还存在(HP > 0)?
    pub fn is_alive(&self) -> bool {
        self.hp > 0
    }
}

// ─── 设施 ────────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Facility {
    pub facility_type: FacilityType,
    pub player_id: u8,
    pub q: i32, pub r: i32,
}

impl Facility {
    /// 此设施产出哪种资源?
    pub fn output_resource(&self) -> &str {
        match self.facility_type {
            FacilityType::Farm => "food",
            FacilityType::Lumbermill => "wood",
            FacilityType::Mine => "gold",
        }
    }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_创建步兵() {
        let u = Unit::create(UnitType::Infantry, 0, 3, 5);
        assert_eq!(u.unit_type, UnitType::Infantry);
        assert_eq!(u.hp, 100);
        assert_eq!(u.atk, 45);
        assert_eq!(u.def, 30);
        assert_eq!(u.move_speed, 1);
        assert!(u.can_enter_mountain);
        assert!(!u.ranged);
        assert!(u.alive);
    }

    #[test]
    fn test_创建骑兵() {
        let u = Unit::create(UnitType::Cavalry, 1, 0, 0);
        assert_eq!(u.hp, 80);
        assert_eq!(u.atk, 60);
        assert!(!u.can_enter_mountain);  // 骑兵不能上山
    }

    #[test]
    fn test_创建弓手() {
        let u = Unit::create(UnitType::Archer, 0, 0, 0);
        assert_eq!(u.hp, 60);
        assert!(u.ranged);
        assert_eq!(u.range_dist, 2);
    }

    #[test]
    fn test_五种兵种全部可创建() {
        let types = [
            UnitType::Infantry, UnitType::Cavalry, UnitType::Archer,
            UnitType::Scout, UnitType::Worker,
        ];
        for (i, ut) in types.iter().enumerate() {
            let u = Unit::create(*ut, 0, i as i32, 0);
            assert!(u.hp > 0, "{:?} 的 HP 应该大于 0", ut);
        }
    }

    #[test]
    fn test_工厂方法确定性() {
        let u1 = Unit::create(UnitType::Infantry, 0, 0, 0);
        let u2 = Unit::create(UnitType::Infantry, 0, 0, 0);
        assert_eq!(u1.hp, u2.hp);
        assert_eq!(u1.atk, u2.atk);
        assert_eq!(u1.def, u2.def);
    }

    #[test]
    fn test_城市创建() {
        let c = City::new(0, 2, 2);
        assert_eq!(c.hp, 80);
        assert_eq!(c.def, 5);
        assert!(c.is_alive());
    }

    #[test]
    fn test_城市死亡() {
        let mut c = City::new(0, 0, 0);
        c.hp = 0;
        assert!(!c.is_alive());
    }

    #[test]
    fn test_设施产出资源() {
        let f1 = Facility { facility_type: FacilityType::Farm, player_id: 0, q: 0, r: 0 };
        let f2 = Facility { facility_type: FacilityType::Lumbermill, player_id: 0, q: 0, r: 0 };
        let f3 = Facility { facility_type: FacilityType::Mine, player_id: 0, q: 0, r: 0 };
        assert_eq!(f1.output_resource(), "food");
        assert_eq!(f2.output_resource(), "wood");
        assert_eq!(f3.output_resource(), "gold");
    }
}
