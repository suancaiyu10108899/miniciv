// Greedy v6 AI — hex-native rewrite (not mechanical translation).
// Strategic assessment + force coordination + opponent modeling + adaptive production.
//
// KEY: Hex geometry calibration needed. Python hex Greedy is broken (mechanical
// translation from square grid — distance gradient too shallow on hex torus).
// Rust port MUST recalibrate movement heuristic weights and strategy thresholds.
use crate::game::GameState;
use crate::ai::{Action, Agent};
use rand::RngCore;

pub struct GreedyAgent;

impl Agent for GreedyAgent {
    fn decide(&self, state: &GameState, player: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        todo!("Phase 7: Implement Greedy v6 with hex-calibrated movement heuristics")
    }

    fn name(&self) -> &str { "Greedy" }
}
