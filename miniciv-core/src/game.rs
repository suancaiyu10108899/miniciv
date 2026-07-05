// Game loop: init, step, victory checks. Translates prototype_hex/game_hex.py.
use serde::{Deserialize, Serialize};
use crate::map::Grid;
use crate::unit::{Unit, City};
use crate::economy::Economy;
use crate::tech::TechManager;
use crate::ai::Action;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum VictoryType {
    Conquest,
    Construction,
    TiebreakConstruction,
    TiebreakCityHp,
    TiebreakRandom,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepResult {
    pub turn: u16,
    pub winner: Option<u8>,
    pub victory_type: Option<VictoryType>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameState {
    pub seed: u64,
    pub size: u8,
    pub generator_id: String,
    pub turn: u16,
    pub grid: Grid,
    pub units: Vec<Unit>,
    pub cities: Vec<City>,
    pub economies: Vec<Economy>,
    pub techs: Vec<TechManager>,
    pub winner: Option<u8>,
    pub victory_type: Option<VictoryType>,
    pub dead_units: Vec<Unit>,
    pub action_log: Vec<Vec<Action>>,  // per-turn action pairs
}

pub fn init_game(seed: u64, generator_id: &str) -> GameState {
    todo!("Phase 6: Implement game initialization")
}

pub fn step_game(gs: &mut GameState, actions_p0: &[Action], actions_p1: &[Action]) -> StepResult {
    todo!("Phase 6: Implement game step")
}
