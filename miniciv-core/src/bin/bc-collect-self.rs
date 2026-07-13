// Phase B: BC自对弈数据采集 — FlatMC d32 vs d24, 1000局
// 记录d32(更强)的决策作为教师信号
// 用法: cargo run --release --bin bc-collect-self -- [games] [output.csv]
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::Action;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{GameState, init_game_with_config, step_game};
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n_games: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(1000);
    let out = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-selfplay-data.csv".to_string());

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0, starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let teacher = FlatMcAgent::with_depth(32);
    let opponent = FlatMcAgent::with_depth(24);
    let sb = 980000u64;

    let header = "game,turn,my_support,my_org,my_branch,my_crisis,my_expand,my_food,my_wood,my_gold,my_inf,my_cav,my_arc,my_worker,my_city_hp,my_techs,my_facs,opp_food,opp_wood,opp_gold,opp_inf,opp_cav,opp_arc,opp_city_hp,opp_techs,dist,act_research,act_produce,act_posture,act_branch,act_redeem,act_expand";
    let mut f = std::fs::File::create(&out).unwrap();
    writeln!(f, "{}", header).ok();

    let mut total_rows = 0u64;
    for game_i in 0..n_games {
        let seed = sb + game_i as u64 * 100;
        let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
        let mut r0 = ChaCha12Rng::seed_from_u64(seed);
        let mut r1 = ChaCha12Rng::seed_from_u64(seed + 1);

        while gs.winner.is_none() && gs.turn < cfg.max_turns {
            let teacher_acts = teacher.decide(&gs, 0, &mut r0);
            let opp_acts = opponent.decide(&gs, 1, &mut r1);

            let feats = extract_features(&gs, 0);
            let labels = decompose(&teacher_acts);
            let row = format!("{},{},{},{:.4},{:.4},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1},{},{},{},{},{},{}",
                game_i, gs.turn,
                feats[0], feats[1], feats[2], feats[3], feats[4],
                feats[5], feats[6], feats[7], feats[8], feats[9], feats[10], feats[11],
                feats[12], feats[13], feats[14], feats[15], feats[16], feats[17], feats[18],
                feats[19], feats[20], feats[21], feats[22], feats[23], feats[24],
                labels.0, labels.1, labels.2, labels.3, labels.4, labels.5
            );
            writeln!(f, "{}", row).ok();
            total_rows += 1;
            step_game(&mut gs, &teacher_acts, &opp_acts);
        }
        if game_i % 100 == 0 { f.flush().ok(); eprintln!("  {} games, {} rows", game_i+1, total_rows); }
    }
    f.flush().ok();
    eprintln!("完成: {} games, {} rows → {}", n_games, total_rows, out);
}

fn extract_features(gs: &GameState, pid: u8) -> Vec<f64> {
    let opp = 1-pid;
    let my_e = &gs.economies[pid as usize]; let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;
    let my_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==pid).collect();
    let opp_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==opp).collect();
    let cu = |u: &[&miniciv_core::unit::Unit], t: UnitType| -> f64 { u.iter().filter(|x| x.unit_type==t).count() as f64 };
    let mut mf = 0u32; for r in 0..ms { for q in 0..ms { if let Some(f)=&gs.grid.get(q,r).facility { if f.player_id==pid {mf+=1;} } } }
    let (eq,er) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);
    let md = my_units.iter().filter(|u|u.unit_type!=UnitType::Worker).map(|u|hex_distance(u.q,u.r,eq,er)as f64).fold(99.0,f64::min);
    vec![
        my_e.support as f64/100.0, my_e.organization as f64/100.0,
        match my_e.branch{Some(Branch::White)=>1.0,Some(Branch::Red)=>-1.0,None=>0.0},
        my_e.crisis_timer as f64/20.0, my_e.expansion_level as f64/5.0,
        my_e.food as f64/200.0, my_e.wood as f64/200.0, my_e.gold as f64/200.0,
        cu(&my_units,UnitType::Infantry),cu(&my_units,UnitType::Cavalry),cu(&my_units,UnitType::Archer),cu(&my_units,UnitType::Worker),
        gs.cities[pid as usize].hp as f64/2000.0, gs.techs[pid as usize].completed.len() as f64/13.0, mf as f64/8.0,
        opp_e.food as f64/200.0,opp_e.wood as f64/200.0,opp_e.gold as f64/200.0,
        cu(&opp_units,UnitType::Infantry),cu(&opp_units,UnitType::Cavalry),cu(&opp_units,UnitType::Archer),
        gs.cities[opp as usize].hp as f64/2000.0, gs.techs[opp as usize].completed.len() as f64/13.0,
        md/15.0, gs.turn as f64/250.0,
    ]
}

fn decompose(actions: &[Action]) -> (String,String,String,String,String,String) {
    let (mut r,mut p,mut po,mut b,mut re,mut ex) = ("None".to_string(),"None".to_string(),"Attack".to_string(),"None".to_string(),"None".to_string(),"No".to_string());
    for a in actions {
        match a {
            Action::Research{tech_id}=>r=tech_id.clone(),
            Action::ProduceUnit{unit_type}=>p=unit_type.clone(),
            Action::ChooseBranch{branch:br}=>b=br.clone(),
            Action::RedeemOrg{mode}=>re=mode.clone(),
            Action::Expand=>ex="Yes".to_string(),
            _=>{}
        }
    }
    (r,p,po,b,re,ex)
}
