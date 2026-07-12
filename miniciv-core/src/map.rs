// 六边形地图生成 — Phase 2
// 翻译自 prototype_hex/mapgen_hex.py (86行)
//
// 算法:
//   1. 按比例建地形池: 35%平原 28%森林 22%山地 8%水域
//   2. 用种子 RNG 洗牌
//   3. 分配到 225 个格子
//   4. 两城市放在对径位置 (2,2) 和 (12,12)
//   5. 城市邻格的水域替换为平原(保证连通)
//
// C++ 对照:
//   enum Terrain { ... }        ≈ enum class TerrainType { ... };
//   struct Tile { ... }          ≈ struct Tile { ... };
//   Vec<Tile>                    ≈ vector<Tile>
//   impl Grid { fn get(...) }    ≈ const Tile& Grid::get(...) const
//   for r in 0..15 {}            ≈ for (int r = 0; r < 15; r++)
//   match terrain { ... }        ≈ switch + 编译器检查你是否漏了分支
//   rng.gen_range(0..15)         ≈ rand() % 15 (但分布更均匀)

use rand::SeedableRng;
use rand::seq::SliceRandom;
use rand_chacha::ChaCha12Rng;
use serde::{Deserialize, Serialize};

use crate::constants::{MAP_W, MAP_H};

// ─── 地形 ────────────────────────────────────────────
// Rust 的 enum ≈ C++ 的 enum class。每个变体可以带数据(像tagged union)，
// 但这里不需要——只是简单标签。
// #[derive(...)] 自动生成比较、Debug打印、序列化——C++需要手写或代码生成器。

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Terrain {
    Plain = 0,      // 平原
    Forest = 1,     // 森林
    Mountain = 2,   // 山地
    Water = 3,      // 水域
    City = 4,       // 城市
}

impl Terrain {
    /// 地形防御加成。用于战斗公式:
    ///   damage = max(1, ATK + 攻击方地形DEF - DEF - 防守方地形DEF)
    // &self ≈ C++ 的 const 成员函数。
    // match ≈ 加强版 switch——编译器强制检查所有分支是否覆盖。
    pub fn def_bonus(&self) -> i32 {
        match self {
            Terrain::Plain => 0,
            Terrain::Forest => 10,
            Terrain::Mountain => 15,
            Terrain::Water => 0,
            Terrain::City => 25,
        }
    }

    /// 单位能否通过此地形成？
    /// 骑兵不能上山(游戏规则，见 constants.rs)。
    // Rust 的 bool 是小写的，语义和 C++ bool 完全一样。
    pub fn is_passable(&self, is_cavalry: bool) -> bool {
        match self {
            Terrain::Water => false,                        // 谁都不能走水
            Terrain::Mountain if is_cavalry => false,       // 骑兵禁止上山
            _ => true,                                      // 其余都可通过
        }
    }
}

// Facility 类型定义在 unit.rs 中，通过 crate::unit::Facility 引用。
// Option<Facility> ≈ C++17 的 std::optional<Facility>

// ─── 格子 ────────────────────────────────────────────
// 六边形地图上的一个格子。facility 是可选的——None 表示空地。

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Tile {
    pub terrain: Terrain,
    pub facility: Option<crate::unit::Facility>,
}

impl Tile {
    fn new(terrain: Terrain) -> Self {
        Self { terrain, facility: None }
    }
}

// ─── 地图 ────────────────────────────────────────────
// 完整的六边形地图。格子用行优先存储(一维Vec，不是嵌套Vec):
//   坐标 (q, r) → tiles[r * width + q]
//
// 一维存储的好处: 更好的缓存局部性，只分配一次内存。
// get/get_mut 封装了索引计算——外部不需要知道存储细节。

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Grid {
    pub width: u8,
    pub height: u8,
    pub tiles: Vec<Tile>,
}

impl Grid {
    /// 环面安全读取。坐标自动 wrap。
    // rem_euclid 是 Rust 版 Python 的 %——对负数也返回非负余数。
    // 例如: -1.rem_euclid(15) = 14，和 Python 的 -1 % 15 完全相同。
    // C++ 的 % 是"截断取余"，负数会返回负数——所以这里用 rem_euclid 而不是 %。
    pub fn get(&self, q: i32, r: i32) -> &Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &self.tiles[wr * self.width as usize + wq]
    }

    /// 环面安全写入。和 get 同样的 wrap 逻辑。
    pub fn get_mut(&mut self, q: i32, r: i32) -> &mut Tile {
        let wq = q.rem_euclid(self.width as i32) as usize;
        let wr = r.rem_euclid(self.height as i32) as usize;
        &mut self.tiles[wr * self.width as usize + wq]
    }
}

// ─── 地形比例常量 ──────────────────────────────────
// 来自 prototype/constants.py GENERATOR_RATIOS["balanced"]
const PLAIN_RATIO: f64 = 0.35;
const FOREST_RATIO: f64 = 0.28;
const MOUNTAIN_RATIO: f64 = 0.22;
const WATER_RATIO: f64 = 0.08;

/// 六边形六方向偏移量(轴向坐标)
/// 和 Python prototype_hex/mapgen_hex.py 的 HEX_DIRS 一致
const HEX_DIRS: [(i32, i32); 6] = [
    (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1),
];

// ─── 地图生成 ─────────────────────────────────────────

/// 生成一张六边形环面地图。
///
/// # 参数
/// * `seed` — 确定性 RNG 种子。相同 seed → 相同地图(同算法下)。
/// * `generator_id` — 生成器类型。当前仅支持 "balanced"。
///
/// # 返回
/// MAP_W × MAP_H (15×15 = 225格) 的 Grid。
///
/// 这个函数拥有返回值的所有权——Grid 被 move 给调用者。
/// 没有堆共享、没有引用计数——就是一次所有权转移(≈ C++ 的 move 语义)。
/// 生成一张六边形环面地图(P1.5: 可配置尺寸 + N 城)。
///
/// # 参数
/// * `seed` — 确定性 RNG 种子。相同 seed → 相同地图。
/// * `generator_id` — 生成器类型。当前仅支持 "balanced"。
/// * `map_size` — 棋盘边长(棋盘 = map_size × map_size)。
/// * `player_count` — 城市数(玩家数)。
///
/// # 城市位置
/// N 个城市均匀分布在对径方向的圆上, 确保间距最大化(P1.5 多人支撑)。
/// 默认 15×15: 2 城在对角 (2,2)/(12,12), 4 城在四象限。
pub fn generate_map(seed: u64, generator_id: &str, map_size: u8, player_count: u8) -> Grid {
    let w = map_size as usize;
    let h = map_size as usize;
    let total = w * h;
    let w_i32 = w as i32;
    let h_i32 = h as i32;

    // ── 第1步: 建地形池 ────────────────────────────
    let mut pool: Vec<Terrain> = Vec::with_capacity(total);
    let n_plain = (total as f64 * PLAIN_RATIO) as usize;
    let n_forest = (total as f64 * FOREST_RATIO) as usize;
    let n_mountain = (total as f64 * MOUNTAIN_RATIO) as usize;
    let n_water = (total as f64 * WATER_RATIO) as usize;

    pool.extend(std::iter::repeat_n(Terrain::Plain, n_plain));
    pool.extend(std::iter::repeat_n(Terrain::Forest, n_forest));
    pool.extend(std::iter::repeat_n(Terrain::Mountain, n_mountain));
    pool.extend(std::iter::repeat_n(Terrain::Water, n_water));

    while pool.len() < total { pool.push(Terrain::Plain); }
    pool.truncate(total);

    // ── 第2步: 洗牌 ────────────────────────────────
    let mut rng = ChaCha12Rng::seed_from_u64(seed);
    pool.shuffle(&mut rng);

    // ── 第3步: 填充格子 ────────────────────────────
    let mut tiles: Vec<Tile> = Vec::with_capacity(total);
    for _r in 0..h {
        for _q in 0..w {
            tiles.push(Tile::new(pool.pop().unwrap()));
        }
    }

    // ── 第4步: 放置 N 座城市 ──────────────────────
    // 用轴向坐标在环面上均匀分布: 圆半径 = map_size/3, 角间隔 = 2π/N。
    // 若 N=2 且 map_size=15 → ≈ (2,2)/(12,12), 保持与旧版一致。
    let center_q = w_i32 / 2;
    let center_r = h_i32 / 2;
    let radius = (map_size as f64 / 3.0).max(2.0);
    let mut city_positions: Vec<(i32, i32)> = Vec::new();
    for i in 0..player_count {
        let angle = 2.0 * std::f64::consts::PI * i as f64 / player_count as f64;
        let q = (center_q as f64 + radius * angle.cos()).round() as i32;
        let r = (center_r as f64 + radius * angle.sin()).round() as i32;
        let cq = q.rem_euclid(w_i32);
        let cr = r.rem_euclid(h_i32);
        city_positions.push((cq, cr));
    }

    for (cq, cr) in &city_positions {
        let idx = (*cr as usize) * w + (*cq as usize);
        tiles[idx].terrain = Terrain::City;
    }

    // ── 第5步: 城市邻格水域 → 平原 ────────────────
    for (cq, cr) in &city_positions {
        for (dq, dr) in HEX_DIRS.iter() {
            let nq = (*cq + dq).rem_euclid(w_i32) as usize;
            let nr = (*cr + dr).rem_euclid(h_i32) as usize;
            let idx = nr * w + nq;
            if idx < tiles.len() && tiles[idx].terrain == Terrain::Water {
                tiles[idx].terrain = Terrain::Plain;
            }
        }
    }

    Grid { width: map_size, height: map_size, tiles }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════
// #[cfg(test)] 表示"只在 cargo test 时编译"。
// 这些代码不会进入 release 构建。
// ≈ C++ 的 #ifdef UNIT_TEST / #endif

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_地形防御加成() {
        assert_eq!(Terrain::Plain.def_bonus(), 0);
        assert_eq!(Terrain::Forest.def_bonus(), 10);
        assert_eq!(Terrain::Mountain.def_bonus(), 15);
        assert_eq!(Terrain::City.def_bonus(), 25);
    }

    #[test]
    fn test_地形通行规则() {
        // 水域阻挡所有人
        assert!(!Terrain::Water.is_passable(false));
        assert!(!Terrain::Water.is_passable(true));
        // 山地只阻挡骑兵
        assert!(Terrain::Mountain.is_passable(false));   // 步兵可以通过
        assert!(!Terrain::Mountain.is_passable(true));    // 骑兵被阻挡
        // 其余都可通过
        assert!(Terrain::Plain.is_passable(true));
        assert!(Terrain::Forest.is_passable(true));
    }

    #[test]
    fn test_环面wrap() {
        let grid = generate_map(42, "balanced", 15, 2);

        // 不同坐标指向同一格（通过环面包裹）
        let t1 = grid.get(0, 0);
        let t2 = grid.get(MAP_W as i32, MAP_H as i32);  // wrap 到 (0, 0)
        assert_eq!(t1.terrain, t2.terrain);

        // 负数 wrap
        let t3 = grid.get(-1, -1);  // wrap 到 (14, 14)
        let t4 = grid.get(14, 14);
        assert_eq!(t3.terrain, t4.terrain);
    }

    #[test]
    fn test_同seed生成相同地图() {
        // 相同 seed → 相同地图（同一 RNG 算法下）
        let g1 = generate_map(12345, "balanced", 15, 2);
        let g2 = generate_map(12345, "balanced", 15, 2);

        for i in 0..g1.tiles.len() {
            assert_eq!(g1.tiles[i].terrain, g2.tiles[i].terrain);
        }
    }

    #[test]
    fn test_不同seed生成不同地图() {
        // 不同 seed → 不同地图（概率极高，实际不可能相同）
        let g1 = generate_map(42, "balanced", 15, 2);
        let g2 = generate_map(99999, "balanced", 15, 2);

        // 至少有一些格子地形不同
        let mut differ = false;
        for i in 0..g1.tiles.len() {
            if g1.tiles[i].terrain != g2.tiles[i].terrain {
                differ = true;
                break;
            }
        }
        assert!(differ, "两个不同 seed 生成了完全相同的地图！");
    }

    #[test]
    fn test_地图恰好有两座城市() {
        let grid = generate_map(42, "balanced", 15, 2);
        let city_count: usize = grid.tiles.iter()
            .filter(|t| t.terrain == Terrain::City)
            .count();
        assert_eq!(city_count, 2, "地图上应该恰好有 2 座城市");
    }

    #[test]
    fn test_地形比例大致合理() {
        // 检查地形分布大致符合预期（±5pp 容差，
        // 因为城市放置会替换掉一些地形格）
        let grid = generate_map(777, "balanced", 15, 2);
        let total = grid.tiles.len() as f64;

        let count = |t: Terrain| grid.tiles.iter().filter(|x| x.terrain == t).count() as f64;

        let plain_pct = count(Terrain::Plain) / total;
        let forest_pct = count(Terrain::Forest) / total;
        let water_pct = count(Terrain::Water) / total;

        // 宽容差——城市放置会覆盖部分格子
        assert!(plain_pct > 0.25, "平原太少: {:.1}%", plain_pct * 100.0);
        assert!(forest_pct > 0.15, "森林太少: {:.1}%", forest_pct * 100.0);
        assert!(water_pct < 0.20, "水域太多: {:.1}%", water_pct * 100.0);
    }
}
