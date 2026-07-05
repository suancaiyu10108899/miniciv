// Combat resolution. Fixed-damage formula.
// Translates prototype/combat.py.

use crate::unit::Unit;
use crate::map::Terrain;
use crate::constants::CAVALRY_CHARGE_BONUS;

#[derive(Debug)]
pub struct MeleeResult {
    pub att_damage: i32, pub def_damage: i32,
    pub attacker_alive: bool, pub defender_alive: bool,
}

#[derive(Debug)]
pub struct RangedResult {
    pub damage: i32, pub target_alive: bool,
}

pub fn resolve_melee(
    attacker: &mut Unit, defender: &mut Unit,
    terrain_att: Terrain, terrain_def: Terrain,
    attacker_just_charged: bool,
) -> MeleeResult {
    todo!("Phase 4: Implement melee combat")
}

pub fn resolve_ranged(
    archer: &mut Unit, target: &mut Unit, terrain_target: Terrain,
) -> RangedResult {
    todo!("Phase 4: Implement ranged combat")
}

pub fn city_occupation_damage(unit: &Unit, city: &crate::unit::City) -> i32 {
    todo!("Phase 4: Implement city occupation damage")
}
