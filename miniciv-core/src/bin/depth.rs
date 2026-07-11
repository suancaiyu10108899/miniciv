// 深度体检 — MCTS 之前的轻量深度探测
// 测两件事:
//   1) 决策分叉: 每个局面下, 最优策略 vs 次优策略的评分 gap。
//      gap 小(多策略接近) = 有真实选择 = 深; gap 大(一策略碾压) = 唯一最优 = 浅。
//   2) 应变实证: 最优策略是否随局面/对手变化。
//      经常变 = 应变被需要 = 深; 总是同一个 = 应变是摆设 = 浅。
//
// 用法: cargo run --release --bin depth -- [seeds]

use std::collections::HashMap;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{init_game_with_config, step_game};
use miniciv_core::ai::Agent;
use miniciv_core::ai::search::evaluate_strategies;
use miniciv_core::ai::probes::{RusherAgent, DefenderAgent, AdaptiveAgent};
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(15);
    // S2: 读默认配置(已=甜点 成本×2 HP160), 不再写死。之前写死 3.0/160 = 已被推翻的旧甜点漂移。
    let cfg = GameConfig::default();

    // 用不同对手推进 P0(观察 P0 该应变吗)
    let rusher = RusherAgent;
    let defender = DefenderAgent;
    let adaptive = AdaptiveAgent;
    let opponents: Vec<(&str, &dyn Agent)> =
        vec![("vsRusher", &rusher), ("vsDefender", &defender), ("vsAdaptive", &adaptive)];

    let mut gaps: Vec<f64> = Vec::new();
    let mut best_by_opp: HashMap<&str, HashMap<String, u32>> = HashMap::new();
    let mut samples = 0u32;

    for (oname, opp) in &opponents {
        let entry = best_by_opp.entry(*oname).or_default();
        for i in 0..seeds {
            let seed = 50000 + i as u64 * 100;
            let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
            let driver = AdaptiveAgent; // P0 用 Adaptive 推进到各种局面
            let mut r0 = ChaCha12Rng::seed_from_u64(seed);
            let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
            let mt = gs.config.max_turns;
            while gs.winner.is_none() && gs.turn < mt {
                // 采样点: 每 5 回合评估一次策略分布
                if gs.turn >= 3 && gs.turn % 5 == 0 {
                    let mut sc = evaluate_strategies(&gs, 0);
                    sc.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
                    let gap = sc[0].1 - sc[1].1;
                    gaps.push(gap);
                    *entry.entry(sc[0].0.to_string()).or_insert(0) += 1;
                    samples += 1;
                }
                let a0 = driver.decide(&gs, 0, &mut r0);
                let a1 = opp.decide(&gs, 1, &mut r1);
                step_game(&mut gs, &a0, &a1);
            }
        }
    }

    // ── 决策分叉 ──
    gaps.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let avg_gap = gaps.iter().sum::<f64>() / gaps.len().max(1) as f64;
    let tied = gaps.iter().filter(|&&g| g < 0.05).count();  // 最优次优几乎相等
    println!("=== 深度体检(默认甜点 成本×2 HP160, {} 采样点)===\n", samples);
    println!("【1. 决策分叉】最优 vs 次优策略评分 gap:");
    println!("  平均 gap: {:.3}  (小=多策略接近=有选择; 大=一策略碾压=浅)", avg_gap);
    println!("  gap<0.05(几乎并列)占比: {:.0}%  (高=经常有多个等优选择=深)",
             tied as f64 / gaps.len().max(1) as f64 * 100.0);

    // ── 应变实证 ──
    println!("\n【2. 应变实证】P0 最优策略随对手是否变化:");
    for (oname, _) in &opponents {
        if let Some(m) = best_by_opp.get(oname) {
            let total: u32 = m.values().sum();
            let mut items: Vec<_> = m.iter().collect();
            items.sort_by(|a, b| b.1.cmp(a.1));
            let top = items.first().map(|(k, v)| format!("{} {:.0}%", k, **v as f64 / total.max(1) as f64 * 100.0)).unwrap_or_default();
            let dist: String = items.iter().map(|(k, v)| format!("{}:{}", k, v)).collect::<Vec<_>>().join(" ");
            println!("  {:>11}: 最优={:<14} [{}]", oname, top, dist);
        }
    }
    println!("\n判读: 若不同对手下最优策略不同 → 应变被需要(深);");
    println!("      若都是同一个策略 → 应变是摆设(浅)。");
}
