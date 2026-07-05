// 六边形移动系统 — Phase 3
// 翻译自 prototype_hex/movement_hex.py (76行)
//
// 三个核心函数:
//   wrap(q, r)           — 环面坐标包裹
//   hex_distance(q1,r1, q2,r2) — 环面六边形距离(9种wrap取最短)
//   legal_moves(unit, grid)    — 单位的合法单步移动
//
// 六边形距离用 cube distance 公式:
//   给定轴向坐标 (q, r)，第三轴 s = -(q + r)（隐含）。
//   dq = |q1 - q2|, dr = |r1 - r2|, ds = |(q1+r1) - (q2+r2)|
//   distance = max(dq, dr, ds)
//
// 环面上要试 9 种 wrap 组合(每个轴 -MAP/0/+MAP)，取最短距离。
// 例如从 (14,14) 到 (1,1): 直接距离很大，但通过环面 wrap 可能只要 3 步。
//
// C++ 新概念:
//   u8, i32         — 带位宽的整数类型(和 C++ 的 uint8_t, int32_t 一样)
//   rem_euclid      — Python 风格的取余(对负数也返回非负)，不用 C++ 的 %
//   const 数组       — [类型; 长度]，编译期已知大小，栈上分配
//   pub fn          — 公开函数。不加 pub = 模块私有(≈ C++ static / 匿名 namespace)

use crate::constants::{MAP_W, MAP_H};
use crate::map::{Grid, Terrain};
use crate::unit::Unit;

/// 六边形六方向偏移量(轴向坐标 q, r)
/// 和 Python 的 HEX_DIRS 完全一致。
/// `const` 数组 = 编译期常量，栈上分配，不涉及堆。
pub const HEX_DIRS: [(i32, i32); 6] = [
    (1, 0),   // 东
    (1, -1),  // 东北
    (0, -1),  // 西北
    (-1, 0),  // 西
    (-1, 1),  // 西南
    (0, 1),   // 东南
];

/// 环面坐标包裹。
/// 把任意整数坐标映射到 [0, MAP_W) × [0, MAP_H) 范围内。
///
/// `rem_euclid` 是关键: 它和 Python 的 `%` 行为完全一致——
/// 对负数返回非负余数。C++ 的 `%` 是截断取余(负数可能返回负数)，
/// 所以这里必须用 rem_euclid 而不是 %。
///
/// 示例:
///   wrap(16, 0)  → (1, 0)   因为 16 % 15 = 1
///   wrap(-1, 0)  → (14, 0)  因为 -1.rem_euclid(15) = 14
pub fn wrap(q: i32, r: i32) -> (i32, i32) {
    (q.rem_euclid(MAP_W as i32), r.rem_euclid(MAP_H as i32))
}

/// 环面六边形距离——整个项目最关键的 15 行代码。
///
/// 算法: 对目标点尝试 9 种环面变体(每个轴: -MAP_W/0/+MAP_W)，
/// 对每种变体计算 cube distance，取最小值。
///
/// Cube distance 公式:
///   dq = |q1 - q2_wrapped|
///   dr = |r1 - r2_wrapped|
///   ds = |(q1 + r1) - (q2_wrapped + r2_wrapped)|
///   distance = max(dq, dr, ds)
///
/// 为什么需要 9 种变体? 因为在环面上，"最短路径"可能穿过地图边界。
/// 例如从 (14,2) 到 (1,2): 直接距离 = 13，但 wrap 后距离 = 2(向东走两步)。
///
/// 返回类型是 u8——距离不可能超过地图直径(约 7-8)，u8 完全够用。
pub fn hex_distance(q1: i32, r1: i32, q2: i32, r2: i32) -> u8 {
    let mut best: u8 = 255;  // 初始化为最大值，保证第一次比较就更新

    // 三层嵌套循环: 9 种 wrap 组合
    for dwq in [-1, 0, 1] {
        for dwr in [-1, 0, 1] {
            // 目标点在这种 wrap 下的坐标
            let q2w = q2 + dwq * (MAP_W as i32);
            let r2w = r2 + dwr * (MAP_H as i32);

            // Cube distance 的三个分量
            let dq = (q1 - q2w).abs();
            let dr = (r1 - r2w).abs();
            // s = q + r 是 cube coordinate 的第三轴
            let ds = ((q1 + r1) - (q2w + r2w)).abs();

            // 取三个分量的最大值
            let d = dq.max(dr).max(ds);

            // `as u8` 把 i32 转为 u8。距离不会超过 255，安全。
            let du = d as u8;
            if du < best {
                best = du;
            }
        }
    }

    best
}

/// 获取单位的合法单步移动方向。
///
/// 遍历 6 个六边形方向，过滤掉:
///   - 水域(所有单位都不能走)
///   - 骑兵不能上山
///
/// 返回合法的 (dq, dr) 方向列表。
/// 注意: 不检查目标格是否有敌方单位——那是战斗系统的事。
///
/// Vec<(i32, i32)> ≈ C++ 的 vector<pair<int, int>>
/// `moves.push((dq, dr))` 添加元素，`moves.len()` 获取长度。
pub fn legal_moves(unit: &Unit, grid: &Grid) -> Vec<(i32, i32)> {
    let mut moves = Vec::with_capacity(6);  // 预分配 6 个槽位(最大可能)

    for (dq, dr) in HEX_DIRS.iter() {
        let nq = unit.q + dq;
        let nr = unit.r + dr;
        let (wq, wr) = wrap(nq, nr);
        let tile = grid.get(wq, wr);

        // 水域不可通行
        if tile.terrain == Terrain::Water {
            continue;
        }
        // 骑兵不能上山
        if unit.unit_type == crate::unit::UnitType::Cavalry
            && tile.terrain == Terrain::Mountain
        {
            continue;
        }

        // `*dq` 解引用: iter() 返回的是 &i32，需要 * 取实际值
        moves.push((*dq, *dr));
    }

    moves
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wrap_正常坐标不变() {
        assert_eq!(wrap(0, 0), (0, 0));
        assert_eq!(wrap(7, 7), (7, 7));
        assert_eq!(wrap(14, 14), (14, 14));
    }

    #[test]
    fn test_wrap_超出边界包裹() {
        assert_eq!(wrap(15, 0), (0, 0));   // 15 % 15 = 0
        assert_eq!(wrap(0, 30), (0, 0));   // 30 % 15 = 0
        assert_eq!(wrap(16, 0), (1, 0));
    }

    #[test]
    fn test_wrap_负数包裹() {
        // 这是关键测试: 负数必须正确 wrap
        assert_eq!(wrap(-1, -1), (14, 14));
        assert_eq!(wrap(-15, -15), (0, 0));
        assert_eq!(wrap(-1, 0), (14, 0));
    }

    #[test]
    fn test_hex_distance_同一点距离为零() {
        assert_eq!(hex_distance(0, 0, 0, 0), 0);
        assert_eq!(hex_distance(7, 7, 7, 7), 0);
        assert_eq!(hex_distance(14, 14, 14, 14), 0);
    }

    #[test]
    fn test_hex_distance_相邻格子距离为一() {
        // 每个六边形方向走一步，距离应该是 1
        for (dq, dr) in HEX_DIRS.iter() {
            let q2 = 5 + dq;
            let r2 = 5 + dr;
            assert_eq!(
                hex_distance(5, 5, q2, r2),
                1,
                "方向 ({},{}) 的距离不对", dq, dr
            );
        }
    }

    #[test]
    fn test_hex_distance_直线距离() {
        // 沿 q 轴走 5 步
        assert_eq!(hex_distance(0, 0, 5, 0), 5);
        // 沿 r 轴走 3 步
        assert_eq!(hex_distance(0, 0, 0, 3), 3);
    }

    #[test]
    fn test_hex_distance_对角线() {
        // (0,0) 到 (3,3): dq=3, dr=3, ds=|0-6|=6, max=6
        assert_eq!(hex_distance(0, 0, 3, 3), 6);
        // (0,0) 到 (3,-3): dq=3, dr=3, ds=|0-0|=0, max=3
        assert_eq!(hex_distance(0, 0, 3, -3), 3);
    }

    #[test]
    fn test_hex_distance_环面包裹() {
        // 从 (14,2) 到 (1,2): 直接距离 = 13，wrap后距离应该更短
        let d = hex_distance(14, 2, 1, 2);
        assert!(d < 10, "环面距离应该通过边界缩短，实际: {}", d);
        // 通过向东 wrap，应该只要 2 步
        assert_eq!(d, 2, "(14,2) 到 (1,2) 通过环面应该 = 2 步");
    }

    #[test]
    fn test_hex_distance_确定性() {
        // 同输入必须同输出
        for _ in 0..100 {
            assert_eq!(hex_distance(5, 5, 12, 12), hex_distance(5, 5, 12, 12));
        }
    }

    #[test]
    fn test_hex_distance_对称性() {
        // A→B 的距离应该等于 B→A 的距离
        let test_points = [(0, 0), (2, 5), (14, 14), (7, 3), (1, 13)];
        for (a, b) in test_points.iter() {
            for (c, d) in test_points.iter() {
                assert_eq!(
                    hex_distance(*a, *b, *c, *d),
                    hex_distance(*c, *d, *a, *b),
                    "不对称: ({},{}) → ({},{})", a, b, c, d
                );
            }
        }
    }
}
