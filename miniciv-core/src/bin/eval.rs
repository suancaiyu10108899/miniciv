// 批量评估 CLI — 门禁 1
//
// 用法:
//   cargo run --release --bin eval -- [seeds] [generator] [out.json]
// 例:
//   cargo run --release --bin eval -- 500 balanced experiments/eval.json
//
// 默认:seeds=100, generator=balanced, 不写文件(只打印表格)。
//
// 诚实原则:先打 pairwise paired 表(能直接看 Greedy vs Random),
// 再打镜像 P0 偏差(诊断先手不变量),最后才是跨对手平均(并标注它会被坏对手刷高)。

use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, HarasserAgent, TurtleAgent, DefenderAgent,
    CavalryRusherAgent, AdaptiveAgent,
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_matrix_par;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(100);
    let generator = args.get(2).map(|s| s.as_str()).unwrap_or("balanced").to_string();
    let out_path = args.get(3).cloned();
    // S2: 参数默认取自 GameConfig::default()(已=甜点), 不再写死 25/1.0/80。
    //     只在显式传参时覆盖。这样"跑 eval 无参"= 默认甜点, 消除工具漂移。
    let def = GameConfig::default();
    let starting_res: i32 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(def.starting_food);
    let cost_mult: f64 = args.get(5).and_then(|s| s.parse().ok()).unwrap_or(def.c_line_cost_mult);
    let city_hp: i32 = args.get(6).and_then(|s| s.parse().ok()).unwrap_or(def.city_hp);
    let seed_base = 50000u64;

    let config = GameConfig {
        starting_food: starting_res,
        starting_wood: starting_res,
        starting_gold: starting_res,
        c_line_cost_mult: cost_mult,
        city_hp,
        ..GameConfig::default()
    };

    let random = RandomAgent;
    let builder = BuilderAgent;
    let rusher = RusherAgent;
    let cavrusher = CavalryRusherAgent;
    let defender = DefenderAgent;
    let adaptive = AdaptiveAgent;
    let always_white = AlwaysWhiteAgent;
    let always_red = AlwaysRedAgent;
    let state_aware = StateAwareAgent;
    let tank_then_red = TankThenRedAgent;
    let _ = (GreedyAgent::new(), EvoAgent::new(), HarasserAgent, TurtleAgent);
    let agents: Vec<&dyn Agent> = vec![
        &builder, &rusher, &cavrusher, &defender, &adaptive, &random,
        &always_white, &always_red, &state_aware, &tank_then_red,
    ];

    eprintln!("跑矩阵: {} AI × {} seeds paired, 起手资源={} C线成本×{} cityHP={}",
              agents.len(), seeds, starting_res, cost_mult, city_hp);

    let m = run_matrix_par(&agents, seeds, seed_base, &generator, &config);

    println!("\n═══ Pairwise paired (先手偏差已抵消) ═══");
    println!("{:>8} vs {:<8} {:>8}  | A靠[征/建/平]赢  B靠[征/建/平]赢",
             "A", "B", "A胜率");
    println!("{}", "-".repeat(64));
    for p in &m.pairs {
        println!("{:>8} vs {:<8} {:7.1}%  |  {:>3}/{:>3}/{:<3}      {:>3}/{:>3}/{:<3}",
                 p.a, p.b, p.a_win_rate * 100.0,
                 p.a_win_conquest, p.a_win_construction, p.a_win_tiebreak,
                 p.b_win_conquest, p.b_win_construction, p.b_win_tiebreak);
    }

    println!("\n═══ 镜像 P0 偏差 (理想 ~50%, 偏离即先手不变量被破坏) ═══");
    println!("{:>8} {:>10} {:>7} {:>7} {:>7}  | {:>12} {:>10}",
             "AI", "P0胜率", "Cq%", "Cs%", "Tb%", "建设P0率", "随机tb P0率");
    println!("{}", "-".repeat(72));
    for mr in &m.mirrors {
        let s = mr.seeds as f64;
        let cs_p0 = if mr.construction > 0 { mr.construction_p0 as f64 / mr.construction as f64 * 100.0 } else { 0.0 };
        let tbr_p0 = if mr.tiebreak_random > 0 { mr.tiebreak_random_p0 as f64 / mr.tiebreak_random as f64 * 100.0 } else { 0.0 };
        println!("{:>8} {:9.1}% {:6.1}% {:6.1}% {:6.1}%  | {:10.1}% (n={:<3}) {:6.1}% (n={})",
                 mr.agent, mr.p0_win_rate * 100.0,
                 mr.conquest as f64 / s * 100.0,
                 mr.construction as f64 / s * 100.0,
                 mr.tiebreak as f64 / s * 100.0,
                 cs_p0, mr.construction, tbr_p0, mr.tiebreak_random);
    }

    println!("\n═══ 跨对手平均 (⚠️ 会被坏对手刷高,别拿来下结论) ═══");
    for s in &m.summaries {
        println!("{:>8}: {:.1}%", s.agent, s.avg_vs_others * 100.0);
    }

    if let Some(path) = out_path {
        match serde_json::to_string_pretty(&m) {
            Ok(json) => {
                if let Err(e) = std::fs::write(&path, json) {
                    eprintln!("写文件失败 {}: {}", path, e);
                } else {
                    eprintln!("\n已写入 {}", path);
                }
            }
            Err(e) => eprintln!("序列化失败: {}", e),
        }
    }
}
