// 兵种战斗数据诊断 — 回答"哪种兵种战斗有效 / 步兵vs弓箭手"
//
// 引擎已追踪 damage_dealt/taken(combat.rs)。这里按兵种聚合:
//   出现率 / 平均造成伤害 / 平均承受 / 存活率
//
// 用法: cargo run --release --bin content -- [seeds] [起手资源] [进攻方AI(可选,聚焦防守场景)]

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

#[derive(Default, Clone)]
struct Stat { games: u32, dealt: i64, taken: i64, alive: u32, dead: u32 }

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

    let mut stats: HashMap<String, Stat> = HashMap::new();
    let mut tech_seen: HashMap<String, u32> = HashMap::new();
    let mut total = 0u32;

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
                total += 1;
                let mut seen: HashMap<String, bool> = HashMap::new();
                for u in gs.units.iter().chain(gs.dead_units.iter()) {
                    let k = format!("{:?}", u.unit_type);
                    let s = stats.entry(k.clone()).or_default();
                    s.dealt += u.damage_dealt as i64;
                    s.taken += u.damage_taken as i64;
                    if u.alive { s.alive += 1; } else { s.dead += 1; }
                    seen.insert(k, true);
                }
                for k in seen.keys() { stats.entry(k.clone()).or_default().games += 1; }
                for t in &gs.techs {
                    for c in &t.completed { *tech_seen.entry(c.clone()).or_insert(0) += 1; }
                }
            }
        }
    }

    println!("兵种战斗数据: {} 局(起手资源={})", total, res);
    println!("{:>9} {:>7} {:>10} {:>10} {:>8}", "兵种", "出现%", "均造伤害", "均承伤害", "存活率");
    println!("{}", "-".repeat(50));
    for ut in ["Infantry", "Cavalry", "Archer", "Scout", "Worker"] {
        if let Some(s) = stats.get(ut) {
            let appeared = s.alive + s.dead;
            let dealt = if appeared > 0 { s.dealt as f64 / appeared as f64 } else { 0.0 };
            let taken = if appeared > 0 { s.taken as f64 / appeared as f64 } else { 0.0 };
            let surv = if appeared > 0 { s.alive as f64 / appeared as f64 * 100.0 } else { 0.0 };
            println!("{:>9} {:>6.1}% {:>10.1} {:>10.1} {:>7.1}%",
                     ut, s.games as f64 / total as f64 * 100.0, dealt, taken, surv);
        } else {
            println!("{:>9}   0.0%(未出现)", ut);
        }
    }
}
