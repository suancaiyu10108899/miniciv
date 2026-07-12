// 经济系统 — Phase 5
// 翻译自 prototype/economy.py (141行)
//
// 三资源模型: 粮食(food) / 木材(wood) / 金币(gold)
// 工人可以: 建造设施(build) / 在设施上生产(produce)
// 城市可以: 生产新单位(produce_unit)
//
// Rust 新概念:
//   &str                        — 字符串切片(≈ C++ string_view)，不拥有数据
//   (i32, i32, i32)             — 元组(≈ C++ tuple/pair的泛化)
//   Option<String>              — 返回值可能是 None(≈ std::optional)
//   .any(|x| condition)         — 迭代器 + 闭包(≈ C++ std::any_of + lambda)

use crate::unit::{Unit, UnitType, City};
use crate::map::{Grid, Terrain};
use crate::constants::{
    STARTING_FOOD, STARTING_WOOD, STARTING_GOLD,
    FACILITY_OUTPUT, CITY_BASE_FOOD,
};
use crate::movement::HEX_DIRS;
use crate::constants::{MAP_W, MAP_H};
use serde::{Deserialize, Serialize};

// ─── P1.5: 红白分叉 ────────────────────────────────

/// 红白路线选择(P1.5 核心机制)。
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum Branch {
    /// 白线(资本主义/先发兑现): 产出×1.5, 周期危机(支持度暴跌)
    White,
    /// 红线(社会主义/后发追赶): 支持度回升, 积累组织度→一次性爆发
    Red,
}

/// 红线组织度兑换方式。
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum OrgRedeemMode {
    /// 西南联大: 消耗组织度 → 瞬间完成 N 个可研究科技
    LianDa,
    /// 集中力量: 消耗组织度 → 下回合产出×N
    Concentrate,
    /// 全民皆兵: 消耗组织度 → 城市免费产 N 个战斗单位
    Mobilize,
}

// ─── 资源 ────────────────────────────────────────────

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct Economy {
    pub player_id: u8,
    pub food: i32,
    pub wood: i32,
    pub gold: i32,
    /// P1.5: 支持度(0-100)。高于80=繁荣加成, 低于阈值=惩罚, 极低=动荡风险。
    pub support: i32,
    /// P1.5: 扩张次数(每次扩张增加产出基数)。
    pub expansion_level: u8,
    /// P1.5: 红白路线选择(None=未选)。
    pub branch: Option<Branch>,
    /// P1.5: 红线组织度(0-100, 高支持度每回合自动积累)。
    pub organization: i32,
    /// P1.5: 白线危机倒计时(回合数, 0=触发危机)。
    pub crisis_timer: u8,
    /// P1.5: 本回合是否已执行组织度兑换(防止同回合补回)。
    pub redeemed_this_turn: bool,
    /// P1.5: 白线危机触发累计次数(instrumentation)。
    pub crisis_count: u8,
    /// P1.5: 红线组织度兑换累计次数(instrumentation)。
    pub redeem_count: u8,
}

impl Economy {
    /// 新建经济——使用初始资源(25/25/25), 支持度默认50。
    pub fn new(player_id: u8) -> Self {
        Self {
            player_id,
            food: STARTING_FOOD,
            wood: STARTING_WOOD,
            gold: STARTING_GOLD,
            support: 50,
            expansion_level: 0,
            branch: None,
            organization: 0,
            crisis_timer: 0,
            redeemed_this_turn: false,
            crisis_count: 0,
            redeem_count: 0,
        }
    }

    /// 能否支付某项花费?
    /// cost 是 (粮食, 木材, 金币) 元组
    pub fn can_afford(&self, cost: (i32, i32, i32)) -> bool {
        self.food >= cost.0 && self.wood >= cost.1 && self.gold >= cost.2
    }

    /// 支付花费。调用前应先检查 can_afford。
    pub fn spend(&mut self, cost: (i32, i32, i32)) {
        self.food -= cost.0;
        self.wood -= cost.1;
        self.gold -= cost.2;
    }

    /// 增加指定资源
    pub fn add(&mut self, resource: &str, amount: i32) {
        match resource {
            "food" => self.food += amount,
            "wood" => self.wood += amount,
            "gold" => self.gold += amount,
            _ => {}  // 未知资源类型，忽略
        }
    }
}

// ─── 设施可建性 ──────────────────────────────────────
// 哪种地形可以建什么设施?
// Python: terrain_buildable(terrain) → "farm" | "lumbermill" | "mine" | None

fn terrain_buildable(terrain: Terrain) -> Option<&'static str> {
    match terrain {
        Terrain::Plain => Some("farm"),
        Terrain::Forest => Some("lumbermill"),
        Terrain::Mountain => Some("mine"),
        _ => None,  // 水域和城市不能建任何设施
    }
}

// ─── 单位花费表 ─────────────────────────────────────
// 来自 prototype/constants.py UNIT_COST
// 格式: (粮食, 木材, 金币)

fn unit_cost(ut: UnitType) -> (i32, i32, i32) {
    match ut {
        UnitType::Infantry => (5, 0, 0),   // 5粮
        UnitType::Cavalry  => (5, 0, 3),   // 5粮 + 3金
        UnitType::Archer   => (3, 3, 0),   // 3粮 + 3木
        UnitType::Scout    => (3, 0, 0),   // 3粮
        UnitType::Worker   => (3, 0, 0),   // 3粮
    }
}

// ─── 工人操作 ────────────────────────────────────────

/// 工人在当前位置建造设施。
/// 返回 true 表示建造成功。
///
/// 前置条件: 当前位置的地形可建(平原→农场, 森林→伐木场, 山地→矿山)
///          且该格没有已有设施。
pub fn worker_action_build(worker: &Unit, grid: &mut Grid, pid: u8) -> bool {
    let tile = grid.get(worker.q, worker.r);
    let buildable = terrain_buildable(tile.terrain);
    if buildable.is_none() {
        return false;
    }
    if tile.facility.is_some() {
        return false;  // 已有设施，不能重复建造
    }

    let facility_type = match buildable.unwrap() {
        "farm" => crate::unit::FacilityType::Farm,
        "lumbermill" => crate::unit::FacilityType::Lumbermill,
        "mine" => crate::unit::FacilityType::Mine,
        _ => return false,
    };

    let facility = crate::unit::Facility {
        facility_type,
        player_id: pid,
        q: worker.q,
        r: worker.r,
    };

    // 需要 get_mut 来写入
    let tile_mut = grid.get_mut(worker.q, worker.r);
    tile_mut.facility = Some(facility);
    true
}

/// 工人在当前位置的设施上生产资源。
/// 返回产出的资源类型("food"/"wood"/"gold")，无设施则返回 None。
pub fn worker_action_produce(
    worker: &Unit,
    grid: &Grid,
    pid: u8,
    economy: &mut Economy,
    tech_bonuses: Option<&crate::tech::TechBonuses>,
) -> Option<String> {
    let tile = grid.get(worker.q, worker.r);
    let facility = tile.facility.as_ref()?;  // ? = 没有设施就返回 None

    if facility.player_id != pid {
        return None;  // 不是己方设施
    }

    let resource_type = facility.output_resource().to_string();
    let mut amount = FACILITY_OUTPUT;

    // 科技加成: E1/E2/E3 各 +1 对应产出
    if let Some(bonuses) = tech_bonuses {
        match resource_type.as_str() {
            "food" => amount += bonuses.farm_bonus,
            "wood" => amount += bonuses.lumbermill_bonus,
            "gold" => amount += bonuses.mine_bonus,
            _ => {}
        }
    }

    economy.add(&resource_type, amount);
    Some(resource_type)
}

/// 在城市邻格生产新单位。
/// 返回 true 表示生产成功(有空格且资源足够)。
///
/// 六边形上城市有 6 个邻格(方格版是 4 个)。
/// 生产规则:
///   - 不能放在水域或敌方单位占据的格子上
///   - 遵守堆叠限制(每格最多 1 战斗 + 1 平民，同类别)
pub fn produce_unit(
    grid: &Grid,
    city: &City,
    economy: &mut Economy,
    unit_type: UnitType,
    all_units: &mut Vec<Unit>,
) -> bool {
    let cost = unit_cost(unit_type);
    if !economy.can_afford(cost) {
        return false;
    }

    // 单位类别判定(堆叠限制用)
    let is_civilian = |ut: UnitType| matches!(ut, UnitType::Worker);
    let cat_is_civilian = is_civilian(unit_type);

    // 遍历城市 6 个邻格
    for (dq, dr) in HEX_DIRS.iter() {
        let nq = (city.q + dq).rem_euclid(MAP_W as i32);
        let nr = (city.r + dr).rem_euclid(MAP_H as i32);
        let tile = grid.get(nq, nr);

        // 不能放在水域
        if tile.terrain == Terrain::Water {
            continue;
        }

        // 敌方单位占据 → 跳过
        let enemy_occupies = all_units.iter().any(|u| {
            u.alive && u.player_id != economy.player_id
                && u.q == nq && u.r == nr
        });
        if enemy_occupies {
            continue;
        }

        // 己方同类别单位已达堆叠上限 → 跳过
        let same_cat_count = all_units.iter().filter(|u| {
            u.alive && u.player_id == economy.player_id
                && u.q == nq && u.r == nr
                && is_civilian(u.unit_type) == cat_is_civilian
        }).count();
        if same_cat_count >= 1 {
            continue;
        }

        // 所有条件满足 → 生产
        economy.spend(cost);
        let new_unit = Unit::create(unit_type, economy.player_id, nq, nr);
        all_units.push(new_unit);
        return true;
    }

    false  // 6 个邻格都不可用
}

/// 摧毁目标格的设施。
/// 返回 true 如果确实有设施被摧毁。
pub fn destroy_facility(grid: &mut Grid, q: i32, r: i32) -> bool {
    let tile = grid.get_mut(q, r);
    if tile.facility.is_some() {
        tile.facility = None;
        return true;
    }
    false
}

/// 城市基础产出(每回合自动触发)。
/// 基础 +1 粮/回合，科技可加成。
pub fn city_base_income(economy: &mut Economy, food_bonus: i32) {
    economy.add("food", CITY_BASE_FOOD + food_bonus);
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::map::generate_map;
    use crate::unit::FacilityType;

    fn make_worker(pid: u8, q: i32, r: i32) -> Unit {
        Unit::create(UnitType::Worker, pid, q, r)
    }

    #[test]
    fn test_初始资源() {
        let e = Economy::new(0);
        assert_eq!(e.food, 25);
        assert_eq!(e.wood, 25);
        assert_eq!(e.gold, 25);
    }

    #[test]
    fn test_支付和负担检查() {
        let mut e = Economy::new(0);
        assert!(e.can_afford((10, 5, 3)));
        assert!(!e.can_afford((100, 0, 0)));
        e.spend((10, 5, 3));
        assert_eq!(e.food, 15);
        assert_eq!(e.wood, 20);
        assert_eq!(e.gold, 22);
    }

    #[test]
    fn test_增加资源() {
        let mut e = Economy::new(0);
        e.add("food", 5);
        e.add("wood", 3);
        assert_eq!(e.food, 30);
        assert_eq!(e.wood, 28);
    }

    #[test]
    fn test_地形可建性() {
        assert_eq!(terrain_buildable(Terrain::Plain), Some("farm"));
        assert_eq!(terrain_buildable(Terrain::Forest), Some("lumbermill"));
        assert_eq!(terrain_buildable(Terrain::Mountain), Some("mine"));
        assert_eq!(terrain_buildable(Terrain::Water), None);
        assert_eq!(terrain_buildable(Terrain::City), None);
    }

    #[test]
    fn test_在平原上建农场() {
        let w = make_worker(0, 5, 5);
        let mut grid = generate_map(42, "balanced", 15, 2);
        // 确保该格是平原且无设施
        let tile_mut = grid.get_mut(5, 5);
        tile_mut.terrain = Terrain::Plain;
        tile_mut.facility = None;

        let ok = worker_action_build(&w, &mut grid, 0);
        assert!(ok);

        let tile = grid.get(5, 5);
        let f = tile.facility.as_ref().unwrap();
        assert_eq!(f.facility_type, FacilityType::Farm);
        assert_eq!(f.player_id, 0);
    }

    #[test]
    fn test_不能在水域上建设施() {
        let w = make_worker(0, 3, 3);
        let mut grid = generate_map(777, "balanced", 15, 2);
        // 把目标格设为水域
        grid.get_mut(3, 3).terrain = Terrain::Water;

        let ok = worker_action_build(&w, &mut grid, 0);
        assert!(!ok);
    }

    #[test]
    fn test_不能重复建造() {
        let w = make_worker(0, 5, 5);
        let mut grid = generate_map(42, "balanced", 15, 2);
        grid.get_mut(5, 5).terrain = Terrain::Plain;
        grid.get_mut(5, 5).facility = None;

        // 第一次成功
        assert!(worker_action_build(&w, &mut grid, 0));
        // 第二次失败——已有设施
        assert!(!worker_action_build(&w, &mut grid, 0));
    }

    #[test]
    fn test_城市基础产出() {
        let mut e = Economy::new(0);
        let before = e.food;
        city_base_income(&mut e, 0);
        assert_eq!(e.food, before + CITY_BASE_FOOD);
    }
}
