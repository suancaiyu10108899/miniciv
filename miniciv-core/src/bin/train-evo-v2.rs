// 方向2: 小NN(25→32→16→6头) + 进化策略(ES)训练
// ~2000参数, ES梯度估计, 200代
// 用法: cargo run --release --bin train-evo-v2 -- [gens] [pop_N] [seeds]
use miniciv_core::ai::Agent;
use miniciv_core::ai::random::RandomAgent;
use miniciv_core::ai::fixed::BuilderAgent;
use miniciv_core::ai::probes::{RusherAgent, AlwaysWhiteAgent, AlwaysRedAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game;
use miniciv_core::game::GameState;
use miniciv_core::unit::UnitType;
use miniciv_core::economy::Branch;
use miniciv_core::movement::hex_distance;
use rand::Rng;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use rand_distr::{Normal, Distribution};
use rayon::prelude::*;
use serde::{Serialize, Deserialize};

// ── NN 架构: 25→32→16→6头 ──
#[derive(Clone, Debug, Serialize, Deserialize)]
struct NnWeights {
    // 层1: 25×32 + bias32
    w1: Vec<Vec<f64>>, // [32][25]
    b1: Vec<f64>,       // [32]
    // 层2: 32×16 + bias16
    w2: Vec<Vec<f64>>, // [16][32]
    b2: Vec<f64>,       // [16]
    // 6个输出头: each 16×N_out + bias
    head_w: Vec<Vec<Vec<f64>>>, // [6][N_out][16]
    head_b: Vec<Vec<f64>>,       // [6][N_out]
    head_sizes: Vec<usize>,      // [8,6,4,3,4,2]
}

impl NnWeights {
    fn new(rng: &mut impl Rng) -> Self {
        // He初始化: 均值0, 方差2/fan_in
        fn init_matrix(rows: usize, cols: usize, rng: &mut impl Rng) -> Vec<Vec<f64>> {
            let std = (2.0 / cols as f64).sqrt();
            let dist = Normal::new(0.0, std).unwrap();
            (0..rows).map(|_| (0..cols).map(|_| dist.sample(rng)).collect()).collect()
        };
        let init_bias = |n: usize| -> Vec<f64> { vec![0.0; n] };

        let head_sizes = vec![8, 6, 4, 3, 4, 2];
        let head_w: Vec<Vec<Vec<f64>>> = head_sizes.iter()
            .map(|&sz| init_matrix(sz, 16, rng)).collect();
        let head_b: Vec<Vec<f64>> = head_sizes.iter().map(|&sz| init_bias(sz)).collect();

        Self {
            w1: init_matrix(32, 25, rng),
            b1: init_bias(32),
            w2: init_matrix(16, 32, rng),
            b2: init_bias(16),
            head_w, head_b, head_sizes,
        }
    }

    /// 前向传播: 25维输入 → 6个输出标签
    fn forward(&self, x: &[f64]) -> [usize; 6] {
        // 层1: relu(W1·x + b1)
        let mut h1 = vec![0.0f64; 32];
        for i in 0..32 {
            let mut s = self.b1[i];
            for j in 0..25 { s += self.w1[i][j] * x[j]; }
            h1[i] = if s > 0.0 { s } else { 0.0 };
        }
        // 层2: relu(W2·h1 + b2)
        let mut h2 = vec![0.0f64; 16];
        for i in 0..16 {
            let mut s = self.b2[i];
            for j in 0..32 { s += self.w2[i][j] * h1[j]; }
            h2[i] = if s > 0.0 { s } else { 0.0 };
        }
        // 6个头: argmax
        let mut result = [0usize; 6];
        for head in 0..6 {
            let sz = self.head_sizes[head];
            let mut best = 0usize;
            let mut best_val = f64::NEG_INFINITY;
            for i in 0..sz {
                let mut s = self.head_b[head][i];
                for j in 0..16 { s += self.head_w[head][i][j] * h2[j]; }
                if s > best_val { best_val = s; best = i; }
            }
            result[head] = best;
        }
        result
    }

    /// 展平为向量(用于ES)
    fn flatten(&self) -> Vec<f64> {
        let mut v = Vec::new();
        for row in &self.w1 { for &w in row { v.push(w); } }
        for &b in &self.b1 { v.push(b); }
        for row in &self.w2 { for &w in row { v.push(w); } }
        for &b in &self.b2 { v.push(b); }
        for h in 0..6 {
            for row in &self.head_w[h] { for &w in row { v.push(w); } }
            for &b in &self.head_b[h] { v.push(b); }
        }
        v
    }

    /// 从展平向量恢复
    fn from_flat(flat: &[f64], head_sizes: &[usize]) -> Self {
        let mut idx = 0;
        let mut w1 = vec![vec![0.0;25];32];
        for i in 0..32 { for j in 0..25 { w1[i][j] = flat[idx]; idx += 1; } }
        let b1: Vec<f64> = (0..32).map(|_| {let v=flat[idx];idx+=1;v}).collect();
        let mut w2 = vec![vec![0.0;32];16];
        for i in 0..16 { for j in 0..32 { w2[i][j] = flat[idx]; idx += 1; } }
        let b2: Vec<f64> = (0..16).map(|_| {let v=flat[idx];idx+=1;v}).collect();
        let mut head_w = Vec::new();
        let mut head_b = Vec::new();
        for h in 0..6 {
            let sz = head_sizes[h];
            let mut hw = vec![vec![0.0;16];sz];
            for i in 0..sz { for j in 0..16 { hw[i][j] = flat[idx]; idx += 1; } }
            let hb: Vec<f64> = (0..sz).map(|_| {let v=flat[idx];idx+=1;v}).collect();
            head_w.push(hw); head_b.push(hb);
        }
        Self { w1, b1, w2, b2, head_w, head_b, head_sizes: head_sizes.to_vec() }
    }
}

// ── NN Agent (推理用) ──
pub struct NnAgent {
    weights: NnWeights,
    action_map: Vec<Vec<String>>, // [head][class_idx] → label string
}

impl NnAgent {
    pub fn from_file(path: &str) -> Result<Self, String> {
        let json = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        let data: serde_json::Value = serde_json::from_str(&json).map_err(|e| e.to_string())?;
        let flat: Vec<f64> = data["weights"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let head_sizes: Vec<usize> = data["head_sizes"].as_array().unwrap().iter().map(|v| v.as_u64().unwrap() as usize).collect();
        let action_map: Vec<Vec<String>> = data["action_map"].as_array().unwrap().iter()
            .map(|a| a.as_array().unwrap().iter().map(|s| s.as_str().unwrap().to_string()).collect()).collect();
        Ok(Self { weights: NnWeights::from_flat(&flat, &head_sizes), action_map })
    }

    pub fn decide_actions(&self, features: &[f64]) -> [String; 6] {
        let preds = self.weights.forward(features);
        let mut result = empty_labels();
        for h in 0..6 {
            result[h] = self.action_map[h][preds[h]].clone();
        }
        result
    }
}

fn empty_labels() -> [String; 6] {
    ["None".into(), "None".into(), "Attack".into(), "None".into(), "None".into(), "No".into()]
}


// ── ES 训练主循环 ──
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let generations: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let pop_n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(100);
    let seeds_per: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(8);

    let cfg = GameConfig {
        max_turns: 250, tech_turns_mult: 12.0, all_tech_cost_mult: 4.0,
        unit_cost_mult: 8.0, facility_build_turns: 14, city_hp: 2000,
        c_line_cost_mult: 1.0,
        starting_food: 40, starting_wood: 40, starting_gold: 40,
        facility_output: 4, starting_workers: 2, branch_available_turn: 40,
        ..GameConfig::default()
    };

    let opponents: Vec<(&str, &dyn Agent)> = vec![
        ("Random",&RandomAgent as &dyn Agent),("Builder",&BuilderAgent),
        ("Rusher",&RusherAgent),("AlwaysWhite",&AlwaysWhiteAgent),("AlwaysRed",&AlwaysRedAgent),
    ];

    let action_map: Vec<Vec<String>> = vec![
        vec!["None","C1","C3","C4","C5","M1","E1","M2"].iter().map(|s|s.to_string()).collect(), // research
        vec!["None","infantry","cavalry","archer","scout","worker"].iter().map(|s|s.to_string()).collect(), // produce
        vec!["Attack","Defend","Harass","Hold"].iter().map(|s|s.to_string()).collect(), // posture
        vec!["None","White","Red"].iter().map(|s|s.to_string()).collect(), // branch
        vec!["None","LianDa","Concentrate","Mobilize"].iter().map(|s|s.to_string()).collect(), // redeem
        vec!["No","Yes"].iter().map(|s|s.to_string()).collect(), // expand
    ];

    let mut rng = ChaCha12Rng::seed_from_u64(55555);
    let nn = NnWeights::new(&mut rng);
    let head_sizes: Vec<usize> = action_map.iter().map(|a| a.len()).collect();
    let mut theta = nn.flatten();
    let n_params = theta.len();
    let sigma = 0.1;  // 噪声标准差
    let lr = 0.01;    // 学习率
    let sb = 800000u64;

    eprintln!("Evo-V2 ES: {}参数 × {}噪声 × {}seeds × {}对手 = {}局/代, {}代",
        n_params, pop_n, seeds_per, opponents.len(), pop_n*2*opponents.len()*seeds_per as usize*2, generations);

    let mut best_fitness = 0.0f64;
    let mut best_theta = theta.clone();

    for gen in 0..generations {
        // 生成噪声扰动
        let dist = Normal::new(0.0, sigma).unwrap();
        let noises: Vec<Vec<f64>> = (0..pop_n).map(|_| {
            (0..n_params).map(|_| dist.sample(&mut rng)).collect()
        }).collect();

        // 并行评估所有θ+ε和θ-ε
        let scores: Vec<(usize, f64, f64)> = noises.par_iter().enumerate().map(|(i, eps)| {
            let theta_plus: Vec<f64> = theta.iter().zip(eps.iter()).map(|(t,e)| t+e).collect();
            let theta_minus: Vec<f64> = theta.iter().zip(eps.iter()).map(|(t,e)| t-e).collect();
            let nn_plus = NnWeights::from_flat(&theta_plus, &head_sizes);
            let nn_minus = NnWeights::from_flat(&theta_minus, &head_sizes);
            let fit = |nn: &NnWeights| -> f64 {
                let mut agent = NnAgent { weights: nn.clone(), action_map: action_map.clone() };
                let mut total_wr = 0.0f64;
                for (_, opp) in &opponents {
                    let mut wins = 0u32;
                    for s in 0..seeds_per {
                        let seed = sb + gen as u64*100000 + i as u64*1000 + s as u64;
                        let g = run_game_nn(&mut agent, *opp, seed, &cfg);
                        if g == Some(0) { wins += 1; }
                        let g2 = run_game_nn(&mut agent, *opp, seed+500000, &cfg);
                        if g2 == Some(0) { wins += 1; }
                    }
                    total_wr += wins as f64 / (seeds_per*2) as f64;
                }
                total_wr / opponents.len() as f64
            };
            (i, fit(&nn_plus), fit(&nn_minus))
        }).collect();

        // 估计梯度: Σ ε_i * (f(θ+ε) - f(θ-ε)) / (2σ²N)
        let mut grad = vec![0.0f64; n_params];
        for &(i, fp, fm) in &scores {
            let diff = fp - fm;
            for j in 0..n_params {
                grad[j] += noises[i][j] * diff;
            }
        }
        for j in 0..n_params {
            grad[j] /= 2.0 * sigma * sigma * pop_n as f64;
        }

        // 更新
        for j in 0..n_params { theta[j] += lr * grad[j]; }

        // 评估当前最好
        let current_nn = NnWeights::from_flat(&theta, &head_sizes);
        let mut agent = NnAgent { weights: current_nn.clone(), action_map: action_map.clone() };
        let mut current_fit = 0.0f64;
        for (_, opp) in &opponents {
            let mut wins = 0u32;
            for s in 0..seeds_per {
                let seed = sb + 999999 + s as u64;
                let g = run_game_nn(&mut agent, *opp, seed, &cfg);
                if g == Some(0) { wins += 1; }
                let g2 = run_game_nn(&mut agent, *opp, seed+500000, &cfg);
                if g2 == Some(0) { wins += 1; }
            }
            current_fit += wins as f64 / (seeds_per*2) as f64;
        }
        current_fit /= opponents.len() as f64;

        if current_fit > best_fitness {
            best_fitness = current_fit;
            best_theta = theta.clone();
        }

        if gen % 10 == 0 || gen == generations - 1 {
            eprintln!("Gen {}: fit={:.3} best={:.3} {}", gen, current_fit, best_fitness,
                if current_fit > best_fitness {"★"}else{""});
        }

        // checkpoint
        if gen % 20 == 0 {
            let ckpt = serde_json::json!({"weights":best_theta,"head_sizes":&head_sizes,"action_map":&action_map,"fitness":best_fitness,"generation":gen});
            std::fs::write("../experiments/v0.10-redwhite/evo-v2-checkpoint.json", serde_json::to_string_pretty(&ckpt).unwrap()).ok();
        }
    }

    // 保存最终权重
    let output = serde_json::json!({"weights":best_theta,"head_sizes":&head_sizes,"action_map":&action_map,"fitness":best_fitness,"generation":generations});
    let out = "../experiments/v0.10-redwhite/evo-v2-weights.json";
    std::fs::write(out, serde_json::to_string_pretty(&output).unwrap()).unwrap();
    eprintln!("V2完成: fitness={:.3} → {}", best_fitness, out);
}

// NN agent 对局
fn run_game_nn(agent: &mut NnAgent, opp: &dyn Agent, seed: u64, cfg: &GameConfig) -> Option<u8> {
    use miniciv_core::game::{init_game_with_config, step_game};
    let mut gs = init_game_with_config(seed, "balanced", cfg.clone());
    let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
    let mut rng1 = ChaCha12Rng::seed_from_u64(seed+1);
    while gs.winner.is_none() && gs.turn < cfg.max_turns {
        let a0 = nn_actions(agent, &gs, 0, &mut rng0);
        let a1 = opp.decide(&gs, 1, &mut rng1);
        step_game(&mut gs, &a0, &a1);
    }
    gs.winner
}

// NN → 游戏动作
fn nn_actions(agent: &NnAgent, gs: &GameState, pid: u8, _rng: &mut dyn rand::RngCore) -> Vec<miniciv_core::ai::Action> {
    use miniciv_core::ai::Action;
    use miniciv_core::movement::legal_moves;
    use miniciv_core::constants::{MAP_W, MAP_H};

    let opp = miniciv_core::game::primary_enemy(pid, &gs.config).unwrap_or(1-pid);
    let feats = extract_features(gs, pid);
    let preds = agent.decide_actions(&feats);
    let mut actions = Vec::new();

    // 研究
    if preds[0] != "None" && gs.techs[pid as usize].researching.is_none() {
        if let Some(cost) = gs.techs[pid as usize].cost_of(&preds[0]) {
            if gs.economies[pid as usize].can_afford(cost) {
                actions.push(Action::Research { tech_id: preds[0].clone() });
            }
        }
    }
    // 生产
    if preds[1] != "None" {
        actions.push(Action::ProduceUnit { unit_type: preds[1].clone() });
    }
    // 分支
    if preds[3] != "None" && gs.turn >= gs.config.branch_available_turn && gs.economies[pid as usize].branch.is_none() {
        actions.push(Action::ChooseBranch { branch: preds[3].clone() });
    }
    // 兑换
    if preds[4] != "None" {
        actions.push(Action::RedeemOrg { mode: preds[4].clone() });
    }
    // 扩张
    if preds[5] == "Yes" {
        actions.push(Action::Expand);
    }
    // 移动
    let posture = &preds[2];
    let (tq, tr) = match posture.as_str() {
        "Defend" => (gs.cities[pid as usize].q, gs.cities[pid as usize].r),
        "Harass" => {
            let opp_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive && u.player_id==opp && u.unit_type==UnitType::Worker).collect();
            if let Some(w) = opp_units.first() { (w.q, w.r) } else { (gs.cities[opp as usize].q, gs.cities[opp as usize].r) }
        }
        _ => (gs.cities[opp as usize].q, gs.cities[opp as usize].r),
    };
    let player_units: Vec<(usize, &miniciv_core::unit::Unit)> = gs.units.iter().enumerate().filter(|(_,u)| u.alive&&u.player_id==pid).collect();
    for (li, (_, unit)) in player_units.iter().enumerate() {
        match unit.unit_type {
            UnitType::Worker => {
                let tile = gs.grid.get(unit.q, unit.r);
                let buildable = matches!(tile.terrain, miniciv_core::map::Terrain::Plain|miniciv_core::map::Terrain::Forest|miniciv_core::map::Terrain::Mountain);
                if buildable && tile.facility.is_none() {
                    actions.push(Action::Build { unit_idx: li });
                } else if tile.facility.as_ref().map(|f| f.player_id==pid).unwrap_or(false) {
                    actions.push(Action::Produce { unit_idx: li });
                } else if let Some((dq,dr)) = step_toward(unit, tq, tr, &gs.grid) {
                    actions.push(Action::Move { unit_idx: li, dq, dr });
                }
            }
            UnitType::Scout => {}
            _ => { if let Some((dq,dr)) = step_toward(unit, tq, tr, &gs.grid) { actions.push(Action::Move { unit_idx: li, dq, dr }); } }
        }
    }
    actions
}

fn extract_features(gs: &GameState, pid: u8) -> Vec<f64> {
    let opp = 1-pid;
    let my_e = &gs.economies[pid as usize]; let opp_e = &gs.economies[opp as usize];
    let ms = gs.config.map_size as i32;
    let my_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==pid).collect();
    let opp_units: Vec<&miniciv_core::unit::Unit> = gs.units.iter().filter(|u| u.alive&&u.player_id==opp).collect();
    let cu = |units: &[&miniciv_core::unit::Unit], ut: UnitType| -> f64 { units.iter().filter(|u| u.unit_type==ut).count() as f64 };
    let mut my_facs = 0u32; for r in 0..ms { for q in 0..ms { if let Some(f)=&gs.grid.get(q,r).facility { if f.player_id==pid {my_facs+=1;} } } }
    let ecq=gs.cities[opp as usize].q; let ecr=gs.cities[opp as usize].r;
    let md = my_units.iter().filter(|u|u.unit_type!=UnitType::Worker).map(|u|hex_distance(u.q,u.r,ecq,ecr)as f64).fold(99.0,f64::min);
    vec![
        my_e.support as f64/100.0, my_e.organization as f64/100.0,
        match my_e.branch {Some(Branch::White)=>1.0,Some(Branch::Red)=>-1.0,None=>0.0},
        my_e.crisis_timer as f64/20.0, my_e.expansion_level as f64/5.0,
        my_e.food as f64/200.0, my_e.wood as f64/200.0, my_e.gold as f64/200.0,
        cu(&my_units,UnitType::Infantry),cu(&my_units,UnitType::Cavalry),cu(&my_units,UnitType::Archer),cu(&my_units,UnitType::Worker),
        gs.cities[pid as usize].hp as f64/2000.0, gs.techs[pid as usize].completed.len() as f64/13.0, my_facs as f64/8.0,
        opp_e.food as f64/200.0,opp_e.wood as f64/200.0,opp_e.gold as f64/200.0,
        cu(&opp_units,UnitType::Infantry),cu(&opp_units,UnitType::Cavalry),cu(&opp_units,UnitType::Archer),
        gs.cities[opp as usize].hp as f64/2000.0, gs.techs[opp as usize].completed.len() as f64/13.0,
        md/15.0, gs.turn as f64/250.0,
    ]
}

fn step_toward(unit: &miniciv_core::unit::Unit, tq: i32, tr: i32, grid: &miniciv_core::map::Grid) -> Option<(i32,i32)> {
    let moves = miniciv_core::movement::legal_moves(unit, grid);
    if moves.is_empty() { return None; }
    let cd = hex_distance(unit.q, unit.r, tq, tr);
    let mut best = None; let mut bd = u8::MAX;
    for (dq,dr) in moves {
        let nq = (unit.q+dq).rem_euclid(miniciv_core::constants::MAP_W as i32);
        let nr = (unit.r+dr).rem_euclid(miniciv_core::constants::MAP_H as i32);
        let d = hex_distance(nq, nr, tq, tr);
        if d < bd { bd = d; best = Some((dq,dr)); }
    }
    if bd <= cd { best } else { None }
}
