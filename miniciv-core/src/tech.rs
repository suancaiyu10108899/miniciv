// 科技树 — Phase 5
// 翻译自 prototype/tech.py (127行)
//
// 13 节点 DAG，三线并行:
//   M 线(军事): M1 → M2/M3 → M4
//   E 线(经济): E1 → E2/E3 → E4
//   C 线(建设): C1 → C2/C3 → C4 → C5(建设胜利)
//
// OR 前置(满足任一即可): M4(M2或M3), C4(C2或C3), E4(E2或E3)
// AND 前置(全部满足):  C5(C3且C4)
// 默认 AND:           其余所有节点
//
// C3 学院效果: 研究速度翻倍(每回合 +2 ticks 而非 +1)
//
// Rust 新概念:
//   HashSet<String>              — ≈ C++ std::unordered_set<string>
//   Option<String>               — "可能没有在研究的科技"
//   self.completed.iter().any(|c| c ==)    — ≈ C++ set.count() 或 set.contains()(C++20)

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

// ─── 科技节点定义 ────────────────────────────────────
// 每个节点: (科技ID, 花费(粮,木,金), 研究回合数, 前置列表, 效果描述)

#[derive(Clone, Debug)]
struct TechNode {
    id: &'static str,
    cost: (i32, i32, i32),
    turns: u8,
    requires: &'static [&'static str],  // 前置科技列表。空列表 = 无前置。
    /// 前置逻辑: And(全部满足) 或 Or(满足任一)
    req_type: RequireType,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum RequireType {
    All,  // 全部前置都完成
    Any,  // 任一前置完成即可
}

// 全部 13 个科技节点的定义(静态数组——避免运行时分配)。
// 和 Python TECH_TREE 字典完全对应。
// `&'static [TechNode]` = 编译期确定的切片引用，永不失效。
static ALL_NODES: &[TechNode] = &[
    // M 线 — 军事
    TechNode { id: "M1", cost: (8, 3, 0),  turns: 1, requires: &[],          req_type: RequireType::All },
    TechNode { id: "M2", cost: (10, 0, 8), turns: 1, requires: &["M1"],       req_type: RequireType::All },
    TechNode { id: "M3", cost: (8, 8, 3),  turns: 1, requires: &["M1"],       req_type: RequireType::All },
    TechNode { id: "M4", cost: (15, 0, 10),turns: 2, requires: &["M2","M3"],  req_type: RequireType::Any },  // M2 或 M3
    // E 线 — 经济
    TechNode { id: "E1", cost: (3, 0, 0),  turns: 1, requires: &[],          req_type: RequireType::All },
    TechNode { id: "E2", cost: (0, 3, 0),  turns: 1, requires: &["E1"],       req_type: RequireType::All },
    TechNode { id: "E3", cost: (5, 0, 3),  turns: 1, requires: &["E1"],       req_type: RequireType::All },
    TechNode { id: "E4", cost: (8, 8, 0),  turns: 1, requires: &["E2","E3"],  req_type: RequireType::Any },  // E2 或 E3
    // C 线 — 建设
    TechNode { id: "C1", cost: (5, 5, 3),  turns: 1, requires: &[],          req_type: RequireType::All },
    TechNode { id: "C2", cost: (4, 6, 0),  turns: 1, requires: &["C1"],       req_type: RequireType::All },
    TechNode { id: "C3", cost: (5, 5, 5),  turns: 2, requires: &["C1"],       req_type: RequireType::All },
    TechNode { id: "C4", cost: (6, 3, 3),  turns: 1, requires: &["C2","C3"],  req_type: RequireType::Any },  // C2 或 C3
    TechNode { id: "C5", cost: (3, 3, 3),  turns: 2, requires: &["C3","C4"],  req_type: RequireType::All },  // C3 且 C4 — 建设胜利
];

/// 根据 ID 查找科技节点
fn find_node(id: &str) -> Option<&'static TechNode> {
    ALL_NODES.iter().find(|n| n.id == id)
}

// ─── 科技管理器 ──────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TechManager {
    pub player_id: u8,
    pub completed: HashSet<String>,
    pub researching: Option<String>,
    pub research_ticks: u8,
    pub has_academy: bool,
    /// C3 学院研究增量(M1.1 可配置): has_academy 时每回合 +这个值。默认 2=减半。
    #[serde(default = "default_academy_increment")]
    pub academy_increment: u8,
    /// 科技耗时覆盖(M1.2): 覆盖特定科技的 turns, 空=用 ALL_NODES 默认。
    #[serde(default)]
    pub turns_override: std::collections::HashMap<String, u8>,
    /// C线成本倍率(资源消耗杠杆): C开头科技的 cost ×这个值。默认1.0。
    #[serde(default = "default_cost_mult")]
    pub c_line_cost_mult: f64,
    /// P1.5深度: 全局科技成本乘数(和c_line_cost_mult乘性叠加)。
    #[serde(default = "default_cost_mult")]
    pub all_tech_cost_mult: f64,
    /// P1.5深度: 全局科技回合乘数。
    #[serde(default = "default_cost_mult")]
    pub tech_turns_mult: f64,
}

fn default_cost_mult() -> f64 { 1.0 }

fn default_academy_increment() -> u8 { 2 }

impl TechManager {
    pub fn new(player_id: u8) -> Self {
        Self {
            player_id,
            completed: HashSet::new(),
            researching: None,
            research_ticks: 0,
            has_academy: false,
            academy_increment: default_academy_increment(),
            turns_override: std::collections::HashMap::new(),
            c_line_cost_mult: 1.0,
            all_tech_cost_mult: 1.0,
            tech_turns_mult: 1.0,
        }
    }

    /// 当前可以开始研究的科技列表。
    pub fn available_to_research(&self) -> Vec<String> {
        let mut available = Vec::new();
        for node in ALL_NODES.iter() {
            if self.completed.iter().any(|c| c == node.id) {
                continue;
            }
            if self.researching.as_deref() == Some(node.id) {
                continue;
            }
            if self.requirements_met(node) {
                available.push(node.id.to_string());
            }
        }
        available
    }

    /// 检查某科技节点的前置条件是否满足。
    fn requirements_met(&self, node: &TechNode) -> bool {
        if node.requires.is_empty() {
            return true;  // 无前置，总是可研究
        }
        match node.req_type {
            RequireType::All => {
                // 全部前置都完成
                node.requires.iter().all(|&r| self.completed.iter().any(|c| c ==r))
            }
            RequireType::Any => {
                // 任一前置完成即可
                node.requires.iter().any(|&r| self.completed.iter().any(|c| c ==r))
            }
        }
    }

    /// 开始研究一项科技。返回 true 表示成功。
    /// 前置: 科技槽空闲 + 该科技未完成 + 前置满足。
    /// 只接受已知科技 ID(ALL_NODES 中的 static str)。
    pub fn start_research(&mut self, tech_id: &str) -> bool {
        if self.researching.is_some() {
            return false;  // 槽位被占
        }
        // 找对应节点——同时验证 tech_id 是已知科技
        let node = match find_node(tech_id) {
            Some(n) => n,
            None => return false,  // 未知科技 ID
        };
        if self.completed.iter().any(|c| c ==node.id) {
            return false;  // 已经完成了
        }
        if !self.requirements_met(node) {
            return false;
        }

        self.researching = Some(node.id.to_string());
        self.research_ticks = 0;
        true
    }

    /// 研究推进 1 回合。
    /// 返回完成的科技 ID(如果本回合完成了)，或 None(研究中/无研究)。
    ///
    /// C3 学院: has_academy=true 时每回合 +2 ticks。
    pub fn tick_research(&mut self) -> Option<String> {
        let tech_id = self.researching.as_ref()?;  // ? = 没有在研究就返回 None

        // 研究速度: 有学院 → +academy_increment(默认2), 没有 → +1
        let increment: u8 = if self.has_academy { self.academy_increment } else { 1 };
        self.research_ticks += increment;

        // 找到对应节点获取所需回合数(M1.2: turns_override 可覆盖)
        let node = find_node(tech_id)?;
        let base_required = self.turns_override.get(tech_id.as_str()).copied().unwrap_or(node.turns);
        let required = (base_required as f64 * self.tech_turns_mult).ceil() as u8;
        if self.research_ticks >= required {
            // 研究完成！
            let completed_id = self.researching.take().unwrap();
            // C3 学院效果: 完成后解锁加速研究(先检查再插入——insert 会 move)
            let is_c3 = completed_id == "C3";
            self.completed.insert(completed_id.clone());
            self.research_ticks = 0;

            if is_c3 {
                self.has_academy = true;
            }

            Some(completed_id)
        } else {
            None
        }
    }

    /// 获取当前所有已完成科技的加成汇总。
    /// 用于战斗/经济计算时查询。
    pub fn get_tech_bonuses(&self) -> TechBonuses {
        let mut b = TechBonuses::default();

        if self.completed.iter().any(|c| c =="M1") {
            b.infantry_atk = 5;
            b.archer_atk = 5;
        }
        if self.completed.iter().any(|c| c =="M2") {
            b.cavalry_charge = 5;
        }
        if self.completed.iter().any(|c| c =="M3") {
            b.infantry_def_forest_mountain = 10;
        }
        if self.completed.iter().any(|c| c =="M4") {
            b.all_hp = 10;
        }
        if self.completed.iter().any(|c| c =="E1") {
            b.farm_bonus = 1;
        }
        if self.completed.iter().any(|c| c =="E2") {
            b.lumbermill_bonus = 1;
        }
        if self.completed.iter().any(|c| c =="E3") {
            b.mine_bonus = 1;
        }
        if self.completed.iter().any(|c| c =="E4") {
            b.worker_speed = 1;
        }
        if self.completed.iter().any(|c| c =="C2") {
            b.city_hp = 30;
        }
        if self.completed.iter().any(|c| c =="C4") {
            b.city_food = 2;
        }

        b
    }

    /// 建设线完成数(C1-C5)，用于阶梯判定。
    pub fn construction_count(&self) -> u8 {
        let c_techs = ["C1", "C2", "C3", "C4", "C5"];
        c_techs.iter().filter(|&t| self.completed.iter().any(|c| c ==t)).count() as u8
    }

    /// 获取科技花费。
    pub fn tech_cost(tech_id: &str) -> Option<(i32, i32, i32)> {
        find_node(tech_id).map(|n| n.cost)
    }

    /// 有效花费(应用 C线成本倍率 + 全局成本倍率)。game 扣费用这个。
    pub fn cost_of(&self, tech_id: &str) -> Option<(i32, i32, i32)> {
        let base = Self::tech_cost(tech_id)?;
        let mut m = self.all_tech_cost_mult;
        if tech_id.starts_with('C') && (self.c_line_cost_mult - 1.0).abs() > 1e-9 {
            m *= self.c_line_cost_mult;
        }
        if (m - 1.0).abs() < 1e-9 {
            Some(base)
        } else {
            Some(((base.0 as f64 * m).ceil() as i32,
                  (base.1 as f64 * m).ceil() as i32,
                  (base.2 as f64 * m).ceil() as i32))
        }
    }
}

// ─── 科技加成汇总 ────────────────────────────────────

/// 当前所有已完成科技的加成效果。
/// 传递给战斗/经济系统查询。
#[derive(Clone, Debug, Default)]
pub struct TechBonuses {
    pub infantry_atk: i32,
    pub archer_atk: i32,
    pub cavalry_charge: i32,
    pub infantry_def_forest_mountain: i32,
    pub all_hp: i32,
    pub farm_bonus: i32,
    pub lumbermill_bonus: i32,
    pub mine_bonus: i32,
    pub worker_speed: i32,
    pub city_hp: i32,
    pub city_food: i32,
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_初始无科技完成() {
        let tm = TechManager::new(0);
        assert!(tm.completed.is_empty());
        assert!(tm.researching.is_none());
    }

    #[test]
    fn test_无前置科技可直接研究() {
        let mut tm = TechManager::new(0);
        // M1 无前置，可以直接开始
        assert!(tm.start_research("M1"));
        assert_eq!(tm.researching.as_deref(), Some("M1"));
    }

    #[test]
    fn test_研究槽被占时不能开始新研究() {
        let mut tm = TechManager::new(0);
        assert!(tm.start_research("M1"));
        assert!(!tm.start_research("E1"));  // 槽被 M1 占了
    }

    #[test]
    fn test_前置未完成时不能研究() {
        let mut tm = TechManager::new(0);
        // M2 需要 M1 前置，但 M1 还没完成
        assert!(!tm.start_research("M2"));
    }

    #[test]
    fn test_完成研究后自动解锁后续() {
        let mut tm = TechManager::new(0);

        // 研究 M1(1回合)
        tm.start_research("M1");
        let result = tm.tick_research();
        assert_eq!(result.as_deref(), Some("M1"));  // 本回合完成
        assert!(tm.completed.contains("M1"));

        // M1 完成后，M2 应该可以研究了
        assert!(tm.start_research("M2"));
    }

    #[test]
    fn test_M4需要M2或M3_二者都无时不可研究() {
        let mut tm = TechManager::new(0);
        // 先完成 M1
        tm.start_research("M1");
        tm.tick_research();

        // M4 需要 M2 或 M3，都没完成 → 不可研究
        assert!(!tm.start_research("M4"));
    }

    #[test]
    fn test_M4需要M2或M3_完成M2后即可() {
        let mut tm = TechManager::new(0);
        // M1 → M2
        tm.start_research("M1"); tm.tick_research();
        tm.start_research("M2"); tm.tick_research();
        assert!(tm.completed.contains("M2"));

        // M4 前置: M2 或 M3 → M2 已完成，应可研究
        assert!(tm.start_research("M4"));
    }

    #[test]
    fn test_C3学院加速研究() {
        let mut tm = TechManager::new(0);
        // C1 → C3(需要2回合)
        tm.start_research("C1"); tm.tick_research();  // C1 完成
        tm.start_research("C3");

        // 第一 tick: has_academy=false → +1 tick
        let r1 = tm.tick_research();
        assert!(r1.is_none());  // 1/2，未完成

        // 第二 tick: 仍在研究 C3 中... 但现在有 academy 了吗? 不——
        // C3 还没完成，has_academy 还是 false，所以还是 +1
        // 第三 tick 才能完成（因为 turns=2, +1/tick, 需要 2 ticks）
        // 等等，是 2 回合，每 tick +1 = 正好 2 ticks 完成

        // 修正: has_academy 在 C3 完成之后才设为 true
        // 所以 C3 本身不受加速影响(需要正好 2 ticks)
        assert!(!tm.has_academy);
        let r2 = tm.tick_research();
        assert_eq!(r2.as_deref(), Some("C3"));  // C3 完成
        assert!(tm.has_academy);  // 学院生效

        // C3 完成后，研究 C4(1回合)，但学院加速 = 1 tick 完成
        tm.start_research("C4");
        let r3 = tm.tick_research();  // has_academy=true → +2 ticks
        assert_eq!(r3.as_deref(), Some("C4"));  // 1 回合完成(加速后)
    }

    #[test]
    fn test_C5需要C3且C4() {
        let mut tm = TechManager::new(0);
        // C1 → C3
        tm.start_research("C1"); tm.tick_research();
        tm.start_research("C3");
        tm.tick_research();  // 1/2
        tm.tick_research();  // 2/2 C3 完成

        // C5 需要 C3 且 C4，C4 还没完成 → 不可研究
        assert!(!tm.start_research("C5"));

        // 完成 C4
        tm.start_research("C4"); tm.tick_research();  // 学院加速 1tick 完成
        assert!(tm.completed.contains("C4"));

        // 现在 C3 且 C4 都完成了
        assert!(tm.start_research("C5"));
    }

    #[test]
    fn test_建设计数() {
        let mut tm = TechManager::new(0);
        assert_eq!(tm.construction_count(), 0);

        // C1 → C2 → C3
        tm.start_research("C1"); tm.tick_research();
        tm.start_research("C2"); tm.tick_research();
        tm.start_research("C3");
        tm.tick_research(); tm.tick_research();  // C3 2turns
        assert_eq!(tm.construction_count(), 3);  // C1, C2, C3
    }

    #[test]
    fn test_科技加成_M1() {
        let mut tm = TechManager::new(0);
        tm.start_research("M1"); tm.tick_research();
        let b = tm.get_tech_bonuses();
        assert_eq!(b.infantry_atk, 5);
        assert_eq!(b.archer_atk, 5);
        assert_eq!(b.cavalry_charge, 0);  // M2 没完成
    }

    #[test]
    fn test_未知科技ID() {
        let mut tm = TechManager::new(0);
        assert!(!tm.start_research("NONEXISTENT"));
        assert_eq!(TechManager::tech_cost("NONEXISTENT"), None);
    }
}
