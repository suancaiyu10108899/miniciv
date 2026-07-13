// P1.5 BC Agent: 行为克隆——从FlatMC蒸馏的策略
// 加载bc-train训练的softmax权重, 推理时前向传播预测6个分解动作

use crate::game::GameState;
use crate::ai::{Action, Agent};
use crate::unit::UnitType;
use crate::economy::Branch;
use crate::movement::hex_distance;
use rand::RngCore;
use std::collections::HashMap;

pub struct BcAgent {
    /// 每个轴: (class_list, weight_matrix[n_classes][n_feats+1])
    models: HashMap<String, (Vec<String>, Vec<Vec<f64>>)>,
}

impl BcAgent {
    pub fn from_json(json_str: &str) -> Result<Self, String> {
        let data: serde_json::Value = serde_json::from_str(json_str).map_err(|e| e.to_string())?;
        let mut models: HashMap<String, (Vec<String>, Vec<Vec<f64>>)> = HashMap::new();
        for ax_name in &["research","produce","posture","branch","redeem","expand"] {
            if let Some(ax_data) = data.get(*ax_name) {
                let classes: Vec<String> = ax_data.get("classes").and_then(|c| c.as_array())
                    .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect())
                    .unwrap_or_default();
                let weights: Vec<Vec<f64>> = ax_data.get("weights").and_then(|w| w.as_array())
                    .map(|a| a.iter().filter_map(|row| row.as_array().map(|r|
                        r.iter().filter_map(|v| v.as_f64()).collect()
                    )).collect()).unwrap_or_default();
                models.insert(ax_name.to_string(), (classes, weights));
            }
        }
        Ok(Self { models })
    }

    /// 从json文件路径加载
    pub fn from_file(path: &str) -> Result<Self, String> {
        let json = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        Self::from_json(&json)
    }

    /// 推理: 给定特征, 预测各轴动作
    fn predict(&self, feats: &[f64]) -> [String; 6] {
        let axes = ["research","produce","posture","branch","redeem","expand"];
        let mut result = ["None".to_string(), "None".to_string(), "Attack".to_string(), "None".to_string(), "None".to_string(), "No".to_string()];
        for (i, ax_name) in axes.iter().enumerate() {
            if let Some((classes, weights)) = self.models.get(*ax_name) {
                let n_classes = classes.len();
                let n_feats = feats.len();
                let mut best_class = 0usize;
                let mut best_score = f64::NEG_INFINITY;
                for c in 0..n_classes {
                    let mut score = weights[c][n_feats]; // bias
                    for f in 0..n_feats { score += weights[c][f] * feats[f]; }
                    if score > best_score { best_score = score; best_class = c; }
                }
                result[i] = classes[best_class].clone();
            } else {
                result[i] = "None".to_string();
            }
        }
        result
    }
}

impl Agent for BcAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = crate::game::primary_enemy(pid, &gs.config).unwrap_or(if pid == 0 { 1 } else { 0 });
        let feats = extract_features(gs, pid);
        let preds = self.predict(&feats);
        let mut actions = Vec::new();

        // 研究
        if preds[0] != "None" && gs.techs[pid as usize].researching.is_none() {
            let tech_id = &preds[0];
            if let Some(cost) = gs.techs[pid as usize].cost_of(tech_id) {
                if gs.economies[pid as usize].can_afford(cost) {
                    actions.push(Action::Research { tech_id: tech_id.clone() });
                }
            }
        }

        // 生产
        if preds[1] != "None" {
            let ut_str = &preds[1];
            actions.push(Action::ProduceUnit { unit_type: ut_str.clone() });
        }

        // 分支
        if preds[3] != "None" && gs.turn >= gs.config.branch_available_turn
           && gs.economies[pid as usize].branch.is_none() {
            actions.push(Action::ChooseBranch { branch: preds[3].clone() });
        }

        // 兑换
        if preds[4] != "None" {
            actions.push(Action::RedeemOrg { mode: preds[4].clone() });
        }

        // 扩张
        if preds[5] == "Yes" {
            actions.push(Action::Expand);
        }

        // 移动: 基于预测姿态做简单移动
        let posture = &preds[2];
        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.alive && u.player_id == pid).collect();

        let (target_q, target_r) = match posture.as_str() {
            "Attack" => (gs.cities[opp as usize].q, gs.cities[opp as usize].r),
            "Defend" => (gs.cities[pid as usize].q, gs.cities[pid as usize].r),
            _ => (gs.cities[opp as usize].q, gs.cities[opp as usize].r), // default: attack
        };

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            match unit.unit_type {
                UnitType::Worker => {
                    // Simple worker logic: build if possible, else produce, else move
                    let tile = gs.grid.get(unit.q, unit.r);
                    let buildable = matches!(tile.terrain, crate::map::Terrain::Plain | crate::map::Terrain::Forest | crate::map::Terrain::Mountain);
                    if buildable && tile.facility.is_none() {
                        actions.push(Action::Build { unit_idx: local_idx });
                    } else if tile.facility.as_ref().map(|f| f.player_id == pid).unwrap_or(false) {
                        actions.push(Action::Produce { unit_idx: local_idx });
                    } else {
                        if let Some((dq, dr)) = step_toward(unit, target_q, target_r, &gs.grid) {
                            actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                        }
                    }
                }
                UnitType::Scout => {}
                _ => {
                    if let Some((dq, dr)) = step_toward(unit, target_q, target_r, &gs.grid) {
                        actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                    }
                }
            }
        }

        actions
    }

    fn name(&self) -> &str { "BC" }
}

/// 和bc-collect一致的25维特征
fn extract_features(gs: &GameState, pid: u8) -> Vec<f64> {
    let opp = 1 - pid;
    let my_e = &gs.economies[pid as usize];
    let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;

    let my_units: Vec<&crate::unit::Unit> = gs.units.iter().filter(|u| u.alive && u.player_id == pid).collect();
    let opp_units: Vec<&crate::unit::Unit> = gs.units.iter().filter(|u| u.alive && u.player_id == opp).collect();

    let count_unit = |units: &[&crate::unit::Unit], ut: UnitType| -> f64 {
        units.iter().filter(|u| u.unit_type == ut).count() as f64
    };

    let mut my_facs = 0u32;
    for r in 0..ms { for q in 0..ms { if let Some(f) = &gs.grid.get(q, r).facility { if f.player_id == pid { my_facs += 1; } } } }

    let opp_cq = gs.cities[opp as usize].q; let opp_cr = gs.cities[opp as usize].r;
    let min_dist = my_units.iter().filter(|u| u.unit_type != UnitType::Worker)
        .map(|u| hex_distance(u.q, u.r, opp_cq, opp_cr) as f64).fold(99.0, f64::min);

    vec![
        my_e.support as f64 / 100.0, my_e.organization as f64 / 100.0,
        match my_e.branch { Some(Branch::White)=>1.0, Some(Branch::Red)=>-1.0, None=>0.0 },
        my_e.crisis_timer as f64 / 20.0, my_e.expansion_level as f64 / 5.0,
        my_e.food as f64 / 200.0, my_e.wood as f64 / 200.0, my_e.gold as f64 / 200.0,
        count_unit(&my_units, UnitType::Infantry), count_unit(&my_units, UnitType::Cavalry),
        count_unit(&my_units, UnitType::Archer), count_unit(&my_units, UnitType::Worker),
        gs.cities[pid as usize].hp as f64 / 2000.0,
        gs.techs[pid as usize].completed.len() as f64 / 13.0,
        my_facs as f64 / 8.0,
        opp_e.food as f64 / 200.0, opp_e.wood as f64 / 200.0, opp_e.gold as f64 / 200.0,
        count_unit(&opp_units, UnitType::Infantry), count_unit(&opp_units, UnitType::Cavalry),
        count_unit(&opp_units, UnitType::Archer),
        gs.cities[opp as usize].hp as f64 / 2000.0,
        gs.techs[opp as usize].completed.len() as f64 / 13.0,
        min_dist / 15.0, gs.turn as f64 / 250.0,
    ]
}

fn step_toward(unit: &crate::unit::Unit, tq: i32, tr: i32, grid: &crate::map::Grid) -> Option<(i32, i32)> {
    let moves = crate::movement::legal_moves(unit, grid);
    if moves.is_empty() { return None; }
    let cur_d = hex_distance(unit.q, unit.r, tq, tr);
    let mut best: Option<(i32, i32)> = None;
    let mut best_d = u8::MAX;
    for (dq, dr) in moves {
        let nq = (unit.q + dq).rem_euclid(crate::constants::MAP_W as i32);
        let nr = (unit.r + dr).rem_euclid(crate::constants::MAP_H as i32);
        let d = hex_distance(nq, nr, tq, tr);
        if d < best_d { best_d = d; best = Some((dq, dr)); }
    }
    if best_d <= cur_d { best } else { None }
}
