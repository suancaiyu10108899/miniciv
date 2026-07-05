// miniciv-core — Hex grid strategy game engine
// AI-first, deterministic, headless.
//
// Crate structure:
//   constants → map → movement → unit → combat → economy → tech → game → ai → eval

pub mod constants;
pub mod map;
pub mod movement;
pub mod unit;
pub mod combat;
pub mod economy;
pub mod tech;
pub mod game;
pub mod snapshot;
pub mod eval;
pub mod ai;

#[cfg(feature = "python")]
pub mod py_bindings;

// Re-exports for convenience
pub use game::{GameState, init_game, step_game, StepResult};
pub use unit::{Unit, UnitType, City, Facility, FacilityType};
pub use map::{Grid, Tile, Terrain};
pub use combat::{resolve_melee, resolve_ranged, MeleeResult, RangedResult};
pub use ai::Agent;
