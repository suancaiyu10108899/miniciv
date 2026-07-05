// Hex grid map generation + terrain.
// Translates prototype_hex/mapgen_hex.py.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Terrain {
    Plain = 0,
    Forest = 1,
    Mountain = 2,
    Water = 3,
    City = 4,
}

impl Terrain {
    pub fn def_bonus(&self) -> i32 {
        match self {
            Terrain::Plain => 0,
            Terrain::Forest => 10,
            Terrain::Mountain => 15,
            Terrain::Water => 0,
            Terrain::City => 25,
        }
    }

    pub fn is_passable(&self, is_cavalry: bool) -> bool {
        match self {
            Terrain::Water => false,
            Terrain::Mountain if is_cavalry => false,
            _ => true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Facility {
    pub facility_type: crate::unit::FacilityType,
    pub player_id: u8,
    pub q: i32,
    pub r: i32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Tile {
    pub terrain: Terrain,
    pub facility: Option<Facility>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Grid {
    pub width: u8,
    pub height: u8,
    pub tiles: Vec<Tile>,  // row-major: tiles[r * width + q]
}

impl Grid {
    pub fn get(&self, q: i32, r: i32) -> &Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &self.tiles[wr * self.width as usize + wq]
    }

    pub fn get_mut(&mut self, q: i32, r: i32) -> &mut Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &mut self.tiles[wr * self.width as usize + wq]
    }
}

/// Generate a hex map. Returns a Grid of size MAP_W × MAP_H.
pub fn generate_map(seed: u64, generator_id: &str) -> Grid {
    todo!("Phase 2: Implement map generation")
}

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
}
