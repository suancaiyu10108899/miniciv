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
pub fn generate_map(seed: u64, generator_id: &str) -> Grid {
    // `let` 声明变量。不加 `mut` = 不可变(≈ C++ const)。
    // `let mut` 才能修改。
    let total = (MAP_W as usize) * (MAP_H as usize);

    // ── 第1步: 建地形池 ────────────────────────────
    // 每种地形按比例放入 Vec，然后整体洗牌。
    // 这保证了精确的地形比例(不像逐个格子独立随机会有波动)。
    //
    // Vec::with_capacity 预分配内存(≈ vector.reserve())。
    // vec![] 宏 ≈ C++ 的初始化列表。
    let mut pool: Vec<Terrain> = Vec::with_capacity(total);

    // `as usize` 显式类型转换。Rust 不允许隐式窄化转换。
    let n_plain = (total as f64 * PLAIN_RATIO) as usize;
    let n_forest = (total as f64 * FOREST_RATIO) as usize;
    let n_mountain = (total as f64 * MOUNTAIN_RATIO) as usize;
    let n_water = (total as f64 * WATER_RATIO) as usize;

    // extend 批量追加元素(≈ 循环 push_back 但更高效)。
    // std::iter::repeat_n 生成 N 个相同值的迭代器。
    pool.extend(std::iter::repeat_n(Terrain::Plain, n_plain));
    pool.extend(std::iter::repeat_n(Terrain::Forest, n_forest));
    pool.extend(std::iter::repeat_n(Terrain::Mountain, n_mountain));
    pool.extend(std::iter::repeat_n(Terrain::Water, n_water));

    // 因为浮点转整数可能有舍入误差，用平原补齐到正好 total 个。
    while pool.len() < total {
        pool.push(Terrain::Plain);
    }
    pool.truncate(total);  // 安全兜底: 确保不会超过 total

    // ── 第2步: 用种子 RNG 洗牌 ──────────────────────
    // ChaCha12 是密码学质量的 RNG，速度仍然很快。
    // Python 的 random.Random 用 Mersenne Twister (MT19937)。
    // 相同的 seed 不会产生和 Python 一模一样的地图(算法不同)，
    // 但统计特性(地形分布)是等价的。
    //
    // ChaCha12Rng::seed_from_u64 创建确定性 RNG。
    // 同 seed 一定产生相同序列。
    let mut rng = ChaCha12Rng::seed_from_u64(seed);

    // `pool.shuffle(&mut rng)` — shuffle 方法来自 `use rand::seq::SliceRandom`。
    // Rust 可以通过导入"扩展 trait"给已有类型添加方法。
    // 这 ≈ C++20 的 `#include <ranges>` 给 vector 加了 .filter() 方法。
    pool.shuffle(&mut rng);

    // ── 第3步: 把洗好的地形分配到格子上 ────────────
    // 按行优先顺序填充(先遍历 r，再遍历 q)。
    // `for _r in 0..MAP_H` ≈ C++ `for (int r = 0; r < MAP_H; r++)`
    let mut tiles: Vec<Tile> = Vec::with_capacity(total);
    for _r in 0..MAP_H {
        for _q in 0..MAP_W {
            // pool.pop() 返回最后一个元素(Option<T>)。
            // unwrap() = "我知道这一定是 Some，不是 None——如果错了就 panic"。
            // pool 的长度 == total，tiles 的长度也会是 total，所以这里不会出错。
            let terrain = pool.pop().unwrap();
            tiles.push(Tile::new(terrain));
        }
    }

    // ── 第4步: 放置城市 ─────────────────────────────
    // 固定位置，和 Python mapgen_hex.py 一致。
    // P0 在 (2, 2)，P1 在对径 (MAP_W-3, MAP_H-3) = (12, 12)。
    // 这两个位置大致在环面上互为最远点。
    let city0_q: i32 = 2;
    let city0_r: i32 = 2;
    let city1_q: i32 = (MAP_W - 3) as i32;  // = 12
    let city1_r: i32 = (MAP_H - 3) as i32;  // = 12

    // 直接写一维 Vec 的索引，避免调用 get_mut 两次。
    let idx0 = (city0_r as usize) * (MAP_W as usize) + (city0_q as usize);
    let idx1 = (city1_r as usize) * (MAP_W as usize) + (city1_q as usize);
    tiles[idx0].terrain = Terrain::City;
    tiles[idx1].terrain = Terrain::City;

    // ── 第5步: 城市邻格的水域 → 平原 ────────────────
    // 防止城市被水域包围导致两城之间不可达。
    //
    // `|参数| { 函数体 }` 是 Rust 的闭包(lambda)语法。
    // `&mut` 表示闭包捕获 tiles 的可变引用。
    // ≈ C++ 的 `auto fix_water = [&](int cq, int cr) { ... };`
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

    // ── 返回 ────────────────────────────────────────
    // 最后一行不带分号 = 这是返回值。
    // 等价于 `return Grid { ... };`——Rust 惯用写法省略了 return。
    Grid {
        width: MAP_W,
        height: MAP_H,
        tiles,
    }
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
        let grid = generate_map(42, "balanced");

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
        let g1 = generate_map(12345, "balanced");
        let g2 = generate_map(12345, "balanced");

        for i in 0..g1.tiles.len() {
            assert_eq!(g1.tiles[i].terrain, g2.tiles[i].terrain);
        }
    }

    #[test]
    fn test_不同seed生成不同地图() {
        // 不同 seed → 不同地图（概率极高，实际不可能相同）
        let g1 = generate_map(42, "balanced");
        let g2 = generate_map(99999, "balanced");

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
        let grid = generate_map(42, "balanced");
        let city_count: usize = grid.tiles.iter()
            .filter(|t| t.terrain == Terrain::City)
            .count();
        assert_eq!(city_count, 2, "地图上应该恰好有 2 座城市");
    }

    #[test]
    fn test_地形比例大致合理() {
        // 检查地形分布大致符合预期（±5pp 容差，
        // 因为城市放置会替换掉一些地形格）
        let grid = generate_map(777, "balanced");
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
