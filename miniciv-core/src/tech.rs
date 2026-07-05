// Tech tree: 13-node DAG. Translates prototype/tech.py.
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TechManager {
    pub player_id: u8,
    pub completed: HashSet<String>,
    pub researching: Option<String>,
    pub research_ticks: u8,
    pub has_academy: bool,
}

impl TechManager {
    pub fn new(player_id: u8) -> Self { todo!("Phase 5") }
    pub fn available_to_research(&self) -> Vec<String> { todo!("Phase 5") }
    pub fn start_research(&mut self, tech_id: &str) -> bool { todo!("Phase 5") }
    pub fn tick_research(&mut self) -> Option<String> { todo!("Phase 5") }
    pub fn get_tech_bonuses(&self) -> TechBonuses { todo!("Phase 5") }
    pub fn construction_count(&self) -> u8 { todo!("Phase 5") }
}

#[derive(Clone, Debug, Default)]
pub struct TechBonuses {
    pub infantry_atk: i32,
    pub archer_atk: i32,
    pub cavalry_charge: i32,
    pub infantry_def_forest_mountain: i32,
    pub all_hp: i32,
    pub farm_bonus: i32,
    pub lumbermill_bonus: i32,
    pub mine_bonus: i32,
    pub worker_speed: i32,
    pub city_hp: i32,
    pub city_food: i32,
}
