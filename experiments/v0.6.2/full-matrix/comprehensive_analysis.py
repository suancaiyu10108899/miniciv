#!/usr/bin/env python
"""Comprehensive v0.6.2 matrix analysis."""
import json, os
from collections import defaultdict

DIR = 'experiments/v0.6.2/full-matrix'
files = sorted(f for f in os.listdir(DIR) if f.startswith('paired_') and f.endswith('.json'))
AIS = ['random','greedy','aggressive','flatmc','dqn_trained','evo']
summaries = []

for fname in files:
    with open(os.path.join(DIR, fname)) as f:
        d = json.load(f)
    stem = fname.replace('paired_','').replace('.json','')
    parts = stem.split('_vs_')
    if len(parts) != 2: continue
    summaries.append({
        'ai_a': parts[0], 'ai_b': parts[1],
        'a_wr': d.get('ai_a_winrate',0), 'b_wr': d.get('ai_b_winrate',0),
        'p0': d.get('p0_winrate',0), 'cq': d.get('conquest_rate',0),
        'cs': d.get('construction_rate',0), 'tb': d.get('tiebreak_rate',0),
        'turns': d.get('avg_turns',0), 'dead': d.get('avg_dead',0),
        'n': d.get('n_games',0),
        'a_ut': d.get('ai_a_unit_composition',{}), 'b_ut': d.get('ai_b_unit_composition',{}),
        'p0_vt': d.get('p0_by_victory_type',{}),
        'a_facs': d.get('ai_a_construction_mean',0), 'b_facs': d.get('ai_b_construction_mean',0),
        'a_eff': d.get('ai_a_resource_efficiency',0), 'b_eff': d.get('ai_b_resource_efficiency',0),
    })

tg = sum(s['n'] for s in summaries)
t_cq = sum(s['cq']*s['n'] for s in summaries)
t_cs = sum(s['cs']*s['n'] for s in summaries)
t_tb = sum(s['tb']*s['n'] for s in summaries)
t_p0 = sum(s['p0']*s['n'] for s in summaries)/tg

wr = defaultdict(lambda: defaultdict(float))
for s in summaries: wr[s['ai_a']][s['ai_b']]=s['a_wr']; wr[s['ai_b']][s['ai_a']]=s['b_wr']
ai_avg = {ai: sum(wr[ai][o] for o in AIS if o!=ai)/(len(AIS)-1) for ai in AIS}

print('='*70)
print('v0.6.2 COMPREHENSIVE ANALYSIS')
print(f'Rules: HP=80 DEF=5 DMG=5 facility=4 max_t=80 stacking=1+1')
print(f'{len(summaries)} pairs, {tg:.0f} games')
print('='*70)

# === 1. VICTORY TYPE ===
print('\n=== 1. VICTORY TYPE DISTRIBUTION ===')
print(f'Construction:  {t_cs/tg:.1%}  ({int(t_cs)} games)')
print(f'Conquest:      {t_cq/tg:.1%}  ({int(t_cq)} games)')
print(f'Tiebreak:      {t_tb/tg:.1%}  ({int(t_tb)} games)')
print(f'P0 overall:    {t_p0:.1%}')

print('\nTop conquest pairs (>15%):')
for s in sorted(summaries, key=lambda x: -x['cq']):
    if s['cq'] > 0.15:
        print(f'  {s["ai_a"]:>12} vs {s["ai_b"]:<12} CQ={s["cq"]:.1%} CS={s["cs"]:.1%} T={s["turns"]:.0f}')

print('\nTop construction pairs (>40%):')
for s in sorted(summaries, key=lambda x: -x['cs']):
    if s['cs'] > 0.40:
        print(f'  {s["ai_a"]:>12} vs {s["ai_b"]:<12} CS={s["cs"]:.1%} CQ={s["cq"]:.1%} T={s["turns"]:.0f}')

# === 2. UNIT COMPOSITION ===
print('\n=== 2. UNIT COMPOSITION (avg per game, across all opponents) ===')
utypes = ['infantry','cavalry','archer','scout','worker']
ai_units = {ai: {ut: {'alive':0,'dead':0,'n':0} for ut in utypes} for ai in AIS}
for s in summaries:
    for prefix, ai_name in [('a_ut', s['ai_a']), ('b_ut', s['ai_b'])]:
        ut_data = s.get(prefix, {})
        if not ut_data: continue
        for ut in utypes:
            ud = ut_data.get(ut, {})
            if ud:
                ai_units[ai_name][ut]['alive'] += ud.get('alive_mean',0) * s['n']
                ai_units[ai_name][ut]['dead'] += ud.get('dead_mean',0) * s['n']
                ai_units[ai_name][ut]['n'] += s['n']

print(f'{"AI":>12}  {"infantry":>15} {"cavalry":>15} {"archer":>15} {"scout":>12} {"worker":>15}')
print('-'*80)
for ai in AIS:
    parts = []
    for ut in utypes:
        d = ai_units[ai][ut]
        n = d['n']
        if n > 0: a = d['alive']/n; d2 = d['dead']/n; parts.append(f'alive={a:.1f} dead={d2:.1f}')
        else: parts.append('--')
    print(f'{ai:>12}  {parts[0]:>15} {parts[1]:>15} {parts[2]:>15} {parts[3]:>12} {parts[4]:>15}')

print('\nCavalry ratio (cav_alive / (inf_alive + cav_alive)):')
for ai in AIS:
    i_a = ai_units[ai]['infantry']['alive'] / max(ai_units[ai]['infantry']['n'], 1)
    c_a = ai_units[ai]['cavalry']['alive'] / max(ai_units[ai]['cavalry']['n'], 1)
    ratio = c_a / max(i_a + c_a, 1)
    print(f'  {ai:>12}: {ratio:.1%}')

print('\nWorker stats:')
for ai in AIS:
    n = ai_units[ai]['worker']['n']
    a = ai_units[ai]['worker']['alive'] / max(n, 1)
    d = ai_units[ai]['worker']['dead'] / max(n, 1)
    print(f'  {ai:>12}: alive={a:.1f} dead={d:.2f} per game')

# === 3. P0 BY VICTORY TYPE ===
print('\n=== 3. P0 BY VICTORY TYPE ===')
total_p0 = {'conquest':[0,0],'construction':[0,0],'tiebreak':[0,0]}
for s in summaries:
    p0vt = s.get('p0_vt',{})
    for vt in ['conquest','construction','tiebreak']:
        vd = p0vt.get(vt,{})
        n = vd.get('n_games',0)
        if n > 0:
            total_p0[vt][0] += vd.get('p0_winrate',0)*n
            total_p0[vt][1] += n
for vt, (ws, n) in total_p0.items():
    print(f'  {vt:>15}: P0={ws/n:.1%} (n={n})')

# === 4. MIRROR ANALYSIS ===
print('\n=== 4. MIRROR MATCH ANALYSIS ===')
for s in summaries:
    if s['ai_a'] == s['ai_b']:
        print(f'  {s["ai_a"]:>12} mirror: CQ={s["cq"]:.1%} CS={s["cs"]:.1%} TB={s["tb"]:.1%} T={s["turns"]:.0f} dead={s["dead"]:.1f}')

# === 5. STRATEGIC FINGERPRINTS ===
print('\n=== 5. STRATEGIC FINGERPRINTS ===')
for ai in AIS:
    i_a = ai_units[ai]['infantry']['alive'] / max(ai_units[ai]['infantry']['n'], 1)
    c_a = ai_units[ai]['cavalry']['alive'] / max(ai_units[ai]['cavalry']['n'], 1)
    w_a = ai_units[ai]['worker']['alive'] / max(ai_units[ai]['worker']['n'], 1)
    w_d = ai_units[ai]['worker']['dead'] / max(ai_units[ai]['worker']['n'], 1)
    a_a = ai_units[ai]['archer']['alive'] / max(ai_units[ai]['archer']['n'], 1)

    if c_a > i_a * 0.3: strat = 'CAVALRY-HEAVY'
    elif i_a > 15: strat = 'INFANTRY-SWARM'
    elif w_a > 4: strat = 'ECONOMY-FOCUS'
    else: strat = 'MIXED'

    print(f'  {ai:>12}: {strat}')
    print(f'           inf={i_a:.1f} cav={c_a:.1f} arch={a_a:.1f} worker={w_a:.1f}a/{w_d:.1f}d')

# === 6. CROSS-MATRIX TRENDS ===
print('\n=== 6. CROSS-MATRIX TRENDS ===')
print(f'  {"Metric":>15} {"v0.6.0":>10} {"v0.6.1":>10} {"v0.6.2":>10}')
data = [
    ('Construction', '23.0%', '24.9%', f'{t_cs/tg:.1%}'),
    ('Conquest', '8.5%', '8.2%', f'{t_cq/tg:.1%}'),
    ('Tiebreak', '68.5%', '66.9%', f'{t_tb/tg:.1%}'),
    ('Evo WR', '87.5%', '72.7%', f'{ai_avg["evo"]:.1%}'),
    ('DQN WR', '78.6%', '82.2%', f'{ai_avg["dqn_trained"]:.1%}'),
    ('Greedy WR', '50.5%', '54.1%', f'{ai_avg["greedy"]:.1%}'),
    ('Aggressive WR', '10.7%', '13.7%', f'{ai_avg["aggressive"]:.1%}'),
    ('P0', '50.4%', '50.2%', f'{t_p0:.1%}'),
]
for name, v0, v1, v2 in data:
    print(f'  {name:>15} {v0:>10} {v1:>10} {v2:>10}')
