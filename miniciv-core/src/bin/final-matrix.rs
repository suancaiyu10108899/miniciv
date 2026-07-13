// P1.5最终矩阵: FlatMC d24 vs Evo vs StateAware vs AlwaysWhite vs Builder vs Adaptive
// 6×6 × 500 seeds
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{AlwaysWhiteAgent, StateAwareAgent, AdaptiveAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_matrix_par;
use std::io::Write;

fn main() {
    let seeds: u32 = 500;
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0, starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    // 加载训练后Evo
    let mut evo = EvoAgent::new();
    if let Ok(json) = std::fs::read_to_string("../experiments/v0.10-redwhite/evo-trained-weights.json") {
        if let Ok(data) = serde_json::from_str::<serde_json::Value>(&json) {
            if let Some(wmap) = data.get("weights") {
                for (k,v) in wmap.as_object().unwrap() { evo.weights.insert(k.clone(), v.as_f64().unwrap_or(1.0)); }
            }
        }
    }

    let flatmc = FlatMcAgent::with_depth(24);
    let builder = BuilderAgent; let aw = AlwaysWhiteAgent; let sa = StateAwareAgent; let adaptive = AdaptiveAgent;
    let agents: Vec<&dyn Agent> = vec![&flatmc, &evo, &sa, &aw, &builder, &adaptive];
    let names = ["FlatMC_d24","Evo_V2b","StateAware","AlwaysWhite","Builder","Adaptive"];

    eprintln!("最终矩阵: 6 AI × {} seeds, C1甜点", seeds);
    let m = run_matrix_par(&agents, seeds, 990000, "balanced", &cfg);

    // 输出矩阵
    println!("═══ 最终矩阵 ({} seeds, C1) ═══", seeds);
    for p in &m.pairs {
        println!("{:>14} vs {:<14} {:6.1}%  Cq:{} Cs:{} Tb:{} avgT:{:.1}",
            p.a, p.b, p.a_win_rate*100.0, p.conquest, p.construction, p.tiebreak, p.avg_turns);
    }
    println!("\n═══ 全局胜率 ═══");
    for s in &m.summaries { println!("  {:>14}: {:5.1}%", s.agent, s.avg_vs_others*100.0); }

    // 保存
    let out = "../experiments/v0.10-redwhite/final-matrix-500s.json";
    std::fs::write(out, serde_json::to_string_pretty(&m).unwrap()).unwrap();
    eprintln!("→ {}", out);
}
