// P1.5 Phase 4: FlatMC 深度打表 — 流式写盘版
// 每完成一对(depth, opponent)立即写入CSV, 中断不丢已跑数据。
// 用法: cargo run --release --bin judge-sweep -- [seeds] [seed_base]
// 默认: 20 seeds, depth 2/3/4/5/6/8 × 10 opponents

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, CavalryRusherAgent, DefenderAgent, AdaptiveAgent,
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
};
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(20);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(900000);

    // C1甜点(不改!)
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let depths: [u16; 6] = [2, 3, 4, 5, 6, 8];
    let builder = BuilderAgent; let rusher = RusherAgent; let cav = CavalryRusherAgent;
    let def = DefenderAgent; let adaptive = AdaptiveAgent; let random = RandomAgent;
    let aw = AlwaysWhiteAgent; let ar = AlwaysRedAgent; let sa = StateAwareAgent; let ttr = TankThenRedAgent;

    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &builder as &dyn Agent), ("Rusher", &rusher as &dyn Agent),
        ("CavRusher", &cav as &dyn Agent), ("Defender", &def as &dyn Agent),
        ("Adaptive", &adaptive as &dyn Agent), ("Random", &random as &dyn Agent),
        ("AlwaysWhite", &aw as &dyn Agent), ("AlwaysRed", &ar as &dyn Agent),
        ("StateAware", &sa as &dyn Agent), ("TankThenRed", &ttr as &dyn Agent),
    ];

    let total = depths.len() * opps.len();
    eprintln!("FlatMC: {} depths × {} opps × {} seeds = {} games, C1甜点(不改)", depths.len(), opps.len(), seeds, total as u64 * seeds as u64 * 2);

    // CSV header + flush
    println!("depth,opponent,flatmc_wr%,avg_turns,conquest%,construction%,tiebreak%");
    std::io::stdout().flush().ok();

    // 串行执行(确保每完成一个就输出一个, 不乱序)
    for &depth in &depths {
        let judge = FlatMcAgent::with_depth(depth);
        for (name, opp) in &opps {
            eprintln!("  depth={} vs {} ...", depth, name);
            let p = run_pair_par(&judge, *opp, seeds, sb + depth as u64 * 100000, "balanced", &cfg);
            let cqp = p.a_win_conquest as f64 / (seeds * 2) as f64 * 100.0;
            let csp = p.a_win_construction as f64 / (seeds * 2) as f64 * 100.0;
            let tbp = p.a_win_tiebreak as f64 / (seeds * 2) as f64 * 100.0;
            // 立即输出+flush → 中断不丢
            println!("{},{},{:.1},{:.1},{:.0},{:.0},{:.0}", depth, name, p.a_win_rate * 100.0, p.avg_turns, cqp, csp, tbp);
            std::io::stdout().flush().ok();
        }
    }
    eprintln!("完成。");
}
