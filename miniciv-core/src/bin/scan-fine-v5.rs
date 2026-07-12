// P1.5 Phase 3: 细扫锁甜点 → 80-100 seeds, 高密度采样最佳候选区
// 第六个AI。基于粗扫结果(hp=2000聚类, branch=35-40, ttM=10-16)。
// 目标: 锁定满足所有目标的精确参数组合, 含方差/分布统计。
//
// 用法: cargo run --release --bin scan-fine-v5 -- [seeds] [seed_base]
// 默认: 80 seeds

use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{
    RusherAgent, StateAwareAgent, AlwaysWhiteAgent, AlwaysRedAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::VictoryType;
use rayon::prelude::*;
use std::sync::atomic::{AtomicU64, Ordering};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(80);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(400000);

    let b = BuilderAgent; let r = RusherAgent;
    let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;
    let ar = AlwaysRedAgent;

    // 细扫: 在粗扫最佳候选区做高密度采样
    // hp=2000固定, 其他参数在窄范围内精细采样
    let ttM_vals: Vec<f64> = vec![10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0];
    let uM_vals: Vec<f64> = vec![8.0, 9.0, 10.0, 11.0, 12.0];
    let fBT_vals: Vec<u8> = vec![10, 11, 12, 13, 14];
    let tcM_vals: Vec<f64> = vec![3.0, 3.5, 4.0, 4.5, 5.0];
    let startR_vals: Vec<i32> = vec![30, 35, 40, 45, 50];
    let branch_vals: Vec<u16> = vec![30, 33, 36, 40]; // 精细采样30-40区间

    struct ParamCombo { idx: u64, ttM: f64, uM: f64, fBT: u8, hp: i32, tcM: f64, startR: i32, branch: u16 }
    let mut combos: Vec<ParamCombo> = Vec::new();
    for &ttM in &ttM_vals { for &uM in &uM_vals { for &fBT in &fBT_vals {
    for &tcM in &tcM_vals { for &startR in &startR_vals { for &branch in &branch_vals {
        combos.push(ParamCombo { idx: combos.len() as u64, ttM, uM, fBT, hp: 2000, tcM, startR, branch });
    }}}}}}

    let total = combos.len();
    let total_games = total as u64 * seeds as u64 * 4;
    eprintln!("scan-fine-v5: {} 参数组合 × {} seeds × 4 pairs = {} 局 (hp=2000固定)",
        total, seeds, total_games);

    // 扩展CSV header: 加入方差/stddev
    println!("ttM,uM,fBT,hp,tcM,startR,branch,BvR_T,BvR_Tstd,BvR_Cq%,BvR_Cs%,BvR_Tb%,SvA_T,SvA_WR%,SvR_T,SvR_WR%,WvR_T,WvR_WR%");

    let done = AtomicU64::new(0);

    let results: Vec<String> = combos.par_iter().map(|combo| {
        let cfg = GameConfig {
            max_turns: 250,
            tech_turns_mult: combo.ttM, all_tech_cost_mult: combo.tcM,
            unit_cost_mult: combo.uM, facility_build_turns: combo.fBT,
            city_hp: combo.hp, c_line_cost_mult: 1.0,
            starting_food: combo.startR, starting_wood: combo.startR, starting_gold: combo.startR,
            facility_output: 4, starting_workers: 2,
            branch_available_turn: combo.branch,
            ..GameConfig::default()
        };

        // Pair 1: Builder vs Rusher (with variance)
        let mut turns: Vec<u16> = Vec::with_capacity(seeds as usize);
        let (mut b_cq, mut b_cs, mut b_tb) = (0u32,0u32,0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + i as u64, &b, &r, "balanced", &cfg);
            turns.push(g.turns);
            match g.victory_type {
                Some(VictoryType::Conquest) => b_cq += 1,
                Some(VictoryType::Construction) => b_cs += 1,
                _ => b_tb += 1,
            }
        }
        let bn = seeds as f64;
        let bvr_t = turns.iter().sum::<u16>() as f64 / bn;
        let bvr_std = (turns.iter().map(|&t| (t as f64 - bvr_t).powi(2)).sum::<f64>() / bn).sqrt();

        // Pair 2: StateAware vs AlwaysWhite
        let (mut st, mut sw_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 100000 + i as u64, &sw, &aw, "balanced", &cfg);
            st += g.turns as u64;
            if g.winner == Some(0) { sw_wins += 1; }
        }
        let sva_t = st as f64 / bn;
        let sva_wr = sw_wins as f64 / bn * 100.0;

        // Pair 3: StateAware vs AlwaysRed
        let (mut srt, mut sr_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 200000 + i as u64, &sw, &ar, "balanced", &cfg);
            srt += g.turns as u64;
            if g.winner == Some(0) { sr_wins += 1; }
        }
        let svr_t = srt as f64 / bn;
        let svr_wr = sr_wins as f64 / bn * 100.0;

        // Pair 4: AlwaysWhite vs AlwaysRed
        let (mut wrt, mut wr_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 300000 + i as u64, &aw, &ar, "balanced", &cfg);
            wrt += g.turns as u64;
            if g.winner == Some(0) { wr_wins += 1; }
        }
        let wvr_t = wrt as f64 / bn;
        let wvr_wr = wr_wins as f64 / bn * 100.0;

        let cqp = b_cq as f64 / bn * 100.0;
        let csp = b_cs as f64 / bn * 100.0;
        let tbp = b_tb as f64 / bn * 100.0;

        let d = done.fetch_add(1, Ordering::Relaxed) + 1;
        if d % (total as u64 / 10).max(1) == 0 {
            eprintln!("进度: {}/{} ({:.0}%)", d, total, d as f64 / total as f64 * 100.0);
        }

        format!("{:.0},{:.0},{},{},{:.1},{},{},{:.1},{:.1},{:.0},{:.0},{:.0},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1}",
            combo.ttM, combo.uM, combo.fBT, combo.hp, combo.tcM, combo.startR, combo.branch,
            bvr_t, bvr_std, cqp, csp, tbp, sva_t, sva_wr, svr_t, svr_wr, wvr_t, wvr_wr)
    }).collect();

    for line in &results { println!("{}", line); }
    eprintln!("完成。{} 条结果", results.len());
    eprintln!("分析提示: awk -F, 'NR>1 && $8>65 && $8<85 && $9>30 && $10>30 && $11<10 && $14>55'");
}
