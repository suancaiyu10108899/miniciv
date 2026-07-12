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
    destroy_facility, city_base_income, Branch,
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

/// 用指定配置初始化游戏(M1.1: 参数可配置化的入口, P1.5: N 玩家)。
pub fn init_game_with_config(seed: u64, generator_id: &str, config: crate::config::GameConfig) -> GameState {
    let grid = generate_map(seed, generator_id, config.map_size, config.player_count);
    let gen_id = generator_id.to_string();
    let ms = config.map_size as i32;
    let n = config.player_count;

    // 找到城市位置
    let mut city_positions: Vec<(i32, i32)> = Vec::new();
    for r in 0..ms {
        for q in 0..ms {
            if grid.get(q, r).terrain == crate::map::Terrain::City {
                city_positions.push((q, r));
            }
        }
    }
    city_positions.sort_by_key(|&(q, r)| (r, q));
    assert!(city_positions.len() >= n as usize,
        "地图城市数({})不足玩家数({})", city_positions.len(), n);

    // N 座城市
    let mut cities: Vec<City> = Vec::new();
    for pid in 0..n {
        let (cq, cr) = city_positions[pid as usize];
        let mut city = City::new(pid, cq, cr);
        city.hp = config.city_hp;
        city.def = config.city_def;
        city.base_food = config.city_base_food;
        cities.push(city);
    }

    // N 组初始单位
    let mut units = Vec::new();
    for pid in 0..n {
        let (cx, cy) = (cities[pid as usize].q, cities[pid as usize].r);
        for _ in 0..config.starting_workers {
            for (dq, dr) in HEX_DIRS.iter() {
                let nq = (cx + dq).rem_euclid(ms);
                let nr = (cy + dr).rem_euclid(ms);
                if grid.get(nq, nr).terrain == crate::map::Terrain::Plain {
                    let occupied = units.iter().any(|u: &Unit| u.q == nq && u.r == nr);
                    if !occupied {
                        units.push(Unit::create(UnitType::Worker, pid, nq, nr));
                        break;
                    }
                }
            }
        }
        for _ in 0..config.starting_scouts {
            for (dq, dr) in HEX_DIRS.iter() {
                let nq = (cx + dq).rem_euclid(ms);
                let nr = (cy + dr).rem_euclid(ms);
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

    let mut economies: Vec<Economy> = Vec::new();
    let mut techs: Vec<TechManager> = Vec::new();
    for pid in 0..n {
        let mut e = Economy::new(pid);
        e.food = config.starting_food;
        e.wood = config.starting_wood;
        e.gold = config.starting_gold;
        e.support = config.initial_support;  // P1.5
        economies.push(e);

        let mut t = TechManager::new(pid);
        t.academy_increment = config.academy_research_increment;
        t.turns_override = config.tech_turns.clone();
        t.c_line_cost_mult = config.c_line_cost_mult;
        techs.push(t);
    }

    GameState {
        seed,
        size: config.map_size,
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

// ─── 团队辅助(P1.5) ────────────────────────────────

/// 查询某玩家的敌对玩家列表(根据 config.teams 分组)。
pub fn enemies_of(pid: u8, config: &crate::config::GameConfig) -> Vec<u8> {
    let my_team = config.teams.get(pid as usize).copied().unwrap_or(pid);
    (0..config.player_count)
        .filter(|&p| {
            let t = config.teams.get(p as usize).copied().unwrap_or(p);
            p != pid && t != my_team
        })
        .collect()
}

/// 两人是否同队(P1.5)。
pub fn same_team(a: u8, b: u8, config: &crate::config::GameConfig) -> bool {
    let ta = config.teams.get(a as usize).copied().unwrap_or(a);
    let tb = config.teams.get(b as usize).copied().unwrap_or(b);
    ta == tb
}

/// 获取某玩家的第一个敌人(向后兼容 1v1 中 `opp = 1 - pid`)。
pub fn primary_enemy(pid: u8, config: &crate::config::GameConfig) -> Option<u8> {
    enemies_of(pid, config).first().copied()
}

/// 团队中是否有任一玩家存活(城市HP>0)。
fn team_alive(team: u8, gs: &GameState) -> bool {
    (0..gs.config.player_count).any(|pid| {
        same_team(pid, pid, &gs.config) // always true — just check team match
            && gs.config.teams.get(pid as usize).copied().unwrap_or(pid) == team
            && gs.cities[pid as usize].is_alive()
    })
}

// ─── 回合执行 ────────────────────────────────────────

/// 执行一回合(N 玩家版, P1.5)。
///
/// `all_actions`: 每个玩家的动作列表, `all_actions[pid]` = pid 的动作。
/// 交替先手: 回合轮转 `(turn + i) % N` 决定执行顺序以消除固定先手偏差。
///
/// 每个玩家执行: 单位动作 → 城市产出。
/// 全部执行后: 科技 tick(所有玩家同时) → 胜利判定 → 城市防守/渐进攻城 → 征服检查 → 阶梯。
pub fn step_game_multi(gs: &mut GameState, all_actions: &[Vec<Action>]) -> StepResult {
    gs.turn += 1;
    let n = gs.config.player_count as usize;

    // 交替先手: 每个回合轮转起始玩家
    // turn=1 → [0,1], turn=2 → [1,0], turn=3 → [1,0] ...
    // N 玩家: turn=1 → [0,1,2,3], turn=2 → [1,2,3,0], ...
    let first = (gs.turn as usize - 1) % n;
    let player_order: Vec<(u8, &[Action])> = (0..n)
        .map(|i| {
            let pid = ((first + i) % n) as u8;
            (pid, all_actions[pid as usize].as_slice())
        })
        .collect();

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
                        // B3: 弓箭手先尝试射程内远程攻击(站原地, 不还手)。有目标则不移动。
                        let is_archer = gs.units[global_idx].ranged
                            && gs.units[global_idx].range_dist >= 2;
                        if is_archer && try_ranged_attack(gs, global_idx) {
                            continue;
                        }
                        // B2 修复: 按 move_speed 走多步(遇敌/占城/受阻停)。
                        // 冲锋(B5): 骑兵连续走过平原后攻击 → +10。
                        let speed = gs.units[global_idx].move_speed.max(1);
                        let mut plains_run = 0u8;
                        for _ in 0..speed {
                            let from = gs.grid.get(gs.units[global_idx].q, gs.units[global_idx].r).terrain;
                            let charged = gs.units[global_idx].unit_type == UnitType::Cavalry
                                && plains_run >= 1
                                && from == crate::map::Terrain::Plain;
                            match do_move(gs, global_idx, *dq, *dr, charged) {
                                MoveOutcome::Moved => {
                                    // 遇林停(改进): 骑兵进入森林后本回合停(能穿林但慢, 不再原地卡死)
                                    let now = gs.grid.get(gs.units[global_idx].q, gs.units[global_idx].r).terrain;
                                    if gs.units[global_idx].unit_type == UnitType::Cavalry
                                        && now == crate::map::Terrain::Forest {
                                        break;
                                    }
                                    if from == crate::map::Terrain::Plain { plains_run += 1; }
                                    else { plains_run = 0; }
                                }
                                _ => break,  // 战斗/占城/受阻 → 停
                            }
                        }
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
                    if let Some(cost) = tech.cost_of(tech_id) {
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
                Action::Expand => {
                    // P1.5: 抽象扩张。花费资源+扣支持度→提升产出基数。
                    let econ = &mut gs.economies[pid as usize];
                    let (ef, ew, eg) = gs.config.expand_resource_cost;
                    if econ.can_afford((ef, ew, eg)) {
                        econ.spend((ef, ew, eg));
                        econ.support -= gs.config.expand_support_cost;
                        econ.expansion_level += 1;
                    }
                }
                Action::ChooseBranch { branch } => {
                    // P1.5: 选择红白路线。需回合≥branch_available_turn。
                    if gs.turn >= gs.config.branch_available_turn {
                        let econ = &mut gs.economies[pid as usize];
                        if econ.branch.is_none() {
                            match branch.as_str() {
                                "White" => {
                                    econ.branch = Some(Branch::White);
                                    econ.crisis_timer = gs.config.white_crisis_interval;
                                }
                                "Red" => {
                                    econ.branch = Some(Branch::Red);
                                    econ.organization = 10;  // 初始组织度
                                }
                                _ => {}
                            }
                        }
                    }
                }
                Action::RedeemOrg { mode } => {
                    // P1.5: 红线组织度兑换。仅红线玩家可用。
                    let econ = &mut gs.economies[pid as usize];
                    if econ.branch != Some(Branch::Red) { continue; }
                    econ.redeemed_this_turn = true;
                    match mode.as_str() {
                        "LianDa" => {
                            if econ.organization >= gs.config.red_lian_da_org_cost {
                                econ.organization -= gs.config.red_lian_da_org_cost;
                                // 瞬间完成 N 个可研究科技
                                let tech = &mut gs.techs[pid as usize];
                                for _ in 0..gs.config.red_lian_da_techs {
                                    let avail = tech.available_to_research();
                                    if let Some(t) = avail.first().cloned() {
                                        tech.completed.insert(t);
                                    }
                                }
                            }
                        }
                        "Concentrate" => {
                            if econ.organization >= gs.config.red_mobilize_org_cost {
                                econ.organization -= gs.config.red_mobilize_org_cost;
                                let m = gs.config.red_concentrate_mult as i32;
                                econ.food += econ.food * m;
                                econ.wood += econ.wood * m;
                                econ.gold += econ.gold * m;
                            }
                        }
                        "Mobilize" => {
                            if econ.organization >= gs.config.red_mobilize_org_cost {
                                econ.organization -= gs.config.red_mobilize_org_cost;
                                // 城市免费产 N 个步兵
                                let city = &gs.cities[pid as usize];
                                for _ in 0..gs.config.red_mobilize_units {
                                    produce_unit(&gs.grid, city, econ,
                                        UnitType::Infantry, &mut gs.units);
                                }
                            }
                        }
                        _ => {}
                    }
                }
            }
        }

        // 城市基础产出(P1.5: +扩张加成)
        let food_bonus = bonuses.city_food;
        let expand_bonus = gs.economies[pid as usize].expansion_level as i32
            * gs.config.expand_income_bonus;
        city_base_income(&mut gs.economies[pid as usize], food_bonus + expand_bonus);

        // P1.5: 支持度衰减。每拥有一个战斗单位, 支持度-1。
        let combat_units = player_units.iter()
            .filter(|&&idx| {
                let u = &gs.units[idx];
                u.alive && u.unit_type != UnitType::Worker && u.unit_type != UnitType::Scout
            })
            .count();
        let decay = combat_units as i32 * gs.config.support_decay_per_military;
        gs.economies[pid as usize].support = (gs.economies[pid as usize].support - decay).max(0);

        // P1.5: 支持度惩罚(低支持→产出打折)。在收入已加完后扣回。
        let sup = gs.economies[pid as usize].support;
        if sup < gs.config.support_penalty_threshold {
            let penalty = (gs.config.support_penalty_factor
                * gs.economies[pid as usize].food as f64) as i32;
            gs.economies[pid as usize].food = (gs.economies[pid as usize].food - penalty).max(0);
            gs.economies[pid as usize].wood = (gs.economies[pid as usize].wood - penalty).max(0);
            gs.economies[pid as usize].gold = (gs.economies[pid as usize].gold - penalty).max(0);
        }

        // ── P1.5: 红白 tick ────────────────────────────
        match gs.economies[pid as usize].branch {
            Some(Branch::White) => {
                // 白线: 产出加成(在收入之后乘, 这样扩张/科技加成也被放大)
                let boost = gs.config.white_output_boost;
                gs.economies[pid as usize].food = (gs.economies[pid as usize].food as f64 * boost) as i32;
                gs.economies[pid as usize].wood = (gs.economies[pid as usize].wood as f64 * boost) as i32;
                gs.economies[pid as usize].gold = (gs.economies[pid as usize].gold as f64 * boost) as i32;
                // 危机倒计时
                let econ = &mut gs.economies[pid as usize];
                if econ.crisis_timer > 0 {
                    econ.crisis_timer -= 1;
                }
                if econ.crisis_timer == 0 {
                    // 危机触发: 扣支持度 + 随机毁设施
                    econ.support = (econ.support - gs.config.white_crisis_support_damage).max(0);
                    // 随机毁一个己方设施(确定性: 用 seed+turn+pid 哈希选)
                    let hash = hash_for(gs.seed, gs.turn, pid);
                    let ms = gs.config.map_size as i32;
                    let mut my_facs: Vec<(i32, i32)> = Vec::new();
                    for r in 0..ms { for q in 0..ms {
                        if let Some(f) = &gs.grid.get(q, r).facility {
                            if f.player_id == pid { my_facs.push((q, r)); }
                        }
                    }}
                    if !my_facs.is_empty() {
                        let idx = (hash as usize) % my_facs.len();
                        let (fq, fr) = my_facs[idx];
                        gs.grid.get_mut(fq, fr).facility = None;
                    }
                    // 重置倒计时(±2 抖动, 确定性)
                    let interval = gs.config.white_crisis_interval;
                    let jitter = (hash as u8 % 5).saturating_sub(2); // -2..+2
                    econ.crisis_timer = interval.saturating_add(jitter).max(5);
                }
            }
            Some(Branch::Red) => {
                // 红线: 无产出加成, 但支持度自动回升 + 积累组织度(本回合未兑换时)
                let econ = &mut gs.economies[pid as usize];
                econ.support = (econ.support + gs.config.red_support_regen).min(100);
                if !econ.redeemed_this_turn {
                    let org_gain = (econ.support as f64 * gs.config.red_org_per_support).ceil() as i32;
                    econ.organization = (econ.organization + org_gain).min(100);
                }
                econ.redeemed_this_turn = false;  // 每回合重置
            }
            None => {}  // 未选分支, 不走红白逻辑
        }
    }

    // 科技研究推进(N 玩家同时——消除先后手研究偏差)
    for pid in 0..n {
        gs.techs[pid].tick_research();
    }

    // 建设胜利检查(每回合, P1.5: 任一人达成 → 其队伍赢)
    check_construction_victory(gs);

    // 城市防守: 每回合对占领者造成伤害(P1.5: 所有城市/所有敌人)
    for pid in 0..n as u8 {
        let city = &gs.cities[pid as usize];
        for u in gs.units.iter_mut() {
            if u.alive && u.player_id != pid && u.q == city.q && u.r == city.r
               && !same_team(u.player_id, pid, &gs.config)
            {
                u.hp -= gs.config.city_damage;
                if u.hp <= 0 { u.hp = 0; u.alive = false; }
            }
        }
    }

    // 渐进攻城(P1.5: 所有城市, 任意敌对近战单位占城持续削)
    for pid in 0..n as u8 {
        let (cq, cr) = (gs.cities[pid as usize].q, gs.cities[pid as usize].r);
        let best_dmg = gs.units.iter()
            .filter(|u| u.alive && u.player_id != pid
                     && !same_team(u.player_id, pid, &gs.config)
                     && u.q == cq && u.r == cr
                     && !u.ranged && u.unit_type != UnitType::Worker)
            .map(|u| city_occupation_damage(u, &gs.cities[pid as usize]))
            .max();
        if let Some(dmg) = best_dmg {
            gs.cities[pid as usize].hp -= dmg;
            if gs.cities[pid as usize].hp < 0 { gs.cities[pid as usize].hp = 0; }
        }
    }

    // 征服胜利检查(P1.5: 城 HP≤0 → 该玩家淘汰, 检查全队)
    check_conquest_victory(gs);

    // 阶梯判定(回合上限)
    if gs.turn >= gs.config.max_turns && gs.winner.is_none() {
        tiebreak_multi(gs);
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
/// 单步移动的结果(用于 move_speed 多步移动的控制)。
enum MoveOutcome { Moved, Fought, Blocked }

fn do_move(gs: &mut GameState, unit_idx: usize, dq: i32, dr: i32, charged: bool) -> MoveOutcome {
    if dq == 0 && dr == 0 {
        return MoveOutcome::Blocked;  // 无实际移动
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
        return MoveOutcome::Blocked;  // 无法移入——己方同类别单位已满
    }

    // 找目标格的敌方单位(P1.5: 只敌队, 队友不互打)
    let my_pid = gs.units[unit_idx].player_id;
    let blocker_idx = gs.units.iter().position(|u| {
        u.alive && u.player_id != my_pid
            && !same_team(u.player_id, my_pid, &gs.config)
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
            // 近战——移动+攻击(charged 由调用方按 move_speed 多步移动判定)
            let terrain_att = gs.grid.get(gs.units[unit_idx].q, gs.units[unit_idx].r).terrain;
            let terrain_def = gs.grid.get(nq, nr).terrain;

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
                // 占城格 = 占领; 城 HP 由回合结算的"渐进攻城"持续削(不在移入时一次性扣)
            }
        }
        MoveOutcome::Fought
    } else {
        // 目标格为空 → 直接移动
        gs.units[unit_idx].q = nq;
        gs.units[unit_idx].r = nr;
        // 进敌城格 = 占领; 城 HP 由回合结算的"渐进攻城"持续削(不在移入时一次性扣)
        MoveOutcome::Moved
    }
}

/// B3: 弓箭手远程攻击。射程 range_dist 内最近敌人 → 单向输出(不还手, 不移动)。
/// 返回是否攻击了(攻击了则本回合不再移动)。
fn try_ranged_attack(gs: &mut GameState, archer_idx: usize) -> bool {
    let (aq, ar, rng, pid) = {
        let a = &gs.units[archer_idx];
        (a.q, a.r, a.range_dist, a.player_id)
    };
    let opp = 1 - pid;
    // 射程内(1..=rng)最近的敌方单位
    let target = gs.units.iter().enumerate()
        .filter(|(_, u)| u.alive && u.player_id == opp)
        .map(|(i, u)| (i, crate::movement::hex_distance(aq, ar, u.q, u.r)))
        .filter(|&(_, d)| d >= 1 && d <= rng)
        .min_by_key(|&(_, d)| d)
        .map(|(i, _)| i);
    if let Some(tgt) = target {
        let terrain = gs.grid.get(gs.units[tgt].q, gs.units[tgt].r).terrain;
        if archer_idx < tgt {
            let (left, right) = gs.units.split_at_mut(tgt);
            resolve_ranged(&mut left[archer_idx], &mut right[0], terrain);
        } else {
            let (left, right) = gs.units.split_at_mut(archer_idx);
            resolve_ranged(&mut right[0], &mut left[tgt], terrain);
        }
        true
    } else {
        false
    }
}

// ─── 胜利判定 ────────────────────────────────────────

/// 建设胜利(P1.5: 任一人达成 → 其队伍赢)。
/// C5 完成 + 设施 ≥ 4, 每回合检查。
fn check_construction_victory(gs: &mut GameState) {
    if gs.winner.is_some() { return; }
    let ms = gs.config.map_size as i32;
    for pid in 0..gs.config.player_count {
        if gs.techs[pid as usize].completed.iter().any(|c| c == "C5") {
            let mut facility_count: u8 = 0;
            for r in 0..ms {
                for q in 0..ms {
                    if let Some(f) = &gs.grid.get(q, r).facility {
                        if f.player_id == pid { facility_count += 1; }
                    }
                }
            }
            if facility_count >= gs.config.construction_require_facilities {
                gs.winner = Some(pid);
                gs.victory_type = Some(VictoryType::Construction);
                return;
            }
        }
    }
}

/// 征服胜利检查(P1.5: 城 HP≤0 → 该玩家淘汰, 敌对队伍赢)。
fn check_conquest_victory(gs: &mut GameState) {
    if gs.winner.is_some() { return; }
    for pid in 0..gs.config.player_count {
        if !gs.cities[pid as usize].is_alive() {
            let losing_team = gs.config.teams.get(pid as usize).copied().unwrap_or(pid);
            // 找第一个不同队伍的玩家作为胜者代表
            for wp in 0..gs.config.player_count {
                let wt = gs.config.teams.get(wp as usize).copied().unwrap_or(wp);
                if wt != losing_team {
                    gs.winner = Some(wp);
                    gs.victory_type = Some(VictoryType::Conquest);
                    return;
                }
            }
        }
    }
}

/// 确定性哈希(seed + turn + pid → 伪随机数), 用于危机/事件等需要确定性的随机。
fn hash_for(seed: u64, turn: u16, pid: u8) -> u64 {
    let mut h = seed ^ ((turn as u64) << 16) ^ ((pid as u64) << 32);
    h ^= h >> 33;
    h = h.wrapping_mul(0xff51afd7ed558ccd);
    h ^= h >> 33;
    h = h.wrapping_mul(0xc4ceb9fe1a85ec53);
    h ^= h >> 33;
    h
}

/// 无偏"硬币":用 game seed 派生确定性但统计无偏的 0/1。
fn unbiased_coin(seed: u64) -> u8 {
    let mut h = seed;
    h ^= h >> 33;
    h = h.wrapping_mul(0xff51afd7ed558ccd);
    h ^= h >> 33;
    h = h.wrapping_mul(0xc4ceb9fe1a85ec53);
    h ^= h >> 33;
    (h & 1) as u8
}

/// 阶梯判定(P1.5: N 玩家, 按队伍聚合)。
/// 队内建设数合计 → 队内城 HP 合计 → 随机。
fn tiebreak_multi(gs: &mut GameState) {
    let n = gs.config.player_count as usize;
    use std::collections::BTreeMap;
    let mut team_constr: BTreeMap<u8, u32> = BTreeMap::new();
    let mut team_hp: BTreeMap<u8, i32> = BTreeMap::new();
    for pid in 0..n {
        let team = gs.config.teams.get(pid).copied().unwrap_or(pid as u8);
        *team_constr.entry(team).or_insert(0) += gs.techs[pid].construction_count() as u32;
        *team_hp.entry(team).or_insert(0) += gs.cities[pid].hp;
    }
    let mut ranked: Vec<(u8, u32, i32)> = team_constr.iter()
        .map(|(&t, &cc)| (t, cc, team_hp.get(&t).copied().unwrap_or(0)))
        .collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1).then(b.2.cmp(&a.2)));

    if ranked.len() >= 2 && ranked[0].1 == ranked[1].1 && ranked[0].2 == ranked[1].2 {
        let coin = unbiased_coin(gs.seed);
        let wt = ranked[coin as usize % ranked.len()].0;
        // 找该队第一个玩家
        gs.winner = (0..n as u8).find(|&p| {
            gs.config.teams.get(p as usize).copied().unwrap_or(p) == wt
        });
    } else {
        let wt = ranked[0].0;
        gs.winner = (0..n as u8).find(|&p| {
            gs.config.teams.get(p as usize).copied().unwrap_or(p) == wt
        });
    }
    if gs.winner.is_some() {
        gs.victory_type = Some(if ranked.len() >= 2 && ranked[0].1 > ranked[1].1 {
            VictoryType::TiebreakConstruction
        } else if ranked.len() >= 2 && ranked[0].2 > ranked[1].2 {
            VictoryType::TiebreakCityHp
        } else {
            VictoryType::TiebreakRandom
        });
    }
}

/// 向后兼容 2 人版(调用 step_game_multi)。
pub fn step_game(gs: &mut GameState, actions_p0: &[Action], actions_p1: &[Action]) -> StepResult {
    step_game_multi(gs, &[actions_p0.to_vec(), actions_p1.to_vec()])
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ai::random::RandomAgent;
    use crate::ai::Agent;
    use crate::config::GameConfig;
    use crate::unit::{Unit, UnitType};
    use crate::map::Terrain;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    // ── 辅助 ──────────────────────────────────────────

    /// 统计某玩家的存活单位数
    fn count_alive(gs: &GameState, pid: u8) -> usize {
        gs.units.iter().filter(|u| u.alive && u.player_id == pid).count()
    }

    // ── 基础测试(已有) ────────────────────────────────

    #[test]
    fn test_初始化游戏() {
        let gs = init_game(42, "balanced");
        assert_eq!(gs.turn, 0);
        assert_eq!(gs.cities.len(), 2);
        assert_eq!(gs.economies.len(), 2);
        assert_eq!(gs.techs.len(), 2);
        let p0_count = count_alive(&gs, 0);
        let p1_count = count_alive(&gs, 1);
        assert!(p0_count >= 1, "P0 应该至少有 1 个初始单位, 实际: {}", p0_count);
        assert!(p1_count >= 1, "P1 应该至少有 1 个初始单位, 实际: {}", p1_count);
        assert!(gs.winner.is_none());
    }

    #[test]
    fn test_初始单位位置在城市附近() {
        let gs = init_game(777, "balanced");
        for u in &gs.units {
            let city = &gs.cities[u.player_id as usize];
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
        while gs.winner.is_none() && gs.turn < gs.config.max_turns {
            let a0 = agent.decide(&gs, 0, &mut rng0);
            let a1 = agent.decide(&gs, 1, &mut rng1);
            step_game(&mut gs, &a0, &a1);
        }
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
        let n = 2000u64;
        let p0 = (0..n).filter(|i| unbiased_coin(50000 + i * 100) == 0).count();
        let rate = p0 as f64 / n as f64;
        assert!((rate - 0.5).abs() < 0.03,
                "unbiased_coin 在 50000+i*100 种子上偏向: P0={:.1}%", rate * 100.0);
        assert_eq!(unbiased_coin(12345), unbiased_coin(12345));
    }

    // ── 胜利路径测试(重构安全网) ──────────────────────

    #[test]
    fn test_征服胜利_城HP归零触发() {
        // 直接设 P1 城 HP=0, 回合结束后 P0 征服胜
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        gs.cities[1].hp = 0;
        step_game(&mut gs, &[], &[]);
        assert_eq!(gs.winner, Some(0));
        assert_eq!(gs.victory_type, Some(VictoryType::Conquest));
    }

    #[test]
    fn test_建设胜利_C5加4设施触发() {
        // 手动完成 C5 + 放 4 个 P0 设施 → 建设胜利
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        // 完成 C5 前置链
        for t in &["C1", "C3", "C4", "C5"] {
            gs.techs[0].completed.insert(t.to_string());
        }
        // 在 P0 城周围 4 个邻格放设施
        let (cq, cr) = (gs.cities[0].q, gs.cities[0].r);
        for i in 0..4 {
            let nq = (cq + HEX_DIRS[i].0).rem_euclid(MAP_W as i32);
            let nr = (cr + HEX_DIRS[i].1).rem_euclid(MAP_H as i32);
            gs.grid.get_mut(nq, nr).facility = Some(crate::unit::Facility {
                facility_type: crate::unit::FacilityType::Farm,
                player_id: 0, q: nq, r: nr,
            });
        }
        step_game(&mut gs, &[], &[]);
        assert_eq!(gs.winner, Some(0), "C5+4设施应触发建设胜利");
        assert_eq!(gs.victory_type, Some(VictoryType::Construction));
    }

    #[test]
    fn test_建设胜利_设施不足不触发() {
        // C5 完成但设施 <4 → 不触发建设胜利
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        for t in &["C1", "C3", "C4", "C5"] {
            gs.techs[0].completed.insert(t.to_string());
        }
        // 只放 3 个设施(不足 4)
        let (cq, cr) = (gs.cities[0].q, gs.cities[0].r);
        for i in 0..3 {
            let nq = (cq + HEX_DIRS[i].0).rem_euclid(MAP_W as i32);
            let nr = (cr + HEX_DIRS[i].1).rem_euclid(MAP_H as i32);
            gs.grid.get_mut(nq, nr).facility = Some(crate::unit::Facility {
                facility_type: crate::unit::FacilityType::Farm,
                player_id: 0, q: nq, r: nr,
            });
        }
        step_game(&mut gs, &[], &[]);
        assert!(gs.winner != Some(0) || gs.victory_type != Some(VictoryType::Construction),
            "设施不足4不应触发建设胜利");
    }

    #[test]
    fn test_阶梯判定_建设数多者胜() {
        // max_turns=1 强制回合1触发阶梯; P0 建设数 > P1
        let cfg = GameConfig { max_turns: 1, ..GameConfig::default() };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        gs.techs[0].completed.insert("C1".to_string());
        gs.techs[0].completed.insert("C2".to_string());
        gs.techs[1].completed.insert("C1".to_string());
        step_game(&mut gs, &[], &[]);
        assert_eq!(gs.winner, Some(0));
        assert_eq!(gs.victory_type, Some(VictoryType::TiebreakConstruction));
    }

    #[test]
    fn test_阶梯判定_城HP多者胜() {
        // max_turns=1, 建设数相同(0), P0 城HP 更高
        let cfg = GameConfig { max_turns: 1, ..GameConfig::default() };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        gs.cities[0].hp = 140;
        gs.cities[1].hp = 100;
        step_game(&mut gs, &[], &[]);
        assert_eq!(gs.winner, Some(0));
        assert_eq!(gs.victory_type, Some(VictoryType::TiebreakCityHp));
    }

    #[test]
    fn test_阶梯判定_随机平局有胜者() {
        // max_turns=1, 建设数相同 + 城HP 相同 → 随机判定, 但必有胜者
        let cfg = GameConfig { max_turns: 1, ..GameConfig::default() };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        // 两边全相同
        step_game(&mut gs, &[], &[]);
        assert!(gs.winner.is_some(), "阶梯随机判定也必须有胜者");
        assert_eq!(gs.victory_type, Some(VictoryType::TiebreakRandom));
    }

    // ── 机制修复测试(B系列硬伤回归) ──────────────────

    #[test]
    fn test_渐进攻城_占城步兵每回合削城HP() {
        // B1 修复: 步兵占领城格 → 每回合持续削城 HP(不在移入时一次性)
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(99999, "balanced", cfg);
        // 手动放 P0 步兵在 P1 城格上
        let (cq1, cr1) = (gs.cities[1].q, gs.cities[1].r);
        gs.units.push(Unit::create(UnitType::Infantry, 0, cq1, cr1));
        let hp_before = gs.cities[1].hp;
        step_game(&mut gs, &[], &[]);
        assert!(gs.cities[1].hp < hp_before,
            "渐进攻城: 敌方步占城后城HP应下降(before={}, after={})",
            hp_before, gs.cities[1].hp);
    }

    #[test]
    fn test_渐进攻城_弓手占城不削城HP() {
        // 弓箭手不能占城/攻城(只有近战非工人能削城)
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(99999, "balanced", cfg);
        let (cq1, cr1) = (gs.cities[1].q, gs.cities[1].r);
        gs.units.push(Unit::create(UnitType::Archer, 0, cq1, cr1));
        let hp_before = gs.cities[1].hp;
        step_game(&mut gs, &[], &[]);
        assert_eq!(gs.cities[1].hp, hp_before,
            "弓手占城不应削城HP(ranged单位无攻城力)");
    }

    #[test]
    fn test_远攻触发_弓手不移动射击射程内敌人() {
        // B3 修复: 弓手射程 2 内有敌 → try_ranged_attack 先触发, 不移动
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        // 在 P1 城附近放弓手和敌方步兵(距离2且无遮挡)
        // 用环面坐标, 选开阔区域
        let ax = 10i32; let ay = 10i32;
        gs.grid.get_mut(ax, ay).terrain = Terrain::Plain;
        gs.grid.get_mut(ax + 1, ay).terrain = Terrain::Plain;
        // P0 弓手在 (ax, ay)
        let n_p0_before = count_alive(&gs, 0);
        gs.units.push(Unit::create(UnitType::Archer, 0, ax, ay));
        // P1 步兵在射程 1 处(ax+1, ay)——弓手发 Move(1,0) 前先 try_ranged_attack
        gs.units.push(Unit::create(UnitType::Infantry, 1, ax + 1, ay));
        let archer_hp_before = gs.units[gs.units.len() - 2].hp;
        let target_hp_before = gs.units[gs.units.len() - 1].hp;
        // P0 弓手发 Move(1,0) → 射程内检测到 P1 步兵 → 远程攻击, 跳过移动
        let p0_actions = vec![Action::Move { unit_idx: n_p0_before, dq: 1, dr: 0 }];
        step_game(&mut gs, &p0_actions, &[]);
        let archer = &gs.units[gs.units.len() - 2];
        let target = &gs.units[gs.units.len() - 1];
        // 弓手不应受伤(远程单向)
        assert_eq!(archer.hp, archer_hp_before,
            "弓手远程攻击不应受伤");
        // 目标应受伤或死亡
        assert!(target.hp < target_hp_before || !target.alive,
            "远程目标应受伤(before={}, after={})", target_hp_before, target.hp);
        // 弓手不应移动(仍站在原位)
        assert_eq!((archer.q, archer.r), (ax, ay),
            "弓手触发远程攻击后不应移动");
    }

    // ── P1.5: N 玩家测试 ────────────────────────────

    #[test]
    fn test_4玩家初始化() {
        let cfg = GameConfig {
            player_count: 4,
            teams: vec![0, 0, 1, 1],  // 2v2
            ..GameConfig::default()
        };
        let gs = init_game_with_config(50000, "balanced", cfg);
        assert_eq!(gs.cities.len(), 4);
        assert_eq!(gs.economies.len(), 4);
        assert_eq!(gs.techs.len(), 4);
        // 四个玩家都应有初始单位
        for pid in 0..4u8 {
            assert!(count_alive(&gs, pid) >= 1,
                "玩家 {} 至少 1 个初始单位", pid);
        }
    }

    #[test]
    fn test_4玩家单局可跑完() {
        let max_t = 20u16;
        let cfg = GameConfig {
            max_turns: max_t,
            player_count: 4,
            teams: vec![0, 0, 1, 1],
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(60000, "balanced", cfg);
        while gs.winner.is_none() && gs.turn < gs.config.max_turns {
            let empty: Vec<Action> = vec![];
            step_game_multi(&mut gs, &vec![empty.clone(), empty.clone(), empty.clone(), empty.clone()]);
        }
        assert!(gs.winner.is_some() || gs.turn >= max_t,
            "4 人游戏应可运行到回合上限");
    }

    #[test]
    fn test_支持度_随战斗单位衰减() {
        let cfg = GameConfig {
            support_decay_per_military: 2,  // 加速测试
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        let sup_before = gs.economies[0].support;
        // 产一个步兵(战斗单位)
        step_game(&mut gs,
            &[Action::ProduceUnit { unit_type: "infantry".to_string() }],
            &[]);
        // 下回合: 支持度应衰减
        step_game(&mut gs, &[], &[]);
        // P0 有 1 战斗单位 → 应衰减 2
        // 注意: 初始侦察兵不计(非战斗), 新产的步兵算战斗单位
        assert!(gs.economies[0].support < sup_before,
            "支持度应衰减(sup_before={} sup_after={})",
            sup_before, gs.economies[0].support);
    }

    #[test]
    fn test_扩张_扣支持度加产出() {
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        let sup_before = gs.economies[0].support;
        let food_before = gs.economies[0].food;
        // 执行一次扩张
        step_game(&mut gs, &[Action::Expand], &[]);
        assert_eq!(gs.economies[0].expansion_level, 1);
        assert!(gs.economies[0].support < sup_before,
            "扩张应扣支持度");
        assert!(gs.economies[0].food < food_before,
            "扩张应花费资源");
    }

    // ── P1.5: 红白分叉测试 ──────────────────────────

    #[test]
    fn test_选择白线_产出加成和危机() {
        let cfg = GameConfig {
            branch_available_turn: 0,  // 开局可选
            white_crisis_interval: 3,   // 加速危机
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        // 选白线
        step_game(&mut gs,
            &[Action::ChooseBranch { branch: "White".to_string() }],
            &[]);
        assert_eq!(gs.economies[0].branch, Some(Branch::White));
        assert!(gs.economies[0].crisis_timer > 0,
            "白线应有危机倒计时");
        // 跑 crisis_timer 回合看危机触发
        for _ in 0..gs.config.white_crisis_interval + 1 {
            step_game(&mut gs, &[], &[]);
        }
        // 危机触发后 timer 应重置
        assert!(gs.economies[0].crisis_timer > 0
            || gs.economies[0].support < 50,
            "危机应重置timer或已扣支持度");
    }

    #[test]
    fn test_选择红线_组织度积累和兑换() {
        let cfg = GameConfig {
            branch_available_turn: 0,
            red_support_regen: 5,         // 加速测试
            red_org_per_support: 1.0,      // 加速测试
            red_lian_da_org_cost: 20,
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        // 选红线
        step_game(&mut gs,
            &[Action::ChooseBranch { branch: "Red".to_string() }],
            &[]);
        assert_eq!(gs.economies[0].branch, Some(Branch::Red));
        assert!(gs.economies[0].organization >= 10,
            "红线初始组织度 ≥10");
        // 跑几回合看组织度积累
        for _ in 0..3 {
            step_game(&mut gs, &[], &[]);
        }
        assert!(gs.economies[0].organization > 10,
            "组织度应随时间增长(org={})", gs.economies[0].organization);
        // 兑换西南联大
        let completed_before = gs.techs[0].completed.len();
        let org_before = gs.economies[0].organization;
        step_game(&mut gs,
            &[Action::RedeemOrg { mode: "LianDa".to_string() }],
            &[]);
        assert!(gs.techs[0].completed.len() > completed_before,
            "西南联大应完成新科技");
        assert!(gs.economies[0].organization < org_before,
            "兑换后组织度应减少(before={} after={})",
            org_before, gs.economies[0].organization);
    }

    #[test]
    fn test_红线_全民皆兵产兵() {
        let cfg = GameConfig {
            branch_available_turn: 0,
            red_mobilize_org_cost: 10,     // 降低门槛, 初始10够
            red_mobilize_units: 2,
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        step_game(&mut gs,
            &[Action::ChooseBranch { branch: "Red".to_string() }],
            &[]);
        let units_before = count_alive(&gs, 0);
        step_game(&mut gs,
            &[Action::RedeemOrg { mode: "Mobilize".to_string() }],
            &[]);
        assert!(count_alive(&gs, 0) > units_before,
            "全民皆兵应产出新单位(before={} after={})",
            units_before, count_alive(&gs, 0));
    }

    #[test]
    fn test_未到可选回合不能选分叉() {
        let cfg = GameConfig {
            branch_available_turn: 50,  // 很远
            ..GameConfig::default()
        };
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        step_game(&mut gs,
            &[Action::ChooseBranch { branch: "White".to_string() }],
            &[]);
        assert_eq!(gs.economies[0].branch, None,
            "回合1<50不应允许选分叉");
    }

    #[test]
    fn test_堆叠限制_同格不能有两战斗单位() {
        // 己方战斗单位不能移入已有己方战斗单位的格
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        let q = 7i32; let r = 7i32;
        gs.grid.get_mut(q, r).terrain = Terrain::Plain;
        gs.grid.get_mut(q + 1, r).terrain = Terrain::Plain;
        // 放两个 P0 步兵: 一个在 (q,r), 另一个在 (q+1,r) 尝试移入 (q,r)
        let n_before = count_alive(&gs, 0);
        gs.units.push(Unit::create(UnitType::Infantry, 0, q, r));
        gs.units.push(Unit::create(UnitType::Infantry, 0, q + 1, r));
        // 第二个步兵发 Move(-1,0) → 目标格已有己方步兵 → 应被堆叠限制挡住
        let p0_actions = vec![Action::Move { unit_idx: n_before + 1, dq: -1, dr: 0 }];
        step_game(&mut gs, &p0_actions, &[]);
        let u2 = &gs.units[gs.units.len() - 1]; // 第二个步兵
        assert_eq!((u2.q, u2.r), (q + 1, r),
            "第二个步兵不应移入己方步兵所在格(堆叠限制)");
    }
}
