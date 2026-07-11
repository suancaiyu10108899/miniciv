// 探针套件 — 阶段 1(第三个 AI)
//
// 目的: 每个探针钉死一条设计假设, 组成"支配性矩阵"作为第一层锚点。
//   Rusher   — 纯军事攻城: 检验"进攻能不能威胁到建设者"
//   Harasser — 骚扰工人:   检验"经济骚扰有没有用"
//
// 用法: 和 Builder 一起进 eval 矩阵。健康游戏里没有单探针对其他所有 >70% 胜。
//
// 这些不是"聪明 AI", 是针对性对抗构造 —— 便宜、证伪导向。

use crate::game::GameState;
use crate::unit::UnitType;
use crate::map::Terrain;
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, hex_distance, HEX_DIRS};
use crate::tech::TechManager;
use crate::constants::{MAP_W, MAP_H};
use rand::RngCore;

/// 朝目标 (tq,tr) 移动一步。确定性。
/// 改进(暴露探针可靠性): 原版只选"严格减小距离"的move, 被山林挡住就卡死(骑兵尤甚)。
/// 现版选合法move里到目标最近的(允许持平/绕路), 避免卡死。
fn step_toward(unit: &crate::unit::Unit, tq: i32, tr: i32, grid: &crate::map::Grid) -> Option<(i32, i32)> {
    let moves = legal_moves(unit, grid);
    if moves.is_empty() { return None; }
    let cur_d = hex_distance(unit.q, unit.r, tq, tr);
    let mut best: Option<(i32, i32)> = None;
    let mut best_d = u8::MAX;
    for (dq, dr) in moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tq, tr);
        if d < best_d {
            best_d = d;
            best = Some((dq, dr));
        }
    }
    // 允许持平移动绕路; 只在会明显远离时才不动(避免来回震荡到无意义)
    if best_d <= cur_d { best } else { None }
}

fn buildable(t: Terrain) -> bool {
    matches!(t, Terrain::Plain | Terrain::Forest | Terrain::Mountain)
}

/// 工人攒资源(建设施 → 采集), 供产兵。返回该工人的动作。
fn worker_econ_action(local_idx: usize, unit: &crate::unit::Unit, gs: &GameState, pid: u8) -> Option<Action> {
    let tile = gs.grid.get(unit.q, unit.r);
    if buildable(tile.terrain) && tile.facility.is_none() {
        return Some(Action::Build { unit_idx: local_idx });
    }
    let on_own = tile.facility.as_ref().map(|f| f.player_id == pid).unwrap_or(false);
    if on_own {
        return Some(Action::Produce { unit_idx: local_idx });
    }
    // 移动找空可建格
    let moves = legal_moves(unit, &gs.grid);
    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let nt = gs.grid.get(nq, nr);
        if buildable(nt.terrain) && nt.facility.is_none() {
            return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
        }
    }
    None
}

// ═══════════════════════════════════════════════════════
// Rusher — 纯军事攻城探针
// ═══════════════════════════════════════════════════════

pub struct RusherAgent;

impl Agent for RusherAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);

        // 研究 M1(步兵/弓手 ATK+5),助攻城
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            for t in ["M1", "M4"] {  // M1 攻击, M4 全军 HP+10
                if tech.available_to_research().iter().any(|a| a == t) {
                    if let Some(cost) = TechManager::tech_cost(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => { /* 侦察兵不参战 */ }
                _ => {
                    // 战斗单位: 直扑敌城
                    if let Some((dq, dr)) = step_toward(unit, ecq, ecr, &gs.grid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
        }

        // 城市: 每回合尽量产步兵(便宜 5/0/0, ATK 高)
        let econ = &gs.economies[pid as usize];
        if econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "Rusher" }
}

// ═══════════════════════════════════════════════════════
// Harasser — 骚扰工人探针
// ═══════════════════════════════════════════════════════

pub struct HarasserAgent;

impl Agent for HarasserAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => {}
                _ => {
                    // 战斗单位: 找最近敌方工人, 扑上去
                    let target = gs.units.iter()
                        .filter(|e| e.alive && e.player_id == opp && e.unit_type == UnitType::Worker)
                        .min_by_key(|e| hex_distance(unit.q, unit.r, e.q, e.r));
                    let (tq, tr) = match target {
                        Some(w) => (w.q, w.r),
                        None => (gs.cities[opp as usize].q, gs.cities[opp as usize].r),  // 没工人就打城
                    };
                    if let Some((dq, dr)) = step_toward(unit, tq, tr, &gs.grid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
        }

        // 城市: 产骑兵(移速 2, 快速扑杀工人)
        let econ = &gs.economies[pid as usize];
        if econ.can_afford((5, 0, 3)) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
        } else if econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "Harasser" }
}

// ═══════════════════════════════════════════════════════
// Turtle — 龟缩防守探针
// ═══════════════════════════════════════════════════════
//
// 边建设边留兵守城: 检验"防守能否挡住 Rusher"(资源17 暴露的核心缺口)。
// 研究直奔 C5(像 Builder), 但城市产步兵守家、战斗单位不出击只拦截。

pub struct TurtleAgent;

impl Agent for TurtleAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();
        let (my_cq, my_cr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

        // 研究: 直奔 C5(和 Builder 同路线)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1", "C2"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = TechManager::tech_cost(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();
        let mut soldier_count = 0u32;

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => {}
                _ => {
                    // 战斗单位: 守城。邻格有敌→攻击; 否则回撤到城市附近待命。
                    soldier_count += 1;
                    let mut acted = false;
                    for (dq, dr) in HEX_DIRS.iter() {
                        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
                        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
                        let has_enemy = gs.units.iter().any(|e|
                            e.alive && e.player_id == opp && e.q == nq && e.r == nr);
                        if has_enemy {
                            actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                            acted = true;
                            break;
                        }
                    }
                    if acted { continue; }
                    // 离城市 >1 格 → 回撤守城
                    if hex_distance(unit.q, unit.r, my_cq, my_cr) > 1 {
                        if let Some((dq, dr)) = step_toward(unit, my_cq, my_cr, &gs.grid) {
                            actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                        }
                    }
                }
            }
        }

        // 城市: 产步兵守家, 上限 4(留资源推建设)
        let econ = &gs.economies[pid as usize];
        if soldier_count < 4 && econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "Turtle" }
}

// ═══════════════════════════════════════════════════════
// Defender — 攻防兼顾(步兵+弓箭手协调防守)
// ═══════════════════════════════════════════════════════
//
// 修正 Turtle 两个失败点:
//   1. 产工人确保建够 4 设施(Turtle 只 3 个没触发建设胜利)
//   2. 用弓箭手(战斗效率最高, 不还手)而非纯步兵
// 目标: 既建够设施能建设胜利, 又用高效兵种守住城。

pub struct DefenderAgent;

impl Agent for DefenderAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();
        let (my_cq, my_cr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

        // 研究: 直奔 C5
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1", "M1", "C2"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = TechManager::tech_cost(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        // 统计己方各兵种
        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();
        let mut n_worker = 0u32;
        let mut n_archer = 0u32;
        let mut n_infantry = 0u32;
        for (_, u) in &player_units {
            match u.unit_type {
                UnitType::Worker => n_worker += 1,
                UnitType::Archer => n_archer += 1,
                UnitType::Infantry => n_infantry += 1,
                _ => {}
            }
        }

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => {}
                _ => {
                    // 战斗单位守城: 邻格有敌→攻击(弓箭手不还手先手); 否则回撤守城
                    let mut acted = false;
                    for (dq, dr) in HEX_DIRS.iter() {
                        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
                        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
                        let has_enemy = gs.units.iter().any(|e|
                            e.alive && e.player_id == opp && e.q == nq && e.r == nr);
                        if has_enemy {
                            actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                            acted = true;
                            break;
                        }
                    }
                    if acted { continue; }
                    if hex_distance(unit.q, unit.r, my_cq, my_cr) > 1 {
                        if let Some((dq, dr)) = step_toward(unit, my_cq, my_cr, &gs.grid) {
                            actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                        }
                    }
                }
            }
        }

        // 城市生产: 先保证 5 工人(建够设施), 再产弓箭手(主力)+ 少量步兵(前排)
        let econ = &gs.economies[pid as usize];
        if n_worker < 5 && econ.can_afford((3, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
        } else if n_archer < 3 && econ.can_afford((3, 3, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
        } else if n_infantry < 2 && econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "Defender" }
}

// ═══════════════════════════════════════════════════════
// CavalryRusher — 骑兵攻城探针
// ═══════════════════════════════════════════════════════
//
// 和 Rusher 同结构但产骑兵(攻城 55/次 vs 步兵 40/次, 更快)。
// 对照点: 骑兵禁山遇林停, 山林多的图到不了城 → 检验地形对军事的影响。

pub struct CavalryRusherAgent;

impl Agent for CavalryRusherAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);

        // 研究 M1(ATK+5) → M2(骑兵冲锋+5)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            for t in ["M1", "M2"] {
                if tech.available_to_research().iter().any(|a| a == t) {
                    if let Some(cost) = TechManager::tech_cost(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => {}
                _ => {
                    if let Some((dq, dr)) = step_toward(unit, ecq, ecr, &gs.grid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
        }

        // 城市: 产骑兵(5/0/3), 资源不够退步兵
        let econ = &gs.economies[pid as usize];
        if econ.can_afford((5, 0, 3)) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
        } else if econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "CavRusher" }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::{init_game, step_game};
    use crate::constants::MAX_TURNS;
    use crate::ai::random::RandomAgent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    fn run(a: &dyn Agent, b: &dyn Agent, seed: u64) -> crate::game::GameState {
        let mut gs = init_game(seed, "balanced");
        let mut r0 = ChaCha12Rng::seed_from_u64(seed);
        let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
        while gs.winner.is_none() && gs.turn < MAX_TURNS {
            let a0 = a.decide(&gs, 0, &mut r0);
            let a1 = b.decide(&gs, 1, &mut r1);
            step_game(&mut gs, &a0, &a1);
        }
        gs
    }

    #[test]
    fn test_探针单局可跑完() {
        assert!(run(&RusherAgent, &RandomAgent, 50000).winner.is_some());
        assert!(run(&HarasserAgent, &RandomAgent, 50000).winner.is_some());
    }
}
