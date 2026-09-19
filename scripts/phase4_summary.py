"""Aggregate the Phase 4 pilot ledgers."""
import json

print(f"{'benchmark':18}{'cond':5}{'cells':6}{'pass':6}{'agent_err':10}")
for bench in ['fastapi', 'entity_relationship', 'evolving_state']:
    runs = json.load(open(f'results/phase4_{bench}/summary.json'))['runs']
    for cond in 'ABCD':
        cells = [r for r in runs if r['condition'] == cond]
        n = len(cells)
        p = sum(1 for r in cells if r['success'])
        err = sum(1 for r in cells if r.get('s2_agent_error'))
        print(f"{bench:18}{cond:5}{n:6}{p:6}{err:10}")
