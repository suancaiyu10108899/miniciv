// Random baseline AI. Translates prototype_hex/ai_random_hex.py.
use crate::game::GameState;
use crate::ai::{Action, Agent};
use rand::RngCore;

pub struct RandomAgent;

impl Agent for RandomAgent {
    fn decide(&self, state: &GameState, player: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        todo!("Phase 6: Implement Random AI")
    }

    fn name(&self) -> &str { "Random" }
}
