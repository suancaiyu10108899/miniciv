// Builder 固定策略 — 门禁 2b（深度裁决用)
//
// 目的: 不是做最强 AI, 而是做一个"少犯错、专注建设"的确定性策略,
//       用来裁决"游戏是否奖励水平"。
//
// 逻辑(刻意简单、无随机):
//   研究: 固定顺序直奔建设胜利科技链 C1→C3→C4→C5 (+E1 补经济)
//   工人: 能建设施就建; 否则移动到相邻可建空格; 站在自己设施上则采集
//   城市: 产工人(补充建设施人力), 上限 5
//   战斗单位: 不动(不打仗、不产兵——专注建设)
//
// 对照意义:
//   - Builder >> Random  → 游戏在"建设专注度"上有深度, Greedy 只是反优化了 → 修 Greedy
//   - Builder ≈ Random   → 建设胜利是运气竞速, 无深度 → 必须改设计

use crate::game::GameState;
use crate::unit::UnitType;
use crate::map::Terrain;
use crate::ai::{Action, Agent};
use crate::movement::legal_moves;
use crate::tech::TechManager;
use rand::RngCore;

pub struct BuilderAgent;

/// 地形是否可建设施(平原/森林/山地可建, 水/城市不可)
fn buildable(t: Terrain) -> bool {
    matches!(t, Terrain::Plain | Terrain::Forest | Terrain::Mountain)
}

impl Agent for BuilderAgent {
    fn decide(&self, gs: &GameState, pid: u8, _rng: &mut dyn RngCore) -> Vec<Action> {
        let mut actions = Vec::new();

        // ── 研究: 固定顺序直奔 C5 ──
        // 建设胜利需 C5(前置 C3且C4)。最短链 C1→C3→C4→C5。
        // C3=学院(研究减半)值得早点。E1 加农场产出帮助负担科技成本。
        let tech = &gs.techs[pid as usize];
        if tech.researching.is_none() {
            let econ = &gs.economies[pid as usize];
            let avail = tech.available_to_research();
            let order = ["C1", "C3", "C4", "C5", "E1", "C2", "E3", "E2", "E4"];
            for t in order {
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

        // ── 工人 + 战斗单位 ──
        let player_units: Vec<(usize, &crate::unit::Unit)> = gs.units.iter().enumerate()
            .filter(|(_, u)| u.player_id == pid && u.alive)
            .collect();
        let mut worker_count = 0u32;

        for (local_idx, (_, unit)) in player_units.iter().enumerate() {
            if unit.unit_type != UnitType::Worker {
                continue;  // 战斗单位不动(专注建设)
            }
            worker_count += 1;

            let tile = gs.grid.get(unit.q, unit.r);
            let can_build_here = buildable(tile.terrain) && tile.facility.is_none();

            if can_build_here {
                actions.push(Action::Build { unit_idx: local_idx });
                continue;
            }

            // 当前格不能建: 找相邻可建空格移动过去
            let moves = legal_moves(unit, &gs.grid);
            let mut moved = false;
            for (dq, dr) in &moves {
                let nq = (unit.q + dq).rem_euclid(crate::constants::MAP_W as i32);
                let nr = (unit.r + dr).rem_euclid(crate::constants::MAP_H as i32);
                let ntile = gs.grid.get(nq, nr);
                if buildable(ntile.terrain) && ntile.facility.is_none() {
                    actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                    moved = true;
                    break;
                }
            }
            if moved { continue; }

            // 没有相邻可建空格: 站在自己设施上则采集, 否则移动一步找机会
            let on_own_facility = tile.facility.as_ref()
                .map(|f| f.player_id == pid).unwrap_or(false);
            if on_own_facility {
                actions.push(Action::Produce { unit_idx: local_idx });
            } else if let Some((dq, dr)) = moves.first() {
                actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
            }
        }

        // ── 城市: 产工人(补充人力, 上限 5) ──
        let econ = &gs.economies[pid as usize];
        if worker_count < 5 && econ.can_afford((3, 0, 0)) {
            actions.push(Action::ProduceUnit { unit_type: "worker".to_string() });
        }

        actions
    }

    fn name(&self) -> &str { "Builder" }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::{init_game, step_game};
    use crate::constants::MAX_TURNS;
    use crate::ai::random::RandomAgent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    #[test]
    fn test_Builder_vs_Random_单局可跑完() {
        let mut gs = init_game(50000, "balanced");
        let b = BuilderAgent;
        let r = RandomAgent;
        let mut rng0 = ChaCha12Rng::seed_from_u64(50000);
        let mut rng1 = ChaCha12Rng::seed_from_u64(50001);
        while gs.winner.is_none() && gs.turn < MAX_TURNS {
            let a0 = b.decide(&gs, 0, &mut rng0);
            let a1 = r.decide(&gs, 1, &mut rng1);
            step_game(&mut gs, &a0, &a1);
        }
        assert!(gs.winner.is_some());
    }

    /// 诊断: Builder 到底几回合速通建设? 验证是合法胜利还是判定 bug。
    /// cargo test builder_rush -- --ignored --nocapture
    #[test]
    #[ignore]
    fn builder_rush_诊断() {
        let b = BuilderAgent;
        let r = RandomAgent;
        for seed in [50000u64, 50100, 50200] {
            let mut gs = init_game(seed, "balanced");
            let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
            let mut rng1 = ChaCha12Rng::seed_from_u64(seed + 1);
            while gs.winner.is_none() && gs.turn < MAX_TURNS {
                let a0 = b.decide(&gs, 0, &mut rng0);
                let a1 = r.decide(&gs, 1, &mut rng1);
                step_game(&mut gs, &a0, &a1);
            }
            // 统计 P0(Builder) 的设施数和已完成科技
            let mut facs = 0;
            for rr in 0..crate::constants::MAP_H as i32 {
                for qq in 0..crate::constants::MAP_W as i32 {
                    if let Some(f) = &gs.grid.get(qq, rr).facility {
                        if f.player_id == 0 { facs += 1; }
                    }
                }
            }
            println!("seed={} winner={:?} turn={} victory={:?} P0设施={} P0科技={:?}",
                     seed, gs.winner, gs.turn, gs.victory_type, facs,
                     gs.techs[0].completed);
        }
    }
}
