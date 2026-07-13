// P1.5 收尾: FlatMC 平台期探测 — depth=8/10/12/16/20 vs 4对手
// 目的: 确认FlatMC胜率是否在depth=8进入平台期, 还是继续随深度提升。
// 如果depth=20仍大幅优于depth=8 → 游戏复杂度被低估, P2需更强裁判。
// 用法: cargo run --release --bin flatmc-plateau -- [seeds] [seed_base]

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, StateAwareAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;
use std::io::Write;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(50);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(950000);

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    // 扩深度范围: 8之后加倍探
    let depths: [u16; 6] = [8, 10, 12, 16, 20, 24];
    let b = BuilderAgent; let r = RusherAgent; let aw = AlwaysWhiteAgent; let sa = StateAwareAgent;
    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &b as &dyn Agent), ("Rusher", &r as &dyn Agent),
        ("AlwaysWhite", &aw as &dyn Agent), ("StateAware", &sa as &dyn Agent),
    ];

    let total = depths.len() * opps.len();
    eprintln!("FlatMC平台期探测: {} depths × {} opps × {} seeds = {} games, C1甜点",
        depths.len(), opps.len(), seeds, total as u64 * seeds as u64 * 2);

    // 追加模式: 先检查已有数据, 跳过已跑的组合
    let existing = std::fs::read_to_string("../experiments/v0.10-redwhite/flatmc-depth-final.csv")
        .unwrap_or_default();
    // 合并depth=2-8的老数据
    let all_old = std::fs::read_to_string("../experiments/v0.10-redwhite/flatmc-d3.csv")
        .unwrap_or_default();

    println!("depth,opponent,flatmc_wr%,avg_turns,time_sec,cq%,cs%,tb%");
    // 先输出已有数据
    for line in all_old.lines().skip(1) { if !line.is_empty() && !line.contains('\0') { println!("{}", line); } }

    let start_time = Instant::now();
    let mut done = 0u32;
    let mut new_data = Vec::new();

    for &depth in &depths {
        for (name, opp) in &opps {
            // 检查是否已跑过
            let key = format!("{},{}", depth, name);
            if all_old.contains(&key) || existing.contains(&key) {
                continue; // skip already-completed
            }

            let t0 = Instant::now();
            let judge = FlatMcAgent::with_depth(depth);
            let p = run_pair_par(&judge, *opp, seeds, sb + depth as u64 * 100000, "balanced", &cfg);
            let elapsed = t0.elapsed().as_secs_f64();

            let tg = (seeds * 2) as f64;
            let cqp = p.a_win_conquest as f64 / tg * 100.0;
            let csp = p.a_win_construction as f64 / tg * 100.0;
            let tbp = p.a_win_tiebreak as f64 / tg * 100.0;

            let line = format!("{},{},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}",
                depth, name, p.a_win_rate * 100.0, p.avg_turns, elapsed, cqp, csp, tbp);
            println!("{}", line);
            std::io::stdout().flush().ok();
            new_data.push(line);

            done += 1;
            eprintln!("[{}/{}] depth={} vs {}: WR={:.1}% T={:.1}s elapsed={:.0}s",
                done, total, depth, name, p.a_win_rate * 100.0, elapsed, start_time.elapsed().as_secs_f64());
        }
    }

    // 追加写入完整表
    if !new_data.is_empty() {
        let mut all_lines: Vec<String> = all_old.lines().skip(1)
            .filter(|l| !l.is_empty() && !l.contains('\0')).map(|l| l.to_string()).collect();
        for nd in &new_data { all_lines.push(nd.clone()); }
        // 去重排序
        all_lines.sort();
        all_lines.dedup();
        let full = format!("depth,opponent,flatmc_wr%,avg_turns,time_sec,cq%,cs%,tb%\n{}\n", all_lines.join("\n"));
        std::fs::write("../experiments/v0.10-redwhite/flatmc-depth-final.csv", &full).ok();
        eprintln!("完整表已保存 ({} rows)", all_lines.len());
    }

    eprintln!("完成。总耗时={:.0}s", start_time.elapsed().as_secs_f64());
}
