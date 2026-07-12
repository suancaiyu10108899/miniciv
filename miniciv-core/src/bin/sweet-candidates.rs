// P1.5 Phase 3: 甜点候选矩阵 + 完整 AI 评估（overnight 运行器）
// 第六个AI。从粗扫选出的 top 候选参数上跑完整矩阵。
//
// 用法: cargo run --release --bin sweet-candidates -- [seeds] [seed_base]
// 默认: 200 seeds (足够统计显著性)
// 输出: experiments/v0.10-redwhite/candidates-*.json

use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::greedy::GreedyAgent;
use miniciv_core::ai::evo::EvoAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, DefenderAgent, CavalryRusherAgent, AdaptiveAgent,
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::{run_matrix_par, run_pair_par};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(600000);

    // Top 3 候选(从粗扫结果选出, hp=2000固定)
    struct Candidate { name: &'static str, ttM: f64, uM: f64, fBT: u8, tcM: f64, startR: i32, branch: u16 }
    let candidates = vec![
        Candidate { name: "C1_平衡70-90T", ttM: 12.0, uM: 8.0, fBT: 14, tcM: 4.0, startR: 40, branch: 40 },
        Candidate { name: "C2_StateAware最强", ttM: 16.0, uM: 8.0, fBT: 14, tcM: 3.0, startR: 30, branch: 40 },
        Candidate { name: "C3_长游戏100T", ttM: 12.0, uM: 10.0, fBT: 14, tcM: 4.0, startR: 50, branch: 35 },
        // 额外: 尝试用更低ttM/fBT缩短到65-80T
        Candidate { name: "C4_缩短至70T", ttM: 10.0, uM: 8.0, fBT: 10, tcM: 4.0, startR: 40, branch: 40 },
        Candidate { name: "C5_缩短v2", ttM: 10.0, uM: 10.0, fBT: 12, tcM: 3.0, startR: 30, branch: 35 },
    ];

    let greedy = GreedyAgent::new();
    let evo = EvoAgent::new();
    let agents: Vec<&dyn Agent> = vec![
        &BuilderAgent, &RusherAgent, &CavalryRusherAgent,
        &DefenderAgent, &AdaptiveAgent, &RandomAgent,
        &AlwaysWhiteAgent, &AlwaysRedAgent, &StateAwareAgent, &TankThenRedAgent,
        &greedy, &evo,
    ];

    for cand in &candidates {
        let cfg = GameConfig {
            max_turns: 250,
            tech_turns_mult: cand.ttM,
            all_tech_cost_mult: cand.tcM,
            unit_cost_mult: cand.uM,
            facility_build_turns: cand.fBT,
            city_hp: 2000,
            c_line_cost_mult: 1.0,
            starting_food: cand.startR, starting_wood: cand.startR, starting_gold: cand.startR,
            facility_output: 4, starting_workers: 2,
            branch_available_turn: cand.branch,
            ..GameConfig::default()
        };

        eprintln!("\n═══ {} ═══", cand.name);
        eprintln!("ttM={:.0} uM={:.0} fBT={} hp=2000 tcM={:.0} startR={} branch@T{}",
            cand.ttM, cand.uM, cand.fBT, cand.tcM, cand.startR, cand.branch);

        // 先跑关键 pair 获得快速信号
        let b = BuilderAgent; let r = RusherAgent;
        let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;
        let ar = AlwaysRedAgent;

        let bvr = run_pair_par(&b, &r, seeds, sb, "balanced", &cfg);
        eprintln!("  BvR: T={:.1} Cq={:.0}% Cs={:.0}% Tb={:.0}% P0={:.1}%",
            bvr.avg_turns, bvr.a_win_conquest as f64/seeds as f64*100.0,
            bvr.a_win_construction as f64/seeds as f64*100.0,
            bvr.a_win_tiebreak as f64/seeds as f64*100.0,
            bvr.p0_win_rate*100.0);

        let sva = run_pair_par(&sw, &aw, seeds, sb+100000, "balanced", &cfg);
        eprintln!("  SvA: T={:.1} WR={:.1}%", sva.avg_turns, sva.a_win_rate*100.0);

        let svr = run_pair_par(&sw, &ar, seeds, sb+200000, "balanced", &cfg);
        eprintln!("  SvR: T={:.1} WR={:.1}%", svr.avg_turns, svr.a_win_rate*100.0);

        let wvr = run_pair_par(&aw, &ar, seeds, sb+300000, "balanced", &cfg);
        eprintln!("  WvR: T={:.1} WR={:.1}%", wvr.avg_turns, wvr.a_win_rate*100.0);

        // 完整矩阵
        eprintln!("  完整 12-AI 矩阵...");
        let matrix = run_matrix_par(&agents, seeds, sb+400000, "balanced", &cfg);

        let out = format!("experiments/v0.10-redwhite/candidate-{}-{}s.json", cand.name, seeds);
        if let Ok(json) = serde_json::to_string_pretty(&matrix) {
            std::fs::write(&out, &json).ok();
            eprintln!("  已写入 {}", out);
        }

        // 打印关键对局
        println!("\n═══ {} ═══", cand.name);
        for p in &matrix.pairs {
            let keys = ["Builder","Rusher","StateAware","AlwaysWhite","AlwaysRed","TankThenRed","Defender","Greedy","Evo"];
            if keys.iter().any(|k| p.a.contains(k)) && keys.iter().any(|k| p.b.contains(k)) {
                println!("  {:>10} vs {:<10} {:6.1}%  Cq:{} Cs:{} Tb:{} avgT:{:.1}",
                    p.a, p.b, p.a_win_rate*100.0, p.conquest, p.construction, p.tiebreak, p.avg_turns);
            }
        }
        println!("  全局胜率:");
        for s in &matrix.summaries {
            println!("    {:>12}: {:5.1}%", s.agent, s.avg_vs_others*100.0);
        }
    }

    eprintln!("\n全部完成。");
}
