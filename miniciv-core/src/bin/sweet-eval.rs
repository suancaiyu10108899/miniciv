// P1.5 甜点矩阵运行器 — 直接在代码里设完整甜点配置
use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, HarasserAgent, TurtleAgent, DefenderAgent,
    CavalryRusherAgent, AdaptiveAgent,
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_matrix_par;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(300);
    let out = args.get(2).cloned().unwrap_or_else(|| "experiments/v0.10-redwhite/sweet-matrix.json".to_string());

    // 甜点配置
    let cfg = GameConfig {
        max_turns: 200,
        tech_turns_mult: 9.0,
        all_tech_cost_mult: 3.0,
        unit_cost_mult: 8.0,
        facility_build_turns: 8,
        city_hp: 1200,
        c_line_cost_mult: 1.0,
        starting_food: 30, starting_wood: 30, starting_gold: 30,
        facility_output: 4, starting_workers: 2,
        branch_available_turn: 25,
        ..GameConfig::default()
    };

    eprintln!("甜点矩阵: {} AI, {} seeds paired, T_max=200, HP=1200, ttM=9.0, fBT=8, uM=8.0, tcM=3.0, startR=30, branch@T25",
        if seeds >= 300 { "10" } else { "10" }, seeds);

    let agents: Vec<&dyn Agent> = vec![
        &BuilderAgent, &RusherAgent, &CavalryRusherAgent,
        &DefenderAgent, &AdaptiveAgent, &RandomAgent,
        &AlwaysWhiteAgent, &AlwaysRedAgent, &StateAwareAgent, &TankThenRedAgent,
    ];

    let m = run_matrix_par(&agents, seeds, 50000, "balanced", &cfg);

    // 输出关键对局
    for p in &m.pairs {
        let key_pairs = ["Builder", "Rusher", "StateAware", "AlwaysWhite", "AlwaysRed", "TankThenRed", "Defender"];
        if key_pairs.iter().any(|k| p.a.contains(k)) && key_pairs.iter().any(|k| p.b.contains(k)) {
            println!("{:>10} vs {:<10} {:6.1}%  Cq:{} Cs:{} Tb:{} avgT:{:.1}",
                p.a, p.b, p.a_win_rate*100.0,
                p.conquest, p.construction, p.tiebreak, p.avg_turns);
        }
    }
    println!("\n═══ 全局胜率 ═══");
    for s in &m.summaries {
        println!("  {:>12}: {:5.1}%", s.agent, s.avg_vs_others*100.0);
    }

    if let Ok(json) = serde_json::to_string_pretty(&m) {
        std::fs::write(&out, &json).ok();
        eprintln!("已写入 {}", out);
    }
}
