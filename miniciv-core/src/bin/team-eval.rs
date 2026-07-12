// P1.5 2v2 团队评估 CLI
// 用法: cargo run --release --bin team-eval -- <seeds> <out.json> [branch_turn]
// 测试多种 2v2 阵容搭配的胜率。

use miniciv_core::ai::Agent;
use miniciv_core::ai::probes::{
    AlwaysWhiteAgent, AlwaysRedAgent, StateAwareAgent, TankThenRedAgent,
    RusherAgent, DefenderAgent,
};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game_n;
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Serialize)]
struct TeamResult {
    team_a_desc: String,
    team_b_desc: String,
    seeds: u32,
    games: u32,
    team_a_wins: u32,
    team_a_win_rate: f64,
    team_a_pids: Vec<u8>,
    team_b_pids: Vec<u8>,
    conquest: u32,
    construction: u32,
    tiebreak: u32,
    avg_turns: f64,
    /// Per-game end states for instrumentation
    end_states: Vec<miniciv_core::eval::PlayerEndState>,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seeds: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(60);
    let out_path = args.get(2).cloned().unwrap_or_else(|| "experiments/v0.10-redwhite/2v2.json".to_string());
    let branch_turn: u16 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(10);

    let seed_base = 80000u64;

    // 阵容定义: (name, [agents for P0..P3], teams)
    struct Lineup {
        name: &'static str,
        agents: [&'static str; 4],  // agent names
        teams: Vec<u8>,
    }

    // 关键测试阵容
    let lineups = vec![
        // 纯阵容: 全白 vs 全白
        Lineup { name: "AllWhite_vs_AllWhite",
            agents: ["AlwaysWhite", "AlwaysWhite", "AlwaysWhite", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // 纯阵容: 全红 vs 全红
        Lineup { name: "AllRed_vs_AllRed",
            agents: ["AlwaysRed", "AlwaysRed", "AlwaysRed", "AlwaysRed"],
            teams: vec![0, 0, 1, 1] },
        // 混合 vs 纯白 (核心R-3测试: 频率依赖)
        Lineup { name: "Mixed_vs_AllWhite",
            agents: ["AlwaysWhite", "AlwaysRed", "AlwaysWhite", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // 混合 vs 混合
        Lineup { name: "Mixed_vs_Mixed",
            agents: ["AlwaysWhite", "AlwaysRed", "AlwaysWhite", "AlwaysRed"],
            teams: vec![0, 0, 1, 1] },
        // 白+红 vs 红+白 (倒换队内位置)
        Lineup { name: "Mixed_vs_Mixed_swapped",
            agents: ["AlwaysWhite", "AlwaysRed", "AlwaysRed", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // StateAware队 vs 纯白队 (核心R-1: 处境选线 vs 固定)
        Lineup { name: "StateAware_vs_AllWhite",
            agents: ["StateAware", "StateAware", "AlwaysWhite", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // StateAware vs 混合 (白+红)
        Lineup { name: "StateAware_vs_Mixed",
            agents: ["StateAware", "StateAware", "AlwaysWhite", "AlwaysRed"],
            teams: vec![0, 0, 1, 1] },
        // 纯Rush vs 纯Rush (2v2基线)
        Lineup { name: "Rusher_vs_Rusher_2v2",
            agents: ["Rusher", "Rusher", "Rusher", "Rusher"],
            teams: vec![0, 0, 1, 1] },
        // 白+Defender vs 白+白 (协作测试: 互补角色)
        Lineup { name: "WhiteDefender_vs_AllWhite",
            agents: ["AlwaysWhite", "Defender", "AlwaysWhite", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // TankThenRed队 vs 纯白
        Lineup { name: "TankRed_vs_AllWhite",
            agents: ["TankThenRed", "TankThenRed", "AlwaysWhite", "AlwaysWhite"],
            teams: vec![0, 0, 1, 1] },
        // TankRed vs StateAware (R-2核心: 摆烂是否输给正常?)
        Lineup { name: "TankRed_vs_StateAware",
            agents: ["TankThenRed", "TankThenRed", "StateAware", "StateAware"],
            teams: vec![0, 0, 1, 1] },
        // AllWhite vs AllRed (红线 vs 白线 在2v2)
        Lineup { name: "AllWhite_vs_AllRed",
            agents: ["AlwaysWhite", "AlwaysWhite", "AlwaysRed", "AlwaysRed"],
            teams: vec![0, 0, 1, 1] },
        // StateAware vs AllRed (处境选线 vs 纯红线)
        Lineup { name: "StateAware_vs_AllRed",
            agents: ["StateAware", "StateAware", "AlwaysRed", "AlwaysRed"],
            teams: vec![0, 0, 1, 1] },
        // 双Rusher vs 双Defender (军事 vs 防守 2v2基线)
        Lineup { name: "Rusher_vs_Defender_2v2",
            agents: ["Rusher", "Rusher", "Defender", "Defender"],
            teams: vec![0, 0, 1, 1] },
    ];

    fn make_agent(name: &str) -> Box<dyn Agent> {
        match name {
            "AlwaysWhite" => Box::new(AlwaysWhiteAgent),
            "AlwaysRed" => Box::new(AlwaysRedAgent),
            "StateAware" => Box::new(StateAwareAgent),
            "TankThenRed" => Box::new(TankThenRedAgent),
            "Rusher" => Box::new(RusherAgent),
            "Defender" => Box::new(DefenderAgent),
            _ => Box::new(AlwaysWhiteAgent),
        }
    }

    let mut tt = std::collections::HashMap::new();
    tt.insert("C5".to_string(), 4u8);
    let cfg = GameConfig {
        player_count: 4,
        branch_available_turn: branch_turn,
        max_turns: 100,
        city_hp: 100,                       // 甜点: 征服可行
        starting_workers: 2,                // 甜点: 减缓建设速度
        c_line_cost_mult: 2.0,
        construction_team_facilities: 8,    // 队内合计8设施
        construction_require_facilities: 4, // C5持有者个人需4设施
        tech_turns: tt,                     // C5=4回合
        ..GameConfig::default()
    };

    let mut results: Vec<TeamResult> = Vec::new();

    for lineup in &lineups {
        let agents_0: Vec<Box<dyn Agent>> = lineup.agents.iter().map(|&n| make_agent(n)).collect();
        let agent_refs: Vec<&dyn Agent> = agents_0.iter().map(|a| a.as_ref()).collect();

        let mut team_a_wins = 0u32;
        let mut turn_sum = 0u64;
        let (mut cq, mut cs, mut tb) = (0u32, 0u32, 0u32);
        let mut all_end_states: Vec<miniciv_core::eval::PlayerEndState> = Vec::new();
        let team_a_pids: Vec<u8> = lineup.teams.iter().enumerate()
            .filter(|(_, &t)| t == 0).map(|(i, _)| i as u8).collect();
        let team_b_pids: Vec<u8> = lineup.teams.iter().enumerate()
            .filter(|(_, &t)| t == 1).map(|(i, _)| i as u8).collect();

        for i in 0..seeds {
            let seed = seed_base + i as u64 * 100;
            let this_cfg = GameConfig {
                teams: lineup.teams.clone(),
                ..cfg.clone()
            };
            let g1 = run_one_game_n(seed, &agent_refs, "balanced", &this_cfg);
            // 判断队伍A是否赢: winner 是 team_a 的成员
            let a_won = g1.winner.map(|w| team_a_pids.contains(&w)).unwrap_or(false);
            if a_won { team_a_wins += 1; }
            turn_sum += g1.turns as u64;
            match g1.victory_type {
                Some(miniciv_core::game::VictoryType::Conquest) => cq += 1,
                Some(miniciv_core::game::VictoryType::Construction) => cs += 1,
                _ => tb += 1,
            }
            all_end_states.extend(g1.end_state.clone());

            // 局2: 交换队伍位置 (消除座位偏差)
            let mut swapped_agents: Vec<&dyn Agent> = Vec::new();
            // 队B坐前两个位置, 队A坐后两个
            for pid in 0..4u8 {
                let original_pid = if pid < 2 { pid + 2 } else { pid - 2 };
                swapped_agents.push(agent_refs[original_pid as usize]);
            }
            let mut swapped_teams = vec![0u8; 4];
            for (i, t) in lineup.teams.iter().enumerate() {
                let new_i = if i < 2 { i + 2 } else { i - 2 };
                swapped_teams[new_i] = *t;
            }
            let a_pids_swapped: Vec<u8> = swapped_teams.iter().enumerate()
                .filter(|(_, &t)| t == 0).map(|(i, _)| i as u8).collect();
            let swapped_cfg = GameConfig { teams: swapped_teams, ..cfg.clone() };
            let g2 = run_one_game_n(seed + 1, &swapped_agents, "balanced", &swapped_cfg);
            let a_won2 = g2.winner.map(|w| a_pids_swapped.contains(&w)).unwrap_or(false);
            if a_won2 { team_a_wins += 1; }
            turn_sum += g2.turns as u64;
            match g2.victory_type {
                Some(miniciv_core::game::VictoryType::Conquest) => cq += 1,
                Some(miniciv_core::game::VictoryType::Construction) => cs += 1,
                _ => tb += 1,
            }
            all_end_states.extend(g2.end_state);
        }

        let games = seeds * 2;
        results.push(TeamResult {
            team_a_desc: lineup.name.to_string(),
            team_b_desc: "N/A".to_string(),
            seeds,
            games,
            team_a_wins,
            team_a_win_rate: team_a_wins as f64 / games as f64,
            team_a_pids,
            team_b_pids,
            conquest: cq,
            construction: cs,
            tiebreak: tb,
            avg_turns: turn_sum as f64 / games as f64,
            end_states: all_end_states,
        });
    }

    // 输出
    println!("═══ 2v2 阵容胜率 ({} seeds, branch@T{}) ═══", seeds, branch_turn);
    println!("{:>30} {:>10} {:>7} {:>7} {:>7} {:>8}",
             "阵容", "队A胜率", "征服%", "建设%", "阶梯%", "均回合");
    println!("{}", "-".repeat(72));
    for r in &results {
        let g = r.games as f64;
        println!("{:>30} {:9.1}% {:6.1}% {:6.1}% {:6.1}% {:7.1}",
                 r.team_a_desc, r.team_a_win_rate * 100.0,
                 r.conquest as f64 / g * 100.0,
                 r.construction as f64 / g * 100.0,
                 r.tiebreak as f64 / g * 100.0,
                 r.avg_turns);
    }

    // 保存
    if let Ok(json) = serde_json::to_string_pretty(&results) {
        if let Err(e) = std::fs::write(&out_path, &json) {
            eprintln!("写文件失败 {}: {}", out_path, e);
        } else {
            eprintln!("\n已写入 {}", out_path);
        }
    }
}
