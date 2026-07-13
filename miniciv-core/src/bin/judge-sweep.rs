// P1.5: FlatMC depth×performance 打表 — 多线程并行版
// 每完成一对(depth,opponent)立即写盘+flush。中断不丢数据。
// 用法: cargo run --release --bin judge-sweep -- [seeds] [seed_base]
// 默认: 50 seeds, depth 2/3/4/5/6/8 × 4 opponents

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, StateAwareAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::PairResult;
use std::io::Write;
use std::sync::Mutex;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(50);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(900000);

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let depths: [u16; 6] = [2, 3, 4, 5, 6, 8];
    let builder = BuilderAgent; let rusher = RusherAgent;
    let aw = AlwaysWhiteAgent; let sa = StateAwareAgent;

    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &builder as &dyn Agent),
        ("Rusher", &rusher as &dyn Agent),
        ("AlwaysWhite", &aw as &dyn Agent),
        ("StateAware", &sa as &dyn Agent),
    ];

    let total = depths.len() * opps.len();
    let total_games = total as u64 * seeds as u64 * 2;
    eprintln!("FlatMC打表: {} depths × {} opps × {} seeds = {} games, C1甜点, 多线并行",
        depths.len(), opps.len(), seeds, total_games);

    // 流式输出: Mutex保护stdout
    let stdout = Mutex::new(std::io::stdout());
    {
        let mut out = stdout.lock().unwrap();
        writeln!(out, "depth,opponent,flatmc_wr%,avg_turns,time_sec,cq%,cs%,tb%").ok();
        out.flush().ok();
    }

    let start_time = Instant::now();
    let mut done = 0u32;

    // 串行跑pairs(每个pair内部用run_pair_par并行seeds → 全核加速单pair)
    let pairs: Vec<(u16, &str, &dyn Agent)> = depths.iter()
        .flat_map(|&d| opps.iter().map(move |(n,o)| (d, *n, *o)))
        .collect();

    for &(depth, name, opp) in &pairs {
        let t0 = Instant::now();
        let judge = FlatMcAgent::with_depth(depth);
        let p: PairResult = miniciv_core::eval::run_pair_par(&judge, opp, seeds, sb + depth as u64 * 100000, "balanced", &cfg);
        let elapsed = t0.elapsed().as_secs_f64();

        let total_g = (seeds * 2) as f64;
        let cqp = p.a_win_conquest as f64 / total_g * 100.0;
        let csp = p.a_win_construction as f64 / total_g * 100.0;
        let tbp = p.a_win_tiebreak as f64 / total_g * 100.0;

        // 立即写盘
        let mut out = stdout.lock().unwrap();
        writeln!(out, "{},{},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}",
            depth, name, p.a_win_rate * 100.0, p.avg_turns, elapsed, cqp, csp, tbp).ok();
        out.flush().ok();
        drop(out);

        done += 1;
        let n = done;
        let total_elapsed = start_time.elapsed().as_secs_f64();
        eprintln!("[{}/{}] depth={} vs {}: WR={:.1}% T={:.1}s elapsed={:.0}s",
            n, total, depth, name, p.a_win_rate * 100.0, elapsed, total_elapsed);
    }

    eprintln!("完成。总耗时={:.0}s", start_time.elapsed().as_secs_f64());
}
