// 游戏配置 — M1.1(第三个 AI,一阶深度阶段)
//
// 目的: 把平衡参数从硬编码常量变成运行时可配置, 让"找平衡甜点"是跑扫描,
//       而不是手工改常量重编译。这是应对下一阶段复杂度的地基之一。
//
// ⚠️ 变更(S2 立裁判阶段, 2026-07-11 第四个 AI):
//   Default 从"历史基线(成本×1, 5T速通坏基线)"改为"一阶深度健康甜点":
//   c_line_cost_mult = 2.0, city_hp = 160(硬伤修复后重测的三方制衡甜点)。
//   动机: 让真相活在默认配置里, 不活在 CLI 魔法参数 `25 2.0 160`。
//   之前 depth.rs 写死成本×3、哨兵测试守 5T 坏基线, 都是"甜点不在默认"导致的漂移/自欺。
//   现在跑 eval/table/depth/replay 无需传参即为甜点。深化再次改变甜点时, 同步改这里。
//   数据依据: experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md(成本×2 HP160 完整矩阵)。

use serde::{Deserialize, Serialize};
use crate::constants::*;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GameConfig {
    /// 回合上限(阶梯判定触发点)。step_game 内部也读这个, 保证和外层循环一致。
    pub max_turns: u16,

    // ── 城市(军事侧杠杆: 攻城速度)──
    pub city_hp: i32,
    pub city_def: i32,
    pub city_damage: i32,       // 城市每回合对占领者的伤害
    pub city_base_food: i32,

    // ── 经济起手 ──
    pub starting_food: i32,
    pub starting_wood: i32,
    pub starting_gold: i32,
    pub starting_workers: u8,
    pub starting_scouts: u8,

    // ── 建设胜利(建设侧杠杆)──
    /// 个人建设胜利所需设施数(1v1)。默认 4。
    pub construction_require_facilities: u8,
    /// P1.5: 团队建设胜利设施门槛。0=用个人门槛, >0=队内设施合计需达此数。
    /// 2v2 推荐 6(比 2×4=8 容易, 比 4 难)。
    pub construction_team_facilities: u8,

    // ── 科技(建设速通最大杠杆)──
    /// C3 学院研究增量: has_academy 时每回合 +这个值(默认 2=减半)。设 1 = 关掉减半。
    pub academy_research_increment: u8,

    /// 科技耗时覆盖(M1.2): 覆盖特定科技的研究回合数, 空=用默认。
    /// 例: {"C5": 6} 让 C5 耗时从 2 变 6。是打破建设速通的直接杠杆。
    pub tech_turns: std::collections::HashMap<String, u8>,

    /// C线成本倍率(资源消耗杠杆): C开头科技 cost ×这个值。默认1.0。
    /// 高成本→建设者研究耗资源→挤占产防守兵的资源, 创造"研究vs产兵"张力。
    pub c_line_cost_mult: f64,

    // ── P1.5: 多人 + 团队 ──
    /// 玩家总数。默认 2(1v1)。
    pub player_count: u8,
    /// 队伍归属: teams[pid] = 队伍 ID。长度 = player_count。
    /// 默认 [0, 1] 即各自为战(1v1); 2v2 例: [0, 0, 1, 1]。
    pub teams: Vec<u8>,
    /// 棋盘尺寸(边长, 棋盘 = map_size × map_size)。默认 15。
    pub map_size: u8,

    // ── P1.5: 支持度负面维度 ──
    /// 初始支持度(0-100)。默认 50。
    pub initial_support: i32,
    /// 每战斗单位每回合支持度衰减。默认 1。0=关支持度。
    pub support_decay_per_military: i32,
    /// 支持度惩罚阈值: 支持度低于此→产出打折。默认 30。
    pub support_penalty_threshold: i32,
    /// 惩罚系数: 0.3 = 低于阈值时产出打七折。默认 0.3。
    pub support_penalty_factor: f64,
    /// 支持度过低可能触发动荡(随机掉兵/掉城HP)。默认 10。
    pub support_revolt_threshold: i32,
    /// 每扩张一次扣支持度。默认 10。
    pub expand_support_cost: i32,
    /// 扩张资源花费 (粮, 木, 金)。
    pub expand_resource_cost: (i32, i32, i32),
    /// 扩张后产出基数加成(每回合额外资源)。
    pub expand_income_bonus: i32,
    /// 设施采集产出/回合。默认 4。降低可减缓建设速度。
    pub facility_output: i32,
    /// 单位生产成本乘数。默认 1.0。提高可减缓军事扩张。
    pub unit_cost_mult: f64,

    // ── P1.5: 红白分叉 ──
    /// 从第几回合起可选择红白路线。默认 15。0=开局可选。
    pub branch_available_turn: u16,
    /// 白线产出倍率。默认 1.5(+50%)。
    pub white_output_boost: f64,
    /// 白线危机周期(回合数)。默认 12。
    pub white_crisis_interval: u8,
    /// 白线危机触发的支持度伤害。默认 25。
    pub white_crisis_support_damage: i32,
    /// 红线支持度自动回复/回合。默认 2。
    pub red_support_regen: i32,
    /// 红线组织度增长率(每点支持度/回合)。默认 0.15。
    pub red_org_per_support: f64,
    /// 西南联大: 组织度消耗。默认 50。
    pub red_lian_da_org_cost: i32,
    /// 西南联大: 瞬间完成的科技数。默认 2。
    pub red_lian_da_techs: u8,
    /// 集中力量: 下回合产出倍率。默认 3.0。
    pub red_concentrate_mult: f64,
    /// 全民皆兵: 组织度消耗。默认 40。
    pub red_mobilize_org_cost: i32,
    /// 全民皆兵: 免费产兵数。默认 3。
    pub red_mobilize_units: u8,
}

impl Default for GameConfig {
    fn default() -> Self {
        Self {
            max_turns: MAX_TURNS,
            city_hp: 160,               // S2 甜点(非 CITY_HP=80 历史基线)
            city_def: CITY_DEF,
            city_damage: CITY_DAMAGE,
            city_base_food: CITY_BASE_FOOD,
            starting_food: STARTING_FOOD,
            starting_wood: STARTING_WOOD,
            starting_gold: STARTING_GOLD,
            starting_workers: STARTING_WORKERS,
            starting_scouts: STARTING_SCOUTS,
            construction_require_facilities: CONSTRUCTION_VICTORY_REQUIRE_FACILITIES,
            construction_team_facilities: 0,  // P1.5: 默认个人门槛
            academy_research_increment: 2,
            tech_turns: std::collections::HashMap::new(),
            c_line_cost_mult: 2.0,       // S2 甜点(非 ×1 历史基线): C线科技成本×2
            player_count: 2,             // P1.5: 默认 1v1
            teams: vec![0, 1],           // P1.5: 各自为战
            map_size: 15,                // P1.5: 默认 15×15
            initial_support: 50,         // P1.5: 支持度起点
            support_decay_per_military: 1,  // P1.5: 每战斗单位每回合-1
            support_penalty_threshold: 30,  // P1.5: 低于30触发产出打折
            support_penalty_factor: 0.3,     // P1.5: 打七折
            support_revolt_threshold: 10,    // P1.5: 低于10可能动荡
            expand_support_cost: 10,         // P1.5: 扩张一次-10支持
            expand_resource_cost: (15, 15, 10),  // P1.5: 扩张花费
            expand_income_bonus: 3,
            facility_output: 4,              // P1.5: 可配置设施产出
            unit_cost_mult: 1.0,             // P1.5: 单位成本乘数
            branch_available_turn: 15,       // P1.5: 第15回合起可选红白
            white_output_boost: 1.5,         // P1.5: 白线+50%产出
            white_crisis_interval: 12,       // P1.5: 白线危机每12回合
            white_crisis_support_damage: 25, // P1.5: 危机扣25支持度
            red_support_regen: 2,            // P1.5: 红线+2支持度/回合
            red_org_per_support: 0.15,       // P1.5: 组织度=支持度×0.15/回合
            red_lian_da_org_cost: 50,        // P1.5: 联大消耗50组织度
            red_lian_da_techs: 2,            // P1.5: 联大完成2科技
            red_concentrate_mult: 3.0,       // P1.5: 集中力量×3产出
            red_mobilize_org_cost: 40,       // P1.5: 全民皆兵消耗40组织度
            red_mobilize_units: 3,           // P1.5: 全民皆兵产3兵
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::{init_game_with_config, step_game};
    use crate::ai::fixed::BuilderAgent;
    use crate::ai::random::RandomAgent;
    use crate::ai::Agent;
    use rand_chacha::ChaCha12Rng;
    use rand::SeedableRng;

    fn run_builder_vs_random(cfg: GameConfig, seed: u64) -> (u16, Option<u8>) {
        let mut gs = init_game_with_config(seed, "balanced", cfg);
        let (b, r) = (BuilderAgent, RandomAgent);
        let mut r0 = ChaCha12Rng::seed_from_u64(seed);
        let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
        let max_turns = gs.config.max_turns;
        while gs.winner.is_none() && gs.turn < max_turns {
            let a0 = b.decide(&gs, 0, &mut r0);
            let a1 = r.decide(&gs, 1, &mut r1);
            step_game(&mut gs, &a0, &a1);
        }
        (gs.turn, gs.winner)
    }

    #[test]
    fn test_默认config_是健康甜点_非5T速通() {
        // S2: 默认已从"5T速通坏基线"翻为"成本×2 HP160 健康甜点"。
        // Builder(裸建设不设防) vs Random 不该再 5T 速通——成本×2 拖慢建设。
        let (turn, winner) = run_builder_vs_random(GameConfig::default(), 50000);
        assert!(turn > 5, "默认应为健康甜点(非5T速通), 实际 {}T", turn);
        assert!(winner.is_some(), "阶梯判定保证有胜者");
    }

    #[test]
    fn test_config_确实拖慢速通() {
        // 关掉学院减半 + 设施门槛提到 8 → Builder 不该再 5T 速通
        let cfg = GameConfig {
            academy_research_increment: 1,
            construction_require_facilities: 8,
            ..GameConfig::default()
        };
        let (turn, _) = run_builder_vs_random(cfg, 50000);
        assert!(turn > 5, "拖慢参数下速通应 >5T, 实际 {}T —— 说明 config 未生效", turn);
    }
}
