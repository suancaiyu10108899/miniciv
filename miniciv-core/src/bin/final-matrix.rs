// P1.5 最终矩阵: 最强AI大乱斗, 500 seeds
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{AlwaysWhiteAgent,StateAwareAgent,AdaptiveAgent};
use miniciv_core::ai::bc::BcAgent;
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_matrix_par;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s|s.parse().ok()).unwrap_or(500);
    let out = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/final-matrix.json".to_string());
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000, c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };
    let fmc24 = FlatMcAgent::with_depth(24);
    let fmc32 = FlatMcAgent::with_depth(32);
    let mut evo = EvoAgent::new();
    if let Ok(j) = std::fs::read_to_string("../experiments/v0.10-redwhite/evo-trained-weights.json") {
        if let Ok(d) = serde_json::from_str::<serde_json::Value>(&j) {
            if let Some(wm) = d.get("weights") { for (k,v) in wm.as_object().unwrap() { evo.weights.insert(k.clone(),v.as_f64().unwrap_or(1.0)); } }
        }
    }
    let bc = BcAgent::from_file("../experiments/v0.10-redwhite/bc-v2-weights.json").ok();
    let builder = BuilderAgent; let aw = AlwaysWhiteAgent; let sa = StateAwareAgent; let ad = AdaptiveAgent;
    let mut agent_list: Vec<Box<dyn Agent>> = vec![Box::new(BuilderAgent),Box::new(AlwaysWhiteAgent),Box::new(StateAwareAgent),Box::new(AdaptiveAgent)];
    if let Some(b) = bc { eprintln!("BC loaded"); agent_list.push(Box::new(b)); }
    agent_list.push(Box::new(evo));
    let refs: Vec<&dyn Agent> = agent_list.iter().map(|a| a.as_ref()).collect();
    eprintln!("Final matrix: {} AI x {} seeds", refs.len(), seeds);
    let m = run_matrix_par(&refs, seeds, 980000, "balanced", &cfg);
    for p in &m.pairs { println!("{:>14} vs {:<14} {:6.1}%  Cq:{} Cs:{} Tb:{} T:{:.1}", p.a, p.b, p.a_win_rate*100.0, p.conquest, p.construction, p.tiebreak, p.avg_turns); }
    println!("\n=== 全局 ===");
    for s in &m.summaries { println!("  {}: {:.1}%", s.agent, s.avg_vs_others*100.0); }
    if let Ok(j) = serde_json::to_string_pretty(&m) { std::fs::write(&out,&j).ok(); eprintln!("-> {}",out); }
}
