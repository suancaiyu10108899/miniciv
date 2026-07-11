// 单局回放 CLI — 阶段 0.2
//
// 用法:
//   cargo run --release --bin replay -- [ai_a] [ai_b] [seed] [out.json]
// 例:
//   cargo run --release --bin replay -- Builder Random 50000 replay.json
//
// 打印每回合摘要(城市HP/设施数/科技进度/胜利),让人"看懂一局"。
// 可选写完整回放 JSON(供未来可视化)。

use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, HarasserAgent, TurtleAgent, DefenderAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::snapshot::run_replay;

fn make_agent(name: &str) -> Box<dyn Agent> {
    match name.to_lowercase().as_str() {
        "builder" => Box::new(BuilderAgent),
        "rusher" => Box::new(RusherAgent),
        "harasser" => Box::new(HarasserAgent),
        "turtle" => Box::new(TurtleAgent),
        "defender" => Box::new(DefenderAgent),
        "greedy" => Box::new(GreedyAgent::new()),
        "evo" => Box::new(EvoAgent::new()),
        "random" => Box::new(RandomAgent),
        other => {
            // 不静默 fallback: 未知 AI 直接退出, 避免拿错误对局误导决策
            eprintln!("错误: 未知 AI '{}'。可选: Builder/Rusher/Harasser/Turtle/Greedy/Evo/Random", other);
            std::process::exit(1);
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let name_a = args.get(1).map(|s| s.as_str()).unwrap_or("Builder");
    let name_b = args.get(2).map(|s| s.as_str()).unwrap_or("Random");
    let seed: u64 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(50000);
    let out_path = args.get(4).cloned();
    let res: i32 = args.get(5).and_then(|s| s.parse().ok()).unwrap_or(25);

    let config = GameConfig {
        starting_food: res, starting_wood: res, starting_gold: res,
        ..GameConfig::default()
    };
    let a = make_agent(name_a);
    let b = make_agent(name_b);
    let rep = run_replay(seed, a.as_ref(), b.as_ref(), "balanced", &config);

    println!("回放: {} (P0) vs {} (P1)  seed={}", rep.config.ai_a, rep.config.ai_b, seed);
    println!("{:>4} | {:>16} | {:>16} | {:>16} | {:>16}",
             "回合", "P0城HP/设施", "P1城HP/设施", "P0科技", "P1科技");
    println!("{}", "-".repeat(80));

    for t in &rep.turns {
        let city_hp = |pid: u8| t.cities.iter().find(|c| c.pid == pid).map(|c| c.hp).unwrap_or(0);
        let facs = |pid: u8| *t.facility_count.get(&pid).unwrap_or(&0);
        let techs = |pid: u8| {
            t.techs.iter().find(|x| x.pid == pid)
                .map(|x| {
                    let mut s = x.completed.join(",");
                    if let Some(r) = &x.researching { s.push_str(&format!("(+{})", r)); }
                    s
                }).unwrap_or_default()
        };
        // 只打印有变化的关键回合 + 首尾, 避免刷屏
        println!("{:>4} | {:>10}/{:<4} | {:>10}/{:<4} | {:>16} | {:>16}",
                 t.turn, city_hp(0), facs(0), city_hp(1), facs(1),
                 techs(0), techs(1));
    }

    println!("{}", "-".repeat(80));
    println!("结果: winner={:?}  victory={:?}  final_turn={}",
             rep.result.winner, rep.result.victory_type, rep.result.final_turn);

    if let Some(path) = out_path {
        match serde_json::to_string_pretty(&rep) {
            Ok(json) => match std::fs::write(&path, json) {
                Ok(_) => eprintln!("完整回放已写入 {}", path),
                Err(e) => eprintln!("写文件失败 {}: {}", path, e),
            },
            Err(e) => eprintln!("序列化失败: {}", e),
        }
    }
}
