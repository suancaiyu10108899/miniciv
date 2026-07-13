// P1.5 BC蒸馏: 采集FlatMC d32的训练数据
// 记录每回合的状态特征和FlatMC的决策(6个分解动作)
// 用法: cargo run --release --bin bc-collect -- [games] [output.csv]
// 默认: 500 games

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, StateAwareAgent};
use miniciv_core::ai::Action;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{GameState, init_game_with_config, step_game, VictoryType};
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n_games: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(500);
    let out = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-training-data.csv".to_string());

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let teacher = FlatMcAgent::with_depth(32);
    let opps: Vec<(&str, &dyn Agent)> = vec![
        ("Builder", &BuilderAgent as &dyn Agent),
        ("Rusher", &RusherAgent as &dyn Agent),
        ("AlwaysWhite", &AlwaysWhiteAgent as &dyn Agent),
        ("StateAware", &StateAwareAgent as &dyn Agent),
    ];

    // CSV header: 25 features + 6 action labels
    let header = "game,turn,pid,opp_name,my_support,my_org,my_branch,my_crisis,my_expand,my_food,my_wood,my_gold,my_inf,my_cav,my_arc,my_worker,my_city_hp,my_techs,my_facs,opp_food,opp_wood,opp_gold,opp_inf,opp_cav,opp_arc,opp_city_hp,opp_techs,dist_to_opp_city,act_research,act_produce,act_posture,act_branch,act_redeem,act_expand";
    let mut f = std::fs::File::create(&out).unwrap();
    writeln!(f, "{}", header).ok();
    f.flush().ok();

    let sb = 970000u64;
    let mut total_rows = 0u64;

    for game_i in 0..n_games {
        let opp_idx = (game_i % opps.len() as u32) as usize;
        let (opp_name, opp_agent) = opps[opp_idx];
        let seed = sb + game_i as u64 * 100;

        let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
        let mut rng0 = rand_chacha::ChaCha12Rng::seed_from_u64(seed);
        let mut rng1 = rand_chacha::ChaCha12Rng::seed_from_u64(seed + 1);

        while gs.winner.is_none() && gs.turn < gs.config.max_turns {
            let flatmc_actions = teacher.decide(&gs, 0, &mut rng0);
            let opp_actions = opp_agent.decide(&gs, 1, &mut rng1);

            // 提取状态特征
            let feats = extract_features(&gs, 0, opp_name);
            // 分解FlatMC的动作为6个标签
            let labels = decompose_actions(&flatmc_actions);

            let row = vec![
                game_i.to_string(), gs.turn.to_string(), "0".to_string(), opp_name.to_string(),
                format!("{:.4}", feats[0]), format!("{:.4}", feats[1]),
                format!("{:.1}", feats[2]), format!("{:.1}", feats[3]), format!("{:.1}", feats[4]),
                format!("{:.1}", feats[5]), format!("{:.1}", feats[6]), format!("{:.1}", feats[7]),
                format!("{:.1}", feats[8]), format!("{:.1}", feats[9]), format!("{:.1}", feats[10]),
                format!("{:.1}", feats[11]), format!("{:.1}", feats[12]), format!("{:.1}", feats[13]),
                format!("{:.1}", feats[14]), format!("{:.1}", feats[15]), format!("{:.1}", feats[16]),
                format!("{:.1}", feats[17]), format!("{:.1}", feats[18]), format!("{:.1}", feats[19]),
                format!("{:.1}", feats[20]), format!("{:.1}", feats[21]), format!("{:.1}", feats[22]),
                format!("{:.1}", feats[23]), format!("{:.1}", feats[24]),
                labels.0, labels.1, labels.2, labels.3, labels.4, labels.5,
            ].join(",");
            writeln!(f, "{}", row).ok();
            total_rows += 1;

            step_game(&mut gs, &flatmc_actions, &opp_actions);
        }

        if game_i % 50 == 0 {
            f.flush().ok();
            eprintln!("  {} games, {} rows", game_i + 1, total_rows);
        }
    }

    f.flush().ok();
    eprintln!("完成: {} games, {} rows → {}", n_games, total_rows, out);
}

/// 提取25维特征
fn extract_features(gs: &GameState, pid: u8, _opp_name: &str) -> Vec<f64> {
    let opp = 1 - pid;
    let my_e = &gs.economies[pid as usize];
    let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;

    let my_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive && u.player_id == pid).collect();
    let opp_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive && u.player_id == opp).collect();

    let count_unit = |units: &[&miniciv_core::unit::Unit], ut: UnitType| -> f64 {
        units.iter().filter(|u| u.unit_type == ut).count() as f64
    };

    let mut my_facs = 0u32;
    for r in 0..ms { for q in 0..ms { if let Some(f) = &gs.grid.get(q, r).facility { if f.player_id == pid { my_facs += 1; } } } }

    let my_cq = gs.cities[pid as usize].q; let my_cr = gs.cities[pid as usize].r;
    let opp_cq = gs.cities[opp as usize].q; let opp_cr = gs.cities[opp as usize].r;
    let min_dist = my_units.iter().filter(|u| u.unit_type != UnitType::Worker).map(|u| hex_distance(u.q, u.r, opp_cq, opp_cr) as f64).fold(99.0, f64::min);

    vec![
        my_e.support as f64 / 100.0,                              // 0
        my_e.organization as f64 / 100.0,                         // 1
        match my_e.branch { Some(Branch::White)=>1.0, Some(Branch::Red)=>-1.0, None=>0.0 }, // 2
        my_e.crisis_timer as f64 / 20.0,                          // 3
        my_e.expansion_level as f64 / 5.0,                        // 4
        my_e.food as f64 / 200.0, my_e.wood as f64 / 200.0, my_e.gold as f64 / 200.0, // 5-7
        count_unit(&my_units, UnitType::Infantry), count_unit(&my_units, UnitType::Cavalry), // 8-9
        count_unit(&my_units, UnitType::Archer), count_unit(&my_units, UnitType::Worker), // 10-11
        gs.cities[pid as usize].hp as f64 / 2000.0,              // 12
        gs.techs[pid as usize].completed.len() as f64 / 13.0,    // 13
        my_facs as f64 / 8.0,                                     // 14
        opp_e.food as f64 / 200.0, opp_e.wood as f64 / 200.0, opp_e.gold as f64 / 200.0, // 15-17
        count_unit(&opp_units, UnitType::Infantry), count_unit(&opp_units, UnitType::Cavalry), // 18-19
        count_unit(&opp_units, UnitType::Archer),                 // 20
        gs.cities[opp as usize].hp as f64 / 2000.0,              // 21
        gs.techs[opp as usize].completed.len() as f64 / 13.0,    // 22
        min_dist / 15.0,                                          // 23
        gs.turn as f64 / 250.0,                                   // 24
    ]
}

/// 分解FlatMC动作列表为6个独立标签
fn decompose_actions(actions: &[Action]) -> (String, String, String, String, String, String) {
    let mut research = "None".to_string();
    let mut produce = "None".to_string();
    let mut posture = "Hold".to_string();
    let mut branch = "None".to_string();
    let mut redeem = "None".to_string();
    let mut expand = "No".to_string();

    for a in actions {
        match a {
            Action::Research { tech_id } => research = tech_id.clone(),
            Action::ProduceUnit { unit_type } => produce = unit_type.clone(),
            Action::ChooseBranch { branch: b } => branch = b.clone(),
            Action::RedeemOrg { mode } => redeem = mode.clone(),
            Action::Expand => expand = "Yes".to_string(),
            Action::Move { .. } => {
                // 推断姿态: 简单启发式(朝敌城=Attack, 朝己城=Defend)
                posture = "Attack".to_string(); // 实际更复杂, 简化
            }
            _ => {}
        }
    }
    (research, produce, posture, branch, redeem, expand)
}
