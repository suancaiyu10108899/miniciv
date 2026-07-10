// Random 基线 AI — Phase 6
// 翻译自 prototype_hex/ai_random_hex.py (183行)
//
// 最简单的 AI: 所有决策随机。作为评估基线使用。
// 如果新 AI 不能稳定赢 Random, 说明基础逻辑有问题。
//
// 策略:
//   战斗单位: 随机选合法方向移动(优先攻击邻格敌人)
//   工人: 随机建造/生产/移动
//   研究: 从可选科技中随机选
//   生产: 从可负担的兵种中随机选

use crate::game::GameState;
use crate::unit::UnitType;
use crate::ai::{Action, Agent};
use crate::movement::{legal_moves, HEX_DIRS};
use crate::constants::{MAP_W, MAP_H};
use rand::RngCore;

/// 六边形攻击方向——和移动方向一致(6方向)
fn hex_attack_dirs() -> [(i32, i32); 6] {
    HEX_DIRS
}

pub struct RandomAgent;

impl Agent for RandomAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let opp = 1 - pid;
        let mut actions = Vec::new();

        // 收集当前玩家的存活单位
        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();

        for (unit_idx, unit) in player_units.iter() {
            let unit_idx = *unit_idx;
            let local_idx = player_units.iter()
                .position(|(i, _)| *i == unit_idx)
                .unwrap();

            match unit.unit_type {
                UnitType::Worker => {
                    // 工人: 50% 生产, 25% 建造, 25% 随机移动
                    let roll = rng.next_u32() % 100;
                    if roll < 50 {
                        actions.push(Action::Produce { unit_idx: local_idx });
                    } else if roll < 75 {
                        actions.push(Action::Build { unit_idx: local_idx });
                    } else {
                        // 随机移动
                        let moves = legal_moves(unit, &gs.grid);
                        if !moves.is_empty() {
                            let pick = (rng.next_u32() as usize) % moves.len();
                            let (dq, dr) = moves[pick];
                            actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                        } else {
                            actions.push(Action::EndTurn);
                        }
                    }
                }
                _ => {
                    // 战斗单位(步兵/骑兵/弓手/侦察兵)
                    // 先检查邻格是否有敌人可以攻击
                    let mut attacked = false;
                    for (dq, dr) in hex_attack_dirs().iter() {
                        let nq = (unit.q + dq).rem_euclid(MAP_W as i32);
                        let nr = (unit.r + dr).rem_euclid(MAP_H as i32);
                        let has_enemy = gs.units.iter().any(|eu| {
                            eu.alive && eu.player_id == opp
                                && eu.q == nq && eu.r == nr
                        });
                        if has_enemy {
                            actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                            attacked = true;
                            break;
                        }
                    }

                    if !attacked {
                        // 随机移动
                        let moves = legal_moves(unit, &gs.grid);
                        if !moves.is_empty() {
                            let pick = (rng.next_u32() as usize) % moves.len();
                            let (dq, dr) = moves[pick];
                            actions.push(Action::Move { unit_idx: local_idx, dq, dr });
                        } else {
                            actions.push(Action::EndTurn);
                        }
                    }
                }
            }
        }

        // 研究: 随机选一个可研究的科技
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let avail = tech.available_to_research();
            if !avail.is_empty() {
                let pick = (rng.next_u32() as usize) % avail.len();
                let econ = &gs.economies[pid as usize];
                let tech_id = &avail[pick];
                if let Some(cost) = crate::tech::TechManager::tech_cost(tech_id) {
                    if econ.can_afford(cost) {
                        actions.push(Action::Research { tech_id: tech_id.clone() });
                    }
                }
            }
        }

        // 生产: 随机选一个可负担的兵种
        let econ = &gs.economies[pid as usize];
        let unit_types = ["infantry", "cavalry", "archer", "scout"];
        // 随机排序
        let mut indices: Vec<usize> = (0..unit_types.len()).collect();
        // Fisher-Yates shuffle with RNG
        for i in (1..indices.len()).rev() {
            let j = (rng.next_u32() as usize) % (i + 1);
            indices.swap(i, j);
        }
        for &i in &indices {
            let ut = unit_types[i];
            let cost = match ut {
                "infantry" => (5, 0, 0),
                "cavalry" => (5, 0, 3),
                "archer" => (3, 3, 0),
                "scout" => (3, 0, 0),
                _ => continue,
            };
            if econ.can_afford(cost) {
                actions.push(Action::ProduceUnit { unit_type: ut.to_string() });
                break;
            }
        }

        actions
    }

    fn name(&self) -> &str { "Random" }
}
