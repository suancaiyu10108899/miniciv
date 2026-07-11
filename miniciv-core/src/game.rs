// 游戏循环 — Phase 6
// 翻译自 prototype_hex/game_hex.py (227行)
//
// 核心流程:
//   init_game(seed, generator) → GameState
//   loop { step_game(&mut gs, actions_p0, actions_p1) → StepResult }
//
// 交替先手: 奇数回合 P0 先执行, 偶数回合 P1 先执行
// 科技 tick: 双方同时(消除 P0 研究先手优势)
// 胜利判定(每回合): 征服 → 建设 → 阶梯(80回合)
//
// Rust 新概念:
//   &mut GameState — 独占可变借用(整个游戏循环持有)
//   Vec<Action>     — AI 返回的动作列表
//   聚合初始化      — GameState { seed, size, ... } 所有字段必须填

use crate::map::{Grid, generate_map};
use crate::unit::{Unit, UnitType, City};
use crate::economy::Economy;
use crate::tech::TechManager;
use crate::ai::Action;
use crate::constants::{
    MAP_W, MAP_H,
};
use crate::movement::HEX_DIRS;
use crate::combat::{resolve_melee, resolve_ranged, city_occupation_damage};
use crate::economy::{
    worker_action_build, worker_action_produce, produce_unit,
    destroy_facility, city_base_income,
};
use serde::{Deserialize, Serialize};

// ─── 胜利类型 ────────────────────────────────────────

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum VictoryType {
    Conquest,              // 征服: 敌方城市 HP ≤ 0
    Construction,          // 建设: C5 完成 + 设施 ≥ 4
    TiebreakConstruction,  // 阶梯: 建设科技数
    TiebreakCityHp,        // 阶梯: 城市 HP
    TiebreakRandom,        // 阶梯: 随机
}

// ─── 回合结果 ────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepResult {
    pub turn: u16,
    pub winner: Option<u8>,              // None = 游戏继续
    pub victory_type: Option<VictoryType>,
}

// ─── 游戏状态 ────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameState {
    pub seed: u64,
    pub size: u8,
    pub generator_id: String,
    pub turn: u16,
    pub grid: Grid,
    pub units: Vec<Unit>,
    pub cities: Vec<City>,
    pub economies: Vec<Economy>,
    pub techs: Vec<TechManager>,
    pub winner: Option<u8>,
    pub victory_type: Option<VictoryType>,
    pub dead_units: Vec<Unit>,
    pub config: crate::config::GameConfig,
}

// ─── 初始化 ──────────────────────────────────────────

/// 初始化一局新游戏。
///
/// 流程:
///   1. 生成地图
///   2. 找到两座城市的位置
///   3. 放置初始单位(3工人 + 1侦察兵, 放在城市邻格平原上)
///   4. 初始化经济和科技
pub fn init_game(seed: u64, generator_id: &str) -> GameState {
    init_game_with_config(seed, generator_id, crate::config::GameConfig::default())
}

/// 用指定配置初始化游戏(M1.1: 参数可配置化的入口)。
pub fn init_game_with_config(seed: u64, generator_id: &str, config: crate::config::GameConfig) -> GameState {
    let grid = generate_map(seed, generator_id);
    // Wrap generator_id in String for owned storage
    let gen_id = generator_id.to_string();

    // 找到城市位置
    let mut city_positions: Vec<(i32, i32)> = Vec::new();
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if grid.get(q, r).terrain == crate::map::Terrain::City {
                city_positions.push((q, r));
            }
        }
    }
    // 按 (r, q) 排序——和 Python 一致
    city_positions.sort_by_key(|&(q, r)| (r, q));
    let (cq0, cr0) = city_positions[0];
    let (cq1, cr1) = city_positions[1];

    let mut cities = vec![
        City::new(0, cq0, cr0),
        City::new(1, cq1, cr1),
    ];
    // M1.1: 用 config 覆盖城市数值
    for c in &mut cities {
        c.hp = config.city_hp;
        c.def = config.city_def;
        c.base_food = config.city_base_food;
    }

    // 放置初始单位: 每个玩家 3 工人 + 1 侦察兵
    let mut units = Vec::new();
    for (pid, (city_q, city_r)) in [(0, (cq0, cr0)), (1, (cq1, cr1))].iter() {
        let pid = *pid;
        let cx = *city_q;
        let cy = *city_r;

        // 放置工人(放在城市邻格的平原上)
        for _ in 0..config.starting_workers {
            for (dq, dr) in HEX_DIRS.iter() {
                let nq = (cx + dq).rem_euclid(MAP_W as i32);
                let nr = (cy + dr).rem_euclid(MAP_H as i32);
                if grid.get(nq, nr).terrain == crate::map::Terrain::Plain {
                    // 检查是否已被占用
                    let occupied = units.iter().any(|u: &Unit| u.q == nq && u.r == nr);
                    if !occupied {
                        units.push(Unit::create(UnitType::Worker, pid, nq, nr));
                        break;
                    }
                }
            }
        }
        // 放置侦察兵
        for _ in 0..config.starting_scouts {
            for (dq, dr) in HEX_DIRS.iter() {
                let nq = (cx + dq).rem_euclid(MAP_W as i32);
                let nr = (cy + dr).rem_euclid(MAP_H as i32);
                if grid.get(nq, nr).terrain == crate::map::Terrain::Plain {
                    let occupied = units.iter().any(|u: &Unit| u.q == nq && u.r == nr);
                    if !occupied {
                        units.push(Unit::create(UnitType::Scout, pid, nq, nr));
                        break;
                    }
                }
            }
        }
    }

    let mut economies = vec![Economy::new(0), Economy::new(1)];
    for e in &mut economies {
        e.food = config.starting_food;
        e.wood = config.starting_wood;
        e.gold = config.starting_gold;
    }
    let mut techs = vec![TechManager::new(0), TechManager::new(1)];
    for t in &mut techs {
        t.academy_increment = config.academy_research_increment;
    }

    GameState {
        seed,
        size: MAP_W,
        generator_id: gen_id,
        turn: 0,
        grid,
        units,
        cities,
        economies,
        techs,
        winner: None,
        victory_type: None,
        dead_units: Vec::new(),
        config,
    }
}

// ─── 回合执行 ────────────────────────────────────────

/// 执行一回合。
///
/// `actions_p0`, `actions_p1`: 每个玩家各自 AI 返回的动作列表。
/// 交替先手: 奇数回合 P0 先, 偶数回合 P1 先。
///
/// 每个单位可执行一个动作, 动作顺序由 AI 决定。
/// 所有动作执行完毕后: 科技研究推进(双方同时) → 城市基础产出 → 胜利判定。
pub fn step_game(
    gs: &mut GameState,
    actions_p0: &[Action],
    actions_p1: &[Action],
) -> StepResult {
    gs.turn += 1;

    // 交替先手: 奇数回合 P0 先, 偶数回合 P1 先
    let player_order: [(u8, &[Action]); 2] = if gs.turn % 2 == 1 {
        [(0, actions_p0), (1, actions_p1)]
    } else {
        [(1, actions_p1), (0, actions_p0)]
    };

    for (pid, actions) in player_order.iter() {
        let pid = *pid;

        // 收集当前玩家的存活单位列表(用于 unit_idx 索引)
        let player_units: Vec<usize> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .map(|(i, _)| i)
            .collect();

        let bonuses = gs.techs[pid as usize].get_tech_bonuses();

        for act in actions.iter() {
            match act {
                Action::Move { unit_idx, dq, dr } => {
                    if let Some(&global_idx) = player_units.get(*unit_idx) {
                        let dq = *dq;
                        let dr = *dr;
                        do_move(gs, global_idx, dq, dr);
                    }
                }
                Action::Build { unit_idx } => {
                    if let Some(&global_idx) = player_units.get(*unit_idx) {
                        let unit = &gs.units[global_idx];
                        if unit.unit_type == UnitType::Worker {
                            worker_action_build(unit, &mut gs.grid, pid);
                        }
                    }
                }
                Action::Produce { unit_idx } => {
                    if let Some(&global_idx) = player_units.get(*unit_idx) {
                        let unit = &gs.units[global_idx];
                        if unit.unit_type == UnitType::Worker {
                            worker_action_produce(
                                unit, &gs.grid, pid,
                                &mut gs.economies[pid as usize],
                                Some(&bonuses),
                            );
                        }
                    }
                }
                Action::ProduceUnit { unit_type } => {
                    let ut = match unit_type.as_str() {
                        "infantry" => UnitType::Infantry,
                        "cavalry" => UnitType::Cavalry,
                        "archer" => UnitType::Archer,
                        "scout" => UnitType::Scout,
                        "worker" => UnitType::Worker,
                        _ => continue,
                    };
                    let city = &gs.cities[pid as usize];
                    produce_unit(
                        &gs.grid, city,
                        &mut gs.economies[pid as usize],
                        ut, &mut gs.units,
                    );
                }
                Action::Research { tech_id } => {
                    let tech = &mut gs.techs[pid as usize];
                    if let Some(cost) = TechManager::tech_cost(tech_id) {
                        if gs.economies[pid as usize].can_afford(cost) {
                            if tech.start_research(tech_id) {
                                gs.economies[pid as usize].spend(cost);
                            }
                        }
                    }
                }
                Action::Destroy { unit_idx } => {
                    if let Some(&global_idx) = player_units.get(*unit_idx) {
                        let unit = &gs.units[global_idx];
                        destroy_facility(&mut gs.grid, unit.q, unit.r);
                    }
                }
                Action::EndTurn => {}  // 显式结束回合, 什么都不做
            }
        }

        // 城市基础产出
        let food_bonus = bonuses.city_food;
        city_base_income(&mut gs.economies[pid as usize], food_bonus);
    }

    // 科技研究推进(双方同时——消除 P0 研究先手优势)
    for pid in [0, 1] {
        gs.techs[pid as usize].tick_research();
    }

    // 建设胜利检查(每回合, 不只 C5 完成那回合)
    check_construction_victory(gs);

    // 城市防守: 每回合对占领者造成伤害
    for pid in [0, 1] {
        let city = &gs.cities[pid as usize];
        let opp = 1 - pid;
        for u in gs.units.iter_mut() {
            if u.alive && u.player_id == opp && u.q == city.q && u.r == city.r {
                u.hp -= gs.config.city_damage;
                if u.hp <= 0 {
                    u.hp = 0;
                    u.alive = false;
                }
            }
        }
    }

    // 征服胜利检查
    for pid in [0, 1] {
        if !gs.cities[1 - pid as usize].is_alive() {
            gs.winner = Some(pid);
            gs.victory_type = Some(VictoryType::Conquest);
        }
    }

    // 阶梯判定(回合上限)
    if gs.turn >= gs.config.max_turns && gs.winner.is_none() {
        tiebreak(gs);
    }

    // 清理死单位(移到 dead_units, 保留统计数据)
    let mut dead: Vec<Unit> = Vec::new();
    gs.units.retain(|u| {
        if !u.alive {
            dead.push(u.clone());
            false
        } else {
            true
        }
    });
    gs.dead_units.extend(dead);

    StepResult {
        turn: gs.turn,
        winner: gs.winner,
        victory_type: gs.victory_type.clone(),
    }
}

// ─── 移动+战斗 ───────────────────────────────────────

/// 堆叠限制
const MAX_COMBAT_PER_TILE: usize = 1;
const MAX_CIVILIAN_PER_TILE: usize = 1;

fn unit_category(ut: &UnitType) -> &str {
    match ut {
        UnitType::Worker => "civilian",
        _ => "combat",
    }
}

/// 执行单位移动+可能的战斗。
///
/// 流程:
///   1. 骑兵遇林检查(骑兵进入森林 → 停止, dq/dr 清零)
///   2. 计算目标坐标(环面 wrap)
///   3. 堆叠检查(己方同类别单位是否已满)
///   4. 目标格有敌方单位 → 战斗(近战互打 / 远程单向)
///   5. 目标格为空 → 直接移动(可能触发城市占领)
fn do_move(gs: &mut GameState, unit_idx: usize, dq: i32, dr: i32) {
    // 骑兵遇林检查: 进入森林 → 停
    let (dq, dr) = if gs.units[unit_idx].unit_type == UnitType::Cavalry {
        let nq = (gs.units[unit_idx].q + dq).rem_euclid(MAP_W as i32);
        let nr = (gs.units[unit_idx].r + dr).rem_euclid(MAP_H as i32);
        if gs.grid.get(nq, nr).terrain == crate::map::Terrain::Forest {
            (0, 0)  // 遇林则停
        } else {
            (dq, dr)
        }
    } else {
        (dq, dr)
    };

    if dq == 0 && dr == 0 {
        return;  // 没有实际移动
    }

    let nq = (gs.units[unit_idx].q + dq).rem_euclid(MAP_W as i32);
    let nr = (gs.units[unit_idx].r + dr).rem_euclid(MAP_H as i32);

    // 堆叠检查
    let cat = unit_category(&gs.units[unit_idx].unit_type);
    let max_allowed = if cat == "combat" { MAX_COMBAT_PER_TILE } else { MAX_CIVILIAN_PER_TILE };
    let friendly_count = gs.units.iter().filter(|u| {
        u.alive && u.player_id == gs.units[unit_idx].player_id
            && u.q == nq && u.r == nr
            && unit_category(&u.unit_type) == cat
    }).count();
    if friendly_count >= max_allowed {
        return;  // 无法移入——己方同类别单位已满
    }

    // 找目标格的敌方单位
    let blocker_idx = gs.units.iter().position(|u| {
        u.alive && u.player_id != gs.units[unit_idx].player_id
            && u.q == nq && u.r == nr
    });

    if let Some(blocker_idx) = blocker_idx {
        // 目标格有敌方单位 → 战斗
        let unit = &gs.units[unit_idx];
        if unit.ranged {
            // 弓手不能移入敌方格子——只能远程攻击
            let terrain_target = gs.grid.get(nq, nr).terrain;
            // 需要两个可变借用: archer 和 target。split_at_mut 来拆分。
            let (archer_idx, target_idx) = if unit_idx < blocker_idx {
                (unit_idx, blocker_idx)
            } else {
                (blocker_idx, unit_idx)
            };
            let (left, right) = gs.units.split_at_mut(target_idx);
            if unit_idx < blocker_idx {
                resolve_ranged(&mut left[archer_idx], &mut right[0], terrain_target);
            } else {
                resolve_ranged(&mut right[0], &mut left[archer_idx], terrain_target);
            }
        } else {
            // 近战——移动+攻击
            let terrain_att = gs.grid.get(gs.units[unit_idx].q, gs.units[unit_idx].r).terrain;
            let terrain_def = gs.grid.get(nq, nr).terrain;
            // 骑兵冲锋判断: 走2格+起始格是平原
            let charged = gs.units[unit_idx].unit_type == UnitType::Cavalry
                && (dq.abs() + dr.abs() == 2 || dq.abs().max(dr.abs()) >= 2)
                && gs.grid.get(
                    gs.units[unit_idx].q, gs.units[unit_idx].r).terrain == crate::map::Terrain::Plain;

            // split_at_mut 技巧: 从 Vec 中同时可变借用两个不同元素
            let (a_idx, b_idx) = if unit_idx < blocker_idx {
                (unit_idx, blocker_idx)
            } else {
                (blocker_idx, unit_idx)
            };
            let (left, right) = gs.units.split_at_mut(b_idx);
            let (attacker, defender) = if unit_idx < blocker_idx {
                (&mut left[a_idx], &mut right[0])
            } else {
                (&mut right[0], &mut left[a_idx])
            };

            let result = resolve_melee(attacker, defender, terrain_att, terrain_def, charged);

            // 胜 → 占领该格
            if result.attacker_alive && !result.defender_alive {
                attacker.q = nq;
                attacker.r = nr;
                // 占领城市?
                let opp = 1 - attacker.player_id;
                if nq == gs.cities[opp as usize].q && nr == gs.cities[opp as usize].r {
                    let dmg = city_occupation_damage(attacker, &gs.cities[opp as usize]);
                    gs.cities[opp as usize].hp -= dmg;
                    if gs.cities[opp as usize].hp <= 0 {
                        gs.cities[opp as usize].hp = 0;
                    }
                }
            }
        }
    } else {
        // 目标格为空 → 直接移动
        gs.units[unit_idx].q = nq;
        gs.units[unit_idx].r = nr;

        // 占领空城?
        let opp = 1 - gs.units[unit_idx].player_id;
        if nq == gs.cities[opp as usize].q && nr == gs.cities[opp as usize].r {
            let dmg = city_occupation_damage(&gs.units[unit_idx], &gs.cities[opp as usize]);
            gs.cities[opp as usize].hp -= dmg;
            if gs.cities[opp as usize].hp <= 0 {
                gs.cities[opp as usize].hp = 0;
            }
        }
    }
}

// ─── 胜利判定 ────────────────────────────────────────

/// 建设胜利: C5 完成 + 设施 ≥ 4 (每回合检查)
fn check_construction_victory(gs: &mut GameState) {
    for pid in [0, 1] {
        if gs.winner.is_some() {
            break;
        }
        if gs.techs[pid as usize].completed.iter().any(|c| c == "C5") {
            let mut facility_count: u8 = 0;
            for r in 0..MAP_H as i32 {
                for q in 0..MAP_W as i32 {
                    if let Some(f) = &gs.grid.get(q, r).facility {
                        if f.player_id == pid {
                            facility_count += 1;
                        }
                    }
                }
            }
            if facility_count >= gs.config.construction_require_facilities {
                gs.winner = Some(pid);
                gs.victory_type = Some(VictoryType::Construction);
            }
        }
    }
}

/// 无偏"硬币":用 game seed 派生确定性但统计无偏的 0/1。
///
/// ⚠️ bug 修复(2026-07-10 门禁2): 原 tiebreak 随机分支用 `gs.turn % 2`,
///    但 tiebreak 恒在 turn==MAX_TURNS(80,偶数)触发 → 恒判 P0 赢,
///    注释说"消除 P0 偏向"实际制造了它。
///    也不能用 `seed % 2`: paired/镜像种子恒为偶数(50000+i*100)→ 同样恒 P0。
///    用 murmur3 finalizer 把连续 seed 打散成伪随机位:
///    - 镜像(不同 seed)→ 奇偶各半 → P0 ~50%
///    - paired(同 seed 两局)→ 同判定位置 → A/B 各赢一次,完美抵消
fn unbiased_coin(seed: u64) -> u8 {
    let mut h = seed;
    h ^= h >> 33;
    h = h.wrapping_mul(0xff51afd7ed558ccd);
    h ^= h >> 33;
    h = h.wrapping_mul(0xc4ceb9fe1a85ec53);
    h ^= h >> 33;
    (h & 1) as u8
}

/// 阶梯判定: construction_count → city_hp → random
fn tiebreak(gs: &mut GameState) {
    let c0 = gs.techs[0].construction_count();
    let c1 = gs.techs[1].construction_count();

    if c0 > c1 {
        gs.winner = Some(0);
        gs.victory_type = Some(VictoryType::TiebreakConstruction);
    } else if c1 > c0 {
        gs.winner = Some(1);
        gs.victory_type = Some(VictoryType::TiebreakConstruction);
    } else if gs.cities[0].hp > gs.cities[1].hp {
        gs.winner = Some(0);
        gs.victory_type = Some(VictoryType::TiebreakCityHp);
    } else if gs.cities[1].hp > gs.cities[0].hp {
        gs.winner = Some(1);
        gs.victory_type = Some(VictoryType::TiebreakCityHp);
    } else {
        // 真·无偏随机判定(见 unbiased_coin 文档)
        gs.winner = Some(unbiased_coin(gs.seed));
        gs.victory_type = Some(VictoryType::TiebreakRandom);
    }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ai::random::RandomAgent;
    use crate::ai::Agent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    #[test]
    fn test_初始化游戏() {
        let gs = init_game(42, "balanced");
        assert_eq!(gs.turn, 0);
        assert_eq!(gs.cities.len(), 2);
        assert_eq!(gs.economies.len(), 2);
        assert_eq!(gs.techs.len(), 2);
        // 初始单位: 每方应至少有 1 个(城市邻格平原不够时可能放不全)
        let p0_count = gs.units.iter().filter(|u| u.player_id == 0 && u.alive).count();
        let p1_count = gs.units.iter().filter(|u| u.player_id == 1 && u.alive).count();
        assert!(p0_count >= 1, "P0 应该至少有 1 个初始单位, 实际: {}", p0_count);
        assert!(p1_count >= 1, "P1 应该至少有 1 个初始单位, 实际: {}", p1_count);
        assert!(gs.winner.is_none());
    }

    #[test]
    fn test_初始单位位置在城市附近() {
        let gs = init_game(777, "balanced");
        for u in &gs.units {
            let city = &gs.cities[u.player_id as usize];
            // 初始单位应该放在城市 6 邻格内
            let dq = (u.q - city.q).abs();
            let dr = (u.r - city.r).abs();
            assert!(dq <= 1 && dr <= 1, "初始单位离城市太远");
        }
    }

    #[test]
    fn test_Random_vs_Random_单局可跑完() {
        let mut gs = init_game(123, "balanced");
        let agent = RandomAgent;
        let mut rng0 = ChaCha12Rng::seed_from_u64(123);
        let mut rng1 = ChaCha12Rng::seed_from_u64(456);

        // 跑 80 回合或直到有人获胜
        while gs.winner.is_none() && gs.turn < gs.config.max_turns {
            let a0 = agent.decide(&gs, 0, &mut rng0);
            let a1 = agent.decide(&gs, 1, &mut rng1);
            step_game(&mut gs, &a0, &a1);
        }

        // 游戏必须结束(有人赢或达到回合上限)
        assert!(gs.winner.is_some() || gs.turn >= gs.config.max_turns);
    }

    #[test]
    fn test_同seed游戏确定性() {
        let run = |seed: u64| {
            let mut gs = init_game(seed, "balanced");
            let agent = RandomAgent;
            let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
            let mut rng1 = ChaCha12Rng::seed_from_u64(seed + 1);
            for _ in 0..10 {
                if gs.winner.is_some() { break; }
                let a0 = agent.decide(&gs, 0, &mut rng0);
                let a1 = agent.decide(&gs, 1, &mut rng1);
                step_game(&mut gs, &a0, &a1);
            }
            (gs.turn, gs.cities[0].hp, gs.units.len())
        };

        let r1 = run(9999);
        let r2 = run(9999);
        assert_eq!(r1, r2, "同 seed 必须产生完全相同的游戏");
    }

    #[test]
    fn test_unbiased_coin_无偏() {
        // 用 eval 实际使用的种子分布 50000+i*100(全偶数,曾导致 seed%2 恒 P0)
        let n = 2000u64;
        let p0 = (0..n).filter(|i| unbiased_coin(50000 + i * 100) == 0).count();
        let rate = p0 as f64 / n as f64;
        // 无偏应 ~50%,允许 ±3%(2000 样本 95% CI 约 ±2.2%)
        assert!((rate - 0.5).abs() < 0.03,
                "unbiased_coin 在 50000+i*100 种子上偏向: P0={:.1}%", rate * 100.0);
        // paired 抵消性:同 seed 恒返回同值
        assert_eq!(unbiased_coin(12345), unbiased_coin(12345));
    }
}
