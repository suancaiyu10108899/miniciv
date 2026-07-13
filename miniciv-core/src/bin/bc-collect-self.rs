// BC自对弈数据采集 — 并行版, 每局即时flush, CPU拉满
// FlatMC d32 vs d24, 1000局
// 用法: cargo run --release --bin bc-collect-self -- [games]
use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::Action;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{GameState, init_game_with_config, step_game, VictoryType};
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::io::Write;
use std::sync::Mutex;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n_games: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(1000);
    let out_path = "../experiments/v0.10-redwhite/bc-selfplay-data.csv".to_string();

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0, starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let header = "game,turn,my_support,my_org,my_branch,my_crisis,my_expand,my_food,my_wood,my_gold,my_inf,my_cav,my_arc,my_worker,my_city_hp,my_techs,my_facs,opp_food,opp_wood,opp_gold,opp_inf,opp_cav,opp_arc,opp_city_hp,opp_techs,dist,act_research,act_produce,act_posture,act_branch,act_redeem,act_expand";
    std::fs::write(&out_path, format!("{}\n", header)).ok();

    let sb = 980000u64;
    let file_mutex = Mutex::new(std::fs::OpenOptions::new().append(true).open(&out_path).unwrap());
    let done = std::sync::atomic::AtomicU32::new(0);
    let total_rows = std::sync::atomic::AtomicU64::new(0);
    let start = std::time::Instant::now();

    eprintln!("BC自对弈: {}局 FlatMC d32 vs d24, CPU拉满", n_games);

    // 并行跑游戏: 每游戏分配独立seed
    (0..n_games).into_par_iter().for_each(|game_i| {
        let seed = sb + game_i as u64 * 100;
        let teacher = FlatMcAgent::with_depth(32);
        let opponent = FlatMcAgent::with_depth(24);
        let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
        let (mut r0, mut r1) = (ChaCha12Rng::seed_from_u64(seed), ChaCha12Rng::seed_from_u64(seed+1));
        let mut rows: Vec<String> = Vec::new();

        while gs.winner.is_none() && gs.turn < cfg.max_turns {
            let ta = teacher.decide(&gs, 0, &mut r0);
            let oa = opponent.decide(&gs, 1, &mut r1);
            let feats = extract_features(&gs, 0);
            let labels = decompose(&ta);
            let row = vec![
                game_i.to_string(), gs.turn.to_string(),
                format!("{:.4}",feats[0]),format!("{:.4}",feats[1]),
                format!("{:.1}",feats[2]),format!("{:.1}",feats[3]),format!("{:.1}",feats[4]),
                format!("{:.1}",feats[5]),format!("{:.1}",feats[6]),format!("{:.1}",feats[7]),
                format!("{:.1}",feats[8]),format!("{:.1}",feats[9]),format!("{:.1}",feats[10]),
                format!("{:.1}",feats[11]),format!("{:.1}",feats[12]),format!("{:.1}",feats[13]),
                format!("{:.1}",feats[14]),format!("{:.1}",feats[15]),format!("{:.1}",feats[16]),
                format!("{:.1}",feats[17]),format!("{:.1}",feats[18]),format!("{:.1}",feats[19]),
                format!("{:.1}",feats[20]),format!("{:.1}",feats[21]),format!("{:.1}",feats[22]),
                format!("{:.1}",feats[23]),format!("{:.1}",feats[24]),
                labels.0,labels.1,labels.2,labels.3,labels.4,labels.5,
            ].join(",");
            rows.push(row);
            step_game(&mut gs, &ta, &oa);
        }

        // 写盘
        let mut f = file_mutex.lock().unwrap();
        for row in &rows { writeln!(f, "{}", row).ok(); }
        f.flush().ok();
        drop(f);

        let n = done.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
        total_rows.fetch_add(rows.len() as u64, std::sync::atomic::Ordering::Relaxed);
        if n % 50 == 0 || n == n_games {
            eprintln!("[{}/{}] {}行 elapsed={:.0}s", n, n_games, total_rows.load(std::sync::atomic::Ordering::Relaxed), start.elapsed().as_secs());
        }
    });

    eprintln!("完成: {}行, {:.0}s", total_rows.load(std::sync::atomic::Ordering::Relaxed), start.elapsed().as_secs());
}

fn extract_features(gs: &GameState, pid: u8) -> Vec<f64> {
    let opp = 1-pid;
    let my_e = &gs.economies[pid as usize]; let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;
    let my_u: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==pid).collect();
    let op_u: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==opp).collect();
    let cu = |u: &[&miniciv_core::unit::Unit], t: UnitType| -> f64 { u.iter().filter(|x| x.unit_type==t).count() as f64 };
    let mut mf = 0u32; for r in 0..ms { for q in 0..ms { if let Some(f)=&gs.grid.get(q,r).facility { if f.player_id==pid {mf+=1;} } } }
    let (eq,er) = (gs.cities[opp as usize].q, gs.cities[opp as usize].r);
    let md = my_u.iter().filter(|u|u.unit_type!=UnitType::Worker).map(|u|hex_distance(u.q,u.r,eq,er)as f64).fold(99.0,f64::min);
    vec![
        my_e.support as f64/100.0, my_e.organization as f64/100.0,
        match my_e.branch{Some(Branch::White)=>1.0,Some(Branch::Red)=>-1.0,None=>0.0},
        my_e.crisis_timer as f64/20.0, my_e.expansion_level as f64/5.0,
        my_e.food as f64/200.0, my_e.wood as f64/200.0, my_e.gold as f64/200.0,
        cu(&my_u,UnitType::Infantry),cu(&my_u,UnitType::Cavalry),cu(&my_u,UnitType::Archer),cu(&my_u,UnitType::Worker),
        gs.cities[pid as usize].hp as f64/2000.0, gs.techs[pid as usize].completed.len() as f64/13.0, mf as f64/8.0,
        opp_e.food as f64/200.0,opp_e.wood as f64/200.0,opp_e.gold as f64/200.0,
        cu(&op_u,UnitType::Infantry),cu(&op_u,UnitType::Cavalry),cu(&op_u,UnitType::Archer),
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
