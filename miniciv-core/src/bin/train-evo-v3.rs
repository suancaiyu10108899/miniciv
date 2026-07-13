// 方向3: Evo分层GA — 战略层(4权重)→战术层(每策略3权重)=16权重
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

#[derive(Clone, Debug, Serialize, Deserialize)]
struct HierIndividual {
    /// 4个战略权重 → softmax选主策略
    strategy_weights: HashMap<String, f64>,
    /// 每个策略下的战术权重
    tactic_weights: HashMap<String, HashMap<String, f64>>,
    fitness: f64,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let generations: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(80);
    let pop_size: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(50);
    let seeds_per: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(15);

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let opponents: Vec<(&str, &dyn Agent)> = vec![
        ("Random",&RandomAgent as &dyn Agent),("Builder",&BuilderAgent),
        ("Rusher",&RusherAgent),("AlwaysWhite",&AlwaysWhiteAgent),("AlwaysRed",&AlwaysRedAgent),
    ];

    let strat_names = ["aggression","construction","defense","greed"];
    let tactic_names = ["rush_weight","research_pref","unit_pref"];
    let gconfig = GreedyConfig::default(); let sb = 700000u64;
    let mut rng = ChaCha12Rng::seed_from_u64(999);

    let mut pop: Vec<HierIndividual> = (0..pop_size).map(|_| {
        let mut sw = HashMap::new();
        for s in &strat_names { sw.insert(s.to_string(), rng.gen_range(0.5..2.0)); }
        let mut tw = HashMap::new();
        for &strat in &["Aggressive","Construction","Defensive","Greed"] {
            let mut m = HashMap::new();
            for t in &tactic_names { m.insert(t.to_string(), rng.gen_range(0.5..2.0)); }
            tw.insert(strat.to_string(), m);
        }
        HierIndividual{strategy_weights:sw, tactic_weights:tw, fitness:0.0}
    }).collect();

    eprintln!("Evo-V3: {}个体×{}代, 分层GA(4战略+12战术=16权重)", pop_size, generations);
    let mut best_ever = HierIndividual{strategy_weights:HashMap::new(),tactic_weights:HashMap::new(),fitness:0.0};

    for gen in 0..generations {
        let results: Vec<(usize,f64)> = pop.iter().enumerate().collect::<Vec<_>>().par_iter().map(|(idx,ind)| {
            let mut agent = EvoAgent::new(); agent.config = gconfig.clone();
            // 将分层权重转换为EvoAgent权重
            let mut w = HashMap::new();
            for (k,v) in &ind.strategy_weights { w.insert(k.clone(),*v); }
            for (_,tw) in &ind.tactic_weights { for (k,v) in tw { w.insert(k.clone(),*v); } }
            agent.weights = w;
            let mut total_wr = 0.0f64;
            for (_,opp) in &opponents {
                let mut wins = 0u32;
                for i in 0..seeds_per {
                    let seed = sb+gen as u64*100000+*idx as u64*1000+i as u64;
                    let g = run_one_game(seed,&agent,*opp,"balanced",&cfg);
                    if g.winner==Some(0){wins+=1;}
                    let g2 = run_one_game(seed+500000,*opp,&agent,"balanced",&cfg);
                    if g2.winner==Some(1){wins+=1;}
                }
                total_wr += wins as f64/(seeds_per*2) as f64;
            }
            (*idx, total_wr/opponents.len() as f64)
        }).collect();
        for (idx,fit) in results { pop[idx].fitness = fit; }
        pop.sort_by(|a,b| b.fitness.partial_cmp(&a.fitness).unwrap());
        if pop[0].fitness > best_ever.fitness { best_ever = pop[0].clone(); }
        if gen%10==0 { eprintln!("Gen {}: best={:.3} {}", gen, pop[0].fitness, if pop[0].fitness>best_ever.fitness{"★"}else{""}); }

        let mut next = Vec::with_capacity(pop_size);
        for i in 0..5.min(pop_size) { next.push(pop[i].clone()); }
        while next.len() < pop_size {
            let p1 = &pop[rng.gen_range(0..pop_size/2)];
            let p2 = &pop[rng.gen_range(0..pop_size/2)];
            let mut child = HierIndividual{strategy_weights:HashMap::new(),tactic_weights:HashMap::new(),fitness:0.0};
            for s in &strat_names {
                let v1=*p1.strategy_weights.get(*s).unwrap_or(&1.0);
                let v2=*p2.strategy_weights.get(*s).unwrap_or(&1.0);
                child.strategy_weights.insert(s.to_string(), ((v1+v2)/2.0+rng.gen_range(-0.3..0.3)).max(0.01).min(5.0));
            }
            for &strat in &["Aggressive","Construction","Defensive","Greed"] {
                let mut tm = HashMap::new();
                for t in &tactic_names {
                    let v1=*p1.tactic_weights.get(strat).and_then(|m|m.get(*t)).unwrap_or(&1.0);
                    let v2=*p2.tactic_weights.get(strat).and_then(|m|m.get(*t)).unwrap_or(&1.0);
                    tm.insert(t.to_string(), ((v1+v2)/2.0+rng.gen_range(-0.3..0.3)).max(0.01).min(5.0));
                }
                child.tactic_weights.insert(strat.to_string(), tm);
            }
            next.push(child);
        }
        pop = next;
    }

    let output = serde_json::json!({"strategy_weights":best_ever.strategy_weights,"tactic_weights":best_ever.tactic_weights,"fitness":best_ever.fitness});
    let out = "../experiments/v0.10-redwhite/evo-v3-weights.json";
    std::fs::write(out, serde_json::to_string_pretty(&output).unwrap()).unwrap();
    eprintln!("V3完成: fitness={:.3} → {}", best_ever.fitness, out);
}
