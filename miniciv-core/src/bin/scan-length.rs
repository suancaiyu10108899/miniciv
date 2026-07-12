// P1.5 游戏长度扫描 — 找40-60T甜点
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, StateAwareAgent, AlwaysWhiteAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::VictoryType;

fn main() {
    let seeds = 40u32;
    let sb = 95000u64;
    println!("{:>5} {:>5} {:>5} {:>8} {:>8} {:>6} {:>6} {:>6}",
             "costX", "hp", "startR", "BvR_avgT", "SvA_avgT", "BvR_Cq%", "BvR_Cs%", "BvR_Tb%");
    println!("{}", "-".repeat(62));

    let b = BuilderAgent; let r = RusherAgent;
    let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;

    for cost_mult in [2.0f64, 2.5, 3.0, 3.5] {
    for hp in [100i32, 120, 140] {
    for start_res in [25i32, 20, 15] {
        let cfg = GameConfig {
            city_hp: hp, c_line_cost_mult: cost_mult,
            starting_food: start_res, starting_wood: start_res, starting_gold: start_res,
            ..GameConfig::default()
        };
        let (mut bt, mut b_cq, mut b_cs, mut b_tb, mut bn) = (0u64,0,0,0,0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + i as u64 * 100, &b, &r, "balanced", &cfg);
            bt += g.turns as u64; bn += 1;
            match g.victory_type {
                Some(VictoryType::Conquest) => b_cq += 1,
                Some(VictoryType::Construction) => b_cs += 1,
                _ => b_tb += 1,
            }
        }
        let (mut st, mut sn) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + i as u64 * 100, &sw, &aw, "balanced", &cfg);
            st += g.turns as u64; sn += 1;
        }
        let ba = bt as f64 / bn as f64;
        let sa = st as f64 / sn as f64;
        println!("{:>5.1} {:>5} {:>5} {:>8.1} {:>8.1} {:>5.0}% {:>5.0}% {:>5.0}%",
            cost_mult, hp, start_res, ba, sa,
            b_cq as f64/bn as f64*100.0, b_cs as f64/bn as f64*100.0, b_tb as f64/bn as f64*100.0);
    }}}
}
