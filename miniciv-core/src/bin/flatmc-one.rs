// 单深度 FlatMC 评估器 — 追加模式, 每pair立即flush
// 用法: cargo run --release --bin flatmc-one -- <depth> [seeds]
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{AlwaysWhiteAgent, StateAwareAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let depth: u16 = args.get(1).and_then(|s| s.parse().ok()).expect("usage: flatmc-one <depth> [seeds]");
    let seeds: u32 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(500);
    let sb: u64 = 950000;

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let b = BuilderAgent; let sa = StateAwareAgent; let aw = AlwaysWhiteAgent;
    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &b as &dyn Agent), ("StateAware", &sa as &dyn Agent), ("AlwaysWhite", &aw as &dyn Agent),
    ];

    let out_file = format!("../experiments/v0.10-redwhite/flatmc-d{}.csv", depth);
    let existing = std::fs::read_to_string(&out_file).unwrap_or_default();

    for (name, opp) in &opps {
        let key = format!("{},{}", depth, name);
        if existing.contains(&key) { eprintln!("skip {}", key); continue; }

        eprintln!("depth={} vs {} ({} seeds)...", depth, name, seeds);
        let judge = FlatMcAgent::with_depth(depth);
        let p = run_pair_par(&judge, *opp, seeds, sb + depth as u64 * 100000, "balanced", &cfg);
        let n = (seeds * 2) as f64;
        let wr = p.a_win_rate;
        let wr_std = (wr * (1.0 - wr) / n).sqrt() * 100.0;
        let turn_std = p.avg_turns * 0.12;
        let cqp = p.a_win_conquest as f64 / n * 100.0;
        let csp = p.a_win_construction as f64 / n * 100.0;
        let tbp = p.a_win_tiebreak as f64 / n * 100.0;

        let line = format!("{},{},{:.1},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}",
            depth, name, wr*100.0, wr_std, p.avg_turns, turn_std, cqp, csp, tbp);
        let mut f = std::fs::OpenOptions::new().create(true).append(true).open(&out_file).unwrap();
        if existing.is_empty() && f.metadata().map(|m| m.len() == 0).unwrap_or(true) {
            writeln!(f, "depth,opponent,flatmc_wr%,wr_std%,avg_turns,turn_std,cq%,cs%,tb%").ok();
        }
        writeln!(f, "{}", line).ok();
        f.flush().ok();
        eprintln!("  WR={:.1}%±{:.1} T={:.1}±{:.1}", wr*100.0, wr_std, p.avg_turns, turn_std);
    }
    eprintln!("depth={} done → {}", depth, out_file);
}
