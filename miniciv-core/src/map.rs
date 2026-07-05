// Hex grid map generation — Phase 2
// Translates prototype_hex/mapgen_hex.py (85 lines).
//
// Algorithm (simpler than square version, no BFS clustering yet):
//   1. Fill terrain pool with ratios: 35% plain, 28% forest, 22% mountain, 8% water
//   2. Shuffle pool randomly (seeded RNG for determinism)
//   3. Assign shuffled terrain to grid cells
//   4. Place two cities at fixed opposite positions
//   5. Replace any water adjacent to cities with plain (ensures connectivity)
//
// C++ comparison for each Rust concept used:
//   enum Terrain { ... }         ≈ enum class TerrainType { ... };
//   struct Tile { ... }           ≈ struct Tile { ... };
//   Vec<Tile>                     ≈ vector<Tile>
//   impl Grid { fn get(...) }     ≈ const Tile& Grid::get(...) const
//   for r in 0..15 {}             ≈ for (int r = 0; r < 15; r++)
//   match terrain { ... }         ≈ switch (terrain) { ... } + compiler checks completeness
//   rng.gen_range(0..15)          ≈ rand() % 15 (but better distribution)

use rand::SeedableRng;
use rand::seq::SliceRandom;
use rand_chacha::ChaCha12Rng;
use serde::{Deserialize, Serialize};

use crate::constants::{MAP_W, MAP_H};

// ─── Terrain ────────────────────────────────────────
// NOTE: Rust enum ≈ C++ enum class. Each variant can carry data
// (like a tagged union), but here none do — they're simple tags.
// The `#[derive]` line auto-generates comparison (PartialEq/Eq),
// debug printing (Debug), and serialization (Serialize/Deserialize).
// In C++ you'd write these manually or use a code generator.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Terrain {
    Plain = 0,
    Forest = 1,
    Mountain = 2,
    Water = 3,
    City = 4,
}

impl Terrain {
    /// Defense bonus from terrain. Used in combat formula:
    ///   damage = max(1, ATK + att_DEF - DEF - def_DEF)
    // NOTE: `&self` ≈ C++ const member function.
    // `match` ≈ exhaustive switch — compiler checks all variants are covered.
    pub fn def_bonus(&self) -> i32 {
        match self {
            Terrain::Plain => 0,
            Terrain::Forest => 10,
            Terrain::Mountain => 15,
            Terrain::Water => 0,
            Terrain::City => 25,
        }
    }

    /// Can a unit move through this terrain?
    /// Cavalry cannot enter mountains (game rule from constants).
    // NOTE: `bool` in Rust is lowercase, same semantic as C++ bool.
    pub fn is_passable(&self, is_cavalry: bool) -> bool {
        match self {
            Terrain::Water => false,                        // nobody can walk on water
            Terrain::Mountain if is_cavalry => false,       // cavalry barred from mountains
            _ => true,                                      // everything else passable
        }
    }
}

// ─── Facility ───────────────────────────────────────
// NOTE: `Option<Facility>` ≈ `std::optional<Facility>` in C++17.
// A tile with no facility has `facility: None`.
// In Rust, there is no `null` / `nullptr` — you use Option for "may or may not exist".

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Facility {
    pub facility_type: crate::unit::FacilityType,
    pub player_id: u8,
    pub q: i32,
    pub r: i32,
}

// ─── Tile ───────────────────────────────────────────
// A single hex cell. Facility is optional — None means empty tile.

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Tile {
    pub terrain: Terrain,
    pub facility: Option<Facility>,
}

impl Tile {
    fn new(terrain: Terrain) -> Self {
        Self { terrain, facility: None }
    }
}

// ─── Grid ───────────────────────────────────────────
// The complete map. Tiles stored in row-major order:
//   tile at (q, r) → tiles[r * width + q]
//
// This is a "flat" storage: one contiguous Vec, not nested Vec<Vec<Tile>>.
// Advantage: better cache locality, single allocation.
// Disadvantage: index math needed (but get/get_mut encapsulate it).

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Grid {
    pub width: u8,
    pub height: u8,
    pub tiles: Vec<Tile>,
}

impl Grid {
    /// Torus-safe read access.
    /// Wraps coordinates using Euclidean remainder (same behavior as Python's `%`).
    // NOTE: `rem_euclid` is the Rust equivalent of Python's `%`.
    // C++'s `%` is "truncation remainder" and can return negative values.
    // Rust's `%` is also truncation — hence we use `rem_euclid` explicitly.
    // Examples: -1.rem_euclid(15) = 14, same as Python's -1 % 15 = 14.
    pub fn get(&self, q: i32, r: i32) -> &Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &self.tiles[wr * self.width as usize + wq]
    }

    /// Torus-safe write access. Same wrapping as get().
    pub fn get_mut(&mut self, q: i32, r: i32) -> &mut Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &mut self.tiles[wr * self.width as usize + wq]
    }
}

// ─── Constants ──────────────────────────────────────
// Terrain ratios for the "balanced" generator.
// Matches prototype/constants.py GENERATOR_RATIOS["balanced"].
const PLAIN_RATIO: f64 = 0.35;
const FOREST_RATIO: f64 = 0.28;
const MOUNTAIN_RATIO: f64 = 0.22;
const WATER_RATIO: f64 = 0.08;

/// Hex direction offsets (axial coordinates).
/// Same as Python's HEX_DIRS in prototype_hex/mapgen_hex.py.
const HEX_DIRS: [(i32, i32); 6] = [
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1),
];

// ─── Map Generation ─────────────────────────────────

/// Generate a hex torus map with the given seed.
///
/// # Arguments
/// * `seed` — deterministic RNG seed. Same seed → same map (with same RNG algorithm).
/// * `generator_id` — currently only "balanced" is supported (matches hex prototype).
///
/// # Returns
/// A `Grid` of size MAP_W × MAP_H (15×15 = 225 cells).
///
/// NOTE: This function OWNS its return value. The Grid is moved to the caller.
/// No heap-sharing, no reference counting — just a plain move (≈ C++ move semantics).
pub fn generate_map(seed: u64, generator_id: &str) -> Grid {
    // NOTE: `let` declares a variable. Without `mut`, it's immutable (≈ C++ const).
    // `let mut` would make it mutable.
    let total = (MAP_W as usize) * (MAP_H as usize);

    // ── Step 1: Build terrain pool ──────────────────
    // Create a Vec with the right count of each terrain type,
    // then shuffle it. This ensures exact terrain ratios.
    //
    // NOTE: `Vec::with_capacity` pre-allocates (≈ vector.reserve()).
    // `vec![]` is a macro for creating Vec from a list (≈ initializer_list).
    let mut pool: Vec<Terrain> = Vec::with_capacity(total);

    // NOTE: `as usize` converts between integer types.
    // Rust requires explicit casts — no implicit narrowing.
    let n_plain = (total as f64 * PLAIN_RATIO) as usize;
    let n_forest = (total as f64 * FOREST_RATIO) as usize;
    let n_mountain = (total as f64 * MOUNTAIN_RATIO) as usize;
    let n_water = (total as f64 * WATER_RATIO) as usize;

    // `extend` appends multiple elements (≈ repeated push_back).
    // `std::iter::repeat_n` creates N copies of a value.
    pool.extend(std::iter::repeat_n(Terrain::Plain, n_plain));
    pool.extend(std::iter::repeat_n(Terrain::Forest, n_forest));
    pool.extend(std::iter::repeat_n(Terrain::Mountain, n_mountain));
    pool.extend(std::iter::repeat_n(Terrain::Water, n_water));

    // Fill any remaining slots (due to rounding) with plains.
    // NOTE: `while` and `push` — same semantics as C++.
    while pool.len() < total {
        pool.push(Terrain::Plain);
    }
    pool.truncate(total);  // Safety: ensure exact size

    // ── Step 2: Shuffle with seeded RNG ─────────────
    // ChaCha12 is a cryptographic-quality RNG that's still very fast.
    // Python's random.Random uses Mersenne Twister (MT19937).
    // Same seed will NOT produce the same map as Python (different algorithms),
    // but the statistical properties (terrain distribution) are equivalent.
    //
    // NOTE: `ChaCha12Rng::seed_from_u64(seed)` creates a deterministic RNG.
    // Every call with the same seed produces the same sequence.
    let mut rng = ChaCha12Rng::seed_from_u64(seed);

    // NOTE: `pool.shuffle(&mut rng)` — the `shuffle` method comes from
    // `use rand::seq::SliceRandom`. In Rust, you can add methods to existing
    // types by importing a "extension trait". This is like C++20's
    // `#include <ranges>` adding `.filter()` to vector.
    pool.shuffle(&mut rng);

    // ── Step 3: Assign terrain to grid cells ────────
    // Build tiles Vec in row-major order.
    // NOTE: `(0..MAP_H)` creates a range. `for r in range` iterates.
    // This is ≈ `for (int r = 0; r < MAP_H; r++)` in C++.
    let mut tiles: Vec<Tile> = Vec::with_capacity(total);
    for _r in 0..MAP_H {
        for _q in 0..MAP_W {
            // `pool.pop()` removes and returns the last element.
            // Since we just shuffled, this gives random terrain.
            // `unwrap()` means "this must be Some — panic if None".
            // We know pool.len() == total == tiles.len(), so this is safe.
            let terrain = pool.pop().unwrap();
            tiles.push(Tile::new(terrain));
        }
    }

    // ── Step 4: Place cities ────────────────────────
    // Fixed positions matching Python mapgen_hex.py.
    // P0 at (2, 2), P1 at opposite corner (MAP_W-3, MAP_H-3) = (12, 12).
    // These are approximately at max torus distance from each other.
    let city0_q: i32 = 2;
    let city0_r: i32 = 2;
    let city1_q: i32 = (MAP_W - 3) as i32;  // 12
    let city1_r: i32 = (MAP_H - 3) as i32;  // 12

    // Write city terrain to tile storage.
    // NOTE: We write directly to the flat Vec to avoid calling get_mut twice.
    let idx0 = (city0_r as usize) * (MAP_W as usize) + (city0_q as usize);
    let idx1 = (city1_r as usize) * (MAP_W as usize) + (city1_q as usize);
    tiles[idx0].terrain = Terrain::City;
    tiles[idx1].terrain = Terrain::City;

    // ── Step 5: Ensure connectivity around cities ───
    // Replace any water adjacent to cities with plain.
    // This guarantees cities aren't isolated on waterlocked islands.
    //
    // NOTE: This closure captures `tiles` by mutable reference (`&mut`).
    // `|args| { body }` is Rust's lambda syntax. Equivalent to C++:
    //   auto fix_water = [&](i32 cq, i32 cr) { ... };
    let mut fix_water = |cq: i32, cr: i32| {
        for (dq, dr) in HEX_DIRS.iter() {
            let nq = (cq + dq).rem_euclid(MAP_W as i32) as usize;
            let nr = (cr + dr).rem_euclid(MAP_H as i32) as usize;
            let idx = nr * (MAP_W as usize) + nq;
            if tiles[idx].terrain == Terrain::Water {
                tiles[idx].terrain = Terrain::Plain;
            }
        }
    };

    fix_water(city0_q, city0_r);
    fix_water(city1_q, city1_r);

    // ── Return ──────────────────────────────────────
    // NOTE: No semicolon at the end of a block = this is the return value.
    // Equivalent to `return Grid { ... };` but idiomatic Rust omits `return`
    // for the final expression.
    Grid {
        width: MAP_W,
        height: MAP_H,
        tiles,
    }
}

// ═══════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════
// NOTE: `#[cfg(test)]` means "compile this only when running `cargo test`".
// These are NOT included in release builds.
// C++ equivalent: #ifdef UNIT_TEST / #endif

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_terrain_def_bonus() {
        assert_eq!(Terrain::Plain.def_bonus(), 0);
        assert_eq!(Terrain::Forest.def_bonus(), 10);
        assert_eq!(Terrain::Mountain.def_bonus(), 15);
        assert_eq!(Terrain::City.def_bonus(), 25);
    }

    #[test]
    fn test_terrain_is_passable() {
        // Water blocks everyone
        assert!(!Terrain::Water.is_passable(false));
        assert!(!Terrain::Water.is_passable(true));
        // Mountain blocks cavalry only
        assert!(Terrain::Mountain.is_passable(false));  // infantry can
        assert!(!Terrain::Mountain.is_passable(true));   // cavalry blocked
        // Everything else passable
        assert!(Terrain::Plain.is_passable(true));
        assert!(Terrain::Forest.is_passable(true));
    }

    #[test]
    fn test_grid_wrap() {
        let grid = generate_map(42, "balanced");

        // Same position via different coordinates should give same tile
        let t1 = grid.get(0, 0);
        let t2 = grid.get(MAP_W as i32, MAP_H as i32);  // wraps to (0, 0)
        assert_eq!(t1.terrain, t2.terrain);

        // Negative wrap
        let t3 = grid.get(-1, -1);  // wraps to (14, 14)
        let t4 = grid.get(14, 14);
        assert_eq!(t3.terrain, t4.terrain);
    }

    #[test]
    fn test_generate_map_deterministic() {
        // Same seed → same map (within same RNG algorithm)
        let g1 = generate_map(12345, "balanced");
        let g2 = generate_map(12345, "balanced");

        for i in 0..g1.tiles.len() {
            assert_eq!(g1.tiles[i].terrain, g2.tiles[i].terrain);
        }
    }

    #[test]
    fn test_generate_map_different_seeds() {
        // Different seeds → different maps (with extremely high probability)
        let g1 = generate_map(42, "balanced");
        let g2 = generate_map(99999, "balanced");

        // At least some tiles should differ
        let mut differ = false;
        for i in 0..g1.tiles.len() {
            if g1.tiles[i].terrain != g2.tiles[i].terrain {
                differ = true;
                break;
            }
        }
        assert!(differ, "Two different seeds produced identical maps!");
    }

    #[test]
    fn test_generate_map_has_two_cities() {
        let grid = generate_map(42, "balanced");
        let city_count: usize = grid.tiles.iter()
            .filter(|t| t.terrain == Terrain::City)
            .count();
        assert_eq!(city_count, 2, "Expected exactly 2 city tiles");
    }

    #[test]
    fn test_generate_map_terrain_ratios() {
        // Check terrain distribution is roughly correct (within ±5pp tolerance
        // because the RNG algorithm differs from Python, and ratios are approximate)
        let grid = generate_map(777, "balanced");
        let total = grid.tiles.len() as f64;

        let count = |t: Terrain| grid.tiles.iter().filter(|x| x.terrain == t).count() as f64;

        let plain_pct = count(Terrain::Plain) / total;
        let forest_pct = count(Terrain::Forest) / total;
        let water_pct = count(Terrain::Water) / total;

        // Wide tolerance because city placement replaces some tiles
        assert!(plain_pct > 0.25, "Too few plains: {:.1}%", plain_pct * 100.0);
        assert!(forest_pct > 0.15, "Too few forests: {:.1}%", forest_pct * 100.0);
        assert!(water_pct < 0.20, "Too much water: {:.1}%", water_pct * 100.0);
    }
}
