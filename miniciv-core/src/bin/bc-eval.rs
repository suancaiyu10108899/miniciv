// P1.5 BC快速评估: BC vs Builder/AlwaysWhite/StateAware
// 用法: cargo run --release --bin bc-eval -- [seeds]

use miniciv_core::ai::Agent;
use miniciv_core::ai::bc::BcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{AlwaysWhiteAgent, StateAwareAgent, RusherAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(100);
    let sb: u64 = 970000;

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let bc = BcAgent::from_file("../experiments/v0.10-redwhite/bc-weights.json")
        .expect("failed to load bc weights");
    let builder = BuilderAgent;
    let aw = AlwaysWhiteAgent;
    let sa = StateAwareAgent;
    let rusher = RusherAgent;

    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &builder as &dyn Agent),
        ("Rusher", &rusher as &dyn Agent),
        ("AlwaysWhite", &aw as &dyn Agent),
        ("StateAware", &sa as &dyn Agent),
    ];

    eprintln!("BC评估: {} seeds paired, C1甜点", seeds);
    println!("opponent,bc_wr%,avg_turns,cq%,cs%,tb%");

    for (name, opp) in &opps {
        let p = run_pair_par(&bc, *opp, seeds, sb, "balanced", &cfg);
        let n = (seeds * 2) as f64;
        println!("{},{:.1},{:.1},{:.0},{:.0},{:.0}",
            name, p.a_win_rate*100.0, p.avg_turns,
            p.a_win_conquest as f64/n*100.0, p.a_win_construction as f64/n*100.0, p.a_win_tiebreak as f64/n*100.0);
    }
    eprintln!("完成");
}
