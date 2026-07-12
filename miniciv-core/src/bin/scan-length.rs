// P1.5 游戏长度扫描 — facility_output + starting_res + cost_mult + city_hp
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, StateAwareAgent, AlwaysWhiteAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::VictoryType;

fn main() {
    let seeds = 40u32; let sb = 95000u64;
    println!("{:>5} {:>5} {:>5} {:>5} {:>8} {:>8} {:>6} {:>6} {:>6}",
             "fOut", "startR", "costX", "hp", "BvR_avgT", "SvA_avgT", "BvR_Cq%", "BvR_Cs%", "BvR_Tb%");
    println!("{}", "-".repeat(68));

    let b = BuilderAgent; let r = RusherAgent;
    let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;

    for fout in [2i32, 3, 4] {
    for start_res in [10i32, 15, 20, 25] {
    for cost_mult in [2.0f64, 2.5, 3.0] {
    for hp in [100i32, 120] {
        let cfg = GameConfig {
            facility_output: fout,
            starting_food: start_res, starting_wood: start_res, starting_gold: start_res,
            c_line_cost_mult: cost_mult, city_hp: hp,
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
        let cqp = b_cq as f64 / bn as f64 * 100.0;
        let csp = b_cs as f64 / bn as f64 * 100.0;
        let tbp = b_tb as f64 / bn as f64 * 100.0;
        // Show all results — find the absolute longest games
        {
            println!("{:>5} {:>5} {:>5.1} {:>5} {:>8.1} {:>8.1} {:>5.0}% {:>5.0}% {:>5.0}%",
                fout, start_res, cost_mult, hp, ba, sa, cqp, csp, tbp);
        }
    }}}}
}
