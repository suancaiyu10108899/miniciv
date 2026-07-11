// 内容利用率诊断 — 维度 G(无死内容)
//
// 目的: 跨大量对局统计每种兵种是否被使用(存活/死亡)、每条科技是否被研究。
//       某兵种/科技从没出现 = 潜在死内容(受限于当前 AI 水平, 仅供参考)。
//
// 用法: cargo run --release --bin content -- [seeds] [起手资源]

use std::collections::HashMap;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{init_game_with_config, step_game};
use miniciv_core::ai::Agent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::probes::{RusherAgent, HarasserAgent, TurtleAgent};
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let res: i32 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(17);

    let config = GameConfig {
        starting_food: res, starting_wood: res, starting_gold: res,
        ..GameConfig::default()
    };

    let greedy = GreedyAgent::new();
    let agents: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &BuilderAgent), ("Rusher", &RusherAgent),
        ("Harasser", &HarasserAgent), ("Turtle", &TurtleAgent),
        ("Greedy", &greedy), ("Random", &RandomAgent),
    ];

    // 统计: 兵种 → (出现过的局数, 累计存活, 累计死亡)
    let mut unit_seen: HashMap<String, u32> = HashMap::new();
    let mut tech_seen: HashMap<String, u32> = HashMap::new();
    let mut total_games = 0u32;

    for (_, a0) in &agents {
        for (_, a1) in &agents {
            for i in 0..seeds {
                let seed = 50000 + i as u64 * 100;
                let mut gs = init_game_with_config(seed, "balanced", config.clone());
                let mut r0 = ChaCha12Rng::seed_from_u64(seed);
                let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
                let mt = gs.config.max_turns;
                while gs.winner.is_none() && gs.turn < mt {
                    let act0 = a0.decide(&gs, 0, &mut r0);
                    let act1 = a1.decide(&gs, 1, &mut r1);
                    step_game(&mut gs, &act0, &act1);
                }
                total_games += 1;
                // 统计终局所有单位(存活+死亡)的兵种
                let mut seen_this: HashMap<String, bool> = HashMap::new();
                for u in gs.units.iter().chain(gs.dead_units.iter()) {
                    seen_this.insert(format!("{:?}", u.unit_type), true);
                }
                for k in seen_this.keys() { *unit_seen.entry(k.clone()).or_insert(0) += 1; }
                // 统计研究过的科技
                let mut seen_tech: HashMap<String, bool> = HashMap::new();
                for t in &gs.techs {
                    for c in &t.completed { seen_tech.insert(c.clone(), true); }
                }
                for k in seen_tech.keys() { *tech_seen.entry(k.clone()).or_insert(0) += 1; }
            }
        }
    }

    println!("内容利用率: {} 局(起手资源={})", total_games, res);
    println!("\n=== 兵种出现率(某兵种在多少比例的对局里出现)===");
    for ut in ["Infantry", "Cavalry", "Archer", "Scout", "Worker"] {
        let n = unit_seen.get(ut).copied().unwrap_or(0);
        let pct = n as f64 / total_games as f64 * 100.0;
        let flag = if pct < 1.0 { "  <== 死内容?" } else { "" };
        println!("  {:>9}: {:>5.1}%{}", ut, pct, flag);
    }
    println!("\n=== 科技研究率 ===");
    for t in ["M1","M2","M3","M4","E1","E2","E3","E4","C1","C2","C3","C4","C5"] {
        let n = tech_seen.get(t).copied().unwrap_or(0);
        let pct = n as f64 / total_games as f64 * 100.0;
        let flag = if pct < 1.0 { "  <== 死内容?" } else { "" };
        println!("  {:>3}: {:>5.1}%{}", t, pct, flag);
    }
}
