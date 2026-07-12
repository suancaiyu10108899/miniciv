// P1.5 参数扫描 — 2v2建设速度
use miniciv_core::ai::Agent;
use miniciv_core::ai::probes::{StateAwareAgent, AlwaysWhiteAgent};
use miniciv_core::config::GameConfig;
use miniciv_core::eval::run_one_game_n;
use std::collections::HashMap;

fn main() {
    let seeds = 40u32;
    let seed_base = 90000u64;
    println!("{:>5} {:>5} {:>5} {:>5} {:>6} {:>5} {:>5} {:>5} {:>7}",
             "costX", "teamF", "indF", "startW", "avgT", "Cq%", "Cs%", "Tb%", "StateW%");
    println!("{}", "-".repeat(55));

    for cost_mult in [2.0f64, 2.2] {
    for team_facs in [8u8] {
    for ind_facs in [4u8, 5] {
    for start_w in [2u8, 3] {
        let mut tt = HashMap::new();
        tt.insert("C5".to_string(), 4u8);
        let cfg = GameConfig {
            player_count: 4, teams: vec![0, 0, 1, 1],
            city_hp: 100, branch_available_turn: 15,
            c_line_cost_mult: cost_mult,
            construction_require_facilities: ind_facs,
            construction_team_facilities: team_facs,
            tech_turns: tt, starting_workers: start_w,
            max_turns: 100, ..GameConfig::default()
        };
        let sw = StateAwareAgent; let aw = AlwaysWhiteAgent;
        let agents: Vec<&dyn Agent> = vec![&sw, &sw, &aw, &aw];
        let (mut cq, mut cs, mut tb, mut sw_w, mut tsum) = (0u32,0,0,0,0u64);
        for i in 0..seeds {
            let g = run_one_game_n(seed_base + i as u64 * 100, &agents, "balanced", &cfg);
            tsum += g.turns as u64;
            match g.victory_type {
                Some(miniciv_core::game::VictoryType::Conquest) => cq += 1,
                Some(miniciv_core::game::VictoryType::Construction) => cs += 1,
                _ => tb += 1,
            }
            if g.winner.map(|w| w == 0 || w == 1).unwrap_or(false) { sw_w += 1; }
        }
        let s = seeds as f64;
        println!("{:>5.1} {:>5} {:>5} {:>5} {:>6.1} {:>4.0}% {:>4.0}% {:>4.0}% {:>6.0}%",
            cost_mult, team_facs, ind_facs, start_w, tsum as f64/s,
            cq as f64/s*100.0, cs as f64/s*100.0, tb as f64/s*100.0, sw_w as f64/s*100.0);
    }}}}
}
