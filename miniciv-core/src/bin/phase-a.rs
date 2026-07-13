// Phase A: FlatMC depth × Evo Gen120 全矩阵 + Evo基线
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{AlwaysWhiteAgent, StateAwareAgent, RusherAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par;
use std::io::Write;

fn main() {
    let seeds: u32 = 500;
    let sb: u64 = 980000;
    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    // Evo Gen120
    let mut evo = EvoAgent::new();
    if let Ok(json) = std::fs::read_to_string("../experiments/v0.10-redwhite/evo-trained-weights.json") {
        if let Ok(data) = serde_json::from_str::<serde_json::Value>(&json) {
            if let Some(wmap) = data.get("weights") {
                for (k, v) in wmap.as_object().unwrap() { evo.weights.insert(k.clone(), v.as_f64().unwrap_or(1.0)); }
            }
            eprintln!("Evo加载: fitness={:.3}", data.get("fitness").and_then(|v| v.as_f64()).unwrap_or(0.0));
        }
    }
    let builder = BuilderAgent; let aw = AlwaysWhiteAgent; let sa = StateAwareAgent; let rusher = RusherAgent;

    let out = "../experiments/v0.10-redwhite/phase-a-matrix.csv";
    let mut f = std::fs::File::create(out).unwrap();
    writeln!(f, "ai_a,ai_b,a_wr%,a_std%,avg_turns,time_sec,cq%,cs%,tb%").ok();

    // 1. Evo基线: vs 探针
    for (name, opp) in &[("Builder",&builder as &dyn Agent),("Rusher",&rusher),("AlwaysWhite",&aw),("StateAware",&sa)] {
        eprintln!("Evo vs {}...", name);
        let t0 = std::time::Instant::now();
        let p = run_pair_par(&evo, *opp, seeds, sb, "balanced", &cfg);
        let n = (seeds*2) as f64;
        let wr = p.a_win_rate*100.0; let ws = (p.a_win_rate*(1.0-p.a_win_rate)/n).sqrt()*100.0;
        let line = format!("Evo_G120,{},{:.1},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}", name, wr, ws, p.avg_turns, t0.elapsed().as_secs_f64(), p.a_win_conquest as f64/n*100.0, p.a_win_construction as f64/n*100.0, p.a_win_tiebreak as f64/n*100.0);
        writeln!(f, "{}", line).ok(); f.flush().ok();
        eprintln!("  WR={:.1}%±{:.1}", wr, ws);
    }

    // 2. FlatMC depth × Evo
    for &depth in &[16u16, 24, 32, 40] {
        let judge = FlatMcAgent::with_depth(depth);
        eprintln!("FlatMC d{} vs Evo...", depth);
        let t0 = std::time::Instant::now();
        let p = run_pair_par(&judge, &evo, seeds, sb + depth as u64*10000, "balanced", &cfg);
        let n = (seeds*2) as f64;
        let wr = p.a_win_rate*100.0; let ws = (p.a_win_rate*(1.0-p.a_win_rate)/n).sqrt()*100.0;
        let line = format!("FlatMC_d{},Evo_G120,{:.1},{:.1},{:.1},{:.1},{:.0},{:.0},{:.0}", depth, wr, ws, p.avg_turns, t0.elapsed().as_secs_f64(), p.a_win_conquest as f64/n*100.0, p.a_win_construction as f64/n*100.0, p.a_win_tiebreak as f64/n*100.0);
        writeln!(f, "{}", line).ok(); f.flush().ok();
        eprintln!("  WR={:.1}%±{:.1}", wr, ws);
    }

    eprintln!("Phase A done → {}", out);
}
