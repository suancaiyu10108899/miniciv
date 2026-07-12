// Evo AI — Phase 8
// 翻译自 prototype/ai_evo.py (461行) + prototype_hex/ai_evo_hex.py
// 15 权重参数化决策, 进化算法优化。
// 权重从 JSON 加载 (evo_hex_weights.json 格式)。
// 移动启发式使用可配置权重(复用 Phase 7 的参数扫描结果)。

use crate::game::GameState;
use crate::unit::{Unit, UnitType};
use crate::map::Terrain;
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, hex_distance, HEX_DIRS};
use crate::constants::{MAP_W, MAP_H};
use crate::game::primary_enemy;
use crate::tech::TechManager;
use rand::RngCore;
use std::collections::HashMap;

use super::greedy::GreedyConfig;

// ─── 默认权重定义 ──────────────────────────────────
// 每个权重: (默认值, 最小值, 最大值, 描述)

fn default_weights() -> HashMap<String, f64> {
    let mut w = HashMap::new();
    w.insert("attack_adjacent".to_string(), 1.0);
    w.insert("rush_enemy_city".to_string(), 1.0);
    w.insert("defend_own_city".to_string(), 1.0);
    w.insert("intercept_near_city".to_string(), 0.8);
    w.insert("retreat_hp_threshold".to_string(), 0.3);
    w.insert("terrain_def_weight".to_string(), 0.15);
    w.insert("retreat_terrain_bonus".to_string(), 0.3);
    w.insert("archer_keep_distance".to_string(), 1.0);
    w.insert("archer_prefer_high".to_string(), 0.1);
    w.insert("build_efficiency".to_string(), 1.0);
    w.insert("resource_variety".to_string(), 1.0);
    w.insert("research_priority".to_string(), 1.0);
    w.insert("military_tech_bias".to_string(), 0.5);
    w.insert("cavalry_production".to_string(), 1.0);
    w.insert("archer_production".to_string(), 1.0);
    w
}

// ─── Evo Agent ──────────────────────────────────────

pub struct EvoAgent {
    pub weights: HashMap<String, f64>,
    pub config: GreedyConfig,  // 复用 Greedy 的移动校准参数
}

impl EvoAgent {
    pub fn new() -> Self {
        Self { weights: default_weights(), config: GreedyConfig::default() }
    }

    /// 从 JSON 加载权重 (Python evo_hex_weights.json 格式)
    pub fn from_json(json_str: &str) -> Result<Self, String> {
        let data: serde_json::Value = serde_json::from_str(json_str)
            .map_err(|e| format!("JSON parse error: {}", e))?;
        let wmap = data.get("weights")
            .or_else(|| data.as_object().map(|_| &data))
            .ok_or("missing 'weights' key")?;

        let mut weights = default_weights();
        if let Some(obj) = wmap.as_object() {
            for (k, v) in obj {
                if let Some(num) = v.as_f64() {
                    weights.insert(k.clone(), num);
                }
            }
        }
        Ok(Self { weights, config: GreedyConfig::default() })
    }
}

impl Agent for EvoAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let w = &self.weights;
        let mut actions = Vec::new();

        let player_units: Vec<(usize, &Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        let opp_city = &gs.cities[opp as usize];
        let my_city = &gs.cities[pid as usize];
        let econ = &gs.economies[pid as usize];
        let tech = &gs.techs[pid as usize];

        // 战术顺序: 弓手 → 近战 → 侦察兵
        let mut archers: Vec<(usize, usize)> = Vec::new();
        let mut fighters: Vec<(usize, usize)> = Vec::new();
        for (global_idx, unit) in &player_units {
            let local_idx = player_units.iter().position(|(i, _)| *i == *global_idx).unwrap();
            match unit.unit_type {
                UnitType::Archer => archers.push((*global_idx, local_idx)),
                UnitType::Worker => {},
                _ => fighters.push((*global_idx, local_idx)),
            }
        }

        for (global_idx, local_idx) in archers.iter().chain(fighters.iter()) {
            let unit = &gs.units[*global_idx];
            if let Some(act) = evo_combat(
                unit, *local_idx, gs, pid, opp_city, my_city, w, &self.config, rng,
            ) {
                actions.push(act);
            }
        }

        // 工人
        for (global_idx, unit) in &player_units {
            if unit.unit_type == UnitType::Worker {
                let local_idx = player_units.iter().position(|(i, _)| *i == *global_idx).unwrap();
                if let Some(act) = evo_worker(unit, local_idx, gs, pid, w, &self.config, rng) {
                    actions.push(act);
                }
            }
        }

        // 研究
        if tech.researching.is_none() {
            let avail = tech.available_to_research();
            if !avail.is_empty() {
                let m_techs: Vec<_> = avail.iter().filter(|t| t.starts_with('M')).collect();
                let e_techs: Vec<_> = avail.iter().filter(|t| t.starts_with('E')).collect();
                // 按 military_tech_bias 选线
                let preferred = if !m_techs.is_empty() && !e_techs.is_empty() {
                    let roll = rng.next_u32() as f64 / u32::MAX as f64;
                    if roll < *w.get("military_tech_bias").unwrap_or(&0.5) {
                        m_techs
                    } else {
                        e_techs
                    }
                } else if !m_techs.is_empty() { m_techs }
                else if !e_techs.is_empty() { e_techs }
                else { avail.iter().collect() };

                for t in &preferred {
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        // 生产
        let prod_order = {
            let cav_w = *w.get("cavalry_production").unwrap_or(&1.0);
            let arc_w = *w.get("archer_production").unwrap_or(&1.0);
            let mut o: Vec<(&str, f64)> = vec![
                ("cavalry", cav_w), ("archer", arc_w), ("infantry", 1.0)
            ];
            o.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            o
        };
        for (ut, _) in &prod_order {
            let cost = match *ut {
                "cavalry" => (5, 0, 3),
                "archer" => (3, 3, 0),
                _ => (5, 0, 0),
            };
            if econ.can_afford(cost) {
                actions.push(Action::ProduceUnit { unit_type: ut.to_string() });
                break;
            }
        }

        actions
    }

    fn name(&self) -> &str { "Evo" }
}

// ═══════════════════════════════════════════════════════
// 战斗单位决策
// ═══════════════════════════════════════════════════════

fn evo_combat(
    unit: &Unit, local_idx: usize, gs: &GameState, pid: u8,
    opp_city: &crate::unit::City, my_city: &crate::unit::City,
    w: &HashMap<String, f64>, cfg: &GreedyConfig, rng: &mut dyn RngCore,
) -> Option<Action> {
    let max_hp = match unit.unit_type {
        UnitType::Infantry => 100, UnitType::Cavalry => 80,
        UnitType::Archer => 60, _ => 40,
    };
    let hp_pct = unit.hp as f64 / max_hp as f64;
    let retreat_threshold = *w.get("retreat_hp_threshold").unwrap_or(&0.3);

    // 残血撤退
    if hp_pct < retreat_threshold {
        let near_enemy = gs.units.iter().any(|eu| {
            eu.alive && eu.player_id != pid
                && hex_distance(eu.q, eu.r, unit.q, unit.r) <= 2
        });
        if near_enemy {
            return Some(move_to_evo(unit, local_idx, gs, my_city.q, my_city.r,
                *w.get("terrain_def_weight").unwrap_or(&0.15),
                *w.get("retreat_terrain_bonus").unwrap_or(&0.3),
                cfg));
        }
    }

    // 弓手
    if unit.ranged {
        let mut nearest_dist = 255u8;
        let mut nearest: Option<&Unit> = None;
        for eu in &gs.units {
            if eu.alive && eu.player_id != pid {
                let d = hex_distance(eu.q, eu.r, unit.q, unit.r);
                if d < nearest_dist { nearest_dist = d; nearest = Some(eu); }
            }
        }
        if let Some(target) = nearest {
            if nearest_dist <= 2 {
                if nearest_dist == 1 {
                    return Some(retreat_from_evo(unit, local_idx, gs, target.q, target.r));
                }
                return Some(Action::EndTurn);
            }
            return Some(approach_archer_evo(unit, local_idx, gs, target.q, target.r,
                *w.get("archer_keep_distance").unwrap_or(&1.0),
                *w.get("archer_prefer_high").unwrap_or(&0.1),
                *w.get("terrain_def_weight").unwrap_or(&0.15),
                cfg));
        }
        return Some(move_to_evo(unit, local_idx, gs, opp_city.q, opp_city.r,
            *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
    }

    // 守城
    for (dq, dr) in HEX_DIRS.iter() {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        if nq == my_city.q && nr == my_city.r {
            let enemy = gs.units.iter().any(|eu| {
                eu.alive && eu.player_id != pid && eu.q == nq && eu.r == nr
            });
            if enemy {
                return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
            }
        }
    }

    // 拦截接近城市的敌人(权重参数化)
    let intercept_w = *w.get("intercept_near_city").unwrap_or(&0.8);
    if intercept_w > 0.0 {
        for eu in &gs.units {
            if eu.alive && eu.player_id != pid {
                let d = hex_distance(eu.q, eu.r, my_city.q, my_city.r);
                if d <= 2 {
                    if rng_f(rng) <intercept_w / 5.0 {
                        return Some(move_to_evo(unit, local_idx, gs, eu.q, eu.r,
                            *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
                    }
                    break;
                }
            }
        }
    }

    // 攻击邻格敌人
    let attack_w = *w.get("attack_adjacent").unwrap_or(&1.0);
    if rng_f(rng) <attack_w / 5.0 {
        for (dq, dr) in HEX_DIRS.iter() {
            let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
            let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
            let enemy = gs.units.iter().any(|eu| {
                eu.alive && eu.player_id != pid && eu.q == nq && eu.r == nr
            });
            if enemy {
                return Some(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
            }
        }
    }

    // 防守
    let defend_w = *w.get("defend_own_city").unwrap_or(&1.0);
    if rng_f(rng) <defend_w / 5.0 {
        if hex_distance(unit.q, unit.r, my_city.q, my_city.r) > 3 {
            return Some(move_to_evo(unit, local_idx, gs, my_city.q, my_city.r,
                *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
        }
    }

    // 向敌城推进
    let rush_w = *w.get("rush_enemy_city").unwrap_or(&1.0);
    if rng_f(rng) <rush_w / 5.0 {
        return Some(move_to_evo(unit, local_idx, gs, opp_city.q, opp_city.r,
            *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
    }

    // 默认: 向敌城推进
    Some(move_to_evo(unit, local_idx, gs, opp_city.q, opp_city.r,
        *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg))
}

/// 从 RNG 生成 [0,1) 的随机浮点数
fn rng_f(rng: &mut dyn RngCore) -> f64 {
    rng.next_u32() as f64 / u32::MAX as f64
}

// ═══════════════════════════════════════════════════════
// 工人决策
// ═══════════════════════════════════════════════════════

fn evo_worker(
    unit: &Unit, local_idx: usize, gs: &GameState, pid: u8,
    w: &HashMap<String, f64>, cfg: &GreedyConfig, rng: &mut dyn RngCore,
) -> Option<Action> {
    let tile = gs.grid.get(unit.q, unit.r);

    // 已有设施 → 生产或离开找缺失类型
    if let Some(f) = &tile.facility {
        if f.player_id == pid {
            let all_types = has_all_types(gs, pid);
            if all_types {
                return Some(Action::Produce { unit_idx: local_idx });
            }
            // 不全 → 找缺失类型
            let variety_w = *w.get("resource_variety").unwrap_or(&1.0);
            if rng_f(rng) <variety_w / 3.0 {
                if let Some(target) = find_missing_resource(unit, gs, pid) {
                    return Some(move_to_evo(unit, local_idx, gs, target.0, target.1,
                        *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
                }
            }
            return Some(Action::Produce { unit_idx: local_idx });
        }
    }

    // 可建 + 缺失该类型 → 建造
    if let Some(ft) = terrain_buildable_evo(tile.terrain) {
        let missing = is_missing_type(gs, pid, ft);
        if missing {
            let build_w = *w.get("build_efficiency").unwrap_or(&1.0);
            if rng_f(rng) <build_w / 3.0 {
                return Some(Action::Build { unit_idx: local_idx });
            }
        }
    }

    // 找缺失资源
    if let Some(target) = find_missing_resource(unit, gs, pid) {
        return Some(move_to_evo(unit, local_idx, gs, target.0, target.1,
            *w.get("terrain_def_weight").unwrap_or(&0.15), 0.0, cfg));
    }

    if tile.facility.is_some() {
        return Some(Action::Produce { unit_idx: local_idx });
    }
    Some(Action::EndTurn)
}

fn terrain_buildable_evo(t: Terrain) -> Option<&'static str> {
    match t {
        Terrain::Plain => Some("farm"),
        Terrain::Forest => Some("lumbermill"),
        Terrain::Mountain => Some("mine"),
        _ => None,
    }
}

fn has_all_types(gs: &GameState, pid: u8) -> bool {
    let (f, l, m) = count_facility_types(gs, pid);
    f > 0 && l > 0 && m > 0
}

fn count_facility_types(gs: &GameState, pid: u8) -> (u32, u32, u32) {
    let (mut f, mut l, mut m) = (0, 0, 0);
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if let Some(fac) = &gs.grid.get(q, r).facility {
                if fac.player_id == pid {
                    match fac.facility_type {
                        crate::unit::FacilityType::Farm => f += 1,
                        crate::unit::FacilityType::Lumbermill => l += 1,
                        crate::unit::FacilityType::Mine => m += 1,
                    }
                }
            }
        }
    }
    (f, l, m)
}

fn is_missing_type(gs: &GameState, pid: u8, ft: &str) -> bool {
    let (f, l, m) = count_facility_types(gs, pid);
    match ft {
        "farm" => f == 0,
        "lumbermill" => l == 0,
        "mine" => m == 0,
        _ => false,
    }
}

fn find_missing_resource(unit: &Unit, gs: &GameState, pid: u8) -> Option<(i32, i32)> {
    let (has_f, has_l, has_m) = count_facility_types(gs, pid);
    let has_f = has_f > 0;
    let has_l = has_l > 0;
    let has_m = has_m > 0;

    let mut best: Option<(i32, i32)> = None;
    let mut best_d = 255u8;
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            let b = terrain_buildable_evo(gs.grid.get(q, r).terrain);
            if b.is_none() || gs.grid.get(q, r).facility.is_some() { continue; }
            let needed = match b.unwrap() {
                "farm" => !has_f, "lumbermill" => !has_l, "mine" => !has_m,
                _ => false,
            };
            if !needed { continue; }
            let d = hex_distance(unit.q, unit.r, q, r);
            if d < best_d { best_d = d; best = Some((q, r)); }
        }
    }
    best
}

// ═══════════════════════════════════════════════════════
// 移动辅助 (Evo专用, 参数化权重)
// ═══════════════════════════════════════════════════════

fn move_to_evo(
    unit: &Unit, local_idx: usize, gs: &GameState,
    tx: i32, ty: i32, terrain_weight: f64, retreat_bonus: f64, cfg: &GreedyConfig,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() { return Action::EndTurn; }

    let mut best: Vec<(i32, i32)> = Vec::new();
    let mut best_score = f64::NEG_INFINITY;

    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tx, ty) as f64;
        let t = gs.grid.get(nq, nr).terrain;
        let db = t.def_bonus() as f64;
        let mut score = -d * cfg.distance_weight;
        score += db * terrain_weight;
        score += db * retreat_bonus;
        if t == Terrain::Water { score = f64::NEG_INFINITY; }
        if t == Terrain::Mountain && !unit.can_enter_mountain { score = f64::NEG_INFINITY; }

        if score > best_score {
            best_score = score; best = vec![(*dq, *dr)];
        } else if (score - best_score).abs() < 0.001 {
            best.push((*dq, *dr));
        }
    }
    if best.is_empty() { return Action::EndTurn; }
    Action::Move { unit_idx: local_idx, dq: best[0].0, dr: best[0].1 }
}

fn retreat_from_evo(
    unit: &Unit, local_idx: usize, gs: &GameState, ex: i32, ey: i32,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() { return Action::EndTurn; }
    let mut best_d = 0u8;
    let mut best = Vec::new();
    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, ex, ey);
        if d > best_d { best_d = d; best = vec![(*dq, *dr)]; }
        else if d == best_d { best.push((*dq, *dr)); }
    }
    if best.is_empty() { return Action::EndTurn; }
    Action::Move { unit_idx: local_idx, dq: best[0].0, dr: best[0].1 }
}

fn approach_archer_evo(
    unit: &Unit, local_idx: usize, gs: &GameState,
    tx: i32, ty: i32, dist_weight: f64, high_ground: f64, terrain_w: f64, cfg: &GreedyConfig,
) -> Action {
    let moves = legal_moves(unit, &gs.grid);
    if moves.is_empty() { return Action::EndTurn; }
    let mut best_score = f64::NEG_INFINITY;
    let mut best = Vec::new();
    for (dq, dr) in &moves {
        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
        let d = hex_distance(nq, nr, tx, ty) as f64;
        let mut score = -(d - 2.0).abs() * dist_weight;
        let db = gs.grid.get(nq, nr).terrain.def_bonus() as f64;
        score += db * terrain_w + db * high_ground;
        if score > best_score { best_score = score; best = vec![(*dq, *dr)]; }
        else if (score - best_score).abs() < 0.01 { best.push((*dq, *dr)); }
    }
    if best.is_empty() { return Action::EndTurn; }
    Action::Move { unit_idx: local_idx, dq: best[0].0, dr: best[0].1 }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::init_game;
    use crate::ai::random::RandomAgent;
    use rand::SeedableRng;
    use rand_chacha::ChaCha12Rng;

    #[test]
    fn test_Evo_vs_Random_单局可跑完() {
        let mut gs = init_game(42, "balanced");
        let agent = EvoAgent::new();
        let random = RandomAgent;
        let mut rng0 = ChaCha12Rng::seed_from_u64(42);
        let mut rng1 = ChaCha12Rng::seed_from_u64(99);

        while gs.winner.is_none() && gs.turn < crate::constants::MAX_TURNS {
            let a0 = agent.decide(&gs, 0, &mut rng0);
            let a1 = random.decide(&gs, 1, &mut rng1);
            crate::game::step_game(&mut gs, &a0, &a1);
        }
        assert!(gs.winner.is_some() || gs.turn >= crate::constants::MAX_TURNS);
    }

    #[test]
    fn test_Evo权重加载() {
        let json = r#"{"weights": {"attack_adjacent": 2.0, "rush_enemy_city": 0.35}}"#;
        let agent = EvoAgent::from_json(json).unwrap();
        assert_eq!(*agent.weights.get("attack_adjacent").unwrap(), 2.0);
        assert_eq!(*agent.weights.get("rush_enemy_city").unwrap(), 0.35);
        // 未指定的保持默认
        assert_eq!(*agent.weights.get("defend_own_city").unwrap(), 1.0);
    }

    #[test]
    fn test_Evo加载hex权重文件() {
        let path = std::path::Path::new("prototype_hex/evo_hex_weights.json");
        if path.exists() {
            let json = std::fs::read_to_string(path).unwrap();
            let agent = EvoAgent::from_json(&json).unwrap();
            assert!(!agent.weights.is_empty());
        }
    }
}
