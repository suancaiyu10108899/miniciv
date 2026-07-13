// P1.5: 评估训练后的Evo在C1甜点全矩阵中的表现
// 用法: cargo run --release --bin eval-trained -- [seeds]
// 加载 evo-trained-weights.json, 在 C1 参数上跑全矩阵

use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::greedy::GreedyConfig;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, DefenderAgent, CavalryRusherAgent, AdaptiveAgent,
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_matrix_par;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(150);
    let out = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/evo-trained-matrix.json".to_string());

    // C1甜点
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    // 加载训练权重
    let weights_path = "../experiments/v0.10-redwhite/evo-trained-weights.json";
    let evo_trained = if let Ok(json) = std::fs::read_to_string(&weights_path) {
        if let Ok(data) = serde_json::from_str::<serde_json::Value>(&json) {
            let mut agent = EvoAgent::new();
            if let Some(wmap) = data.get("weights") {
                for (k, v) in wmap.as_object().unwrap() {
                    agent.weights.insert(k.clone(), v.as_f64().unwrap_or(1.0));
                }
            }
            eprintln!("Evo(训练后): 加载 {} 权重, fitness={:.3}", agent.weights.len(), data.get("fitness").and_then(|v| v.as_f64()).unwrap_or(0.0));
            agent
        } else {
            eprintln!("Evo: JSON解析失败, 使用默认权重");
            EvoAgent::new()
        }
    } else {
        eprintln!("Evo: 权重文件未找到({}), 使用默认权重", weights_path);
        EvoAgent::new()
    };
    let evo_default = EvoAgent::new();
    let greedy = GreedyAgent::new();

    let agents: Vec<&dyn Agent> = vec![
        &BuilderAgent, &RusherAgent, &CavalryRusherAgent,
        &DefenderAgent, &AdaptiveAgent, &RandomAgent,
        &AlwaysWhiteAgent, &AlwaysRedAgent, &StateAwareAgent, &TankThenRedAgent,
        &greedy, &evo_default, &evo_trained,
    ];

    eprintln!("矩阵: {} AI × {} seeds paired, C1甜点", agents.len(), seeds);
    let matrix = run_matrix_par(&agents, seeds, 950000, "balanced", &cfg);

    // 关键对局
    println!("═══ 关键对局 ═══");
    for p in &matrix.pairs {
        let keys = ["Builder","Rusher","StateAware","AlwaysWhite","Evo","AlwaysRed","TankThenRed","Defender"];
        if keys.iter().any(|k| p.a.contains(k)) && keys.iter().any(|k| p.b.contains(k)) {
            println!("{:>14} vs {:<14} {:6.1}%  Cq:{} Cs:{} Tb:{} avgT:{:.1}",
                p.a, p.b, p.a_win_rate*100.0, p.conquest, p.construction, p.tiebreak, p.avg_turns);
        }
    }
    println!("\n═══ 全局胜率 ═══");
    for s in &matrix.summaries {
        println!("  {:>16}: {:5.1}%", s.agent, s.avg_vs_others*100.0);
    }

    if let Ok(json) = serde_json::to_string_pretty(&matrix) {
        std::fs::write(&out, &json).ok();
        eprintln!("已写入 {}", out);
    }
}
