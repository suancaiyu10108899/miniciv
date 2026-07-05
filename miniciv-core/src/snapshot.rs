// JSON serialization in GameReplay format. Translates prototype/snapshot.py.
use crate::game::GameState;
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

// Snapshot sub-types (simplified for stub)
#[derive(Serialize, Deserialize)] pub struct UnitSnapshot { pub unit_type: String, pub pid: u8, pub q: i32, pub r: i32, pub hp: i32, pub atk: i32, pub def: i32 }
#[derive(Serialize, Deserialize)] pub struct CitySnapshot { pub pid: u8, pub q: i32, pub r: i32, pub hp: i32 }
#[derive(Serialize, Deserialize)] pub struct EconomySnapshot { pub pid: u8, pub food: i32, pub wood: i32, pub gold: i32 }
#[derive(Serialize, Deserialize)] pub struct TechSnapshot { pub pid: u8, pub completed: Vec<String>, pub researching: Option<String>, pub research_ticks: u8 }
#[derive(Serialize, Deserialize)] pub struct FacilitySnapshot { pub pid: u8, pub facility_type: String, pub q: i32, pub r: i32 }
#[derive(Serialize, Deserialize)] pub struct EventSnapshot { pub event_type: String, pub pid: u8, pub detail: String }
#[derive(Serialize, Deserialize)] pub struct ReplayResult { pub winner: Option<u8>, pub victory_type: Option<String>, pub final_turn: u16 }

pub fn create_replay(gs: &GameState, seed: u64, ai_a: &str, ai_b: &str) -> GameReplay {
    todo!("Phase 6: Implement replay creation")
}

pub fn save_replay(gs: &GameState, filepath: &str, seed: u64) -> GameReplay {
    todo!("Phase 6: Implement replay saving")
}
