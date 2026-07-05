// Hex grid movement: axial coords, torus wrap, distance.
// Translates prototype_hex/movement_hex.py.

use crate::constants::{MAP_W, MAP_H};

/// 6 hex directions in axial coordinates (q, r)
pub const HEX_DIRS: [(i32, i32); 6] = [
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1),
];

/// Torus wrapping for hex axial coordinates.
pub fn wrap(q: i32, r: i32) -> (i32, i32) {
    (q.rem_euclid(MAP_W as i32), r.rem_euclid(MAP_H as i32))
}

/// Torus-aware hex distance: try 9 wrapping variants, take shortest.
pub fn hex_distance(q1: i32, r1: i32, q2: i32, r2: i32) -> u8 {
    todo!("Phase 3: Implement hex distance with torus wrap")
}

/// Legal single-step moves for a unit on hex grid.
pub fn legal_moves(
    q: i32, r: i32,
    is_cavalry: bool,
    grid: &crate::map::Grid,
) -> Vec<(i32, i32)> {
    todo!("Phase 3: Implement legal moves")
}
