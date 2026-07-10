// 战斗结算 — Phase 4
// 翻译自 prototype/combat.py (100行)
//
// 公式(GDD 固定伤害):
//   damage = max(1, ATK + 攻击方地形DEF - 防守方DEF - 防守方地形DEF)
//
// 近战: 双方互打。弓手: 只攻方输出，守方不还手。
// 骑兵冲锋: 走2格平原后攻击 → +10 ATK
// 城市占领: 渐进伤害，弓手不能占城
//
// Rust 新概念:
//   &mut Unit          — 可变引用(≈ C++ 非 const 指针/引用)，可以修改 HP
//   -> MeleeResult     — 返回结构体。Rust 惯例: 纯数据用 struct 返回
//   max(1, x)          — std::cmp::max，和 C++ 的 std::max 一样

use crate::unit::{Unit, UnitType, City};
use crate::map::Terrain;
use crate::constants::CAVALRY_CHARGE_BONUS;

/// 近战结算结果
#[derive(Debug, PartialEq)]
pub struct MeleeResult {
    pub att_damage: i32,       // 攻击方造成伤害
    pub def_damage: i32,       // 防守方造成伤害
    pub attacker_alive: bool,  // 攻击方是否存活
    pub defender_alive: bool,  // 防守方是否存活
}

/// 远程攻击结果
#[derive(Debug, PartialEq)]
pub struct RangedResult {
    pub damage: i32,
    pub target_alive: bool,
}

/// 计算单次攻击的伤害值(GDD 核心公式)。
///
/// damage = max(1, atk + att_terrain_DEF - def - def_terrain_DEF)
///
/// 最小值保证为 1——即使工人打城市也至少造成 1 点伤害。
/// 这防止了"永远打不动"的僵局。
fn calc_damage(atk: i32, att_terrain_def: i32, def: i32, def_terrain_def: i32) -> i32 {
    let raw = atk + att_terrain_def - def - def_terrain_def;
    raw.max(1)  // 最少 1 点伤害
}

/// 近战结算: 双方互打。
///
/// 参数:
///   attacker, defender  — 攻守双方(都会被修改 HP)
///   terrain_att, terrain_def — 攻守双方所在地形
///   attacker_just_charged — 骑兵是否刚完成冲锋(走2格平原)
///
/// 返回值包含双方的伤害和存活状态。
///
/// `&mut Unit` = 可变借用——调用者把单位的修改权临时交给这个函数。
/// 函数返回后，借用结束，调用者恢复对单位的控制。
/// 同一个单位不能同时有两个 `&mut`——编译器在编译时检查这一点。
pub fn resolve_melee(
    attacker: &mut Unit,
    defender: &mut Unit,
    terrain_att: Terrain,
    terrain_def: Terrain,
    attacker_just_charged: bool,
) -> MeleeResult {
    let att_bonus = terrain_att.def_bonus();
    let def_bonus = terrain_def.def_bonus();

    // 攻方对守方造成的伤害
    let mut att_damage = calc_damage(attacker.atk, att_bonus, defender.def, def_bonus);

    // 守方对攻方造成的伤害
    let mut def_damage = calc_damage(defender.atk, def_bonus, attacker.def, att_bonus);

    // 骑兵冲锋额外加成(走2格平原后触发)
    if attacker.unit_type == UnitType::Cavalry && attacker_just_charged {
        att_damage += CAVALRY_CHARGE_BONUS;  // +10
    }

    // 应用伤害
    defender.hp -= att_damage;
    attacker.hp -= def_damage;

    // 统计累计伤害(用于数据分析)
    attacker.damage_dealt += att_damage;
    attacker.damage_taken += def_damage;
    defender.damage_dealt += def_damage;
    defender.damage_taken += att_damage;

    // 判定死亡
    if defender.hp <= 0 {
        defender.hp = 0;
        defender.alive = false;
    }
    if attacker.hp <= 0 {
        attacker.hp = 0;
        attacker.alive = false;
    }

    MeleeResult {
        att_damage,
        def_damage,
        attacker_alive: attacker.alive,
        defender_alive: defender.alive,
    }
}

/// 远程攻击: 弓手射击目标。守方不还手。
///
/// 弓手自身地形不参与伤害计算——只有目标的地形影响防御。
/// 这是弓手的核心战术价值: 站在安全位置输出伤害。
///
/// # Panics
/// 如果 archer 不是远程单位(ranged == false)会 panic——
/// 这是调用者的 bug，应该在 AI 逻辑层面避免。
pub fn resolve_ranged(
    archer: &mut Unit,
    target: &mut Unit,
    terrain_target: Terrain,
) -> RangedResult {
    // 断言: 调用者必须确保这是远程单位。不是 → panic(调用者bug)
    assert!(
        archer.ranged,
        "resolve_ranged 被非远程单位 {} 调用",
        match archer.unit_type {
            UnitType::Infantry => "步兵",
            UnitType::Cavalry => "骑兵",
            UnitType::Scout => "侦察兵",
            UnitType::Worker => "工人",
            UnitType::Archer => "弓手(不应该到这里)",
        }
    );

    let def_bonus = terrain_target.def_bonus();
    let damage = calc_damage(archer.atk, 0, target.def, def_bonus);

    target.hp -= damage;
    archer.damage_dealt += damage;
    target.damage_taken += damage;

    if target.hp <= 0 {
        target.hp = 0;
        target.alive = false;
    }

    RangedResult {
        damage,
        target_alive: target.alive,
    }
}

/// 检查单位能否占领城市。
/// 弓手不能占城——这是游戏规则(GDD 原始设计)。
pub fn can_occupy_city(unit: &Unit, city: &City) -> bool {
    if unit.ranged {
        return false;
    }
    let damage = (unit.atk - city.def).max(1);
    damage >= city.hp
}

/// 城市占领伤害——近战单位入城时对城市 HP 造成的伤害。
/// 公式: max(1, ATK - CITY_DEF)
pub fn city_occupation_damage(unit: &Unit, city: &City) -> i32 {
    (unit.atk - city.def).max(1)
}

// ═══════════════════════════════════════════════════════
// 测试 — 覆盖 GDD 的战斗示例
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    // ── 辅助: 快速创建测试单位 ──────────────────────

    fn make(ut: UnitType, hp: i32) -> Unit {
        let mut u = Unit::create(ut, 0, 0, 0);
        u.hp = hp;  // 覆盖默认 HP 方便测试
        u
    }

    // ── 近战测试 ─────────────────────────────────────

    #[test]
    fn test_步兵对步兵_平原对平原() {
        let mut a = make(UnitType::Infantry, 100);
        let mut d = make(UnitType::Infantry, 100);
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::Plain, false);
        // att_damage = max(1, 45+0-30-0) = 15
        // def_damage = max(1, 45+0-30-0) = 15
        assert_eq!(r.att_damage, 15);
        assert_eq!(r.def_damage, 15);
        assert_eq!(a.hp, 85);
        assert_eq!(d.hp, 85);
        assert!(r.attacker_alive);
        assert!(r.defender_alive);
    }

    #[test]
    fn test_骑兵冲锋_平原对平原步兵() {
        let mut a = make(UnitType::Cavalry, 80);
        let mut d = make(UnitType::Infantry, 100);
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::Plain, true);
        // att_damage = max(1, 60+0-30-0) + 10(冲锋) = 30 + 10 = 40
        assert_eq!(r.att_damage, 40);
        assert_eq!(d.hp, 60);
    }

    #[test]
    fn test_骑兵对山地步兵_冲锋有效但地形抵消() {
        let mut a = make(UnitType::Cavalry, 80);
        let mut d = make(UnitType::Infantry, 100);
        // 步兵在山地上: DEF+15 → 有效DEF=30+15=45
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::Mountain, true);
        // att_damage = max(1, 60+0-30-15) + 10(冲锋) = 15 + 10 = 25
        assert_eq!(r.att_damage, 25);
    }

    #[test]
    fn test_森林防守方受伤更少() {
        let mut a1 = make(UnitType::Infantry, 100);
        let mut d1 = make(UnitType::Infantry, 100);
        let r1 = resolve_melee(&mut a1, &mut d1, Terrain::Plain, Terrain::Plain, false);

        let mut a2 = make(UnitType::Infantry, 100);
        let mut d2 = make(UnitType::Infantry, 100);
        let r2 = resolve_melee(&mut a2, &mut d2, Terrain::Plain, Terrain::Forest, false);

        // 森林 DEF+10 → 守方受伤更少
        assert!(r2.att_damage < r1.att_damage,
            "森林防守方应受伤更少: 平原={} 森林={}", r1.att_damage, r2.att_damage);
    }

    #[test]
    fn test_最小伤害为1() {
        let mut a = make(UnitType::Worker, 10);  // ATK=0
        let mut d = make(UnitType::Infantry, 100);
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::City, false);
        // ATK=0, 守方DEF=30+25=55 → raw=0-55=-55 → max(1, -55)=1
        assert_eq!(r.att_damage, 1, "最小伤害应该是 1");
    }

    #[test]
    fn test_击杀单位() {
        let mut a = make(UnitType::Infantry, 100);
        let mut d = make(UnitType::Worker, 5);  // HP=5
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::Plain, false);
        // att_damage = max(1,45+0-0-0) = 45 → d.hp = 5-45 = -40 → 死亡
        assert!(!r.defender_alive);
        assert_eq!(d.hp, 0);
        assert!(!d.alive);
    }

    #[test]
    fn test_同归于尽() {
        let mut a = make(UnitType::Infantry, 5);
        let mut d = make(UnitType::Infantry, 5);
        let r = resolve_melee(&mut a, &mut d, Terrain::Plain, Terrain::Plain, false);
        assert!(!r.attacker_alive);
        assert!(!r.defender_alive);
    }

    // ── 远程测试 ─────────────────────────────────────

    #[test]
    fn test_弓手射击_守方不还手() {
        let mut archer = make(UnitType::Archer, 60);
        let mut target = make(UnitType::Cavalry, 80);
        let hp_before = archer.hp;
        let r = resolve_ranged(&mut archer, &mut target, Terrain::Plain);
        // damage = max(1,50+0-15-0) = 35
        assert_eq!(r.damage, 35);
        assert_eq!(target.hp, 45);
        assert_eq!(archer.hp, hp_before);  // 弓手不受伤！
        assert!(r.target_alive);
    }

    #[test]
    fn test_弓手射击山地目标_伤害减少() {
        let mut archer = make(UnitType::Archer, 60);
        let mut target = make(UnitType::Infantry, 100);
        let r = resolve_ranged(&mut archer, &mut target, Terrain::Mountain);
        // damage = max(1,50+0-30-15) = 5
        assert_eq!(r.damage, 5);
    }

    #[test]
    #[should_panic(expected = "resolve_ranged 被非远程单位")]
    fn test_非远程单位调用远程攻击会panic() {
        let mut infantry = make(UnitType::Infantry, 100);
        let mut target = make(UnitType::Infantry, 100);
        resolve_ranged(&mut infantry, &mut target, Terrain::Plain);
    }

    // ── 城市占领测试 ─────────────────────────────────

    #[test]
    fn test_弓手不能占城() {
        let archer = make(UnitType::Archer, 60);
        let city = City::new(0, 0, 0);
        assert!(!can_occupy_city(&archer, &city));
    }

    #[test]
    fn test_步兵可以占城() {
        let infantry = make(UnitType::Infantry, 100);
        let mut city = City::new(1, 0, 0);
        city.hp = 10;  // 重伤城市
        // damage = max(1, 45-5) = 40 >= city.hp(10)
        assert!(can_occupy_city(&infantry, &city));
    }

    #[test]
    fn test_城市占领伤害计算() {
        let unit = make(UnitType::Infantry, 100);
        let city = City::new(0, 0, 0);
        let dmg = city_occupation_damage(&unit, &city);
        assert_eq!(dmg, 40);  // max(1, 45-5) = 40
    }
}
