// 策略级搜索 AI — M3-A(第三个 AI)
//
// 最小起步(先A后B): 不做完整 MCTS(动作空间爆炸), 而是"策略级 rollout"。
// 候选策略 = 现有探针当基元(Builder/Rusher/CavRusher/Defender)。
// 每回合: 对每个候选策略, 用它 rollout 到结束 vs 若干参考对手, 取最坏结果(minimax),
//         选"最坏情况最好"的策略执行这一步。
//
// 意义: 比固定探针和两态 Adaptive 强(用实际 rollout 选择, 不受手写规则局限)。
// 若它在甜点带找不到某个始终最优的策略、被迫应变 → 一阶深度信号更硬。
// 若它锁定某个策略碾压 → 暴露残留支配。

use crate::game::{GameState, step_game};
use crate::ai::{Action, Agent};
use crate::ai::fixed::BuilderAgent;
use crate::ai::probes::{RusherAgent, CavalryRusherAgent, DefenderAgent};
use rand_chacha::ChaCha12Rng;
use rand::{RngCore, SeedableRng};

pub struct SearchAgent;

/// 从当前状态 rollout 到结束, 返回 pid 视角评分(1胜/0负/0.5平)。
/// 我方用 `my`, 对手用 `opp`。确定性(seed 派生自局面)。
fn rollout(start: &GameState, pid: u8, my: &dyn Agent, opp: &dyn Agent) -> f64 {
    let mut g = start.clone();
    let mut r0 = ChaCha12Rng::seed_from_u64(g.seed ^ 0xA5A5 ^ g.turn as u64);
    let mut r1 = ChaCha12Rng::seed_from_u64(g.seed ^ 0x5A5A ^ g.turn as u64);
    let mt = g.config.max_turns;
    while g.winner.is_none() && g.turn < mt {
        let (a0, a1) = if pid == 0 {
            (my.decide(&g, 0, &mut r0), opp.decide(&g, 1, &mut r1))
        } else {
            (opp.decide(&g, 0, &mut r0), my.decide(&g, 1, &mut r1))
        };
        step_game(&mut g, &a0, &a1);
    }
    match g.winner {
        Some(w) if w == pid => 1.0,
        Some(_) => 0.0,
        None => 0.5,
    }
}

/// 评估当前局面下每个候选策略的 minimax 评分(对最坏参考对手的结果)。
/// 供 SearchAgent 决策 + 深度分析(评分分布/决策分叉)用。
pub fn evaluate_strategies(gs: &GameState, pid: u8) -> Vec<(&'static str, f64)> {
    let builder = BuilderAgent;
    let rusher = RusherAgent;
    let cav = CavalryRusherAgent;
    let def = DefenderAgent;
    let strats: [(&'static str, &dyn Agent); 4] =
        [("Builder", &builder), ("Rusher", &rusher), ("CavRusher", &cav), ("Defender", &def)];
    let opp_b = BuilderAgent;
    let opp_r = RusherAgent;
    let opps: [&dyn Agent; 2] = [&opp_b, &opp_r];

    strats.iter().map(|(name, s)| {
        let mut worst = f64::MAX;
        for o in &opps {
            worst = worst.min(rollout(gs, pid, *s, *o));
        }
        (*name, worst)
    }).collect()
}

impl Agent for SearchAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let scores = evaluate_strategies(gs, pid);
        let best = scores.iter().enumerate()
            .max_by(|a, b| a.1.1.partial_cmp(&b.1.1).unwrap())
            .map(|(i, _)| i).unwrap_or(0);
        let builder = BuilderAgent;
        let rusher = RusherAgent;
        let cav = CavalryRusherAgent;
        let def = DefenderAgent;
        match best {
            0 => builder.decide(gs, pid, rng),
            1 => rusher.decide(gs, pid, rng),
            2 => cav.decide(gs, pid, rng),
            _ => def.decide(gs, pid, rng),
        }
    }

    fn name(&self) -> &str { "Search" }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::game::init_game_with_config;
    use crate::config::GameConfig;
    use crate::ai::probes::RusherAgent;

    #[test]
    fn test_search_单局可跑完() {
        // S2: 用默认配置(已=甜点 成本×2 HP160), 不再写死。
        let cfg = GameConfig::default();
        let mut gs = init_game_with_config(50000, "balanced", cfg);
        let s = SearchAgent;
        let r = RusherAgent;
        let mut r0 = ChaCha12Rng::seed_from_u64(1);
        let mut r1 = ChaCha12Rng::seed_from_u64(2);
        // 只跑几回合(rollout 慢), 确认不 panic
        for _ in 0..3 {
            if gs.winner.is_some() { break; }
            let a0 = s.decide(&gs, 0, &mut r0);
            let a1 = r.decide(&gs, 1, &mut r1);
            step_game(&mut gs, &a0, &a1);
        }
        assert!(gs.turn >= 3 || gs.winner.is_some());
    }
}
