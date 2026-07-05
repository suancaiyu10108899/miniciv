// Game parameters — single source of truth.
// Translated from prototype/constants.py (v0.7.0 locked).

// ─── Map ──────────────────────────────────────────
pub const MAP_W: u8 = 15;
pub const MAP_H: u8 = 15;
pub const DEFAULT_SIZE: u8 = 15;
pub const MAX_TURNS: u16 = 80;

// ─── City ─────────────────────────────────────────
pub const CITY_HP: i32 = 80;
pub const CITY_DEF: i32 = 5;
pub const CITY_DAMAGE: i32 = 5;
pub const CITY_BASE_FOOD: i32 = 1;

// ─── Combat ───────────────────────────────────────
pub const CAVALRY_CHARGE_BONUS: i32 = 10;

// ─── Economy ──────────────────────────────────────
pub const STARTING_FOOD: i32 = 25;
pub const STARTING_WOOD: i32 = 25;
pub const STARTING_GOLD: i32 = 25;
pub const STARTING_WORKERS: u8 = 3;
pub const STARTING_SCOUTS: u8 = 1;
pub const FACILITY_OUTPUT: i32 = 4;
pub const CONSTRUCTION_VICTORY_REQUIRE_FACILITIES: u8 = 4;

// ─── Unit stats: (hp, atk, def, move, vision, can_enter_mountain, ranged, range_dist)
// Will be moved to unit.rs with proper struct initialization.
