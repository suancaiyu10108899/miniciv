// M3-A 验证: 策略级搜索 AI vs 探针(甜点带)
// 用法: cargo run --release --bin m3 -- [seeds]

use miniciv_core::config::GameConfig;
use miniciv_core::ai::Agent;
use miniciv_core::ai::search::SearchAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::probes::{RusherAgent, CavalryRusherAgent, DefenderAgent, AdaptiveAgent};
use miniciv_core::eval::run_pair;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(30);
    // 甜点带
    let cfg = GameConfig { c_line_cost_mult: 3.0, city_hp: 160, ..GameConfig::default() };

    let search = SearchAgent;
    let builder = BuilderAgent;
    let rusher = RusherAgent;
    let cav = CavalryRusherAgent;
    let def = DefenderAgent;
    let adaptive = AdaptiveAgent;
    let random = RandomAgent;

    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &builder), ("Rusher", &rusher), ("CavRusher", &cav),
        ("Defender", &def), ("Adaptive", &adaptive), ("Random", &random),
    ];

    println!("M3-A: Search(策略级rollout) vs 探针, 甜点带(成本×3 HP160), {} seeds paired", seeds);
    println!("{:>12} | {:>8} {:>10}", "对手", "Search胜率", "avg回合");
    println!("{}", "-".repeat(36));
    for (name, opp) in &opps {
        let p = run_pair(&search, *opp, seeds, 50000, "balanced", &cfg);
        println!("{:>12} | {:>7.1}% {:>9.1}", name, p.a_win_rate * 100.0, p.avg_turns);
    }
    println!("\n判读: Search 若显著强于探针/Adaptive → rollout选择有价值(应变是深度);");
    println!("      若被某探针压 → 探针基元不够(需更强基元或真MCTS)。");
}
