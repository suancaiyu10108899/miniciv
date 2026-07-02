# show gradient results
import json, os

print("=== Greedy Version Gradient ===")
for v in ['v1', 'v2', 'v3', 'v4']:
    results = {}
    for opp in ['random', 'aggressive']:
        path = f'eval_greedy_grad/{v}_vs_{opp}/summary.json'
        if os.path.exists(path):
            d = json.load(open(path))
            p = d['pairs']
            for pair in p:
                if pair['ai0'].startswith('greedy') and pair['ai1'] == opp:
                    results[f'vs_{opp}'] = f"P0win={pair['p0_winrate']*100:.0f}% cq={pair['conquests']} cs={pair['constructions']} tie={pair['tiebreaks']}"

    mirror_path = f'eval_greedy_grad/{v}_mirror/summary.json'
    if os.path.exists(mirror_path):
        d = json.load(open(mirror_path))
        for pair in d['pairs']:
            if 'greedy' in pair['ai0']:
                results['mirror'] = f"P0win={pair['p0_winrate']*100:.0f}% tie={pair['tiebreaks']}"

    print(f"Greedy {v}: {results}")

print()
print("=== Randomness Impact ===")
rp = 'eval_randomness/report.md'
if os.path.exists(rp):
    print(open(rp).read()[:500])

print()
print("=== Paired P0 ===")
for sc in ['rush', 'standard', 'develop']:
    path = f'eval_paired/{sc}/summary.json'
    if os.path.exists(path):
        d = json.load(open(path))
        print(f"{sc}: {d.get('pairs',[])}")

print()
print("=== Evo Checkpoints ===")
for f in os.listdir('eval_gradient/evo_checkpoints'):
    if f.endswith('.json'):
        d = json.load(open(f'eval_gradient/evo_checkpoints/{f}'))
        print(f"{f}: gen={d.get('generation','?')} best={d.get('best_winrate','?')}")
