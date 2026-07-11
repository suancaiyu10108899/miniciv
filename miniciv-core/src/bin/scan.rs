// 平衡扫描 — M1.2(第三个 AI)
//
// 目的: 数据驱动找门禁3甜点。对每组参数, 测两个关键指标:
//   speedrun_turn      — Builder vs Random 平均结束回合(建设速通有多快)
//   rusher_vs_builder  — Rusher vs Builder paired 胜率(军事能否惩罚裸建设)
//
// 甜点判据: speedrun_turn ≥30(理想40-60) 且 rusher_vs_builder >0(军事够得着)。
//
// 用法: cargo run --release --bin scan -- [seeds]

use std::collections::HashMap;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{init_game_with_config, step_game};
use miniciv_core::ai::Agent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::probes::RusherAgent;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;

/// 跑一局到结束, 返回 (结束回合, winner)。
fn run_game(cfg: &GameConfig, seed: u64, a0: &dyn Agent, a1: &dyn Agent) -> (u16, Option<u8>) {
    let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
    let mut r0 = ChaCha12Rng::seed_from_u64(seed);
    let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
    let max_turns = gs.config.max_turns;
    while gs.winner.is_none() && gs.turn < max_turns {
        let act0 = a0.decide(&gs, 0, &mut r0);
        let act1 = a1.decide(&gs, 1, &mut r1);
        step_game(&mut gs, &act0, &act1);
    }
    (gs.turn, gs.winner)
}

/// Builder vs Random 平均结束回合。
fn builder_speedrun(cfg: &GameConfig, seeds: u32) -> f64 {
    let (b, r) = (BuilderAgent, RandomAgent);
    let mut sum = 0u64;
    for i in 0..seeds {
        let seed = 50000 + i as u64 * 100;
        let (turn, _) = run_game(cfg, seed, &b, &r);
        sum += turn as u64;
    }
    sum as f64 / seeds as f64
}

/// Rusher vs Builder paired 胜率(Rusher 视角, 先手抵消)。
fn rusher_vs_builder(cfg: &GameConfig, seeds: u32) -> f64 {
    let (rush, build) = (RusherAgent, BuilderAgent);
    let mut rush_wins = 0u32;
    for i in 0..seeds {
        let seed = 50000 + i as u64 * 100;
        let (_, w1) = run_game(cfg, seed, &rush, &build);   // Rusher=P0
        if w1 == Some(0) { rush_wins += 1; }
        let (_, w2) = run_game(cfg, seed, &build, &rush);   // Rusher=P1
        if w2 == Some(1) { rush_wins += 1; }
    }
    rush_wins as f64 / (seeds * 2) as f64
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(100);

    // 耗时杠杆有效(整条C线)。细扫: turns 控速通, city_hp 控军事强度, 找 Rusher 40~60%。
    let turns_opts = [8u8];
    let hp_opts = [80i32, 81, 82, 83, 84];

    println!("平衡扫描: {} seeds/组. C线耗时×城市HP(academy关)", seeds);
    println!("{:>8} {:>8} | {:>10} {:>14} {}", "C线turns", "cityHP", "速通(T)", "Rusher胜率", "");
    println!("{}", "-".repeat(58));

    let base = GameConfig::default();
    for &ct in &turns_opts {
        for &hp in &hp_opts {
            let mut tech_turns = HashMap::new();
            for t in ["C1", "C3", "C4", "C5"] { tech_turns.insert(t.to_string(), ct); }
            let cfg = GameConfig {
                academy_research_increment: 1,
                city_hp: hp,
                tech_turns,
                ..base.clone()
            };
            let sr = builder_speedrun(&cfg, seeds);
            let rw = rusher_vs_builder(&cfg, seeds);
            let sweet = if sr >= 28.0 && rw >= 0.40 && rw <= 0.60 { " <== 甜点!" }
                        else if rw >= 0.30 && rw <= 0.70 { " <- 接近" } else { "" };
            println!("{:>8} {:>8} | {:>9.1} {:>13.1}%{}", ct, hp, sr, rw * 100.0, sweet);
        }
    }
}
