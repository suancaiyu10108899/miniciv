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
                    if let Some(cost) = tech.cost_of(t) {
                        if econ.can_afford(cost) {
                            actions.push(Action::Research { tech_id: t.to_string() });
                            break;
                        }
                    }
                }
            }
        }

        // ── 工人 + 战斗单位 ──
        // M2 诊断修正: 数自己设施, 建够 5(超门槛4)后工人转采集,
        // 避免"只建不采"导致研究缺资源(旧版在资源17下被拖到30T的假象根因)。
        let mut my_facs = 0u32;
        for r in 0..crate::constants::MAP_H as i32 {
            for q in 0..crate::constants::MAP_W as i32 {
                if let Some(f) = &gs.grid.get(q, r).facility {
                    if f.player_id == pid { my_facs += 1; }
                }
            }
        }
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
            let on_own_facility = tile.facility.as_ref()
                .map(|f| f.player_id == pid).unwrap_or(false);

            // 建够 5 设施前: 优先建; 建够后: 采集供研究
            if can_build_here && my_facs < 5 {
                actions.push(Action::Build { unit_idx: local_idx });
                continue;
            }
            if on_own_facility {
                actions.push(Action::Produce { unit_idx: local_idx });
                continue;
            }

            // 需要建但当前格不行→找相邻空可建格; 否则移动一步(去找设施采集)
            let moves = legal_moves(unit, &gs.grid);
            let mut acted = false;
            if my_facs < 5 {
                for (dq, dr) in &moves {
                    let nq = (unit.q + dq).rem_euclid(crate::constants::MAP_W as i32);
                    let nr = (unit.r + dr).rem_euclid(crate::constants::MAP_H as i32);
                    let ntile = gs.grid.get(nq, nr);
                    if buildable(ntile.terrain) && ntile.facility.is_none() {
                        actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                        acted = true;
                        break;
                    }
                }
            }
            if !acted {
                if let Some((dq, dr)) = moves.first() {
                    actions.push(Action::Move { unit_idx: local_idx, dq: *dq, dr: *dr });
                }
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

    /// 反速通哨兵(S2 立裁判阶段翻面, 2026-07-11 第四个 AI)。
    ///
    /// 历史: 门禁2b 曾在此记录**不健康基线**(5T建设速通, Builder 100%通杀 Random),
    ///       故意"速通被打破时 fail"逼迫更新。S2 把默认翻为甜点后, 该守护对象也翻面:
    ///       现在守的是**健康甜点不变量**——默认配置下不存在裸建设速通、无单一策略碾压。
    ///
    /// 断言(健康):
    ///   1. Builder(裸建设不设防) vs Random 平均结束回合 > 5(成本×2 拖慢建设, 无 5T 速通)。
    ///   2. Builder 不再 100% 通杀(不设防在甜点下会被军事惩罚, 胜率 < 100%)。
    /// 若这里 fail: 要么甜点被无声改回坏基线, 要么平衡漂移——都该查。
    #[test]
    fn test_反速通哨兵_守健康甜点() {
        use crate::eval::run_pair;
        let b = BuilderAgent;
        let r = RandomAgent;
        let p = run_pair(&b, &r, 50, 50000, "balanced", &crate::config::GameConfig::default());
        assert!(p.avg_turns > 5.0,
            "反速通哨兵: Builder vs Random 平均结束回合={:.1} 应 >5(甜点拖慢建设)。\
             若 ~5 说明默认被改回 5T 速通坏基线。", p.avg_turns);
        assert!(p.a_win_rate < 1.0,
            "反速通哨兵: Builder 裸建设在甜点下不该 100% 通杀 Random(实际={:.3})。\
             100% 说明军事惩罚失效或默认漂移回坏基线。", p.a_win_rate);
    }
}
