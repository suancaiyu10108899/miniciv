// 平衡打表 — 成本×城防 网格 × 多攻防AI(第三个AI)
//
// 修正认识(用户洞察): 军事不是单一参数, 攻城依兵种(骑兵55/步兵40/弓不占城)。
// 参数只设环境(成本=建设速度, city_hp=攻城次数台阶), 军事强弱靠AI兵种决策。
// 每格跑 3 种攻防打法 vs Builder, 看该环境下谁有活路。
//
// 用法: cargo run --release --bin table -- [seeds]

use miniciv_core::config::GameConfig;
use miniciv_core::ai::Agent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, CavalryRusherAgent, DefenderAgent};
use miniciv_core::eval::run_pair;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(150);
    let seed_base = 50000u64;

    // 轴1: C线成本(建设速度, 平滑). 轴2: city_hp 台阶(步兵2/3/4次打穿).
    let cost_opts = [1.0f64, 2.0, 3.0, 4.0];
    let hp_opts = [80i32, 120, 160];

    let builder = BuilderAgent;
    let inf = RusherAgent;       // 步兵 rush(40/次)
    let cav = CavalryRusherAgent; // 骑兵 rush(55/次, 有地形限制)
    let def = DefenderAgent;      // 步兵+弓箭手 防守+建设

    println!("平衡打表: {} seeds/格. 每格 = 攻防AI vs Builder 胜率(%)", seeds);
    println!("城HP台阶: 80=步兵2次, 120=3次, 160=4次打穿\n");
    println!("{:>6} {:>6} | {:>10} {:>10} {:>10} | {:>9}",
             "成本×", "城HP", "步兵rush", "骑兵rush", "防守Def", "建设T");
    println!("{}", "-".repeat(64));

    for &cost in &cost_opts {
        for &hp in &hp_opts {
            let cfg = GameConfig { c_line_cost_mult: cost, city_hp: hp, ..GameConfig::default() };
            let ri = run_pair(&inf, &builder, seeds, seed_base, "balanced", &cfg);
            let rc = run_pair(&cav, &builder, seeds, seed_base, "balanced", &cfg);
            let rd = run_pair(&def, &builder, seeds, seed_base, "balanced", &cfg);
            // 建设速度: Builder 视角结束回合(用步兵rush局的均值近似)
            println!("{:>6.1} {:>6} | {:>9.1}% {:>9.1}% {:>9.1}% | {:>8.1}",
                     cost, hp,
                     ri.a_win_rate * 100.0, rc.a_win_rate * 100.0, rd.a_win_rate * 100.0,
                     ri.avg_turns);
        }
    }

    println!("\n判读: 健康甜点带 = 步兵/骑兵rush 都在 20~70%(军事有活路但不碾压)");
    println!("      + 防守Def 也不碾压(不是纯建设无敌)。建设T 应落 40~80。");
}
