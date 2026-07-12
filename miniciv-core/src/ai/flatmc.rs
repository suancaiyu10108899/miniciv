// FlatMC 裁判 — S2「立裁判」阶段(2026-07-11 第四个 AI)
//
// 目的: 打破"深度验证循环论证"。
//   现有 Search(search.rs)只在 4 个手写剧本里选 → 天花板 = 剧本能表达的行为。
//   "无支配/有深度"于是退化成"我的 5 个脚本互相不碾压"(循环)。
//
// FlatMC 的关键区别 —— **操作层级在剧本之下**:
//   每回合把决策分解成三条独立轴, 组合出剧本表达不了的行为:
//     ① 研究   ∈ {不研究} ∪ {每个当前可研究且付得起的科技}   ← 测非标准科技顺序(死机制: 互斥点)
//     ② 生产   ∈ {不产}   ∪ {付得起的每个兵种(含侦察兵)}      ← 测侦察兵/弓箭手是否被自发使用
//     ③ 军队姿态 ∈ {进攻/防守/骚扰/按兵}                       ← 剧本是固定姿态, 这里逐回合选
//   对每个候选 turn-plan 做 rollout 评估(己方本候选 + 双方默认策略打到底/截断),
//   取胜率最高的执行。这是 1-ply + rollout 的 FlatMC。
//
// 诚实边界(先写死, 不事后找补):
//   - rollout 尾巴用**自带的廉价默认策略**(default_move, 非 4 剧本), 所以 FlatMC 是
//     "对默认策略的 1-ply 改进"。它的天花板 = 默认策略 + 一步真实搜索。不是全局最优。
//   - 单一对手假设(rollout 里对手也走 default_move), 未做 minimax。
//   - rollout 截断深度可调(rollout_depth), 截断处用启发式估值(有偏, 已知)。
//   即便如此, 它的**根菜单**严格富于 4 剧本 → 能发现并使用死机制 → 足以第一次
//   把"当前甜点真深还是假深"变成可裁决的问题。

use crate::game::{GameState, step_game, same_team, primary_enemy};
use crate::economy::Branch;
use crate::unit::UnitType;
use crate::map::Terrain;
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, hex_distance};
use crate::tech::TechManager;
use crate::constants::{MAP_W, MAP_H};
use rand::RngCore;

#[derive(Clone, Copy, Debug, PartialEq)]
enum Posture { Attack, Defend, Harass, Hold }

pub struct FlatMcAgent {
    /// rollout 截断深度(相对回合数)。0 = 打到游戏结束。默认 0(全 rollout, 无启发式偏置)。
    pub rollout_depth: u16,
}

impl FlatMcAgent {
    pub fn new() -> Self { Self { rollout_depth: 0 } }
    pub fn with_depth(d: u16) -> Self { Self { rollout_depth: d } }
}

impl Agent for FlatMcAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        // ── 组合根菜单 ──────────────────────────────
        // 轴①研究候选
        let econ = &gs.economies[pid as usize];
        let tech = &gs.techs[pid as usize];
        let mut research_opts: Vec<Option<String>> = vec![None];
        if tech.researching.is_none() {
            for t in tech.available_to_research() {
                if let Some(cost) = tech.cost_of(&t) {
                    if econ.can_afford(cost) {
                        research_opts.push(Some(t));
                    }
                }
            }
        }
        // 轴②生产候选(付得起的兵种)
        let mut produce_opts: Vec<Option<&'static str>> = vec![None];
        for (ut, cost) in [
            ("infantry", (5, 0, 0)),
            ("cavalry",  (5, 0, 3)),
            ("archer",   (3, 3, 0)),
            ("scout",    (3, 0, 0)),
            ("worker",   (3, 0, 0)),
        ] {
            if econ.can_afford(cost) { produce_opts.push(Some(ut)); }
        }
        // 轴③姿态候选
        let postures = [Posture::Attack, Posture::Defend, Posture::Harass, Posture::Hold];
        // 轴④ P1.5: 分支候选
        let mut branch_opts: Vec<Option<&str>> = vec![None];
        let my_econ = &gs.economies[pid as usize];
        if my_econ.branch.is_none() && gs.turn >= gs.config.branch_available_turn {
            branch_opts.push(Some("White"));
            branch_opts.push(Some("Red"));
        }
        // 轴⑤ P1.5: 组织度兑换候选(仅红线)
        let mut redeem_opts: Vec<Option<&str>> = vec![None];
        if my_econ.branch == Some(crate::economy::Branch::Red) {
            if my_econ.organization >= gs.config.red_lian_da_org_cost {
                redeem_opts.push(Some("LianDa"));
            }
            if my_econ.organization >= gs.config.red_mobilize_org_cost {
                redeem_opts.push(Some("Mobilize"));
            }
        }
        // 轴⑥ P1.5: 扩张候选
        let expand_opt: Option<bool> = if my_econ.can_afford(gs.config.expand_resource_cost) {
            Some(true)
        } else {
            None
        };

        // ── 逐候选 rollout 评估 ─────────────────────
        let mut best_plan: Vec<Action> = Vec::new();
        let mut best_score = f64::NEG_INFINITY;
        for r in &research_opts {
            for p in &produce_opts {
                for &posture in &postures {
                    for branch in &branch_opts {
                        for redeem in &redeem_opts {
                            // Expand: only add when affordable, skip the None branch to avoid explosion
                            let plan = build_turn_plan_p15(gs, pid, r, p, posture, *branch, *redeem, expand_opt.is_some());
                            let score = self.eval_plan(gs, pid, &plan);
                            if score > best_score {
                                best_score = score;
                                best_plan = plan;
                            }
                        }
                    }
                }
            }
        }
        best_plan
    }

    fn name(&self) -> &str { "FlatMC" }
}

impl FlatMcAgent {
    /// 评估: 应用本候选(己方) + 对手响应策略, 步进一回合, 再 rollout 到底/截断。
    /// **minimax**: 对手可能建设也可能强攻——取两种响应下的最坏结果, 使裁判对 rush 不失防。
    /// 关键: rollout 尾巴里对手**持续**保持同一 aggressive 假设(否则只在第1回合算威胁,
    /// 被持续 rush 的 Rusher/CavRusher 屠)。
    fn eval_plan(&self, gs: &GameState, pid: u8, plan: &[Action]) -> f64 {
        // P1.5: 用 primary_enemy 替代 1-pid(兼容多人)
        let opp = primary_enemy(pid, &gs.config).unwrap_or(1 - pid);
        let mut worst = f64::MAX;
        // 对手响应假设: 0=建设 1=步兵强攻 2=骑兵强攻。取最坏(minimax), 覆盖三种主要威胁。
        for mode in [0u8, 1, 2] {
            let mut g = gs.clone();
            let opp_plan = default_move_ex(&g, opp, mode);
            let (a0, a1) = if pid == 0 { (plan.to_vec(), opp_plan) } else { (opp_plan, plan.to_vec()) };
            step_game(&mut g, &a0, &a1);
            let v = rollout(&mut g, pid, self.rollout_depth, mode);
            if v < worst { worst = v; }
        }
        worst
    }
}

/// 从当前状态 rollout。pid(我方)走建设向默认(会威胁自适应防守);
/// 对手持续按 opp_mode 假设走(1/2=持续强攻)。直到结束或截断。
/// 返回 pid 视角 [0,1] 值(胜1/负0/平0.5; 截断处用启发式估值)。
fn rollout(g: &mut GameState, pid: u8, depth: u16, opp_mode: u8) -> f64 {
    let start_turn = g.turn;
    let max_turns = g.config.max_turns;
    let opp = primary_enemy(pid, &g.config).unwrap_or(1 - pid);
    while g.winner.is_none() && g.turn < max_turns {
        if depth > 0 && g.turn.saturating_sub(start_turn) >= depth {
            return heuristic_value(g, pid);
        }
        let my_plan = default_move_ex(g, pid, 0);
        let opp_plan = default_move_ex(g, opp, opp_mode);
        let (a0, a1) = if pid == 0 { (my_plan, opp_plan) } else { (opp_plan, my_plan) };
        step_game(g, &a0, &a1);
    }
    match g.winner {
        Some(w) if w == pid => 1.0,
        Some(_) => 0.0,
        None => 0.5,
    }
}

/// 截断处启发式估值: 综合建设进度 / 攻城进度 / 军事 / 己城血, 映射到 [0,1]。
/// 有偏(尤其权重), 已知。方向: 更接近任一胜利条件 = 更高。
fn heuristic_value(g: &GameState, pid: u8) -> f64 {
    let prog = |p: u8| -> f64 {
        let opp = primary_enemy(p, &g.config).unwrap_or(1 - p);
        let constr = g.techs[p as usize].construction_count() as f64 / 5.0; // 0..1
        let c5 = if g.techs[p as usize].completed.iter().any(|c| c == "C5") { 1.0 } else { 0.0 };
        // 攻城进度: 敌城被削比例(默认满血 = config.city_hp)
        let full = g.config.city_hp.max(1) as f64;
        let conquest = 1.0 - (g.cities[opp as usize].hp.max(0) as f64 / full);
        // 军事力量(战斗单位 atk 和)
        let mil: i32 = g.units.iter()
            .filter(|u| u.alive && u.player_id == p && u.unit_type != UnitType::Worker)
            .map(|u| u.atk).sum();
        let my_city_frac = g.cities[p as usize].hp.max(0) as f64 / full;
        1.2 * constr + 1.5 * c5 + 1.5 * conquest + 0.004 * mil as f64 + 0.5 * my_city_frac
    };
    let d = prog(pid) - prog(1 - pid);
    1.0 / (1.0 + (-d).exp()) // sigmoid → (0,1)
}

/// P1.5 版本: 加入 ChooseBranch/RedeemOrg/Expand 候选。
fn build_turn_plan_p15(
    gs: &GameState, pid: u8,
    research: &Option<String>, produce: &Option<&'static str>, posture: Posture,
    branch: Option<&str>, redeem: Option<&str>, expand: bool,
) -> Vec<Action> {
    let mut actions = Vec::new();
    // P1.5 actions first (before unit actions)
    if let Some(b) = branch {
        actions.push(Action::ChooseBranch { branch: b.to_string() });
    }
    if let Some(r_mode) = redeem {
        actions.push(Action::RedeemOrg { mode: r_mode.to_string() });
    }
    if expand {
        actions.push(Action::Expand);
    }
    // Base actions
    let mut base = build_turn_plan(gs, pid, research, produce, posture);
    actions.append(&mut base);
    actions
}

/// 构造一个完整 turn-plan: 工人经济 + 本候选研究 + 本候选生产 + 按姿态移动战斗单位。
fn build_turn_plan(
    gs: &GameState, pid: u8,
    research: &Option<String>, produce: &Option<&'static str>, posture: Posture,
) -> Vec<Action> {
    let mut actions = Vec::new();
    let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
        .filter(|(_, u)| u.player_id == pid && u.alive)
        .collect();
    let my_facs = count_facilities(gs, pid);

    // 研究(本候选)
    if let Some(t) = research {
        actions.push(Action::Research { tech_id: t.clone() });
    }

    // 单位动作
    for (local_idx, (_, unit)) in player_units.iter().enumerate() {
        match unit.unit_type {
            UnitType::Worker => {
                if let Some(a) = worker_econ(local_idx, unit, gs, pid, my_facs) {
                    actions.push(a);
                }
            }
            UnitType::Scout => {
                // 侦察兵: 骚扰姿态下扑敌工人(它机动 2/无视地形), 否则不动
                if posture == Posture::Harass {
                    if let Some((dq, dr)) = move_toward_enemy_worker(unit, gs, pid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
            _ => {
                // 战斗单位: 按姿态移动
                if let Some((dq, dr)) = combat_move(unit, gs, pid, posture) {
                    actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                }
            }
        }
    }

    // 生产(本候选)
    if let Some(ut) = produce {
        actions.push(Action::ProduceUnit { unit_type: ut.to_string() });
    }

    actions
}

// ─── 默认策略(rollout 尾巴, 非 4 剧本) ──────────────────
// 廉价、确定、自洽: 工人建满再采; 受威胁产弓箭手守城否则产步兵推城; 研究奔 C5;
// 战斗单位受威胁则守/拦截, 否则攻城。这是 FlatMC 的天花板参照。

/// 默认策略。mode: 0=建设向(威胁自适应防守) 1=步兵强攻 2=骑兵强攻。
/// 1/2 用于 minimax 最坏情形(持续 rush 假设)。
fn default_move_ex(gs: &GameState, pid: u8, mode: u8) -> Vec<Action> {
    let opp = primary_enemy(pid, &gs.config).unwrap_or(1 - pid);
    let aggressive = mode >= 1;
    let mut actions = Vec::new();
    let (mcq, mcr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);

    // P1.5: 可选即选分支(默认: 建设向选Red, 进攻向选White)
    let econ_p15 = &gs.economies[pid as usize];
    if econ_p15.branch.is_none() && gs.turn >= gs.config.branch_available_turn {
        if aggressive {
            actions.push(Action::ChooseBranch { branch: "White".to_string() });
        } else {
            actions.push(Action::ChooseBranch { branch: "Red".to_string() });
        }
    }
    // P1.5: 红线兑换
    if econ_p15.branch == Some(Branch::Red) {
        if econ_p15.organization >= gs.config.red_lian_da_org_cost {
            actions.push(Action::RedeemOrg { mode: "LianDa".to_string() });
        } else if econ_p15.organization >= gs.config.red_mobilize_org_cost && aggressive {
            actions.push(Action::RedeemOrg { mode: "Mobilize".to_string() });
        }
    }
    // P1.5: 扩张(资源充足时)
    if econ_p15.can_afford(gs.config.expand_resource_cost) && econ_p15.support > 40 {
        actions.push(Action::Expand);
    }

    let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
        .filter(|(_, u)| u.player_id == pid && u.alive)
        .collect();
    let my_facs = count_facilities(gs, pid);

    // 威胁: 敌方战斗单位逼近我城(≤3)
    let threat = gs.units.iter().filter(|u|
        u.alive && u.player_id == opp
        && !matches!(u.unit_type, UnitType::Worker | UnitType::Scout)
        && hex_distance(u.q, u.r, mcq, mcr) <= 3
    ).count();
    let posture = if aggressive {
        Posture::Attack
    } else if threat >= 1 {
        Posture::Defend
    } else {
        Posture::Attack
    };

    // 研究: 强攻先出军事科技助攻城; 否则直奔 C5(建设胜利最短链)
    let tech = &gs.techs[pid as usize];
    if tech.researching.is_none() {
        let econ = &gs.economies[pid as usize];
        let avail = tech.available_to_research();
        let order: &[&str] = match mode {
            1 => &["M1", "M4", "M2", "C1", "E1"],       // 步兵强攻
            2 => &["M1", "M2", "M4", "C1", "E1"],       // 骑兵强攻(M2 骑兵冲锋)
            _ => &["C1", "C3", "C4", "C5", "E1", "M1", "C2"],
        };
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

    for (local_idx, (_, unit)) in player_units.iter().enumerate() {
        match unit.unit_type {
            UnitType::Worker => {
                if let Some(a) = worker_econ(local_idx, unit, gs, pid, my_facs) {
                    actions.push(a);
                }
            }
            UnitType::Scout => {}
            _ => {
                if let Some((dq, dr)) = combat_move(unit, gs, pid, posture) {
                    actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                }
            }
        }
    }

    // 生产: 强攻全力产军(mode2 骑兵/mode1 步兵); 否则受威胁产弓箭手守城, 平时保工人再产步兵。
    let econ = &gs.economies[pid as usize];
    let n_worker = player_units.iter().filter(|(_, u)| u.unit_type == UnitType::Worker).count();
    if mode == 2 {
        if econ.can_afford((5, 0, 3)) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
        } else if econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }
    } else if mode == 1 {
        if econ.can_afford((5, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
        }
    } else if threat >= 1 && econ.can_afford((3, 3, 0)) {
        actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
    } else if n_worker < 5 && econ.can_afford((3, 0, 0)) {
        actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
    } else if econ.can_afford((5, 0, 0)) {
        actions.push(Action::ProduceUnit { unit_type: "infantry".to_string() });
    }

    actions
}

// ─── 共享辅助 ────────────────────────────────────────

fn buildable(t: Terrain) -> bool {
    matches!(t, Terrain::Plain | Terrain::Forest | Terrain::Mountain)
}

fn count_facilities(gs: &GameState, pid: u8) -> u32 {
    let mut n = 0;
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if let Some(f) = &gs.grid.get(q, r).facility {
                if f.player_id == pid { n += 1; }
            }
        }
    }
    n
}

/// 工人经济: 建满 5 设施前优先建, 之后站己方设施采集。
fn worker_econ(local_idx: usize, unit: &crate::unit::Unit, gs: &GameState, pid: u8, my_facs: u32) -> Option<Action> {
    let tile = gs.grid.get(unit.q, unit.r);
    let can_build_here = buildable(tile.terrain) && tile.facility.is_none();
    let on_own = tile.facility.as_ref().map(|f| f.player_id == pid).unwrap_or(false);
    if can_build_here && my_facs < 5 {
        return Some(Action::Build { unit_idx: local_idx });
    }
    if on_own {
        return Some(Action::Produce { unit_idx: local_idx });
    }
    // 找相邻空可建格; 否则移动一步
    let moves = legal_moves(unit, &gs.grid);
    if my_facs < 5 {
        for (dq, dr) in &moves {
            let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
            let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
            let nt = gs.grid.get(nq, nr);
            if buildable(nt.terrain) && nt.facility.is_none() {
                return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
            }
        }
    }
    moves.first().map(|(dq, dr)| Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr })
}

/// 战斗单位按姿态给出移动方向。
fn combat_move(unit: &crate::unit::Unit, gs: &GameState, pid: u8, posture: Posture) -> Option<(i32, i32)> {
    let opp = primary_enemy(pid, &gs.config).unwrap_or(1 - pid);
    let (ecq, ecr) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);
    let (mcq, mcr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);
    match posture {
        Posture::Attack => step_toward(unit, ecq, ecr, gs),
        Posture::Hold => None,
        Posture::Harass => move_toward_enemy_worker(unit, gs, pid),
        Posture::Defend => {
            // 邻格有敌 → 攻击(移入); 否则回撤守城
            for (dq, dr) in crate::movement::HEX_DIRS.iter() {
                let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
                let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
                let has_enemy = gs.units.iter().any(|e|
                    e.alive && e.player_id == opp && e.q == nq && e.r == nr);
                if has_enemy { return Some((*dq, *dr)); }
            }
            if hex_distance(unit.q, unit.r, mcq, mcr) > 1 {
                return step_toward(unit, mcq, mcr, gs);
            }
            None
        }
    }
}

fn move_toward_enemy_worker(unit: &crate::unit::Unit, gs: &GameState, pid: u8) -> Option<(i32, i32)> {
    let opp = primary_enemy(pid, &gs.config).unwrap_or(1 - pid);
    let target = gs.units.iter()
        .filter(|e| e.alive && e.player_id == opp && e.unit_type == UnitType::Worker)
        .min_by_key(|e| hex_distance(unit.q, unit.r, e.q, e.r));
    let (tq, tr) = match target {
        Some(w) => (w.q, w.r),
        None => (gs.cities[opp as usize].q, gs.cities[opp as usize].r),
    };
    step_toward(unit, tq, tr, gs)
}

/// 朝目标走一步(允许持平绕路, 避免被山林卡死)。
fn step_toward(unit: &crate::unit::Unit, tq: i32, tr: i32, gs: &GameState) -> Option<(i32, i32)> {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() { return None; }
    let cur_d = hex_distance(unit.q, unit.r, tq, tr);
    let mut best: Option<(i32, i32)> = None;
    let mut best_d = u8::MAX;
    for (dq, dr) in moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tq, tr);
        if d < best_d { best_d = d; best = Some((dq, dr)); }
    }
    if best_d <= cur_d { best } else { None }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::init_game_with_config;
    use crate::config::GameConfig;
    use crate::ai::probes::RusherAgent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    #[test]
    fn test_flatmc_单局可跑完_确定性() {
        let cfg = GameConfig::default();
        let run = || {
            let mut gs = init_game_with_config(50000, "balanced", cfg.clone());
            let s = FlatMcAgent::with_depth(12);
            let r = RusherAgent;
            let mut r0 = ChaCha12Rng::seed_from_u64(1);
            let mut r1 = ChaCha12Rng::seed_from_u64(2);
            let mt = gs.config.max_turns;
            while gs.winner.is_none() && gs.turn < mt {
                let a0 = s.decide(&gs, 0, &mut r0);
                let a1 = r.decide(&gs, 1, &mut r1);
                step_game(&mut gs, &a0, &a1);
            }
            (gs.turn, gs.winner)
        };
        let a = run();
        let b = run();
        assert!(a.1.is_some(), "游戏应结束");
        assert_eq!(a, b, "FlatMC 应确定性(同 seed 同结果)");
    }
}
