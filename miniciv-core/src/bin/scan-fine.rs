// P1.5 Phase C v4: 最终微调 — 目标50T, 征服40-50%, 建设40-50%
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, StateAwareAgent, AlwaysWhiteAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::VictoryType;

fn main() {
    let seeds = 60u32; let sb = 160000u64;
    println!("{:>5} {:>5} {:>5} {:>5} {:>5} {:>8} {:>8} {:>6} {:>6} {:>6}",
        "ttM", "uM", "fBT", "hp", "startR", "BvR_avgT", "SvA_avgT", "BvR_Cq%", "BvR_Cs%", "BvR_Tb%");
    println!("{}", "-".repeat(72));
    let b = BuilderAgent; let r = RusherAgent;
    let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;
    for ttM in [8.0f64, 9.0] {
    for uM in [7.0f64, 8.0, 9.0] {
    for fBT in [7u8, 8] {
    for hp in [1200i32, 1400] {
    for startR in [30i32, 35] {
        let cfg = GameConfig {
            max_turns: 200, tech_turns_mult: ttM, all_tech_cost_mult: 3.0,
            unit_cost_mult: uM, facility_build_turns: fBT,
            city_hp: hp, c_line_cost_mult: 1.0,
            starting_food: startR, starting_wood: startR, starting_gold: startR,
            facility_output: 4, starting_workers: 2, ..GameConfig::default()
        };
        let (mut bt, mut b_cq, mut b_cs, mut b_tb, mut bn) = (0u64,0,0,0,0u32);
        for i in 0..seeds {
            let g = run_one_game(sb+i as u64*100, &b, &r, "balanced", &cfg);
            bt += g.turns as u64; bn += 1;
            match g.victory_type { Some(VictoryType::Conquest)=>b_cq+=1, Some(VictoryType::Construction)=>b_cs+=1, _=>b_tb+=1 }
        }
        let (mut st, mut sn) = (0u64,0u32);
        for i in 0..seeds {
            let g = run_one_game(sb+i as u64*100, &sw, &aw, "balanced", &cfg);
            st += g.turns as u64; sn += 1;
        }
        let ba=bt as f64/bn as f64; let sa=st as f64/sn as f64;
        let cqp=b_cq as f64/bn as f64*100.0; let csp=b_cs as f64/bn as f64*100.0;
        let tbp=b_tb as f64/bn as f64*100.0;
        let avg=(ba+sa)/2.0;
        // Show balanced or long combos
        if (cqp >= 30.0 && csp >= 30.0) || avg > 45.0 {
            println!("{:>5.1} {:>5.1} {:>5} {:>5} {:>5} {:>8.1} {:>8.1} {:>5.0}% {:>5.0}% {:>5.0}%  <===",
                ttM, uM, fBT, hp, startR, ba, sa, cqp, csp, tbp);
        }
    }}}}}
}
