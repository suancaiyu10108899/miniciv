// FlatMC 自对弈: deep vs shallow, 500 seeds
// 用法: cargo run --release --bin flatmc-self -- <deep> <shallow> [seeds]
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let deep: u16 = args.get(1).and_then(|s| s.parse().ok()).expect("flatmc-self <deep> <shallow> [seeds]");
    let shallow: u16 = args.get(2).and_then(|s| s.parse().ok()).expect("need shallow depth");
    let seeds: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(500);
    let sb: u64 = 960000;

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    eprintln!("FlatMC self-play: d{} vs d{} ({} seeds)...", deep, shallow, seeds);
    let d = FlatMcAgent::with_depth(deep);
    let s = FlatMcAgent::with_depth(shallow);
    let p = run_pair_par(&d, &s, seeds, sb, "balanced", &cfg);

    let n = (seeds * 2) as f64;
    let wr = p.a_win_rate * 100.0;
    let wr_std = (p.a_win_rate * (1.0 - p.a_win_rate) / n).sqrt() * 100.0;

    let out = format!("../experiments/v0.10-redwhite/flatmc-self-d{}-d{}.csv", deep, shallow);
    let mut f = std::fs::File::create(&out).unwrap();
    writeln!(f, "deep,shallow,deep_wr%,wr_std%,avg_turns,cq%,cs%,tb%").ok();
    writeln!(f, "{},{},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}",
        deep, shallow, wr, wr_std, p.avg_turns,
        p.a_win_conquest as f64/n*100.0, p.a_win_construction as f64/n*100.0, p.a_win_tiebreak as f64/n*100.0).ok();

    eprintln!("d{} vs d{}: WR={:.1}%±{:.1} T={:.1} → {}", deep, shallow, wr, wr_std, p.avg_turns, out);
}
