"""Fresh, frozen 0.6.2 versus actual Codex /goal comparison; no grader feedback."""
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from goalpilot.engine import atomic_json as write


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def create(out):
    from goalpilot import __version__
    from evaluation.ambitious.specs import GOALS, SPECS
    from evaluation.ambitious.preflight import run
    assert __version__ == '0.6.2'
    ci = json.loads((ROOT/'reports/tests.json').read_text())
    assert ci['successful'] and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == sha
                                  for p, sha in ci['source_fingerprint'].items())
    checked = run()
    assert not out.exists()
    out.mkdir(parents=True)
    snap = out/'source_snapshot'
    for folder in ('goalpilot', 'evaluation', 'tests', 'examples'):
        shutil.copytree(ROOT/folder, snap/folder, ignore=shutil.ignore_patterns('__pycache__'))
    (snap/'tools').mkdir()
    for name in ('current_native_campaign.py', 'audit_current_native.py'):
        shutil.copy2(ROOT/'tools'/name, snap/'tools'/name)
    for name in ('pyproject.toml', 'validate.py'):
        shutil.copy2(ROOT/name, snap/name)
    m = {'registered_at': time.time(), 'product_version': __version__, 'model': 'gpt-6.1-sol',
         'cases': ['flowdesk', 'stockroom'], 'goals': {c: GOALS[c] for c in ('flowdesk', 'stockroom')},
         'public_contracts': {c: SPECS[c] for c in ('flowdesk', 'stockroom')},
         'order': [{'case': c, 'mode': mode, 'id': c+'-'+mode}
                   for c, modes in [('flowdesk', ['native_goal', 'goalpilot']),
                                    ('stockroom', ['goalpilot', 'native_goal'])] for mode in modes],
         'seconds_per_trial': 900, 'max_calls_goalpilot': 6,
         'raw_token_soft_cap_per_trial': 1500000, 'observed_campaign_token_cap': 4000000,
         'source_fingerprint': hashes(snap), 'offline_validation': ci, 'preflight': checked,
         'primary_rule': 'Four NEW executions. Report correct-and-normally-closed goals, artifact correctness separately, aggregate full workflow time, raw input+output and input-minus-cached+output. Efficiency target: no paired closure/correctness regression AND >=20% savings on EACH of the three resources; require complete raw-audited usage for exact token comparisons. No positive composite if incomplete or any threshold misses.',
         'baseline': 'Actual persistent Codex thread/goal/set active. Automatic continuations run without a six-turn cap. Normal native delivery requires server complete status AND final completed inactive turn. No early stop at first answer or client-forced complete.',
         'design': 'Same gpt-6.1-sol, initial files, original contracts, 900s workflow and soft1.5M raw cap per arm. GoalPilot at most6 calls including acceptance generation/repair/arithmetic validation and code repairs. Alternating arm order between two cases; serial isolated fresh processes. No human steering, injected failures or independent-judge feedback. All setup, reviews, local checks and teardown included in elapsed time; research judge excluded equally.',
         'novelty': 'Familiar synthetic Flowdesk and Stockroom cases exposed in earlier development; no held-out or personal-goal generalization. All FOUR model executions are new, no historical controls or old percentages pooled.',
         'stopping': 'At whole paired-case boundaries stop on any paired closure or correctness regression; keep original4 denominator, incomplete study cannot pass. At whole-trial boundaries stop on fatal infrastructure/provider failure, incomplete usage, or observed4M cap. No retry or source/protocol adjustment after launch.',
         'limits': ['Only two familiar domains, single realization per arm.',
                    'Detailed public contracts despite broad goal text.',
                    'Native Codex workspace sandbox may deny sockets whereas GoalPilot host checks can bindlocalhost; disclose any closure difference caused by this.',
                    'Tokens are API counters, not an exact subscription quota or money conversion.'],
         'definitions': {'correct': '26 original judge groups per artifact,13 on each fixed seed90173/470117',
                         'uncached': 'input_tokens-cached_input_tokens+output_tokens'}}
    write(out/'protocol.json', m)
    write(out/'preregistered-protocol.json', m)
    print('REGISTERED', out, flush=True)


def worker(out, ident):
    from evaluation.ambitious.cases import materialize
    from evaluation.ambitious.judge import evaluate
    from evaluation.native_goals.adapter import NativeGoalAdapter
    from goalpilot.finish import run_finish
    from goalpilot.engine import token_totals
    from goalpilot.model import ContractError
    m = json.loads((out/'protocol.json').read_text())
    assert hashes(out/'source_snapshot') == m['source_fingerprint']
    item = next(x for x in m['order'] if x['id'] == ident)
    trial = out/'trials'/ident
    assert not trial.exists(), 'Never repeat an uncommitted execution'
    trial.mkdir(parents=True)
    repo = materialize(out/'repos'/ident, item['case'])
    write(trial/'started.json', {'at': time.time(), 'initial_repo_fingerprint': hashes(repo)})
    goal = m['goals'][item['case']] + '''\nFollow all original README contracts, finish every workflow, preserve data, resolve reversible ambiguities autonomously. Test meaningful public behavior. No human steering, external services, deployment or credentials. Work only in this repository; do not read benchmark/evaluation sources, references, sibling trials or protocol. Do not launch other agents/model sessions or nested Codex commands. Give a factual handoff.'''
    print('START', ident, flush=True)
    start = time.monotonic()
    calls, error, status = [], None, 'incomplete'
    try:
        if item['mode'] == 'native_goal':
            with NativeGoalAdapter(m['model']) as adapter:
                result = adapter.execute_goal(goal, repo, m['seconds_per_trial'], trial/'run/calls/1', m['raw_token_soft_cap_per_trial'])
                calls = [{'strategy': 'native_goal', 'result': result.to_dict()}]
                observed = (result.telemetry.get('native_goal_at_stop') or {}).get('status', 'incomplete')
                status = observed if result.returncode == 0 or observed in ('blocked', 'usageLimited', 'budgetLimited') else 'incomplete'
        else:
            state = run_finish(goal, repo, trial/'run', wall_seconds=m['seconds_per_trial'],
                               max_calls=m['max_calls_goalpilot'], max_tokens=m['raw_token_soft_cap_per_trial'],
                               model=m['model'], audit_policy='on-interruption',
                               notify=lambda s: print(ident, s, flush=True))
            calls, status = state['calls'], state['status']
    except (ContractError, OSError, ValueError) as exc:
        error = f'{type(exc).__name__}: {exc}'
        for name in ('state.json', 'finish-run.json'):
            p = trial/'run'/name
            if p.exists():
                saved = json.loads(p.read_text()); calls, status = saved['calls'], saved['status']; break
    execution = {'seconds': time.monotonic()-start, 'calls': calls, 'error': error, 'status': status}
    write(trial/'execution.json', execution)
    checks = [r for seed in (90173, 470117) for r in evaluate(item['case'], repo, seed)]
    write(trial/'judgments.json', checks)
    normal = status in ('complete', 'scope_passed', 'completed')
    artifact = len(checks) == 26 and all(c['passed'] for c in checks)
    row = {**item, **execution, 'judgments': checks, 'normal_exit': normal, 'artifact_success': artifact,
           'success': normal and artifact, 'usage': token_totals(calls), 'human_inputs': 0,
           'fatal': any(c.get('result', {}).get('fatal') for c in calls) or bool(error and not calls)}
    write(trial/'record.json', row)
    print('RESULT', json.dumps({k: row[k] for k in ('id', 'seconds', 'status', 'success', 'artifact_success', 'usage')}), flush=True)


def run(out):
    m = json.loads((out/'protocol.json').read_text())
    assert m == json.loads((out/'preregistered-protocol.json').read_text())
    for item in m['order']:
        rows = [json.loads(p.read_text()) for p in (out/'trials').glob('*/record.json')]
        reason = None
        if any(r['fatal'] for r in rows): reason = 'Fatal infrastructure/provider failure'
        elif any(not r['usage']['usage_complete'] for r in rows): reason = 'Incomplete usage meter'
        elif sum(r['usage']['total_tokens'] for r in rows) >= m['observed_campaign_token_cap']: reason = 'Observed campaign token cap'
        for case in m['cases']:
            pair = {r['mode']: r for r in rows if r['case'] == case}
            if len(pair) == 2 and any(pair['native_goal'][k] and not pair['goalpilot'][k] for k in ('success', 'artifact_success')):
                reason = 'Paired closure/correctness regression'
        if reason:
            write(out/'stopped.json', {'reason': reason, 'completed_trials': len(rows), 'planned_trials': 4}); break
        if any(r['id'] == item['id'] for r in rows): continue
        assert hashes(out/'source_snapshot') == m['source_fingerprint']
        subprocess.run([sys.executable, str(out/'source_snapshot/tools/current_native_campaign.py'), 'worker', str(out), item['id']], check=True, cwd=out/'source_snapshot')
    report(out)


def report(out):
    from audit_current_native import audit
    integrity = audit(out)
    rows = [json.loads(p.read_text()) for p in (out/'trials').glob('*/record.json')]
    totals = {}
    for mode in ('native_goal', 'goalpilot'):
        selected = [r for r in rows if r['mode'] == mode]
        totals[mode] = {'executed': len(selected), 'closed_correct': sum(r['success'] for r in selected),
                        'correct_artifacts': sum(r['artifact_success'] for r in selected),
                        'seconds': sum(r['seconds'] for r in selected),
                        'raw_tokens': sum(r['usage']['total_tokens'] for r in selected),
                        'uncached_tokens': sum(r['usage']['total_tokens']-r['usage']['cached_input_tokens'] for r in selected),
                        'groups_passed': sum(sum(j['passed'] for j in r['judgments']) for r in selected)}
    full = len(rows) == 4
    meter = integrity['all_usage_complete'] and full
    savings = {k: 100*(1-totals['goalpilot'][k]/totals['native_goal'][k]) if full and totals['native_goal'][k] and (k == 'seconds' or meter) else None
               for k in ('seconds', 'raw_tokens', 'uncached_tokens')}
    no_regressions = full and all(not b[k] or next(r for r in rows if r['case'] == b['case'] and r['mode'] == 'goalpilot')[k]
                                for b in rows if b['mode'] == 'native_goal' for k in ('success', 'artifact_success'))
    result = {'complete': full, 'planned_trials': 4, 'completed_trials': len(rows), 'totals': totals,
              'savings_percent': savings, 'no_paired_regressions': no_regressions,
              'joint_20_percent_target_met': no_regressions and integrity['quality_integrity_verified'] and meter and all(v is not None and v >= 20 for v in savings.values()),
              'integrity_verified': integrity['quality_integrity_verified'], 'usage_complete': meter,
              'new_known_raw_tokens': sum(r['usage']['total_tokens'] for r in rows),
              'limitation': 'Two familiar synthetic cases; single run per arm. No population claim, quota conversion or pooled old-version savings.'}
    write(out/'analysis.json', result)
    with (out/'trials.csv').open('w') as f:
        names = ['id', 'case', 'mode', 'status', 'success', 'artifact_success', 'seconds', 'raw_tokens', 'uncached_tokens', 'usage_complete']
        writer = csv.DictWriter(f, fieldnames=names); writer.writeheader()
        for r in rows:
            writer.writerow({**{k: r[k] for k in names if k in r}, 'raw_tokens': r['usage']['total_tokens'], 'uncached_tokens': r['usage']['total_tokens']-r['usage']['cached_input_tokens'], 'usage_complete': r['usage']['usage_complete']})
    (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>GoalPilot0.6.2 versus Codex native</title><h1>Fresh comparison</h1><p>Four planned new runs; familiar synthetic cases. Independent judge never feeds workers. All GoalPilot review costs included.</p><pre>'+html.escape(json.dumps(result, indent=2))+'</pre><p><a href="trials.csv">Trials</a> · <a href="protocol.json">Frozen protocol</a> · <a href="audit.json">Raw lifecycle/meter audit</a></p>')
    print('ANALYSIS', json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    action, out = sys.argv[1], Path(sys.argv[2]).resolve()
    if action == 'worker': worker(out, sys.argv[3])
    else: {'create': create, 'run': run, 'report': report}[action](out)
