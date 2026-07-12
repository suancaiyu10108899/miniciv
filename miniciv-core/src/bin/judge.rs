// 立裁判 CLI — S2(第四个 AI)
// 1) FlatMC 裁判 vs 全部手写剧本的胜率矩阵(默认甜点配置)
// 2) 死机制使用率: FlatMC 是否自发使用侦察兵/弓箭手/非标准科技顺序
//
// 用法: cargo run --release --bin judge -- [seeds] [rollout_depth] [instr_seeds]

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, CavalryRusherAgent, DefenderAgent, AdaptiveAgent};
use miniciv_core::ai::Action;
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_pair_par as run_pair;
use miniciv_core::game::{init_game_with_config, step_game};
use miniciv_core::unit::UnitType;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(60);
    let depth: u16 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(25);
    let instr_seeds: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(20);
    let cfg = GameConfig::default();
    let seed_base = 50000u64;

    let judge = FlatMcAgent::with_depth(depth);
    let builder = BuilderAgent;
    let rusher = RusherAgent;
    let cav = CavalryRusherAgent;
    let def = DefenderAgent;
    let adaptive = AdaptiveAgent;
    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &builder), ("Rusher", &rusher), ("CavRusher", &cav),
        ("Defender", &def), ("Adaptive", &adaptive),
    ];

    eprintln!("裁判矩阵: FlatMC(depth={}) vs 剧本, {} seeds paired, 默认甜点(成本×2 HP160)", depth, seeds);
    println!("\n═══ FlatMC vs 手写剧本(paired 胜率) ═══");
    println!("{:>10} {:>8} {:>10}", "对手", "FlatMC胜率", "均结束T");
    println!("{}", "-".repeat(32));
    let mut sum = 0.0; let mut lo = 1.0f64; let mut worst = "";
    for (name, opp) in &opps {
        let p = run_pair(&judge, *opp, seeds, seed_base, "balanced", &cfg);
        println!("{:>10} {:9.1}% {:9.1}", name, p.a_win_rate * 100.0, p.avg_turns);
        sum += p.a_win_rate;
        if p.a_win_rate < lo { lo = p.a_win_rate; worst = name; }
    }
    println!("平均 {:.1}% | 最低 {:.1}%(vs {})", sum / opps.len() as f64 * 100.0, lo * 100.0, worst);

    // ── 死机制使用率 ──────────────────────────────
    println!("\n═══ 死机制使用率(FlatMC 自发使用? {} seeds, vs Rusher+Builder) ═══", instr_seeds);
    let std_order = ["C1", "C3", "C4", "C5"]; // Builder 固定链
    let mut prod: std::collections::BTreeMap<&str, u32> = Default::default();
    let mut research_events = 0u32;
    let mut nonstd_research = 0u32;  // 研究了非 C线主链的科技(M/E/C2)
    let mut archer_moves = 0u32;     // 弓箭手被移动(触发射程2)
    let mut scout_moves = 0u32;
    let mut games = 0u32;
    for (_, opp) in [("Rusher", &rusher as &dyn Agent), ("Builder", &builder as &dyn Agent)] {
        for i in 0..instr_seeds {
            let seed = seed_base + i as u64 * 100;
            let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
            let mut r0 = ChaCha12Rng::seed_from_u64(seed);
            let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);
            let mt = gs.config.max_turns;
            while gs.winner.is_none() && gs.turn < mt {
                let a0 = judge.decide(&gs, 0, &mut r0);
                // 统计 FlatMC(P0)本回合动作
                for act in &a0 {
                    match act {
                        Action::ProduceUnit { unit_type } => { *prod.entry(leak(unit_type)).or_insert(0) += 1; }
                        Action::Research { tech_id } => {
                            research_events += 1;
                            if !std_order.contains(&tech_id.as_str()) { nonstd_research += 1; }
                        }
                        Action::Move { unit_idx, .. } => {
                            // 判断被移动单位兵种
                            let pu: Vec<&miniciv_core::unit::Unit> = gs.units.iter()
                                .filter(|u| u.player_id == 0 && u.alive).collect();
                            if let Some(u) = pu.get(*unit_idx) {
                                match u.unit_type {
                                    UnitType::Archer => archer_moves += 1,
                                    UnitType::Scout => scout_moves += 1,
                                    _ => {}
                                }
                            }
                        }
                        _ => {}
                    }
                }
                let a1 = opp.decide(&gs, 1, &mut r1);
                step_game(&mut gs, &a0, &a1);
            }
            games += 1;
        }
    }
    println!("生产兵种分布(总计, {} 局):", games);
    for (k, v) in &prod {
        println!("  {:>9}: {}", k, v);
    }
    println!("研究事件 {} 次, 其中非C主链(M/E/C2) {} 次 ({:.0}%)",
             research_events, nonstd_research,
             nonstd_research as f64 / research_events.max(1) as f64 * 100.0);
    println!("弓箭手移动(触发射程2) {} 次 | 侦察兵移动 {} 次", archer_moves, scout_moves);
    println!("\n判读:");
    println!("  侦察兵/弓箭手/骑兵被自发生产+使用, 或研究大量偏离 C 主链 → 死机制被裁判激活 = 潜在深度(H1)");
    println!("  只产步兵+纯 C 主链、不碰侦察兵/弓箭手 → 死机制仍死 = 当前甜点浅(H0)");
}

// ProduceUnit 的 unit_type 是 String; 为 BTreeMap<&str> 转成 static。
fn leak(s: &str) -> &'static str {
    match s {
        "infantry" => "infantry", "cavalry" => "cavalry", "archer" => "archer",
        "scout" => "scout", "worker" => "worker", _ => "other",
    }
}
