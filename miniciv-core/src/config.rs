// 游戏配置 — M1.1(第三个 AI,一阶深度阶段)
//
// 目的: 把平衡参数从硬编码常量变成运行时可配置, 让"找平衡甜点"是跑扫描,
//       而不是手工改常量重编译。这是应对下一阶段复杂度的地基之一。
//
// 原则: Default = 当前 constants.rs 锁定值 → 行为完全不变。
//       本轮(M1.1)只接线速通/军事平衡最相关的杠杆; 科技树 turns/cost 的
//       完整覆盖放 M1.2(见 tech.rs)。

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
    pub construction_require_facilities: u8,

    // ── 科技(建设速通最大杠杆)──
    /// C3 学院研究增量: has_academy 时每回合 +这个值(默认 2=减半)。设 1 = 关掉减半。
    pub academy_research_increment: u8,
}

impl Default for GameConfig {
    fn default() -> Self {
        Self {
            max_turns: MAX_TURNS,
            city_hp: CITY_HP,
            city_def: CITY_DEF,
            city_damage: CITY_DAMAGE,
            city_base_food: CITY_BASE_FOOD,
            starting_food: STARTING_FOOD,
            starting_wood: STARTING_WOOD,
            starting_gold: STARTING_GOLD,
            starting_workers: STARTING_WORKERS,
            starting_scouts: STARTING_SCOUTS,
            construction_require_facilities: CONSTRUCTION_VICTORY_REQUIRE_FACILITIES,
            academy_research_increment: 2,
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
    fn test_默认config_行为不变_5T速通() {
        let (turn, winner) = run_builder_vs_random(GameConfig::default(), 50000);
        assert_eq!(turn, 5, "默认 config 应保持当前行为(5T 速通)");
        assert_eq!(winner, Some(0));
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
