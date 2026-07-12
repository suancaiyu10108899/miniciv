// AI trait + implementations.
use crate::game::GameState;
use serde::{Deserialize, Serialize};
use rand::RngCore;

pub mod random;
pub mod greedy;
pub mod evo;
pub mod fixed;
pub mod probes;
pub mod search;
pub mod flatmc;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Action {
    Move { unit_idx: usize, dq: i32, dr: i32 },
    Build { unit_idx: usize },
    Produce { unit_idx: usize },
    ProduceUnit { unit_type: String },
    Research { tech_id: String },
    Destroy { unit_idx: usize },
    /// P1.5: 抽象扩张——投入资源/扣支持度, 换取永久产出基数提升。
    Expand,
    /// P1.5: 选择红白路线。
    ChooseBranch { branch: String },  // "Red" / "White"
    /// P1.5: 红线组织度兑换。
    RedeemOrg { mode: String },       // "LianDa" / "Concentrate" / "Mobilize"
    EndTurn,
}

/// All AI implementations must satisfy this trait.
/// `Send + Sync` enables parallel batch evaluation.
pub trait Agent: Send + Sync {
    fn decide(&self, state: &GameState, player: u8, rng: &mut dyn RngCore) -> Vec<Action>;
    fn name(&self) -> &str;
}
