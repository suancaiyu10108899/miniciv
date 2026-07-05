// Batch evaluation. Translates prototype_hex/eval_hex.py.
use crate::game::{GameState, init_game, step_game, StepResult};
use crate::ai::{Agent, Action};

pub struct EvalResult {
    pub seed: u64, pub winner: Option<u8>, pub victory_type: Option<String>,
    pub turns: u16, pub elapsed_ms: f64,
    pub p0_alive: u8, pub p1_alive: u8, pub p0_dead: u8, pub p1_dead: u8,
}

pub fn run_one_game(
    seed: u64, ai0: &dyn Agent, ai1: &dyn Agent,
    generator_id: &str, max_turns: u16, verbose: bool,
) -> EvalResult {
    todo!("Phase 9: Implement single game evaluation")
}

pub fn run_matrix(
    ais: &[(&str, &dyn Agent)], games_per_pair: u32, seed_base: u64,
) -> Vec<EvalResult> {
    todo!("Phase 9: Implement matrix evaluation")
}
