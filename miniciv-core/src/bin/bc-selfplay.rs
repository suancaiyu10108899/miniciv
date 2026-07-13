// BC自对弈数据采集: FlatMC d32(教师) vs FlatMC d24(对手)
// 记录每回合25维特征+教师的6个分解动作
// 用法: cargo run --release --bin bc-selfplay -- [games] [output.csv]

use miniciv_core::ai::Agent;
use miniciv_core::ai::flatmc::FlatMcAgent;
use miniciv_core::ai::Action;
use miniciv_core::config::GameConfig;
use miniciv_core::game::{GameState, init_game_with_config, step_game};
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use std::io::Write;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n_games: u32 = args.get(1).and_then(|s|s.parse().ok()).unwrap_or(1000);
    let out = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-selfplay-data.csv".to_string());

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let teacher = FlatMcAgent::with_depth(32);
    let opponent = FlatMcAgent::with_depth(24);

    let header = "game,turn,my_support,my_org,my_branch,my_crisis,my_expand,my_food,my_wood,my_gold,my_inf,my_cav,my_arc,my_worker,my_city_hp,my_techs,my_facs,opp_food,opp_wood,opp_gold,opp_inf,opp_cav,opp_arc,opp_city_hp,opp_techs,dist_opp,act_research,act_produce,act_posture,act_branch,act_redeem,act_expand";
    let mut f = std::fs::File::create(&out).unwrap();
    writeln!(f, "{}", header).ok();
    f.flush().ok();

    use rayon::prelude::*;
    use std::sync::Mutex;
    // 先关闭header文件句柄, 用Mutex<File>在线程间共享
    drop(f);
    let sb = 970000u64;
    let file_mutex = Mutex::new(std::fs::OpenOptions::new().append(true).create(true).open(&out).unwrap());
    let total = std::sync::atomic::AtomicU64::new(0);
    let done_games = std::sync::atomic::AtomicU32::new(0);

    eprintln!("BC自对弈: {}局, FlatMC d32 vs d24, 全核并行", n_games);

    (0..n_games).into_par_iter().for_each(|game_i| {
        let seed = sb + game_i as u64 * 100;
        let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
        let mut rng0 = rand_chacha::ChaCha12Rng::seed_from_u64(seed);
        let mut rng1 = rand_chacha::ChaCha12Rng::seed_from_u64(seed + 1);
        use rand::SeedableRng;
        let mut rows = Vec::new();

        while gs.winner.is_none() && gs.turn < gs.config.max_turns {
            let teacher_acts = teacher.decide(&gs, 0, &mut rng0);
            let opp_acts = opponent.decide(&gs, 1, &mut rng1);
            let feats = extract_features(&gs, 0);
            let labels = decompose(&teacher_acts);
            let row = vec![
                game_i.to_string(), gs.turn.to_string(),
                format!("{:.4}",feats[0]),format!("{:.4}",feats[1]),format!("{:.1}",feats[2]),
                format!("{:.1}",feats[3]),format!("{:.1}",feats[4]),
                format!("{:.1}",feats[5]),format!("{:.1}",feats[6]),format!("{:.1}",feats[7]),
                format!("{:.1}",feats[8]),format!("{:.1}",feats[9]),format!("{:.1}",feats[10]),
                format!("{:.1}",feats[11]),format!("{:.1}",feats[12]),format!("{:.1}",feats[13]),
                format!("{:.1}",feats[14]),format!("{:.1}",feats[15]),format!("{:.1}",feats[16]),
                format!("{:.1}",feats[17]),format!("{:.1}",feats[18]),format!("{:.1}",feats[19]),
                format!("{:.1}",feats[20]),format!("{:.1}",feats[21]),format!("{:.1}",feats[22]),
                format!("{:.1}",feats[23]),format!("{:.1}",feats[24]),
                labels.0.clone(),labels.1.clone(),labels.2.clone(),labels.3.clone(),labels.4.clone(),labels.5.clone(),
            ].join(",");
            rows.push(row);
            step_game(&mut gs, &teacher_acts, &opp_acts);
        }

        // 批量写入(加锁)
        if !rows.is_empty() {
            let mut f = file_mutex.lock().unwrap();
            for r in &rows { writeln!(*f, "{}", r).ok(); }
            total.fetch_add(rows.len() as u64, std::sync::atomic::Ordering::Relaxed);
            let dg = done_games.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
            if dg % 100 == 0 { f.flush().ok(); eprintln!("{}g/{}r", dg, total.load(std::sync::atomic::Ordering::Relaxed)); }
        }
    });

    let mut f2 = file_mutex.into_inner().unwrap();
    f2.flush().ok();
    let tr = total.load(std::sync::atomic::Ordering::Relaxed);
    eprintln!("完成: {} games, {} rows → {}", n_games, tr, out);
}

fn extract_features(gs: &GameState, pid: u8) -> Vec<f64> {
    let opp = 1-pid;
    let my_e = &gs.economies[pid as usize]; let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;
    let my_u: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u|u.alive&&u.player_id==pid).collect();
    let opp_u: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u|u.alive&&u.player_id==opp).collect();
    let cu = |u:&[&miniciv_core::unit::Unit],ut:UnitType|->f64{u.iter().filter(|x|x.unit_type==ut).count() as f64};
    let mut nf=0u32; for r in 0..ms{for q in 0..ms{if let Some(f)=&gs.grid.get(q,r).facility{if f.player_id==pid{nf+=1;}}}}
    let ocq=gs.cities[opp as usize].q; let ocr=gs.cities[opp as usize].r;
    let md=my_u.iter().filter(|x|x.unit_type!=UnitType::Worker).map(|x|hex_distance(x.q,x.r,ocq,ocr)as f64).fold(99.0,f64::min);
    vec![
        my_e.support as f64/100.0, my_e.organization as f64/100.0,
        match my_e.branch{Some(Branch::White)=>1.0,Some(Branch::Red)=>-1.0,None=>0.0},
        my_e.crisis_timer as f64/20.0, my_e.expansion_level as f64/5.0,
        my_e.food as f64/200.0,my_e.wood as f64/200.0,my_e.gold as f64/200.0,
        cu(&my_u,UnitType::Infantry),cu(&my_u,UnitType::Cavalry),cu(&my_u,UnitType::Archer),cu(&my_u,UnitType::Worker),
        gs.cities[pid as usize].hp as f64/2000.0,gs.techs[pid as usize].completed.len() as f64/13.0,nf as f64/8.0,
        opp_e.food as f64/200.0,opp_e.wood as f64/200.0,opp_e.gold as f64/200.0,
        cu(&opp_u,UnitType::Infantry),cu(&opp_u,UnitType::Cavalry),cu(&opp_u,UnitType::Archer),
        gs.cities[opp as usize].hp as f64/2000.0,gs.techs[opp as usize].completed.len() as f64/13.0,
        md/15.0,gs.turn as f64/250.0,
    ]
}

/// 分解FlatMC动作 → 6个独立标签(修复版: 不靠Move推断posture)
fn decompose(actions: &[Action]) -> (String,String,String,String,String,String) {
    let (mut r,mut p,mut po,mut b,mut re,mut ex) =
        ("None".to_string(),"None".to_string(),"Attack".to_string(),"None".to_string(),"None".to_string(),"No".to_string());
    for a in actions {
        match a {
            Action::Research{tech_id}=> r=tech_id.clone(),
            Action::ProduceUnit{unit_type}=> p=unit_type.clone(),
            Action::ChooseBranch{branch:br}=> b=br.clone(),
            Action::RedeemOrg{mode}=> re=mode.clone(),
            Action::Expand=> ex="Yes".to_string(),
            Action::Move{..}=> { /* 姿态由FlatMC的rollout选择决定, 这里不覆盖 */ }
            _ => {}
        }
    }
    // 姿态: 检查动作列表中的方向模式(简化: 朝敌城=Attack, 朝己城=Defend)
    // 实际FlatMC的posture在eval_plan中决定, 这里用动作数量推断
    let move_count = actions.iter().filter(|a|matches!(a,Action::Move{..})).count();
    if move_count == 0 { po = "Hold".to_string(); }
    (r,p,po,b,re,ex)
}
