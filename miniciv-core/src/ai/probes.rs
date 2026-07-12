// 探针套件 — 阶段 1(第三个 AI) + P1.5深度适配(第六个 AI)
//
// 目的: 每个探针钉死一条设计假设, 组成"支配性矩阵"作为第一层锚点。
//   Rusher   — 纯军事攻城: 检验"进攻能不能威胁到建设者"
//   Harasser — 骚扰工人:   检验"经济骚扰有没有用"
//
// 用法: 和 Builder 一起进 eval 矩阵。健康游戏里没有单探针对其他所有 >70% 胜。
//
// 这些不是"聪明 AI", 是针对性对抗构造 —— 便宜、证伪导向。
//
// P1.5深度适配(2026-07-13): 所有探针的 can_afford 改用 config-aware 成本,
// 避免极端参数(unit_cost_mult=8-12)下探针自欺"付得起"但 produce_unit 拒执行。

use crate::game::GameState;
use crate::unit::UnitType;
use crate::map::Terrain;
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, hex_distance, HEX_DIRS};
use crate::tech::TechManager;
use crate::constants::{MAP_W, MAP_H};
use crate::config::GameConfig;
use rand::RngCore;

/// P1.5深度: 获取单位在给定 config 下的实际成本(base × unit_cost_mult)。
fn effective_unit_cost(ut: &str, config: &GameConfig) -> (i32, i32, i32) {
    let base = match ut {
        "infantry" => (5, 0, 0),
        "cavalry"  => (5, 0, 3),
        "archer"   => (3, 3, 0),
        "scout"    => (3, 0, 0),
        "worker"   => (3, 0, 0),
        _ => return (i32::MAX, i32::MAX, i32::MAX),
    };
    let m = config.unit_cost_mult;
    if (m - 1.0).abs() < 1e-9 {
        base
    } else {
        ((base.0 as f64 * m).ceil() as i32,
         (base.1 as f64 * m).ceil() as i32,
         (base.2 as f64 * m).ceil() as i32)
    }
}

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
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);

        // 研究 M1(步兵/弓手 ATK+5),助攻城
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            for t in ["M1", "M4"] {  // M1 攻击, M4 全军 HP+10
                if tech.available_to_research().iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
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

        // 城市: 每回合尽量产步兵(便宜, ATK 高)。P1.5深度: 用config-aware成本。
        let econ = &gs.economies[pid as usize];
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if econ.can_afford(inf_cost) {
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
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
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

        // 城市: 产骑兵(移速 2, 快速扑杀工人)。P1.5深度: 用config-aware成本。
        let econ = &gs.economies[pid as usize];
        let cav_cost = effective_unit_cost("cavalry", &gs.config);
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if econ.can_afford(cav_cost) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
        } else if econ.can_afford(inf_cost) {
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
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let (my_cq, my_cr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

        // 研究: 直奔 C5(和 Builder 同路线)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1", "C2"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
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

        // 城市: 产步兵守家, 上限 4(留资源推建设)。P1.5深度: 用config-aware成本。
        let econ = &gs.economies[pid as usize];
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if soldier_count < 4 && econ.can_afford(inf_cost) {
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
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let (my_cq, my_cr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

        // 研究: 直奔 C5
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1", "M1", "C2"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
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

        // 城市生产: 先保证 5 工人(建够设施), 再产弓箭手(主力)+ 少量步兵(前排)。
        // P1.5深度: 用config-aware成本。
        let econ = &gs.economies[pid as usize];
        let w_cost = effective_unit_cost("worker", &gs.config);
        let a_cost = effective_unit_cost("archer", &gs.config);
        let i_cost = effective_unit_cost("infantry", &gs.config);
        if n_worker < 5 && econ.can_afford(w_cost) {
            actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
        } else if n_archer < 3 && econ.can_afford(a_cost) {
            actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
        } else if n_infantry < 2 && econ.can_afford(i_cost) {
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
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);

        // 研究 M1(ATK+5) → M2(骑兵冲锋+5)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            for t in ["M1", "M2"] {
                if tech.available_to_research().iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
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

        // 城市: 产骑兵优先, 资源不够退步兵。P1.5深度: 用config-aware成本。
        let econ = &gs.economies[pid as usize];
        let cav_cost = effective_unit_cost("cavalry", &gs.config);
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if econ.can_afford(cav_cost) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
        } else if econ.can_afford(inf_cost) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "CavRusher" }
}

// ═══════════════════════════════════════════════════════
// Adaptive — 自适应 AI(比固定探针强: 会根据威胁切换)
// ═══════════════════════════════════════════════════════
//
// 桥接 M2/M3: 观察对手威胁, 无威胁时专注建设(Builder), 有威胁时防守(Defender)。
// 用来暴露"应变是否是关键深度"——若它显著强于固定探针, 说明深度在切换/应变。

pub struct AdaptiveAgent;

impl Agent for AdaptiveAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let (mcq, mcr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);
        // 威胁: 对手战斗单位逼近我城(距离 ≤ 3)
        let threat = gs.units.iter().filter(|u|
            u.alive && u.player_id == opp
            && !matches!(u.unit_type, UnitType::Worker | UnitType::Scout)
            && hex_distance(u.q, u.r, mcq, mcr) <= 3
        ).count();

        if threat >= 2 {
            DefenderAgent.decide(gs, pid, rng)     // 有威胁 → 攻防兼顾防守
        } else {
            crate::ai::fixed::BuilderAgent.decide(gs, pid, rng)  // 无威胁 → 专注建设
        }
    }

    fn name(&self) -> &str { "Adaptive" }
}

// ═══════════════════════════════════════════════════════
// P1.5: 红白探针
// ═══════════════════════════════════════════════════════

/// AlwaysWhite — 可选的回合立刻选白, 之后全力产兵推城。
/// 检验: 白线在非领先状态下是否自毁(支持度危机→崩盘)。
pub struct AlwaysWhiteAgent;

impl Agent for AlwaysWhiteAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);

        // 可选即选白
        if gs.economies[pid as usize].branch.is_none()
           && gs.turn >= gs.config.branch_available_turn {
            actions.push(Action::ChooseBranch { branch: "White".to_string() });
        }

        // 研究和产兵(和 Rusher 一样: M1助攻城+产步兵)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            for t in ["M1", "M4"] {
                if tech.available_to_research().iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive).collect();
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

        let econ = &gs.economies[pid as usize];
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if econ.can_afford(inf_cost) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }
        actions
    }
    fn name(&self) -> &str { "AlwaysWhite" }
}

/// AlwaysRed — 可选的回合立刻选红, 积累组织度→兑换西南联大→建设胜利。
/// 检验: 红线在非落后状态下是否过低效(放弃产出加成→被白线碾压)。
pub struct AlwaysRedAgent;

impl Agent for AlwaysRedAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let mut actions = Vec::new();
        let econ = &gs.economies[pid as usize];

        // 可选即选红
        if econ.branch.is_none() && gs.turn >= gs.config.branch_available_turn {
            actions.push(Action::ChooseBranch { branch: "Red".to_string() });
        }

        // 组织度够了就兑西南联大(弯道超车科技)
        if econ.branch == Some(crate::economy::Branch::Red)
           && econ.organization >= gs.config.red_lian_da_org_cost {
            actions.push(Action::RedeemOrg { mode: "LianDa".to_string() });
        }

        // 研究直奔 C5(建设胜利)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1", "C2"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive).collect();
        let mut n_worker = 0u32;
        for (_, u) in &player_units {
            if u.unit_type == UnitType::Worker { n_worker += 1; }
        }

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            if let UnitType::Worker = unit.unit_type {
                if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                    actions.push(a);
                }
            }
            // 战斗单位守城(不主动出击)
        }

        let econ2 = &gs.economies[pid as usize];
        let w_cost = effective_unit_cost("worker", &gs.config);
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        if n_worker < 5 && econ2.can_afford(w_cost) {
            actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
        } else if econ2.can_afford(inf_cost) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }
        actions
    }
    fn name(&self) -> &str { "AlwaysRed" }
}

/// StateAware — 领先→选白, 落后→选红。
/// P1.5深度改进(第六个AI): 领先判断从"设施≥3且城HP≥对手"
/// 改为多维信号(资源/军事/科技/支持度风险), 适配极端参数下设施建造极慢的情况。
/// 检验规格 R-1: "处境决定路线"是否优于 AlwaysWhite/AlwaysRed。
pub struct StateAwareAgent;

impl Agent for StateAwareAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let mut actions = Vec::new();
        let econ = &gs.economies[pid as usize];

        // P1.5深度: 多维领先判断(不只依赖设施数——极端参数下建得极慢)
        let mut my_facs = 0u32;
        let ms = gs.config.map_size as i32;
        for r in 0..ms { for q in 0..ms {
            if let Some(f) = &gs.grid.get(q, r).facility {
                if f.player_id == pid { my_facs += 1; }
            }
        }}
        // 军事力: 己方战斗单位 vs 对手
        let my_mil = gs.units.iter()
            .filter(|u| u.alive && u.player_id == pid
                     && u.unit_type != UnitType::Worker && u.unit_type != UnitType::Scout)
            .count();
        let opp_mil = gs.units.iter()
            .filter(|u| u.alive && u.player_id == opp
                     && u.unit_type != UnitType::Worker && u.unit_type != UnitType::Scout)
            .count();
        // 资源总量
        let my_res = econ.food + econ.wood + econ.gold;
        let opp_res = gs.economies[opp as usize].food + gs.economies[opp as usize].wood + gs.economies[opp as usize].gold;
        // 科技数
        let my_techs = gs.techs[pid as usize].completed.len();
        let opp_techs = gs.techs[opp as usize].completed.len();
        let my_city_hp = gs.cities[pid as usize].hp;
        let opp_city_hp = gs.cities[opp as usize].hp;

        // 综合领先评分(每个维度 >对手 积1分, 共5维)
        let mut lead_score = 0i32;
        if my_facs > 0 && my_facs >= 2 { lead_score += 1; }  // 至少建了2设施
        if my_mil >= opp_mil { lead_score += 1; }
        if my_res >= opp_res { lead_score += 1; }
        if my_techs >= opp_techs { lead_score += 1; }
        if my_city_hp >= opp_city_hp { lead_score += 1; }

        // 领先(≥3/5维度占优) → 白; 落后(≤1) → 红; 均势(2)→看支持度风险
        let leading = lead_score >= 3;
        let trailing = lead_score <= 1;

        // P1.5深度: 支持度风险评估——如果支持度已偏低, 选白会加速危机, 可能不如选红稳
        let support_risky = econ.support < gs.config.support_penalty_threshold + 15;

        if econ.branch.is_none() && gs.turn >= gs.config.branch_available_turn {
            if leading && !support_risky {
                actions.push(Action::ChooseBranch { branch: "White".to_string() });
            } else if trailing || support_risky {
                actions.push(Action::ChooseBranch { branch: "Red".to_string() });
            } else {
                // 均势且支持度安全: 略倾向白(利用产出加成扩大优势)
                actions.push(Action::ChooseBranch { branch: "White".to_string() });
            }
        }

        // 按所选路线行动
        if econ.branch == Some(crate::economy::Branch::Red)
           && econ.organization >= gs.config.red_lian_da_org_cost {
            actions.push(Action::RedeemOrg { mode: "LianDa".to_string() });
        }

        // 研究: 白线走M兵 → C1(解锁经济基础), 红线走C建设
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let order: &[&str] = if econ.branch == Some(crate::economy::Branch::White) {
                &["M1", "C1", "M4", "M2", "E1"]
            } else {
                &["C1", "C3", "C4", "C5", "E1", "M1"]
            };
            let avail = tech.available_to_research();
            for t in order {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive).collect();
        let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);
        let (mcq, mcr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                        actions.push(a);
                    }
                }
                UnitType::Scout => {}
                _ => {
                    // 白线进攻, 红线守城
                    let (tq, tr) = if econ.branch == Some(crate::economy::Branch::White) {
                        (ecq, ecr)
                    } else {
                        (mcq, mcr)
                    };
                    if let Some((dq, dr)) = step_toward(unit, tq, tr, &gs.grid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
        }

        let econ2 = &gs.economies[pid as usize];
        let inf_cost = effective_unit_cost("infantry", &gs.config);
        let w_cost = effective_unit_cost("worker", &gs.config);
        if econ.branch == Some(crate::economy::Branch::White) {
            if econ2.can_afford(inf_cost) {
                actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
            }
        } else {
            if econ2.can_afford(w_cost) {
                actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
            }
        }
        actions
    }
    fn name(&self) -> &str { "StateAware" }
}

/// TankThenRed — 前期故意不产兵(保持高支持度)→选红线→爆发。
/// 检验规格 R-2: "故意摆烂等红线"是否比正常发育更差(应输)。
pub struct TankThenRedAgent;

impl Agent for TankThenRedAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let mut actions = Vec::new();
        let econ = &gs.economies[pid as usize];
        let has_branch = econ.branch.is_some();

        // 先选红线(不造兵, 支持度高→组织度快)
        if !has_branch && gs.turn >= gs.config.branch_available_turn {
            actions.push(Action::ChooseBranch { branch: "Red".to_string() });
        }

        // 选了红线后, 组织度够了就尽可能兑换
        if econ.branch == Some(crate::economy::Branch::Red) {
            if econ.organization >= gs.config.red_lian_da_org_cost {
                actions.push(Action::RedeemOrg { mode: "LianDa".to_string() });
            } else if econ.organization >= gs.config.red_mobilize_org_cost {
                actions.push(Action::RedeemOrg { mode: "Mobilize".to_string() });
            }
        }

        // 研究直奔建设(靠组织度兑换弯道超车, 不靠常规研究)
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let avail = tech.available_to_research();
            for t in ["C1", "C3", "C4", "C5", "E1"] {
                if avail.iter().any(|a| a == t) {
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive).collect();

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            if let UnitType::Worker = unit.unit_type {
                if let Some(a) = worker_econ_action(local_idx, unit, gs, pid) {
                    actions.push(a);
                }
            }
            // 战斗单位: 守城不进攻(不产兵→只能被动防守)
        }

        // 不主动产战斗单位(只在 Mobilize 兑换时才产)
        // 只产工人保证建设。P1.5深度: 用config-aware成本。
        let worker_count = player_units.iter()
            .filter(|(_, u)| u.unit_type == UnitType::Worker).count();
        let w_cost = effective_unit_cost("worker", &gs.config);
        if worker_count < 6 && econ.can_afford(w_cost) {
            actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
        }

        actions
    }
    fn name(&self) -> &str { "TankThenRed" }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::{init_game, init_game_with_config, step_game};
    use crate::config::GameConfig;
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

    #[test]
    fn test_红白探针单局可跑完() {
        // P1.5: 确保红白探针不会 panic/死循环
        let cfg = GameConfig { branch_available_turn: 0, ..GameConfig::default() };
        let probes: [(&str, &dyn Agent); 4] = [
            ("AlwaysWhite", &AlwaysWhiteAgent),
            ("AlwaysRed", &AlwaysRedAgent),
            ("StateAware", &StateAwareAgent),
            ("TankThenRed", &TankThenRedAgent),
        ];
        for (name, agent) in probes.iter() {
            let mut gs = init_game_with_config(50000, "balanced", cfg.clone());
            let mut r0 = ChaCha12Rng::seed_from_u64(50000);
            let mut r1 = ChaCha12Rng::seed_from_u64(50001);
            let mt = gs.config.max_turns;
            while gs.winner.is_none() && gs.turn < mt {
                let a0 = agent.decide(&gs, 0, &mut r0);
                let a1 = RandomAgent.decide(&gs, 1, &mut r1);
                step_game(&mut gs, &a0, &a1);
            }
            assert!(gs.winner.is_some(), "{} vs Random 未决出胜者", name);
        }
    }
}
