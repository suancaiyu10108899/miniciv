// Greedy v6 AI — Phase 7
// 翻译自 prototype/ai_greedy.py (804行) + prototype_hex/ai_greedy_hex.py (808行)
//
// 四层架构:
//   战略评估 → 策略选择 → 战术执行 → 经济/研究/生产
//
// 六边形重校准: Python hex 版机械翻译自方格, 已确认为 broken。
// Rust 版在 _move_to() 中使用参数化权重, 后续跑扫描找最优值:
//   DISTANCE_WEIGHT: 移动评分中距离的权重 (默认 3.0)
//   TERRAIN_WEIGHT:  移动评分中地形的权重 (默认 0.10)
//
// Rust 新概念:
//   HashMap<u64, OpponentModel> — ≈ C++ unordered_map, key=seed
//   enum Strategy { ... }        — 策略模式
//   Vec::retain()                — 原地过滤(比 Python 的列表推导更高效)

use crate::game::GameState;
use crate::unit::{Unit, UnitType, City};
use crate::map::{Grid, Terrain};
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, hex_distance, HEX_DIRS};
use crate::constants::{
    MAP_W, MAP_H, CITY_HP, CITY_DEF, CAVALRY_CHARGE_BONUS,
    FACILITY_OUTPUT, CITY_BASE_FOOD,
    STARTING_FOOD, STARTING_WOOD, STARTING_GOLD,
};
use crate::tech::{TechManager, TechBonuses};
use rand::RngCore;
use std::collections::HashMap;

// ═══════════════════════════════════════════════════════
// 可调参数结构体 — 六边形几何重校准的核心
// 字段而非 const, 支持运行时参数扫描
// ═══════════════════════════════════════════════════════

#[derive(Clone, Debug)]
pub struct GreedyConfig {
    /// 移动评分中路径距离的权重。方格版用 1.0, 六边环面需要更高。
    pub distance_weight: f64,
    /// 移动评分中地形防御的权重。方格版用 0.15, 六边需要更低。
    pub terrain_weight: f64,
    /// 撤退时额外看重防御加成
    pub retreat_terrain_bonus: f64,
}

impl Default for GreedyConfig {
    fn default() -> Self {
        Self {
            // 参数扫描结果 (600 games): TW=0.15最优, DW影响不大
            distance_weight: 3.0,
            terrain_weight: 0.15,
            retreat_terrain_bonus: 0.20,
        }
    }
}

/// 弓手保持最佳射程(2格)的权重
const ARCHER_DIST_WEIGHT: f64 = 1.0;

/// 弓手偏好高地形的权重
const ARCHER_HIGH_GROUND: f64 = 0.1;

// ═══════════════════════════════════════════════════════
// 策略枚举
// ═══════════════════════════════════════════════════════

#[derive(Clone, Copy, Debug, PartialEq)]
enum Strategy {
    Balanced,
    Aggressive,
    Defensive,
    Construction,
    DefensiveConstruction,
}

// ═══════════════════════════════════════════════════════
// 对手模型 — 跨回合持久化
// ═══════════════════════════════════════════════════════

#[derive(Clone, Debug)]
struct OpponentModel {
    /// (回合, 侵略性分数) 的历史记录, 保留最近 10 回合
    history: Vec<(u16, f64)>,
    /// 滚动平均侵略性: 0=被动, 1=激进
    aggression: f64,
    /// 对手各兵种的累计出现次数
    enemy_unit_types: HashMap<String, u32>,
}

impl OpponentModel {
    fn new() -> Self {
        Self {
            history: Vec::new(),
            aggression: 0.5,
            enemy_unit_types: HashMap::new(),
        }
    }
}

// ═══════════════════════════════════════════════════════
// Greedy Agent
// ═══════════════════════════════════════════════════════

pub struct GreedyAgent {
    /// 可调权重配置(运行时参数扫描用)
    pub config: GreedyConfig,
    /// 对手模型 — 按 game seed 索引(同一局内跨回合持久)
    opponent_models: std::sync::Mutex<HashMap<u64, OpponentModel>>,
}

impl GreedyAgent {
    pub fn new() -> Self {
        Self { config: GreedyConfig::default(), opponent_models: std::sync::Mutex::new(HashMap::new()) }
    }
    pub fn with_config(config: GreedyConfig) -> Self {
        Self { config, opponent_models: std::sync::Mutex::new(HashMap::new()) }
    }

    fn get_opponent_model(&self, seed: u64) -> OpponentModel {
        let mut map = self.opponent_models.lock().unwrap();
        map.entry(seed).or_insert_with(OpponentModel::new).clone()
    }

    fn update_opponent_model(&self, seed: u64, model: OpponentModel) {
        let mut map = self.opponent_models.lock().unwrap();
        map.insert(seed, model);
    }

    /// 清理旧的对手模型(保留最近 50 个 seed)
    fn clean_opponent_history(&self) {
        let mut map = self.opponent_models.lock().unwrap();
        if map.len() > 100 {
            let keys: Vec<u64> = map.keys().cloned().collect();
            let to_remove = keys.len() - 50;
            for k in keys.iter().take(to_remove) {
                map.remove(k);
            }
        }
    }
}

impl Agent for GreedyAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();

        // 收集当前玩家的存活单位
        let player_units: Vec<(usize, &Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        // ── 第一层: 战略评估 ──────────────────────
        let assessment = strategic_assess(gs, pid);

        // ── 对手建模 ──────────────────────────────
        let mut opp_model = self.get_opponent_model(gs.seed);
        update_opponent_model(&mut opp_model, gs, pid);
        self.update_opponent_model(gs.seed, opp_model.clone());

        // ── 第二层: 策略选择 ──────────────────────
        let strategy = select_strategy(gs, pid, &assessment, &opp_model);

        // ── 部队协调(第四层v4) ────────────────────
        let (rally_point, wave_ready) = compute_force_coordination(gs, pid, &assessment);
        let production_counter = compute_adaptive_counter(&opp_model);

        // 战术顺序: 弓手 → 近战 → 侦察兵
        let mut archers: Vec<usize> = Vec::new();
        let mut fighters: Vec<usize> = Vec::new();
        let mut scouts: Vec<usize> = Vec::new();
        for (ui, u) in &player_units {
            match u.unit_type {
                UnitType::Archer => archers.push(*ui),
                UnitType::Scout => scouts.push(*ui),
                UnitType::Worker => {}  // 后面单独处理
                _ => fighters.push(*ui),
            }
        }

        for global_idx in archers.iter().chain(fighters.iter()).chain(scouts.iter()) {
            let local_idx = player_units.iter()
                .position(|(i, _)| *i == *global_idx).unwrap();
            let unit = &gs.units[*global_idx];
            if let Some(act) = greedy_combat(
                unit, local_idx, gs, pid,
                strategy, &assessment, rally_point, wave_ready, &self.config,
            ) {
                actions.push(act);
            }
        }

        // 工人
        for (global_idx, unit) in &player_units {
            if unit.unit_type == UnitType::Worker {
                let local_idx = player_units.iter()
                    .position(|(i, _)| *i == *global_idx).unwrap();
                if let Some(act) = greedy_worker(unit, local_idx, gs, pid, strategy, &self.config) {
                    actions.push(act);
                }
            }
        }

        // ── 第四层: 研究 ──────────────────────────
        if gs.techs[pid as usize].researching.is_none() {
            do_research(gs, pid, strategy, &mut actions);
        }

        // ── 第四层: 生产 ──────────────────────────
        do_production(gs, pid, strategy, &production_counter, &assessment, &mut actions);

        self.clean_opponent_history();
        actions
    }

    fn name(&self) -> &str { "Greedy" }
}

// ═══════════════════════════════════════════════════════
// 第一层: 战略评估
// ═══════════════════════════════════════════════════════

#[derive(Clone, Debug)]
struct StrategicAssessment {
    my_count: usize,
    opp_count: usize,
    unit_ratio: f64,
    res_ratio: f64,
    tech_lead: i32,
    my_city_hp: i32,
    opp_city_hp: i32,
    my_frontline_count: usize,
    opp_frontline_count: usize,
    opp_near_city_count: usize,
    enemy_defense_strong: bool,
    weak_point: Option<(i32, i32)>,
    my_power: i32,
    opp_power: i32,
    city_threatened: bool,
}

fn strategic_assess(gs: &GameState, pid: u8) -> StrategicAssessment {
    let opp = 1 - pid;
    let size = MAP_W as i32;

    let my_combat: Vec<&Unit> = gs.units.iter()
        .filter(|u| u.player_id == pid && u.alive && u.unit_type != UnitType::Worker)
        .collect();
    let opp_combat: Vec<&Unit> = gs.units.iter()
        .filter(|u| u.player_id == opp && u.alive && u.unit_type != UnitType::Worker)
        .collect();

    let my_count = my_combat.len();
    let opp_count = opp_combat.len();
    let unit_ratio = my_count as f64 / (opp_count.max(1) as f64);

    let my_econ = &gs.economies[pid as usize];
    let opp_econ = &gs.economies[opp as usize];
    let my_total = my_econ.food + my_econ.wood + my_econ.gold;
    let opp_total = opp_econ.food + opp_econ.wood + opp_econ.gold;
    let res_ratio = my_total as f64 / (opp_total.max(1) as f64);

    let my_techs = gs.techs[pid as usize].completed.len() as i32;
    let opp_techs = gs.techs[opp as usize].completed.len() as i32;
    let tech_lead = my_techs - opp_techs;

    let my_city_hp = gs.cities[pid as usize].hp;
    let opp_city_hp = gs.cities[opp as usize].hp;

    let opp_city = &gs.cities[opp as usize];
    let my_city = &gs.cities[pid as usize];

    // 前线: 战斗单位距离敌城 ≤6
    let my_frontline: Vec<&&Unit> = my_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, opp_city.q, opp_city.r) <= 6)
        .collect();
    let opp_frontline: Vec<&&Unit> = opp_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, my_city.q, my_city.r) <= 6)
        .collect();

    // 敌城周围密度(用于 weak point 检测)
    let opp_near_their_city: Vec<&&Unit> = opp_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, opp_city.q, opp_city.r) <= 4)
        .collect();

    // 找 weak point: 敌城周围防守最薄弱的方向
    let mut weak_point = None;
    let mut min_enemies = 999;
    let scan_dirs = [(3, 0), (-3, 0), (0, 3), (0, -3), (2, 2), (-2, 2), (2, -2), (-2, -2)];
    for (dq, dr) in scan_dirs.iter() {
        let wx = (opp_city.q + dq).rem_euclid(size);
        let wy = (opp_city.r + dr).rem_euclid(size);
        let nearby = opp_combat.iter()
            .filter(|u| hex_distance(u.q, u.r, wx, wy) <= 3)
            .count();
        if nearby < min_enemies {
            min_enemies = nearby;
            weak_point = Some((wx, wy));
        }
    }

    let my_power: i32 = my_combat.iter().map(|u| u.atk).sum();
    let opp_power: i32 = opp_combat.iter().map(|u| u.atk).sum();

    let city_threatened = opp_combat.iter().any(|u| {
        hex_distance(u.q, u.r, my_city.q, my_city.r) <= 2
    });

    StrategicAssessment {
        my_count, opp_count, unit_ratio, res_ratio, tech_lead,
        my_city_hp, opp_city_hp,
        my_frontline_count: my_frontline.len(),
        opp_frontline_count: opp_frontline.len(),
        opp_near_city_count: opp_near_their_city.len(),
        enemy_defense_strong: opp_near_their_city.len() >= 3,
        weak_point,
        my_power, opp_power,
        city_threatened,
    }
}

// ═══════════════════════════════════════════════════════
// 对手建模
// ═══════════════════════════════════════════════════════

fn update_opponent_model(model: &mut OpponentModel, gs: &GameState, pid: u8) {
    let opp = 1 - pid;
    let size = MAP_W as i32;
    let my_city = &gs.cities[pid as usize];
    let opp_city = &gs.cities[opp as usize];

    let opp_combat: Vec<&Unit> = gs.units.iter()
        .filter(|u| u.player_id == opp && u.alive && u.unit_type != UnitType::Worker)
        .collect();

    // 侵略性: 对手有多少单位在前线(离我城≤6) vs 防御(离他城≤6)
    let near_my = opp_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, my_city.q, my_city.r) <= 6)
        .count();
    let near_their = opp_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, opp_city.q, opp_city.r) <= 6)
        .count();
    let total = opp_combat.len().max(1);

    let aggression = (near_my as f64 / total as f64) - (near_their as f64 / total as f64);
    let aggression = (aggression + 1.0) / 2.0;  // 归一化到 [0, 1]

    model.history.push((gs.turn, aggression));
    // 保留最近 10 回合
    model.history.retain(|(t, _)| gs.turn.saturating_sub(*t) < 10);
    if !model.history.is_empty() {
        model.aggression = model.history.iter().map(|(_, a)| a).sum::<f64>()
            / model.history.len() as f64;
    }

    // 跟踪对手兵种
    for u in &opp_combat {
        let type_name = match u.unit_type {
            UnitType::Infantry => "infantry",
            UnitType::Cavalry => "cavalry",
            UnitType::Archer => "archer",
            UnitType::Scout => "scout",
            UnitType::Worker => continue,
        };
        *model.enemy_unit_types.entry(type_name.to_string()).or_insert(0) += 1;
    }
}

// ═══════════════════════════════════════════════════════
// 第二层: 策略选择
// ═══════════════════════════════════════════════════════

fn select_strategy(
    gs: &GameState, pid: u8,
    a: &StrategicAssessment,
    opp: &OpponentModel,
) -> Strategy {
    // 前期强制 balanced(经济积累)
    if gs.turn < 8 {
        return Strategy::Balanced;
    }

    // 双方都没战斗单位
    if a.my_count == 0 && a.opp_count == 0 {
        return Strategy::Balanced;
    }

    // 军事碾压
    if a.unit_ratio > 1.3 && a.my_count >= 3 {
        return Strategy::Aggressive;
    }

    // 城市被威胁 + 兵力劣势
    if a.city_threatened && a.my_count < a.opp_count {
        return Strategy::Defensive;
    }
    if a.unit_ratio < 0.6 && a.opp_count > 2 {
        return Strategy::Defensive;
    }

    // 中后期建设条件(回合>20 才允许建设策略——给战斗留窗口)
    if gs.turn < 20 {
        return Strategy::Balanced;
    }

    // 已在 C 线上
    if gs.techs[pid as usize].completed.iter().any(|c| c == "C1") {
        if gs.turn > 25 {
            return Strategy::Construction;
        }
    }

    // 安全 + 资源充足
    let my_res = gs.economies[pid as usize].food
        + gs.economies[pid as usize].wood
        + gs.economies[pid as usize].gold;
    if gs.turn > 30 && my_res > 35 && !a.city_threatened {
        return Strategy::Construction;
    }

    // 长期僵持
    if gs.turn > 35 && a.opp_city_hp >= 85 && a.my_city_hp >= 85 {
        return Strategy::Construction;
    }

    // 对手建模
    if opp.aggression > 0.65 && gs.turn > 15 {
        if gs.turn > 30 {
            return Strategy::DefensiveConstruction;
        }
        return Strategy::Defensive;
    }
    if opp.aggression < 0.35 && gs.turn > 15 {
        return Strategy::Aggressive;
    }

    Strategy::Balanced
}

// ═══════════════════════════════════════════════════════
// 部队协调 (v4)
// ═══════════════════════════════════════════════════════

fn compute_force_coordination(
    gs: &GameState, pid: u8, a: &StrategicAssessment,
) -> ((i32, i32), bool) {
    let opp_city = &gs.cities[1 - pid as usize];

    // rally point: weak_point(如果有), 否则直接敌城
    let rally_point = if a.opp_count >= 3 {
        a.weak_point.unwrap_or((opp_city.q, opp_city.r))
    } else {
        (opp_city.q, opp_city.r)
    };

    // 计算聚集在 rally point 周围的己方战斗单位数
    let my_combat: Vec<&Unit> = gs.units.iter()
        .filter(|u| u.player_id == pid && u.alive && u.unit_type != UnitType::Worker)
        .collect();
    let wave_units = my_combat.iter()
        .filter(|u| hex_distance(u.q, u.r, rally_point.0, rally_point.1) <= 4)
        .count();

    (rally_point, wave_units >= 2)
}

fn compute_adaptive_counter(opp: &OpponentModel) -> Option<String> {
    let total: u32 = opp.enemy_unit_types.values().sum();
    if total < 3 {
        return None;  // 数据不足
    }

    let archer_c = *opp.enemy_unit_types.get("archer").unwrap_or(&0);
    let cavalry_c = *opp.enemy_unit_types.get("cavalry").unwrap_or(&0);
    let infantry_c = *opp.enemy_unit_types.get("infantry").unwrap_or(&0);

    // 对手弓手多 → 造骑兵(快速接近)
    if archer_c >= 2 && archer_c >= cavalry_c && archer_c >= infantry_c {
        return Some("cavalry".to_string());
    }
    // 对手骑兵多 → 造步兵(高DEF, 占山地)
    if cavalry_c >= 2 && cavalry_c >= archer_c && cavalry_c >= infantry_c {
        return Some("infantry".to_string());
    }
    // 对手步兵多 → 造步兵对抗
    if infantry_c >= 2 {
        return Some("infantry".to_string());
    }

    None
}

// ═══════════════════════════════════════════════════════
// 第三层: 战斗单位决策
// ═══════════════════════════════════════════════════════

fn greedy_combat(
    unit: &Unit, local_idx: usize, gs: &GameState, pid: u8,
    strategy: Strategy, a: &StrategicAssessment,
    rally_point: (i32, i32), wave_ready: bool,
    cfg: &GreedyConfig,
) -> Option<Action> {
    let opp = 1 - pid;
    let my_city = &gs.cities[pid as usize];
    let opp_city = &gs.cities[opp as usize];

    let max_hp = match unit.unit_type {
        UnitType::Infantry => 100,
        UnitType::Cavalry => 80,
        UnitType::Archer => 60,
        _ => 40,
    };
    let hp_pct = unit.hp as f64 / max_hp as f64;

    // ── 残血撤退 ──────────────────────────────────
    if hp_pct < 0.3 {
        let near_enemy = gs.units.iter().any(|eu| {
            eu.alive && eu.player_id != pid
                && hex_distance(eu.q, eu.r, unit.q, unit.r) <= 2
        });
        if near_enemy {
            return Some(move_to(unit, local_idx, gs, my_city.q, my_city.r, true, cfg));
        }
    }

    // ── 弓手距离战术 ──────────────────────────────
    if unit.ranged {
        // 找最近的敌人
        let mut nearest: Option<&Unit> = None;
        let mut nearest_dist = 255u8;
        for eu in &gs.units {
            if eu.alive && eu.player_id != pid {
                let d = hex_distance(eu.q, eu.r, unit.q, unit.r);
                if d < nearest_dist {
                    nearest_dist = d;
                    nearest = Some(eu);
                }
            }
        }
        if let Some(target) = nearest {
            if nearest_dist <= 2 {
                if nearest_dist == 1 {
                    // 敌人贴脸 → 撤退
                    return Some(retreat_from(unit, local_idx, gs, target.q, target.r, cfg));
                }
                // 理想射程(2格) → 射击
                return Some(Action::EndTurn);
            } else {
                // 太远 → 接近并保持射程
                return Some(approach_archer(unit, local_idx, gs, target.q, target.r, cfg));
            }
        }
        // 没敌人 → 向敌城推进
        return Some(move_to(unit, local_idx, gs, opp_city.q, opp_city.r, false, cfg));
    }

    // ── 守城: 敌人在我城格上 ──────────────────────
    for (dq, dr) in HEX_DIRS.iter() {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        if nq == my_city.q && nr == my_city.r {
            let enemy_on_city = gs.units.iter().any(|eu| {
                eu.alive && eu.player_id != pid && eu.q == nq && eu.r == nr
            });
            if enemy_on_city {
                return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
            }
        }
    }

    // ── 拦截接近城市的敌人 ────────────────────────
    for eu in &gs.units {
        if eu.alive && eu.player_id != pid {
            let d = hex_distance(eu.q, eu.r, my_city.q, my_city.r);
            if d <= 2 {
                return Some(move_to(unit, local_idx, gs, eu.q, eu.r, false, cfg));
            }
        }
    }

    // ── 攻击邻格敌人 ──────────────────────────────
    for (dq, dr) in HEX_DIRS.iter() {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let enemy_adjacent = gs.units.iter().any(|eu| {
            eu.alive && eu.player_id != pid && eu.q == nq && eu.r == nr
        });
        if enemy_adjacent {
            return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
        }
    }

    // ── 防御策略: 留守城市附近 ────────────────────
    if strategy == Strategy::Defensive || strategy == Strategy::DefensiveConstruction {
        let dist_to_my = hex_distance(unit.q, unit.r, my_city.q, my_city.r);
        if dist_to_my > 3 {
            return Some(move_to(unit, local_idx, gs, my_city.q, my_city.r, true, cfg));
        }
    }

    // ── 部队协调: wave ready → 全军冲城 ──────────
    if wave_ready {
        return Some(move_to(unit, local_idx, gs, opp_city.q, opp_city.r, false, cfg));
    }

    // ── rally point 聚兵 ──────────────────────────
    let (rpx, rpy) = rally_point;
    let dist_to_rally = hex_distance(unit.q, unit.r, rpx, rpy);
    if dist_to_rally <= 2 {
        let friends_nearby = gs.units.iter().filter(|other| {
            other.alive && other.player_id == pid
                && other.q != unit.q && other.r != unit.r  // 不是自己
                && hex_distance(other.q, other.r, unit.q, unit.r) <= 2
        }).count();
        if friends_nearby >= 2 {
            return Some(Action::EndTurn);  // 等人聚齐
        }
    }

    // ── 默认: 向敌城推进 ─────────────────────────
    Some(move_to(unit, local_idx, gs, opp_city.q, opp_city.r, false, cfg))
}

// ═══════════════════════════════════════════════════════
// 工人决策
// ═══════════════════════════════════════════════════════

fn greedy_worker(
    unit: &Unit, local_idx: usize, gs: &GameState, pid: u8,
    strategy: Strategy, cfg: &GreedyConfig,
) -> Option<Action> {
    let tile = gs.grid.get(unit.q, unit.r);

    // 统计已有设施类型
    let mut type_counts: HashMap<String, u32> = HashMap::new();
    type_counts.insert("farm".to_string(), 0);
    type_counts.insert("lumbermill".to_string(), 0);
    type_counts.insert("mine".to_string(), 0);
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if let Some(f) = &gs.grid.get(q, r).facility {
                if f.player_id == pid {
                    let key = f.output_resource().to_string();
                    // 把 resource name 转成 facility type name
                    let ft = match key.as_str() {
                        "food" => "farm",
                        "wood" => "lumbermill",
                        "gold" => "mine",
                        _ => continue,
                    };
                    *type_counts.entry(ft.to_string()).or_insert(0) += 1;
                }
            }
        }
    }

    let has_all = type_counts.values().all(|&c| c >= 1);
    let total_facs: u32 = type_counts.values().sum();
    let c5_done = gs.techs[pid as usize].completed.iter().any(|c| c == "C5");
    let need_expansion = c5_done || matches!(strategy, Strategy::Construction | Strategy::DefensiveConstruction);

    // 已有己方设施
    if let Some(f) = &tile.facility {
        if f.player_id == pid {
            if need_expansion || !has_all {
                // 离开找新资源格
                if let Some(target) = nearest_missing_type(unit, gs, pid, &type_counts) {
                    return Some(move_to(unit, local_idx, gs, target.0, target.1, false, cfg));
                }
            }
            return Some(Action::Produce { unit_idx: local_idx });
        }
    }

    // 可建 + 没有设施
    let buildable = terrain_buildable(tile.terrain);
    if let Some(ft) = buildable {
        if type_counts.get(ft).copied().unwrap_or(0) == 0 {
            return Some(Action::Build { unit_idx: local_idx });  // 缺这种类型 → 建
        }
        if has_all && total_facs < 6 {
            return Some(Action::Build { unit_idx: local_idx });  // 扩张
        }
        let avg = total_facs as f64 / 3.0;
        if (*type_counts.get(ft).unwrap_or(&0) as f64) < avg {
            return Some(Action::Build { unit_idx: local_idx });  // 此类不足
        }
        // 不缺 → 找缺的
        if let Some(target) = nearest_missing_type(unit, gs, pid, &type_counts) {
            return Some(move_to(unit, local_idx, gs, target.0, target.1, false, cfg));
        }
    }

    // 找最近的可用建造点
    if let Some(target) = nearest_buildable(unit, gs, pid) {
        return Some(move_to(unit, local_idx, gs, target.0, target.1, false, cfg));
    }

    // 有设施就生产
    if tile.facility.is_some() {
        return Some(Action::Produce { unit_idx: local_idx });
    }
    Some(Action::EndTurn)
}

/// 哪种地形可以建什么设施?
fn terrain_buildable(t: Terrain) -> Option<&'static str> {
    match t {
        Terrain::Plain => Some("farm"),
        Terrain::Forest => Some("lumbermill"),
        Terrain::Mountain => Some("mine"),
        _ => None,
    }
}

/// 找最近缺失设施类型的可建格
fn nearest_missing_type(
    unit: &Unit, gs: &GameState, pid: u8,
    type_counts: &HashMap<String, u32>,
) -> Option<(i32, i32)> {
    let mut best: Option<(i32, i32)> = None;
    let mut best_d = 255u8;
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            let b = terrain_buildable(gs.grid.get(q, r).terrain);
            if b.is_none() { continue; }
            let ft = b.unwrap();
            if gs.grid.get(q, r).facility.is_some() { continue; }
            // 只找缺失的类型
            if type_counts.get(ft).copied().unwrap_or(0) > 0
                && type_counts.values().all(|&c| c >= 1)
            {
                continue;  // 不缺这种类型
            }
            let d = hex_distance(unit.q, unit.r, q, r);
            if d < best_d {
                best_d = d;
                best = Some((q, r));
            }
        }
    }
    best
}

/// 找最近可建格(不考虑类型)
fn nearest_buildable(unit: &Unit, gs: &GameState, _pid: u8) -> Option<(i32, i32)> {
    let mut best: Option<(i32, i32)> = None;
    let mut best_d = 255u8;
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if terrain_buildable(gs.grid.get(q, r).terrain).is_none() { continue; }
            if gs.grid.get(q, r).facility.is_some() { continue; }
            let d = hex_distance(unit.q, unit.r, q, r);
            if d < best_d {
                best_d = d;
                best = Some((q, r));
            }
        }
    }
    best
}

// ═══════════════════════════════════════════════════════
// 研究决策 (v3: strategy-aware)
// ═══════════════════════════════════════════════════════

fn do_research(gs: &GameState, pid: u8, strategy: Strategy, actions: &mut Vec<Action>) {
    let tech = &gs.techs[pid as usize];
    let econ = &gs.economies[pid as usize];
    let avail = tech.available_to_research();

    // C5 优先(如果可研究且建设策略或回合>20)
    let in_construction = matches!(strategy, Strategy::Construction | Strategy::DefensiveConstruction);
    if avail.contains(&"C5".to_string())
        && (in_construction || gs.turn > 20)
    {
        if let Some(cost) = TechManager::tech_cost("C5") {
            if econ.can_afford(cost) {
                actions.push(Action::Research { tech_id: "C5".to_string() });
                return;
            }
        }
    }

    let order: &[&str] = match strategy {
        Strategy::Aggressive => &["M1", "M2", "M3", "M4", "C1", "E1", "E2", "E3", "E4", "C2", "C3", "C4", "C5"],
        Strategy::Defensive | Strategy::DefensiveConstruction => &["E1", "E2", "E3", "E4", "C1", "M1", "M2", "M3", "M4", "C2", "C3", "C4", "C5"],
        Strategy::Construction => &["C1", "C2", "C3", "C4", "C5", "E1", "E2", "E3", "E4", "M1", "M2", "M3", "M4"],
        Strategy::Balanced => {
            // 中后期偏向 C 线
            if gs.turn > 15 {
                for ct in &["C2", "C3", "C4", "C5", "C1"] {
                    if avail.contains(&ct.to_string()) {
                        if let Some(cost) = TechManager::tech_cost(ct) {
                            if econ.can_afford(cost) {
                                actions.push(Action::Research { tech_id: ct.to_string() });
                                return;
                            }
                        }
                    }
                }
            }
            &["M1", "E1", "M2", "E2", "M3", "E3", "C1", "M4", "E4", "C2", "C3", "C4", "C5"]
        }
    };

    for t in order {
        if avail.contains(&t.to_string()) {
            if let Some(cost) = TechManager::tech_cost(t) {
                if econ.can_afford(cost) {
                    actions.push(Action::Research { tech_id: t.to_string() });
                    return;
                }
            }
        }
    }
}

// ═══════════════════════════════════════════════════════
// 生产决策 (v4: 自适应克制 + strategy-aware)
// ═══════════════════════════════════════════════════════

fn do_production(
    gs: &GameState, pid: u8, strategy: Strategy,
    counter: &Option<String>, a: &StrategicAssessment,
    actions: &mut Vec<Action>,
) {
    let econ = &gs.economies[pid as usize];
    let size = MAP_W as i32;

    let my_combat: Vec<&Unit> = gs.units.iter()
        .filter(|u| u.player_id == pid && u.alive && u.unit_type != UnitType::Worker)
        .collect();
    let n_arc = my_combat.iter().filter(|u| u.unit_type == UnitType::Archer).count();
    let n_inf = my_combat.iter().filter(|u| u.unit_type == UnitType::Infantry).count();
    let n_cav = my_combat.iter().filter(|u| u.unit_type == UnitType::Cavalry).count();
    let n_total = my_combat.len();

    let my_city = &gs.cities[pid as usize];

    // 紧急防守: 敌人在城市附近 → 造弓手
    let enemy_near = gs.units.iter().any(|eu| {
        eu.alive && eu.player_id != pid
            && eu.unit_type != UnitType::Worker
            && hex_distance(eu.q, eu.r, my_city.q, my_city.r) <= 3
    });
    if enemy_near && econ.wood >= 5 {
        if econ.can_afford((3, 3, 0)) {
            // archer cost: 3/3/0
            actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
            return;
        }
    }

    // 弓手比例维持 ~30%
    if n_total > 2 && econ.wood >= 5 {
        let archer_ratio = n_arc as f64 / n_total as f64;
        if archer_ratio < 0.3 && econ.can_afford((3, 3, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
            return;
        }
    }

    // 骑兵比例维持 ~30%
    if n_total > 2 && econ.gold >= 6 {
        let cav_ratio = n_cav as f64 / n_total as f64;
        if cav_ratio < 0.3 && econ.can_afford((5, 0, 3)) {
            actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
            return;
        }
    }

    // 自适应克制
    if let Some(ct) = counter {
        let cost = match ct.as_str() {
            "cavalry" => (5, 0, 3),
            "infantry" => (5, 0, 0),
            _ => (5, 0, 0),
        };
        if econ.can_afford(cost) && econ.food > 8 {
            actions.push(Action::ProduceUnit { unit_type: ct.clone() });
            return;
        }
    }

    // 策略模式生产
    match strategy {
        Strategy::Aggressive => {
            for ut in &["cavalry", "archer", "infantry"] {
                if try_produce(econ, ut, actions) { return; }
            }
        }
        Strategy::Defensive | Strategy::DefensiveConstruction => {
            for ut in &["infantry", "archer", "cavalry"] {
                if try_produce(econ, ut, actions) { return; }
            }
        }
        Strategy::Construction => {
            // 建设策略: 维持防御+可能造工人
            let n_workers = gs.units.iter()
                .filter(|u| u.player_id == pid && u.alive && u.unit_type == UnitType::Worker)
                .count();
            if n_workers < 4 && econ.food >= 15 && n_total >= 3 {
                if econ.can_afford((3, 0, 0)) {
                    actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
                    return;
                }
            }
            if econ.gold >= 10 && n_cav < n_inf && econ.can_afford((5, 0, 3)) {
                actions.push(Action::ProduceUnit { unit_type: "cavalry".to_string() });
                return;
            }
            if econ.wood >= 8 && n_arc < n_inf && econ.can_afford((3, 3, 0)) {
                actions.push(Action::ProduceUnit { unit_type: "archer".to_string() });
                return;
            }
            if try_produce(econ, "infantry", actions) { return; }
        }
        Strategy::Balanced => {
            // Balanced: 可能造工人 + 多样兵种
            let n_workers = gs.units.iter()
                .filter(|u| u.player_id == pid && u.alive && u.unit_type == UnitType::Worker)
                .count();
            let n_combat = my_combat.len();
            if n_workers < 4 && econ.food >= 15 && n_combat >= 3 {
                if econ.can_afford((3, 0, 0)) {
                    actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
                    return;
                }
            }
            for ut in &["cavalry", "archer", "infantry"] {
                if try_produce(econ, ut, actions) { return; }
            }
        }
    }
}

fn try_produce(econ: &crate::economy::Economy, ut: &str, actions: &mut Vec<Action>) -> bool {
    let cost = match ut {
        "infantry" => (5, 0, 0),
        "cavalry" => (5, 0, 3),
        "archer" => (3, 3, 0),
        "scout" => (3, 0, 0),
        _ => return false,
    };
    if econ.can_afford(cost) {
        actions.push(Action::ProduceUnit { unit_type: ut.to_string() });
        true
    } else {
        false
    }
}

// ═══════════════════════════════════════════════════════
// 移动辅助函数
// ═══════════════════════════════════════════════════════

/// 向目标移动一步(带地形偏好)。
/// 六边重校准核心——使用参数化 DISTANCE_WEIGHT 和 TERRAIN_WEIGHT。
fn move_to(
    unit: &Unit, local_idx: usize, gs: &GameState,
    tx: i32, ty: i32, prefer_defense: bool, cfg: &GreedyConfig,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() {
        return Action::EndTurn;
    }

    let mut best_moves: Vec<(i32, i32)> = Vec::new();
    let mut best_score = f64::NEG_INFINITY;

    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tx, ty) as f64;
        let terrain = gs.grid.get(nq, nr).terrain;
        let def_bonus = terrain.def_bonus() as f64;

        // 六边重校准核心公式 — 权重由 cfg 控制(参数扫描用)
        let mut score = -d * cfg.distance_weight;
        score += def_bonus * cfg.terrain_weight;
        if prefer_defense {
            score += def_bonus * cfg.retreat_terrain_bonus;
        }
        // 不可通行的惩罚
        if terrain == Terrain::Water {
            score = f64::NEG_INFINITY;
        }
        if terrain == Terrain::Mountain && !unit.can_enter_mountain {
            score = f64::NEG_INFINITY;
        }

        if score > best_score {
            best_score = score;
            best_moves = vec![(*dq, *dr)];
        } else if (score - best_score).abs() < 0.001 {
            best_moves.push((*dq, *dr));
        }
    }

    if best_moves.is_empty() {
        return Action::EndTurn;
    }

    // 随机选一个最优方向
    Action::Move {
        unit_idx: local_idx,
        dq: best_moves[0].0,
        dr: best_moves[0].1,
    }
}

/// 远离敌人
fn retreat_from(
    unit: &Unit, local_idx: usize, gs: &GameState,
    ex: i32, ey: i32, _cfg: &GreedyConfig,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() {
        return Action::EndTurn;
    }

    let mut best: Vec<(i32, i32)> = Vec::new();
    let mut best_d = 0u8;

    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, ex, ey);
        if d > best_d {
            best_d = d;
            best = vec![(*dq, *dr)];
        } else if d == best_d {
            best.push((*dq, *dr));
        }
    }

    if best.is_empty() {
        return Action::EndTurn;
    }
    Action::Move { unit_idx: local_idx, dq: best[0].0, dr: best[0].1 }
}

/// 弓手接近目标并保持最佳射程(2格)
fn approach_archer(
    unit: &Unit, local_idx: usize, gs: &GameState,
    tx: i32, ty: i32, cfg: &GreedyConfig,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() {
        return Action::EndTurn;
    }

    let mut best_moves: Vec<(i32, i32)> = Vec::new();
    let mut best_score = f64::NEG_INFINITY;

    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tx, ty) as f64;
        // 理想距离 = 2(弓手射程)
        let mut score = -(d - 2.0).abs() * ARCHER_DIST_WEIGHT;
        let t = gs.grid.get(nq, nr).terrain;
        let db = t.def_bonus() as f64;
        score += db * cfg.terrain_weight;
        score += db * ARCHER_HIGH_GROUND;

        if score > best_score {
            best_score = score;
            best_moves = vec![(*dq, *dr)];
        } else if (score - best_score).abs() < 0.01 {
            best_moves.push((*dq, *dr));
        }
    }

    if best_moves.is_empty() {
        return Action::EndTurn;
    }
    Action::Move { unit_idx: local_idx, dq: best_moves[0].0, dr: best_moves[0].1 }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::init_game;
    use crate::ai::random::RandomAgent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    #[test]
    fn test_Greedy_vs_Random_单局可跑完() {
        let mut gs = init_game(42, "balanced");
        let agent = GreedyAgent::new();
        let random = RandomAgent;
        let mut rng0 = ChaCha12Rng::seed_from_u64(42);
        let mut rng1 = ChaCha12Rng::seed_from_u64(99);

        // 跑 80 回合或直到有人赢
        while gs.winner.is_none() && gs.turn < crate::constants::MAX_TURNS {
            let a0 = agent.decide(&gs, 0, &mut rng0);
            let a1 = random.decide(&gs, 1, &mut rng1);
            crate::game::step_game(&mut gs, &a0, &a1);
        }
        // 只要不 panic 就算通过
        assert!(gs.winner.is_some() || gs.turn >= crate::constants::MAX_TURNS);
    }

    /// 参数扫描: Greedy vs Random, 不同 distance_weight + terrain_weight 组合
    /// 运行: cargo test scan_greedy -- --nocapture --ignored
    #[test]
    #[ignore]  // 默认跳过(耗时), 手动 --ignored 运行
    fn scan_greedy_params() {
        let d_weights = [1.0, 2.0, 3.0, 5.0];
        let t_weights = [0.05, 0.10, 0.15];
        let games_per = 50u64;

        println!("\n{:>5} {:>5} {:>8} {:>8} {:>8}",
                 "DW", "TW", "WR%", "Conq%", "Cons%");
        println!("{}", "-".repeat(42));

        for &dw in &d_weights {
            for &tw in &t_weights {
                let cfg = GreedyConfig {
                    distance_weight: dw,
                    terrain_weight: tw,
                    retreat_terrain_bonus: 0.20,
                };
                let agent = GreedyAgent::with_config(cfg);
                let random = RandomAgent;

                let mut wins = 0u32;
                let mut conquests = 0u32;
                let mut constructions = 0u32;

                for i in 0..games_per {
                    let mut gs = init_game(42000 + i * 100, "balanced");
                    let mut rng0 = ChaCha12Rng::seed_from_u64(42000 + i * 100);
                    let mut rng1 = ChaCha12Rng::seed_from_u64(42000 + i * 200);

                    while gs.winner.is_none() && gs.turn < crate::constants::MAX_TURNS {
                        let a0 = agent.decide(&gs, 0, &mut rng0);
                        let a1 = random.decide(&gs, 1, &mut rng1);
                        crate::game::step_game(&mut gs, &a0, &a1);
                    }

                    if gs.winner == Some(0) { wins += 1; }
                    match &gs.victory_type {
                        Some(crate::game::VictoryType::Conquest) => conquests += 1,
                        Some(crate::game::VictoryType::Construction) => constructions += 1,
                        _ => {}
                    }
                }

                let wr = wins as f64 / games_per as f64 * 100.0;
                let cq = conquests as f64 / games_per as f64 * 100.0;
                let cs = constructions as f64 / games_per as f64 * 100.0;
                println!("{:5.1} {:5.2} {:7.1}% {:7.1}% {:7.1}%",
                         dw, tw, wr, cq, cs);
            }
        }
    }

    /// 集成验证: 3×3 矩阵 (Greedy/Evo/Random, 30 seeds paired)
    /// cargo test integration_matrix -- --nocapture --ignored
    #[test]
    #[ignore]
    fn integration_matrix() {
        use crate::ai::evo::EvoAgent;
        let games_per = 30u64;
        let agents: Vec<(&str, Box<dyn Agent>)> = vec![
            ("Greedy", Box::new(GreedyAgent::new())),
            ("Evo", Box::new(EvoAgent::new())),
            ("Random", Box::new(RandomAgent)),
        ];

        println!("\n{:>8} vs {:<8} {:>6} {:>6} {:>6} {:>6}",
                 "P0", "P1", "WR%", "Cq%", "Cs%", "Tb%");
        println!("{}", "-".repeat(45));

        let mut all_results: Vec<(String, String, f64, f64, f64, f64)> = Vec::new();

        for (name0, agent0) in &agents {
            for (name1, agent1) in &agents {
                let mut wins = 0u32;
                let mut cq = 0u32;
                let mut cs = 0u32;
                let mut tb = 0u32;

                for i in 0..games_per {
                    let seed = 50000 + i * 100;
                    let mut gs = init_game(seed, "balanced");
                    let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
                    let mut rng1 = ChaCha12Rng::seed_from_u64(seed + 1);

                    while gs.winner.is_none() && gs.turn < crate::constants::MAX_TURNS {
                        let a0 = agent0.decide(&gs, 0, &mut rng0);
                        let a1 = agent1.decide(&gs, 1, &mut rng1);
                        crate::game::step_game(&mut gs, &a0, &a1);
                    }
                    if gs.winner == Some(0) { wins += 1; }
                    match &gs.victory_type {
                        Some(crate::game::VictoryType::Conquest) => cq += 1,
                        Some(crate::game::VictoryType::Construction) => cs += 1,
                        _ => tb += 1,
                    }
                }
                let wr = wins as f64 / games_per as f64 * 100.0;
                let cqp = cq as f64 / games_per as f64 * 100.0;
                let csp = cs as f64 / games_per as f64 * 100.0;
                let tbp = tb as f64 / games_per as f64 * 100.0;
                println!("{:>8} vs {:<8} {:5.1}% {:5.1}% {:5.1}% {:5.1}%",
                         name0, name1, wr, cqp, csp, tbp);
                all_results.push((name0.to_string(), name1.to_string(), wr, cqp, csp, tbp));
            }
        }

        // 计算跨对手平均胜率
        println!();
        for ai_name in &["Random", "Greedy", "Evo"] {
            let mut wr_sum = 0.0;
            let mut n = 0;
            for (a0, a1, wr, _, _, _) in &all_results {
                if a0 == *ai_name && a1 != *ai_name {
                    wr_sum += wr; n += 1;
                } else if a1 == *ai_name && a0 != *ai_name {
                    wr_sum += 100.0 - wr; n += 1;
                }
            }
            if n > 0 {
                println!("{} avg vs others: {:.1}%", ai_name, wr_sum / n as f64);
            }
        }
    }

    #[test]
    fn test_Greedy镜像_单局可跑完() {
        let mut gs = init_game(777, "balanced");
        let agent = GreedyAgent::new();
        let mut rng0 = ChaCha12Rng::seed_from_u64(100);
        let mut rng1 = ChaCha12Rng::seed_from_u64(200);

        for _ in 0..10 {
            if gs.winner.is_some() { break; }
            let a0 = agent.decide(&gs, 0, &mut rng0);
            let a1 = agent.decide(&gs, 1, &mut rng1);
            crate::game::step_game(&mut gs, &a0, &a1);
        }
        // 10 回合内不 panic
        assert!(gs.turn >= 10 || gs.winner.is_some());
    }
}
