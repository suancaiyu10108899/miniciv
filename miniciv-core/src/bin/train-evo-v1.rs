// 方向1: Evo交互特征 — 25原始+12交互=37维, GA训练
// 用法: cargo run --release --bin train-evo-v1 -- [gens] [pop] [seeds]
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::greedy::GreedyConfig;
use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, AlwaysRedAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::GameState;
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use rand::Rng;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashMap;
use serde::{Serialize, Deserialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Individual {
    weights: HashMap<String, f64>,
    #[serde(default)]
    fitness: f64,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let generations: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(80);
    let pop_size: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(50);
    let seeds_per: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(15);
    let out_path = "../experiments/v0.10-redwhite/evo-v1-weights.json";
    let ckpt_path = "../experiments/v0.10-redwhite/evo-v1-checkpoint.json";

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

    // 37个特征: 25原始 + 12交互
    let weight_names: Vec<String> = {
        let mut v: Vec<String> = vec![
            "attack_adjacent","rush_enemy_city","defend_own_city",
            "intercept_near_city","retreat_hp_threshold","terrain_def_weight",
            "retreat_terrain_bonus","archer_keep_distance","archer_prefer_high",
            "build_efficiency","resource_variety","research_priority",
            "military_tech_bias","cavalry_production","archer_production",
        ].iter().map(|s| s.to_string()).collect();
        for name in &["supp_mil","branch_white_enemy","org_tech","crisis_mil","fac_dist","turn_branch","enemy_aw_def","supp_per_mil","res_tech","expand_supp","archer_cav","inf_mountain"] {
            v.push(name.to_string());
        }
        v
    };

    let mut rng = ChaCha12Rng::seed_from_u64(12345678);
    let gconfig = GreedyConfig::default();
    let sb = 700000u64;

    // 初始化
    let mut population: Vec<Individual> = (0..pop_size).map(|_| {
        let mut w = HashMap::new();
        for name in &weight_names {
            let base = default_weight(name);
            w.insert(name.clone(), (base + rng.gen_range(-1.0..1.0)).max(0.01).min(5.0));
        }
        Individual { weights: w, fitness: 0.0 }
    }).collect();

    let mut best_ever = Individual { weights: HashMap::new(), fitness: 0.0 };
    eprintln!("Evo-V1: {}个体×{}代×{}seeds, {}特征(25+12交互)", pop_size, generations, seeds_per, weight_names.len());

    for gen in 0..generations {
        let results: Vec<(usize, f64)> = population.iter().enumerate()
            .collect::<Vec<_>>().par_iter().map(|(idx, ind)| {
                let mut agent = EvoAgent::new();
                agent.weights = ind.weights.clone();
                agent.config = gconfig.clone();
                let mut total_wr = 0.0f64;
                for (_, opp) in &opponents {
                    let mut wins = 0u32;
                    for i in 0..seeds_per {
                        let seed = sb + gen as u64*100000 + *idx as u64*1000 + i as u64;
                        let g = run_one_game(seed, &agent, *opp, "balanced", &cfg);
                        if g.winner == Some(0) { wins += 1; }
                        let g2 = run_one_game(seed+500000, *opp, &agent, "balanced", &cfg);
                        if g2.winner == Some(1) { wins += 1; }
                    }
                    total_wr += wins as f64 / (seeds_per*2) as f64;
                }
                (*idx, total_wr / opponents.len() as f64)
            }).collect();

        for (idx, fit) in results { population[idx].fitness = fit; }
        population.sort_by(|a,b| b.fitness.partial_cmp(&a.fitness).unwrap());
        let best = &population[0];
        if best.fitness > best_ever.fitness { best_ever = best.clone(); }
        if gen % 10 == 0 || best.fitness > best_ever.fitness {
            eprintln!("Gen {}: best={:.3} top10={:.3} {}", gen, best.fitness,
                population.iter().take(10).map(|i|i.fitness).sum::<f64>()/10.0,
                if best.fitness > best_ever.fitness {"★"}else{""});
        }

        // 繁殖
        let mut next_gen = Vec::with_capacity(pop_size);
        for i in 0..5.min(pop_size) { next_gen.push(population[i].clone()); }
        while next_gen.len() < pop_size {
            let p1 = tournament_select(&population, 5, &mut rng);
            let p2 = tournament_select(&population, 5, &mut rng);
            let mut child_w = HashMap::new();
            for name in &weight_names {
                let v1 = *p1.weights.get(name).unwrap_or(&1.0);
                let v2 = *p2.weights.get(name).unwrap_or(&1.0);
                let (lo,hi) = if v1<v2{(v1,v2)}else{(v2,v1)};
                let cv = lo - 0.5*(hi-lo) + rng.gen::<f64>()*(hi-lo)*2.0;
                child_w.insert(name.clone(), cv.max(0.01).min(5.0));
            }
            for name in &weight_names {
                if rng.gen::<f64>() < 0.2 {
                    let v = *child_w.get(name).unwrap_or(&1.0);
                    child_w.insert(name.clone(), (v+rng.gen_range(-0.3..0.3)).max(0.01).min(5.0));
                }
            }
            next_gen.push(Individual{weights:child_w, fitness:0.0});
        }
        population = next_gen;
    }

    let output = serde_json::json!({"weights":best_ever.weights,"fitness":best_ever.fitness,"generation":generations});
    std::fs::write(out_path, serde_json::to_string_pretty(&output).unwrap()).unwrap();
    eprintln!("V1完成: fitness={:.3} → {}", best_ever.fitness, out_path);
}

fn tournament_select(pop: &[Individual], k: usize, rng: &mut impl Rng) -> Individual {
    let best_idx = (0..k).map(|_| rng.gen_range(0..pop.len())).max_by(|&a,&b| pop[a].fitness.partial_cmp(&pop[b].fitness).unwrap()).unwrap();
    pop[best_idx].clone()
}

fn default_weight(name: &str) -> f64 {
    match name {
        "attack_adjacent"|"rush_enemy_city"|"defend_own_city"|"archer_keep_distance"|"build_efficiency"|"resource_variety"|"research_priority"|"cavalry_production"|"archer_production" => 1.0,
        "intercept_near_city" => 0.8, "retreat_hp_threshold" => 0.3,
        "terrain_def_weight" => 0.15, "retreat_terrain_bonus" => 0.3,
        "archer_prefer_high" => 0.1, "military_tech_bias" => 0.5,
        _ => 0.5, // 交互特征默认0.5
    }
}
