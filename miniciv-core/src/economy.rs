// Economy system: resources, worker actions, unit production.
// Translates prototype/economy.py.
use crate::unit::{Unit, UnitType};
use crate::map::Grid;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Economy {
    pub player_id: u8,
    pub food: i32, pub wood: i32, pub gold: i32,
}

impl Economy {
    pub fn new(player_id: u8) -> Self { todo!("Phase 5") }
    pub fn can_afford(&self, cost: (i32, i32, i32)) -> bool { todo!("Phase 5") }
    pub fn spend(&mut self, cost: (i32, i32, i32)) { todo!("Phase 5") }
    pub fn add(&mut self, resource: &str, amount: i32) { todo!("Phase 5") }
}

pub fn worker_action_build(worker: &Unit, grid: &mut Grid, pid: u8) -> bool { todo!("Phase 5") }
pub fn worker_action_produce(worker: &Unit, grid: &Grid, pid: u8, economy: &mut Economy) -> Option<String> { todo!("Phase 5") }
pub fn produce_unit(grid: &Grid, city: &crate::unit::City, economy: &mut Economy, unit_type: UnitType, all_units: &mut Vec<Unit>) -> bool { todo!("Phase 5") }
pub fn destroy_facility(grid: &mut Grid, q: i32, r: i32) -> bool { todo!("Phase 5") }
pub fn city_base_income(economy: &mut Economy, food_bonus: i32) { todo!("Phase 5") }
