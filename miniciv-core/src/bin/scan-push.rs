// P1.5 Phase 2: 扩参数粗扫 → 推高回合数至65-80T (rayon并行版)
// 第六个AI。在 scan-fine v4 基础上扩大参数范围 + 加入分支点扫描。
// 目标: 找到均结束回合 >55T 且征服/建设双路径成立的参数候选区。
//
// 用法: cargo run --release --bin scan-push -- [seeds_per_combo] [seed_base] [output.txt]
// 默认: 30 seeds(粗扫), seed_base=200000
// 输出: CSV到stdout(重定向到文件) + 进度到stderr

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
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(30);
    let sb: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(200000);

    let b = BuilderAgent; let r = RusherAgent;
    let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;
    let ar = AlwaysRedAgent;

    // 扩参数范围(比 scan-fine v4 的 ttM∈[8,9] 更激进)
    let ttM_vals: Vec<f64> = vec![10.0, 12.0, 14.0, 16.0];
    let uM_vals: Vec<f64> = vec![8.0, 10.0, 12.0, 14.0];
    let fBT_vals: Vec<u8> = vec![10, 12, 14];
    let hp_vals: Vec<i32> = vec![1500, 2000, 2500, 3000];
    let tcM_vals: Vec<f64> = vec![3.0, 4.0, 5.0];
    let startR_vals: Vec<i32> = vec![30, 40, 50];
    let branch_vals: Vec<u16> = vec![25, 30, 35, 40];

    // 收集所有参数组合
    struct ParamCombo { idx: u64, ttM: f64, uM: f64, fBT: u8, hp: i32, tcM: f64, startR: i32, branch: u16 }
    let mut combos: Vec<ParamCombo> = Vec::new();
    for &ttM in &ttM_vals { for &uM in &uM_vals { for &fBT in &fBT_vals {
    for &hp in &hp_vals { for &tcM in &tcM_vals { for &startR in &startR_vals {
    for &branch in &branch_vals {
        combos.push(ParamCombo { idx: combos.len() as u64, ttM, uM, fBT, hp, tcM, startR, branch });
    }}}}}}}

    let total = combos.len();
    let total_games = total as u64 * seeds as u64 * 4;
    eprintln!("scan-push: {} 参数组合 × {} seeds × 4 pairs = {} 局 (rayon并行)",
        total, seeds, total_games);
    eprintln!("参数范围: ttM={:?}, uM={:?}, fBT={:?}, hp={:?}, tcM={:?}, startR={:?}, branch={:?}",
        ttM_vals, uM_vals, fBT_vals, hp_vals, tcM_vals, startR_vals, branch_vals);

    // CSV header
    println!("ttM,uM,fBT,hp,tcM,startR,branch,BvR_T,BvR_Cq%,BvR_Cs%,BvR_Tb%,SvA_T,SvA_WR%,SvR_T,SvR_WR%,WvR_T,WvR_WR%");

    let done = AtomicU64::new(0);

    // 并行处理所有参数组合
    let results: Vec<String> = combos.par_iter().map(|combo| {
        let cfg = GameConfig {
            max_turns: 300,
            tech_turns_mult: combo.ttM,
            all_tech_cost_mult: combo.tcM,
            unit_cost_mult: combo.uM,
            facility_build_turns: combo.fBT,
            city_hp: combo.hp,
            c_line_cost_mult: 1.0,
            starting_food: combo.startR, starting_wood: combo.startR, starting_gold: combo.startR,
            facility_output: 4, starting_workers: 2,
            branch_available_turn: combo.branch,
            ..GameConfig::default()
        };

        // Pair 1: Builder vs Rusher
        let (mut bt, mut b_cq, mut b_cs, mut b_tb) = (0u64,0u32,0u32,0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + i as u64, &b, &r, "balanced", &cfg);
            bt += g.turns as u64;
            match g.victory_type {
                Some(VictoryType::Conquest) => b_cq += 1,
                Some(VictoryType::Construction) => b_cs += 1,
                _ => b_tb += 1,
            }
        }
        let bn = seeds;
        let bvr_t = bt as f64 / bn as f64;

        // Pair 2: StateAware vs AlwaysWhite
        let (mut st, mut sw_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 100000 + i as u64, &sw, &aw, "balanced", &cfg);
            st += g.turns as u64;
            if g.winner == Some(0) { sw_wins += 1; }
        }
        let sva_t = st as f64 / bn as f64;
        let sva_wr = sw_wins as f64 / bn as f64 * 100.0;

        // Pair 3: StateAware vs AlwaysRed
        let (mut srt, mut sr_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 200000 + i as u64, &sw, &ar, "balanced", &cfg);
            srt += g.turns as u64;
            if g.winner == Some(0) { sr_wins += 1; }
        }
        let svr_t = srt as f64 / bn as f64;
        let svr_wr = sr_wins as f64 / bn as f64 * 100.0;

        // Pair 4: AlwaysWhite vs AlwaysRed
        let (mut wrt, mut wr_wins) = (0u64, 0u32);
        for i in 0..seeds {
            let g = run_one_game(sb + combo.idx * 1000 + 300000 + i as u64, &aw, &ar, "balanced", &cfg);
            wrt += g.turns as u64;
            if g.winner == Some(0) { wr_wins += 1; }
        }
        let wvr_t = wrt as f64 / bn as f64;
        let wvr_wr = wr_wins as f64 / bn as f64 * 100.0;

        let cqp = b_cq as f64 / bn as f64 * 100.0;
        let csp = b_cs as f64 / bn as f64 * 100.0;
        let tbp = b_tb as f64 / bn as f64 * 100.0;

        // 进度(每完成约5%汇报)
        let d = done.fetch_add(1, Ordering::Relaxed) + 1;
        if d % (total as u64 / 20).max(1) == 0 {
            eprintln!("进度: {}/{} ({:.0}%)", d, total, d as f64 / total as f64 * 100.0);
        }

        format!("{:.0},{:.0},{},{},{:.0},{},{},{:.1},{:.0},{:.0},{:.0},{:.1},{:.1},{:.1},{:.1},{:.1},{:.1}",
            combo.ttM, combo.uM, combo.fBT, combo.hp, combo.tcM, combo.startR, combo.branch,
            bvr_t, cqp, csp, tbp, sva_t, sva_wr, svr_t, svr_wr, wvr_t, wvr_wr)
    }).collect();

    // 输出结果
    for line in &results {
        println!("{}", line);
    }

    eprintln!("完成。{} 条结果写到 stdout", results.len());
    eprintln!("分析提示: grep ',{:.0},' 筛选回合>55T的组合", 55.0);
    eprintln!("          awk -F, '$8>55 && $9>20 && $10>20' 找候选区");
}
