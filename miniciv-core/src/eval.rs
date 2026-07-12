// 批量评估工具 — 门禁 1（第三个 AI 接手落地）
//
// 取代原 todo!()。目标:让所有胜率结论有可信数字,而不是靠 30-seed 玩具测试。
//
// 核心设计:
//   run_one_game  — 驱动一局,返回结构化结果
//   run_pair      — 对一对 AI 做 paired 对局(A为P0 + B为P0,同map),消先手偏差
//   run_matrix    — N×N 全矩阵 + 跨对手 paired 平均 + P0 偏差统计
//
// 诚实原则:pairwise paired 表全量输出,读者能直接看到 Greedy vs Random,
// 不用"跨对手平均"这种会被坏对手刷高的数字下结论。

use crate::game::{GameState, init_game_with_config, step_game, VictoryType};
use crate::config::GameConfig;
use crate::ai::Agent;
use rand_chacha::ChaCha12Rng;
use rand::SeedableRng;
use serde::Serialize;

// ─── 单局结果 ────────────────────────────────────────

#[derive(Clone, Debug, Serialize)]
pub struct GameOutcome {
    pub seed: u64,
    pub winner: Option<u8>,               // 0 / 1 / None(不应出现,阶梯保证有胜者)
    pub victory_type: Option<VictoryType>,
    pub turns: u16,
    pub p0_alive: u16,
    pub p1_alive: u16,
    pub p0_dead: u16,
    pub p1_dead: u16,
}

/// 驱动一局到结束。
/// P0 的 RNG = seed, P1 的 RNG = seed+1(和既有 integration_matrix 约定一致)。
/// 地图由 init_game(seed) 决定 → paired 对局用同 seed 得到同一张图。
pub fn run_one_game(
    seed: u64,
    ai0: &dyn Agent,
    ai1: &dyn Agent,
    generator_id: &str,
    config: &GameConfig,
) -> GameOutcome {
    let mut gs: GameState = init_game_with_config(seed, generator_id, config.clone());
    let max_turns = config.max_turns;
    let mut rng0 = ChaCha12Rng::seed_from_u64(seed);
    let mut rng1 = ChaCha12Rng::seed_from_u64(seed + 1);

    while gs.winner.is_none() && gs.turn < max_turns {
        let a0 = ai0.decide(&gs, 0, &mut rng0);
        let a1 = ai1.decide(&gs, 1, &mut rng1);
        step_game(&mut gs, &a0, &a1);
    }

    let count = |pid: u8, alive: bool| {
        gs.units.iter().filter(|u| u.player_id == pid && u.alive == alive).count() as u16
    };

    GameOutcome {
        seed,
        winner: gs.winner,
        victory_type: gs.victory_type.clone(),
        turns: gs.turn,
        p0_alive: count(0, true),
        p1_alive: count(1, true),
        p0_dead: count(0, false),
        p1_dead: count(1, false),
    }
}

// ─── 一对 AI 的 paired 结果 ──────────────────────────

/// A vs B 的 paired 汇总。
/// 每个 seed 打两局:A为P0(局1) + B为P0(局2),同一张地图。
/// A 的 paired 胜场 = (局1 winner==0) + (局2 winner==1),总场次 = 2*seeds。
/// 这样 P0 先手优势在 A/B 之间抵消,得到 A 相对 B 的真实胜率。
#[derive(Clone, Debug, Serialize)]
pub struct PairResult {
    pub a: String,
    pub b: String,
    pub seeds: u32,
    pub games: u32,               // = 2 * seeds
    pub a_wins: u32,              // A 的 paired 胜场
    pub a_win_rate: f64,          // a_wins / games
    pub conquest: u32,            // 两局合计
    pub construction: u32,
    pub tiebreak: u32,
    pub p0_wins: u32,             // 两局合计:winner==0 的局数(先手偏差诊断)
    pub p0_win_rate: f64,        // p0_wins / games
    pub avg_turns: f64,
    // 分解:A 靠各类型赢的局数(诊断"谁靠什么赢")
    pub a_win_conquest: u32,
    pub a_win_construction: u32,
    pub a_win_tiebreak: u32,
    // B 靠各类型赢的局数
    pub b_win_conquest: u32,
    pub b_win_construction: u32,
    pub b_win_tiebreak: u32,
}

pub fn run_pair(
    ai_a: &dyn Agent,
    ai_b: &dyn Agent,
    seeds: u32,
    seed_base: u64,
    generator_id: &str,
    config: &GameConfig,
) -> PairResult {
    use crate::game::VictoryType as VT;
    let mut a_wins = 0u32;
    let (mut cq, mut cs, mut tb) = (0u32, 0u32, 0u32);
    let mut p0_wins = 0u32;
    let mut turn_sum = 0u64;
    let (mut awc, mut aws, mut awt) = (0u32, 0u32, 0u32);
    let (mut bwc, mut bws, mut bwt) = (0u32, 0u32, 0u32);

    let mut tally = |o: &GameOutcome, a_is_p0: bool| {
        // A 是否赢:A 在 P0 位则 winner==0,在 P1 位则 winner==1
        let a_won = o.winner == Some(if a_is_p0 { 0 } else { 1 });
        if a_won { a_wins += 1; }
        if o.winner == Some(0) { p0_wins += 1; }
        // 胜利类型归类(tiebreak 三种合并)
        let is_cq = matches!(o.victory_type, Some(VT::Conquest));
        let is_cs = matches!(o.victory_type, Some(VT::Construction));
        if is_cq { cq += 1; } else if is_cs { cs += 1; } else { tb += 1; }
        // 分解到胜者
        if a_won {
            if is_cq { awc += 1; } else if is_cs { aws += 1; } else { awt += 1; }
        } else {
            if is_cq { bwc += 1; } else if is_cs { bws += 1; } else { bwt += 1; }
        }
        turn_sum += o.turns as u64;
    };

    for i in 0..seeds {
        let seed = seed_base + i as u64 * 100;
        // 局1:A=P0, B=P1
        let g1 = run_one_game(seed, ai_a, ai_b, generator_id, config);
        tally(&g1, true);
        // 局2:B=P0, A=P1(同 seed → 同地图,交换阵营)
        let g2 = run_one_game(seed, ai_b, ai_a, generator_id, config);
        tally(&g2, false);
    }

    let games = seeds * 2;
    PairResult {
        a: ai_a.name().to_string(),
        b: ai_b.name().to_string(),
        seeds,
        games,
        a_wins,
        a_win_rate: a_wins as f64 / games as f64,
        conquest: cq,
        construction: cs,
        tiebreak: tb,
        p0_wins,
        p0_win_rate: p0_wins as f64 / games as f64,
        avg_turns: turn_sum as f64 / games as f64,
        a_win_conquest: awc,
        a_win_construction: aws,
        a_win_tiebreak: awt,
        b_win_conquest: bwc,
        b_win_construction: bws,
        b_win_tiebreak: bwt,
    }
}

// ─── 并行评估(P1.5 Step 0: rayon) ─────────────────

/// 单 seed 的统计片段(并行安全: 每个线程独立生产, 最后 reduce 聚合)。
/// 内部类型, 不对外暴露。
#[derive(Default, Clone)]
struct SeedTally {
    a_wins: u32,
    p0_wins: u32,
    conquest: u32,
    construction: u32,
    tiebreak: u32,
    awc: u32, aws: u32, awt: u32,  // A 靠各类型赢
    bwc: u32, bws: u32, bwt: u32,  // B 靠各类型赢
    turn_sum: u64,
    games: u32,
}

impl SeedTally {
    fn merge(mut self, other: &SeedTally) -> Self {
        self.a_wins += other.a_wins;
        self.p0_wins += other.p0_wins;
        self.conquest += other.conquest;
        self.construction += other.construction;
        self.tiebreak += other.tiebreak;
        self.awc += other.awc; self.aws += other.aws; self.awt += other.awt;
        self.bwc += other.bwc; self.bws += other.bws; self.bwt += other.bwt;
        self.turn_sum += other.turn_sum;
        self.games += other.games;
        self
    }

    fn to_pair_result(&self, a_name: &str, b_name: &str, seeds: u32) -> PairResult {
        let g = self.games;
        PairResult {
            a: a_name.to_string(),
            b: b_name.to_string(),
            seeds,
            games: g,
            a_wins: self.a_wins,
            a_win_rate: self.a_wins as f64 / g as f64,
            conquest: self.conquest,
            construction: self.construction,
            tiebreak: self.tiebreak,
            p0_wins: self.p0_wins,
            p0_win_rate: self.p0_wins as f64 / g as f64,
            avg_turns: self.turn_sum as f64 / g as f64,
            a_win_conquest: self.awc,
            a_win_construction: self.aws,
            a_win_tiebreak: self.awt,
            b_win_conquest: self.bwc,
            b_win_construction: self.bws,
            b_win_tiebreak: self.bwt,
        }
    }
}

/// 从 paired 两局提取统计(每个 seed 调一次, 纯函数, 并行安全)。
fn tally_seed(g1: &GameOutcome, g2: &GameOutcome) -> SeedTally {
    use crate::game::VictoryType as VT;
    let mut t = SeedTally { games: 2, ..SeedTally::default() };

    for (g, a_is_p0) in [(g1, true), (g2, false)] {
        let a_won = g.winner == Some(if a_is_p0 { 0 } else { 1 });
        if a_won { t.a_wins += 1; }
        if g.winner == Some(0) { t.p0_wins += 1; }
        let is_cq = matches!(g.victory_type, Some(VT::Conquest));
        let is_cs = matches!(g.victory_type, Some(VT::Construction));
        if is_cq { t.conquest += 1; } else if is_cs { t.construction += 1; } else { t.tiebreak += 1; }
        if a_won {
            if is_cq { t.awc += 1; } else if is_cs { t.aws += 1; } else { t.awt += 1; }
        } else {
            if is_cq { t.bwc += 1; } else if is_cs { t.bws += 1; } else { t.bwt += 1; }
        }
        t.turn_sum += g.turns as u64;
    }
    t
}

/// `run_pair` 的并行版(P1.5 Step 0)。
///
/// 用 rayon 把 seed 循环并行化。每 seed 两局独立 → embarrassingly parallel。
/// 确定性: 每局仍用 `seed`/`seed+1` 初始化 RNG, 和串行版完全相同的对局结果,
/// 只是 seed 的处理顺序不同。外部结果完全相同(见 `test_并行等于串行`)。
pub fn run_pair_par(
    ai_a: &dyn Agent,
    ai_b: &dyn Agent,
    seeds: u32,
    seed_base: u64,
    generator_id: &str,
    config: &GameConfig,
) -> PairResult {
    use rayon::prelude::*;
    let total = (0..seeds).into_par_iter()
        .map(|i| {
            let seed = seed_base + i as u64 * 100;
            let g1 = run_one_game(seed, ai_a, ai_b, generator_id, config);
            let g2 = run_one_game(seed, ai_b, ai_a, generator_id, config);
            tally_seed(&g1, &g2)
        })
        .reduce(|| SeedTally::default(), |a, b| a.merge(&b));
    total.to_pair_result(&ai_a.name(), &ai_b.name(), seeds)
}

// ─── 镜像对局(自我对战,先手偏差诊断)──────────────

#[derive(Clone, Debug, Serialize)]
pub struct MirrorResult {
    pub agent: String,
    pub seeds: u32,
    pub p0_wins: u32,
    pub p0_win_rate: f64,        // 理想 ~0.50,偏离即先手偏差
    pub conquest: u32,
    pub construction: u32,
    pub tiebreak: u32,
    // 分解:每种胜利类型里 P0 赢的局数(诊断偏向来源)
    pub conquest_p0: u32,
    pub construction_p0: u32,
    pub tiebreak_random: u32,      // TiebreakRandom 子类总数
    pub tiebreak_random_p0: u32,   // 其中 P0 赢的数(bug 修复后应 ~50%)
}

pub fn run_mirror(
    ai: &dyn Agent,
    seeds: u32,
    seed_base: u64,
    generator_id: &str,
    config: &GameConfig,
) -> MirrorResult {
    use crate::game::VictoryType as VT;
    let mut p0_wins = 0u32;
    let (mut cq, mut cs, mut tb) = (0u32, 0u32, 0u32);
    let (mut cq_p0, mut cs_p0) = (0u32, 0u32);
    let (mut tbr, mut tbr_p0) = (0u32, 0u32);
    for i in 0..seeds {
        let seed = seed_base + i as u64 * 100;
        let o = run_one_game(seed, ai, ai, generator_id, config);
        let p0_won = o.winner == Some(0);
        if p0_won { p0_wins += 1; }
        match o.victory_type {
            Some(VT::Conquest) => { cq += 1; if p0_won { cq_p0 += 1; } }
            Some(VT::Construction) => { cs += 1; if p0_won { cs_p0 += 1; } }
            Some(VT::TiebreakRandom) => { tb += 1; tbr += 1; if p0_won { tbr_p0 += 1; } }
            _ => { tb += 1; }  // TiebreakConstruction / TiebreakCityHp
        }
    }
    MirrorResult {
        agent: ai.name().to_string(),
        seeds,
        p0_wins,
        p0_win_rate: p0_wins as f64 / seeds as f64,
        conquest: cq,
        construction: cs,
        tiebreak: tb,
        conquest_p0: cq_p0,
        construction_p0: cs_p0,
        tiebreak_random: tbr,
        tiebreak_random_p0: tbr_p0,
    }
}

// ─── 全矩阵 ──────────────────────────────────────────

#[derive(Clone, Debug, Serialize)]
pub struct AgentSummary {
    pub agent: String,
    /// 跨所有对手(不含自己)的 paired 平均胜率。
    /// ⚠️ 若某对手是坏掉的 AI,这个平均会被刷高 —— 下结论看 pairwise 表,不看这个数。
    pub avg_vs_others: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct MatrixResult {
    pub generator: String,
    pub seeds: u32,
    pub seed_base: u64,
    pub max_turns: u16,
    pub pairs: Vec<PairResult>,       // 每对无序 AI 一条(A vs B)
    pub mirrors: Vec<MirrorResult>,   // 每个 AI 的自我对战先手偏差
    pub summaries: Vec<AgentSummary>,
}

/// 跑全矩阵。`agents` 顺序决定 pairwise 表里谁是 A。
pub fn run_matrix(
    agents: &[&dyn Agent],
    seeds: u32,
    seed_base: u64,
    generator_id: &str,
    config: &GameConfig,
) -> MatrixResult {
    let mut pairs = Vec::new();
    // 无序对:i < j
    for i in 0..agents.len() {
        for j in (i + 1)..agents.len() {
            pairs.push(run_pair(agents[i], agents[j], seeds, seed_base, generator_id, config));
        }
    }

    let mut mirrors = Vec::new();
    for a in agents {
        mirrors.push(run_mirror(*a, seeds, seed_base, generator_id, config));
    }

    // 跨对手平均:对每个 AI,收集它在所有 pair 里的胜率(注意方向)
    let mut summaries = Vec::new();
    for a in agents {
        let name = a.name();
        let mut sum = 0.0;
        let mut n = 0u32;
        for p in &pairs {
            if p.a == name { sum += p.a_win_rate; n += 1; }
            else if p.b == name { sum += 1.0 - p.a_win_rate; n += 1; }
        }
        summaries.push(AgentSummary {
            agent: name.to_string(),
            avg_vs_others: if n > 0 { sum / n as f64 } else { 0.0 },
        });
    }

    MatrixResult {
        generator: generator_id.to_string(),
        seeds,
        seed_base,
        max_turns: config.max_turns,
        pairs,
        mirrors,
        summaries,
    }
}

/// 便捷:用默认配置跑矩阵。
pub fn run_matrix_default(agents: &[&dyn Agent], seeds: u32, seed_base: u64, generator_id: &str) -> MatrixResult {
    run_matrix(agents, seeds, seed_base, generator_id, &GameConfig::default())
}

/// 便捷:用指定配置跑矩阵。
pub fn run_matrix_with_config(agents: &[&dyn Agent], seeds: u32, seed_base: u64, generator_id: &str, config: &GameConfig) -> MatrixResult {
    run_matrix(agents, seeds, seed_base, generator_id, config)
}

/// 并行跑全矩阵(P1.5 Step 0)。pair 循环用 rayon 并行。
pub fn run_matrix_par(
    agents: &[&dyn Agent],
    seeds: u32,
    seed_base: u64,
    generator_id: &str,
    config: &GameConfig,
) -> MatrixResult {
    use rayon::prelude::*;
    // 无序对列表
    let mut pair_indices: Vec<(usize, usize)> = Vec::new();
    for i in 0..agents.len() {
        for j in (i + 1)..agents.len() {
            pair_indices.push((i, j));
        }
    }
    let pairs: Vec<PairResult> = pair_indices.into_par_iter()
        .map(|(i, j)| run_pair_par(agents[i], agents[j], seeds, seed_base, generator_id, config))
        .collect();

    let mirrors: Vec<MirrorResult> = agents.par_iter()
        .map(|a| run_mirror(*a, seeds, seed_base, generator_id, config))
        .collect();

    let mut summaries = Vec::new();
    for a in agents {
        let name = a.name();
        let mut sum = 0.0;
        let mut n = 0u32;
        for p in &pairs {
            if p.a == name { sum += p.a_win_rate; n += 1; }
            else if p.b == name { sum += 1.0 - p.a_win_rate; n += 1; }
        }
        summaries.push(AgentSummary {
            agent: name.to_string(),
            avg_vs_others: if n > 0 { sum / n as f64 } else { 0.0 },
        });
    }

    MatrixResult {
        generator: generator_id.to_string(),
        seeds,
        seed_base,
        max_turns: config.max_turns,
        pairs,
        mirrors,
        summaries,
    }
}

// ═══════════════════════════════════════════════════════
// 测试
// ═══════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ai::random::RandomAgent;
    use crate::ai::greedy::GreedyAgent;

    #[test]
    fn test_run_one_game_有胜者且确定性() {
        // 用确定 AI(Builder)测引擎确定性。Greedy 有 HashMap 迭代非确定性(见 BUGS B6),
        // 不适合确定性断言。
        let g = crate::ai::fixed::BuilderAgent;
        let r = RandomAgent;
        let o1 = run_one_game(50000, &g, &r, "balanced", &GameConfig::default());
        let o2 = run_one_game(50000, &g, &r, "balanced", &GameConfig::default());
        // 确定性:同 seed 同结果
        assert_eq!(o1.winner, o2.winner);
        assert_eq!(o1.turns, o2.turns);
        // 阶梯判定保证一定有胜者
        assert!(o1.winner.is_some());
    }

    #[test]
    fn test_paired_场次守恒() {
        let g = GreedyAgent::new();
        let r = RandomAgent;
        let p = run_pair(&g, &r, 5, 50000, "balanced", &GameConfig::default());
        assert_eq!(p.games, 10);
        assert!(p.a_wins <= p.games);
        assert_eq!(p.conquest + p.construction + p.tiebreak, p.games);
        // 胜率在 [0,1]
        assert!(p.a_win_rate >= 0.0 && p.a_win_rate <= 1.0);
    }

    #[test]
    fn test_matrix_结构完整() {
        let g = GreedyAgent::new();
        let r = RandomAgent;
        let agents: Vec<&dyn Agent> = vec![&g, &r];
        let m = run_matrix(&agents, 3, 50000, "balanced", &GameConfig::default());
        assert_eq!(m.pairs.len(), 1);       // 2 个 AI → 1 对
        assert_eq!(m.mirrors.len(), 2);
        assert_eq!(m.summaries.len(), 2);
    }

    #[test]
    fn test_并行等于串行() {
        // P1.5 Step 0: rayon 并行必须和串行产生完全相同的数字。
        // 每局 RNG 由 seed 初始化, 和线程调度无关 → 每局结果相同。
        // 汇总只是加法(可交换可结合) → 总数相同。
        let b = crate::ai::fixed::BuilderAgent;
        let r = RandomAgent;
        let cfg = GameConfig::default();
        let serial = run_pair(&b, &r, 30, 60000, "balanced", &cfg);
        let parallel = run_pair_par(&b, &r, 30, 60000, "balanced", &cfg);
        assert_eq!(serial.a_wins, parallel.a_wins, "并行应=串行: a_wins");
        assert_eq!(serial.games, parallel.games, "并行应=串行: games");
        assert_eq!(serial.p0_wins, parallel.p0_wins, "并行应=串行: p0_wins");
        assert_eq!(serial.conquest, parallel.conquest, "并行应=串行: conquest");
        assert_eq!(serial.construction, parallel.construction, "并行应=串行: construction");
        assert_eq!(serial.tiebreak, parallel.tiebreak, "并行应=串行: tiebreak");
        assert!((serial.avg_turns - parallel.avg_turns).abs() < 0.01,
                "并行avg_turns={:.2} 串行={:.2}", parallel.avg_turns, serial.avg_turns);
    }
}
