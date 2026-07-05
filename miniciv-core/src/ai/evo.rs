// Evo AI — 15-parameter weighted decision making.
// Translates prototype_hex/ai_evo_hex.py.
// Weights loaded from JSON (evo_hex_weights.json equivalent).
use crate::game::GameState;
use crate::ai::{Action, Agent};
use rand::RngCore;
use std::collections::HashMap;

pub struct EvoAgent {
    pub weights: HashMap<String, f64>,
}

impl Agent for EvoAgent {
    fn decide(&self, state: &GameState, player: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        todo!("Phase 8: Implement Evo AI")
    }

    fn name(&self) -> &str { "Evo" }
}
