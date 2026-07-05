// Units, cities, facilities — pure data containers.
// Translates prototype/unit.py.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum UnitType { Infantry, Cavalry, Archer, Scout, Worker }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum FacilityType { Farm, Lumbermill, Mine }

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Unit {
    pub unit_type: UnitType,
    pub player_id: u8,
    pub q: i32, pub r: i32,  // axial hex coordinates
    pub hp: i32, pub atk: i32, pub def: i32,
    pub move_speed: u8, pub vision: u8,
    pub can_enter_mountain: bool,
    pub ranged: bool, pub range_dist: u8,
    pub alive: bool,
    pub damage_dealt: i32, pub damage_taken: i32,
}

impl Unit {
    pub fn create(unit_type: UnitType, player_id: u8, q: i32, r: i32) -> Self {
        todo!("Phase 4: Implement Unit::create from UNIT_STATS")
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct City {
    pub player_id: u8,
    pub q: i32, pub r: i32,
    pub hp: i32, pub def: i32,
    pub base_food: i32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Facility {
    pub facility_type: FacilityType,
    pub player_id: u8,
    pub q: i32, pub r: i32,
}
