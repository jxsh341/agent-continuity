import json, glob, os

out = {'runs': []}
seen = {}
for run_dir in sorted(glob.glob('results/stage3_config_env/*-*')):
    sm = os.path.join(run_dir, 'summary.json')
    if not os.path.exists(sm):
        continue
    try:
        cfg = json.load(open(os.path.join(run_dir, 'config.json')))
        s1 = json.load(open(os.path.join(run_dir, 'session_1.json')))
        s2 = json.load(open(os.path.join(run_dir, 'session_2.json')))
    except Exception:
        continue
    cond = cfg['config']['condition']
    budget = cfg['config']['context_budget']
    seed = cfg['config']['run_seed']
    key = (cond, budget, seed)
    entry = {
        'run_id': os.path.basename(run_dir),
        'benchmark': 'config_env',
        'condition': cond, 'budget': budget, 'seed': seed,
        's1_visible_tests_passed': s1['evaluation']['passed'],
        's2_all_tests_passed': s2['evaluation']['passed'],
        'decision_leaked_to_repo': cfg['config'].get('decision_leaked_to_repo', False),
        'fact_fidelity': s2['context_artifact'].get('provenance', {}).get('fact_fidelity', {}),
        's2_context_tokens': s2['context_artifact']['token_count'],
        's2_context_truncated': s2['context_artifact']['truncated'],
        's2_agent_error': s2['agent_error'],
        'success': bool(s1['evaluation']['passed'] and s2['evaluation']['passed'] and (not s2['agent_error'])),
    }
    seen[key] = entry  # newest run dir wins (sorted glob)

out['runs'] = list(seen.values())
with open('results/stage3_config_env/summary.json', 'w') as f:
    json.dump(out, f, indent=2)
print(f"rebuilt: {len(out['runs'])} entries")
cond_count = {}
for r in out['runs']:
    cond_count.setdefault(r['condition'], []) .append(r['success'])
print({c: f"{sum(v)}/{len(v)}" for c, v in cond_count.items()})