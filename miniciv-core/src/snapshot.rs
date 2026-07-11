// 单局回放输出 — 阶段 0.2(第三个 AI)
//
// 目的: 让人能"看一局到底发生了什么"。人类可观察性的最小前提,
//       也是引入人类锚点(验证金字塔第4层)的地基。
//
// 设计: snapshot_turn(gs) 从当前状态抓一帧; run_replay 驱动一局并逐回合收集。
//       原 create_replay 只拿到最终 gs 拿不到历史,故新增带记录的驱动器。

use crate::game::{GameState, init_game, step_game};
use crate::map::{Grid, Terrain};
use crate::ai::Agent;
use crate::constants::{MAP_W, MAP_H, MAX_TURNS};
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct GameReplay {
    pub format_version: String,
    pub config: ReplayConfig,
    pub turns: Vec<TurnSnapshot>,
    pub result: ReplayResult,
}

#[derive(Serialize, Deserialize)]
pub struct ReplayConfig {
    pub size: u8,
    pub gen: String,
    pub max_turns: u16,
    pub seed: u64,
    pub terrain_grid: Vec<Vec<u8>>,
    pub ai_a: String,
    pub ai_b: String,
    pub grid_type: String,
}

#[derive(Serialize, Deserialize)]
pub struct TurnSnapshot {
    pub turn: u16,
    pub units: Vec<UnitSnapshot>,
    pub cities: Vec<CitySnapshot>,
    pub economies: Vec<EconomySnapshot>,
    pub techs: Vec<TechSnapshot>,
    pub facility_count: std::collections::HashMap<u8, u8>,
    pub facilities: Vec<FacilitySnapshot>,
    pub events: Vec<EventSnapshot>,
}

#[derive(Serialize, Deserialize)] pub struct UnitSnapshot { pub unit_type: String, pub pid: u8, pub q: i32, pub r: i32, pub hp: i32, pub atk: i32, pub def: i32 }
#[derive(Serialize, Deserialize)] pub struct CitySnapshot { pub pid: u8, pub q: i32, pub r: i32, pub hp: i32 }
#[derive(Serialize, Deserialize)] pub struct EconomySnapshot { pub pid: u8, pub food: i32, pub wood: i32, pub gold: i32 }
#[derive(Serialize, Deserialize)] pub struct TechSnapshot { pub pid: u8, pub completed: Vec<String>, pub researching: Option<String>, pub research_ticks: u8 }
#[derive(Serialize, Deserialize)] pub struct FacilitySnapshot { pub pid: u8, pub facility_type: String, pub q: i32, pub r: i32 }
#[derive(Serialize, Deserialize)] pub struct EventSnapshot { pub event_type: String, pub pid: u8, pub detail: String }
#[derive(Serialize, Deserialize)] pub struct ReplayResult { pub winner: Option<u8>, pub victory_type: Option<String>, pub final_turn: u16 }

/// 地形 → u8(回放渲染用)
fn terrain_code(t: Terrain) -> u8 {
    match t {
        Terrain::Plain => 0,
        Terrain::Forest => 1,
        Terrain::Mountain => 2,
        Terrain::Water => 3,
        Terrain::City => 4,
    }
}

/// 从当前 GameState 抓一帧快照(纯函数,不改状态)。
pub fn snapshot_turn(gs: &GameState) -> TurnSnapshot {
    let mut units = Vec::new();
    for u in gs.units.iter().filter(|u| u.alive) {
        units.push(UnitSnapshot {
            unit_type: format!("{:?}", u.unit_type),
            pid: u.player_id,
            q: u.q, r: u.r, hp: u.hp,
            atk: u.atk, def: u.def,
        });
    }

    let cities = gs.cities.iter().map(|c| CitySnapshot {
        pid: c.player_id, q: c.q, r: c.r, hp: c.hp,
    }).collect();

    let economies = gs.economies.iter().enumerate().map(|(pid, e)| EconomySnapshot {
        pid: pid as u8, food: e.food, wood: e.wood, gold: e.gold,
    }).collect();

    let techs = gs.techs.iter().enumerate().map(|(pid, t)| {
        let mut completed: Vec<String> = t.completed.iter().cloned().collect();
        completed.sort();  // HashSet 无序 → 排序保证回放确定性
        TechSnapshot {
            pid: pid as u8,
            completed,
            researching: t.researching.clone(),
            research_ticks: t.research_ticks,
        }
    }).collect();

    // 扫全图收集设施
    let mut facilities = Vec::new();
    let mut facility_count = std::collections::HashMap::new();
    for r in 0..MAP_H as i32 {
        for q in 0..MAP_W as i32 {
            if let Some(f) = &gs.grid.get(q, r).facility {
                facilities.push(FacilitySnapshot {
                    pid: f.player_id,
                    facility_type: format!("{:?}", f.facility_type),
                    q, r,
                });
                *facility_count.entry(f.player_id).or_insert(0) += 1;
            }
        }
    }

    TurnSnapshot {
        turn: gs.turn,
        units, cities, economies, techs,
        facility_count, facilities,
        events: Vec::new(),  // 逐回合事件留待需要时补(当前胜利记在 result)
    }
}

fn terrain_grid(grid: &Grid) -> Vec<Vec<u8>> {
    (0..MAP_H as i32).map(|r| {
        (0..MAP_W as i32).map(|q| terrain_code(grid.get(q, r).terrain)).collect()
    }).collect()
}

/// 驱动一局并逐回合收集回放。P0 rng=seed, P1 rng=seed+1(与 eval 一致)。
pub fn run_replay(
    seed: u64, ai0: &dyn Agent, ai1: &dyn Agent,
    generator_id: &str, max_turns: u16,
) -> GameReplay {
    let mut gs = init_game(seed, generator_id);
    let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
    let mut rng1 = ChaCha12Rng::seed_from_u64(seed + 1);

    let config = ReplayConfig {
        size: gs.size,
        gen: generator_id.to_string(),
        max_turns,
        seed,
        terrain_grid: terrain_grid(&gs.grid),
        ai_a: ai0.name().to_string(),
        ai_b: ai1.name().to_string(),
        grid_type: "hex".to_string(),
    };

    let mut turns = vec![snapshot_turn(&gs)];  // turn 0 初始帧
    while gs.winner.is_none() && gs.turn < max_turns {
        let a0 = ai0.decide(&gs, 0, &mut rng0);
        let a1 = ai1.decide(&gs, 1, &mut rng1);
        step_game(&mut gs, &a0, &a1);
        turns.push(snapshot_turn(&gs));
    }

    GameReplay {
        format_version: "1.0".to_string(),
        config,
        turns,
        result: ReplayResult {
            winner: gs.winner,
            victory_type: gs.victory_type.as_ref().map(|v| format!("{:?}", v)),
            final_turn: gs.turn,
        },
    }
}

/// 便捷:默认 MAX_TURNS。
pub fn run_replay_default(seed: u64, ai0: &dyn Agent, ai1: &dyn Agent, generator_id: &str) -> GameReplay {
    run_replay(seed, ai0, ai1, generator_id, MAX_TURNS)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ai::fixed::BuilderAgent;
    use crate::ai::random::RandomAgent;

    #[test]
    fn test_回放帧数与结果一致() {
        let b = BuilderAgent;
        let r = RandomAgent;
        let rep = run_replay_default(50000, &b, &r, "balanced");
        // turns 含 turn0 初始帧 + 每回合一帧
        assert_eq!(rep.turns.len(), rep.result.final_turn as usize + 1);
        assert!(rep.result.winner.is_some());
        // 地图尺寸正确
        assert_eq!(rep.config.terrain_grid.len(), MAP_H as usize);
        assert_eq!(rep.config.terrain_grid[0].len(), MAP_W as usize);
    }

    #[test]
    fn test_回放确定性() {
        let b = BuilderAgent;
        let r = RandomAgent;
        let r1 = run_replay_default(50000, &b, &r, "balanced");
        let r2 = run_replay_default(50000, &b, &r, "balanced");
        assert_eq!(r1.result.final_turn, r2.result.final_turn);
        assert_eq!(r1.result.winner, r2.result.winner);
    }
}
