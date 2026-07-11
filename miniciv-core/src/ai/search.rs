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

impl Agent for SearchAgent {
    fn decide(&self, gs: &GameState, pid: u8, rng: &mut dyn RngCore) -> Vec<Action> {
        let builder = BuilderAgent;
        let rusher = RusherAgent;
        let cav = CavalryRusherAgent;
        let def = DefenderAgent;
        let strats: [&dyn Agent; 4] = [&builder, &rusher, &cav, &def];
        // 参考对手: 建设威胁 + 军事威胁(minimax 对这两种都要稳)
        let opp_b = BuilderAgent;
        let opp_r = RusherAgent;
        let opps: [&dyn Agent; 2] = [&opp_b, &opp_r];

        let mut best_i = 0usize;
        let mut best_score = f64::MIN;
        for (i, s) in strats.iter().enumerate() {
            let mut worst = f64::MAX;
            for o in &opps {
                worst = worst.min(rollout(gs, pid, *s, *o));
            }
            if worst > best_score {
                best_score = worst;
                best_i = i;
            }
        }
        strats[best_i].decide(gs, pid, rng)
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
        // 甜点带 config
        let cfg = GameConfig { c_line_cost_mult: 3.0, city_hp: 160, ..GameConfig::default() };
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
