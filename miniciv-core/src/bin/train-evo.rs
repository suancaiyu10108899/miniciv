// P1.5 Phase 4: Evo GA Rust端重训 — 增量存盘版
// 每10代自动保存最佳权重到checkpoint, 中断可从最近的checkpoint恢复。
// 用法: cargo run --release --bin train-evo -- [generations] [population] [seeds] [resume.json]
// 默认: 80代, 50个体, 15 seeds

use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::greedy::GreedyConfig;
use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, AlwaysRedAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use rand::Rng;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashMap;
use serde::{Serialize, Deserialize};
use std::io::Write;

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Individual {
    weights: HashMap<String, f64>,
    #[serde(default)]
    fitness: f64,
}

#[derive(Serialize, Deserialize)]
struct Checkpoint {
    generation: u32,
    best: Individual,
    population: Vec<Individual>,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let generations: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(80);
    let pop_size: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(50);
    let seeds_per: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(15);
    let resume_path = args.get(4).cloned();
    let out_path = "../experiments/v0.10-redwhite/evo-trained-weights.json".to_string();
    let ckpt_path = "../experiments/v0.10-redwhite/evo-checkpoint.json".to_string();

    // C1甜点(不改!)
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let opponents: Vec<(&str, &dyn Agent)> = vec![
        ("Random", &RandomAgent as &dyn Agent),
        ("Builder", &BuilderAgent as &dyn Agent),
        ("Rusher", &RusherAgent as &dyn Agent),
        ("AlwaysWhite", &AlwaysWhiteAgent as &dyn Agent),
        ("AlwaysRed", &AlwaysRedAgent as &dyn Agent),
    ];

    let weight_names = vec![
        "attack_adjacent", "rush_enemy_city", "defend_own_city",
        "intercept_near_city", "retreat_hp_threshold", "terrain_def_weight",
        "retreat_terrain_bonus", "archer_keep_distance", "archer_prefer_high",
        "build_efficiency", "resource_variety", "research_priority",
        "military_tech_bias", "cavalry_production", "archer_production",
    ];

    let mut rng = ChaCha12Rng::seed_from_u64(12345678);
    let gconfig = GreedyConfig::default();
    let sb = 700000u64;

    // 初始化或从checkpoint恢复
    let (start_gen, mut population, mut best_ever) = if let Some(rp) = &resume_path {
        if let Ok(json) = std::fs::read_to_string(rp) {
            if let Ok(ckpt) = serde_json::from_str::<Checkpoint>(&json) {
                eprintln!("从checkpoint恢复: gen={} best_fitness={:.3}", ckpt.generation, ckpt.best.fitness);
                (ckpt.generation + 1, ckpt.population, ckpt.best)
            } else { (0, init_population(pop_size, &weight_names, &mut rng), Individual { weights: HashMap::new(), fitness: 0.0 }) }
        } else { (0, init_population(pop_size, &weight_names, &mut rng), Individual { weights: HashMap::new(), fitness: 0.0 }) }
    } else {
        (0, init_population(pop_size, &weight_names, &mut rng), Individual { weights: HashMap::new(), fitness: 0.0 })
    };

    eprintln!("Evo GA: {}个体 × {}代(从{}代开始) × {}seeds × {}对手 = {} 评估/代, C1甜点(不改)",
        pop_size, generations, start_gen, seeds_per, opponents.len(), pop_size * opponents.len() * seeds_per as usize * 2);

    for gen in start_gen..generations {
        // 并行评估
        let results: Vec<(usize, f64)> = population.iter().enumerate()
            .collect::<Vec<_>>().par_iter().map(|(idx, ind)| {
                let mut agent = EvoAgent::new();
                agent.weights = ind.weights.clone();
                agent.config = gconfig.clone();
                let mut total_wr = 0.0f64;
                for (_, opp) in &opponents {
                    let mut wins = 0u32;
                    for i in 0..seeds_per {
                        let seed = sb + gen as u64 * 100000 + *idx as u64 * 1000 + i as u64;
                        let g = run_one_game(seed, &agent, *opp, "balanced", &cfg);
                        if g.winner == Some(0) { wins += 1; }
                        let g2 = run_one_game(seed + 500000, *opp, &agent, "balanced", &cfg);
                        if g2.winner == Some(1) { wins += 1; }
                    }
                    total_wr += wins as f64 / (seeds_per * 2) as f64;
                }
                (*idx, total_wr / opponents.len() as f64)
            }).collect();

        for (idx, fit) in results { population[idx].fitness = fit; }
        population.sort_by(|a, b| b.fitness.partial_cmp(&a.fitness).unwrap());

        let best = &population[0];
        let improved = best.fitness > best_ever.fitness;
        if improved {
            best_ever = best.clone();
        }
        let top10_avg = population.iter().take(10).map(|i| i.fitness).sum::<f64>() / 10.0;
        eprintln!("Gen {}: best={:.3} top10avg={:.3} {}", gen, best.fitness, top10_avg, if improved { "★" } else { "" });

        // 每10代存checkpoint(中断不丢)
        if gen % 10 == 0 || improved {
            let ckpt = Checkpoint { generation: gen, best: best_ever.clone(), population: population.clone() };
            if let Ok(json) = serde_json::to_string_pretty(&ckpt) {
                std::fs::write(&ckpt_path, &json).ok();
                eprintln!("  checkpoint → {}", ckpt_path);
            }
        }

        // 下一代
        let mut next_gen: Vec<Individual> = Vec::with_capacity(pop_size);
        for i in 0..5.min(pop_size) { next_gen.push(population[i].clone()); }
        while next_gen.len() < pop_size {
            let p1 = tournament_select(&population, 5, &mut rng);
            let p2 = tournament_select(&population, 5, &mut rng);
            let mut child_w = HashMap::new();
            for &name in &weight_names {
                let v1 = *p1.weights.get(name).unwrap_or(&1.0);
                let v2 = *p2.weights.get(name).unwrap_or(&1.0);
                let (lo, hi) = if v1 < v2 { (v1, v2) } else { (v2, v1) };
                let range = hi - lo;
                let cv = lo - 0.5 * range + rng.gen::<f64>() * (range * 2.0);
                child_w.insert(name.to_string(), cv.max(0.01).min(5.0));
            }
            for &name in &weight_names {
                if rng.gen::<f64>() < 0.2 {
                    let v = *child_w.get(name).unwrap_or(&1.0);
                    child_w.insert(name.to_string(), (v + rng.gen_range(-0.3..0.3)).max(0.01).min(5.0));
                }
            }
            next_gen.push(Individual { weights: child_w, fitness: 0.0 });
        }
        population = next_gen;
    }

    // 保存最终权重
    #[derive(Serialize)] struct Output { weights: HashMap<String, f64>, fitness: f64, generation: u32 }
    let output = Output { weights: best_ever.weights.clone(), fitness: best_ever.fitness, generation: generations };
    let json = serde_json::to_string_pretty(&output).unwrap();
    std::fs::write(&out_path, &json).unwrap();
    eprintln!("\n最终权重 → {} (fitness={:.3})", out_path, best_ever.fitness);
    for &name in &weight_names {
        println!("  {}: {:.3}", name, best_ever.weights.get(name).unwrap_or(&0.0));
    }
}

fn init_population(n: usize, names: &[&str], rng: &mut impl Rng) -> Vec<Individual> {
    (0..n).map(|_| {
        let mut w = HashMap::new();
        for &name in names {
            let base = default_weight(name);
            w.insert(name.to_string(), (base + rng.gen_range(-1.0..1.0)).max(0.01).min(5.0));
        }
        Individual { weights: w, fitness: 0.0 }
    }).collect()
}

fn tournament_select(pop: &[Individual], k: usize, rng: &mut impl Rng) -> Individual {
    let best_idx = (0..k).map(|_| rng.gen_range(0..pop.len()))
        .max_by(|&a, &b| pop[a].fitness.partial_cmp(&pop[b].fitness).unwrap()).unwrap();
    pop[best_idx].clone()
}

fn default_weight(name: &str) -> f64 {
    match name {
        "attack_adjacent" => 1.0, "rush_enemy_city" => 1.0, "defend_own_city" => 1.0,
        "intercept_near_city" => 0.8, "retreat_hp_threshold" => 0.3, "terrain_def_weight" => 0.15,
        "retreat_terrain_bonus" => 0.3, "archer_keep_distance" => 1.0, "archer_prefer_high" => 0.1,
        "build_efficiency" => 1.0, "resource_variety" => 1.0, "research_priority" => 1.0,
        "military_tech_bias" => 0.5, "cavalry_production" => 1.0, "archer_production" => 1.0,
        _ => 1.0,
    }
}
