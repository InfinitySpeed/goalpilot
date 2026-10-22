"""Real marginal-cost study of three unchanged resumes and one injected regression.

This is a workflow integration study on previously completed synthetic projects,
not a held-out first-goal intelligence benchmark. Direct always invokes Codex;
GoalPilot checks its persisted criteria and invokes Codex only if needed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.validation_cases_v21 import cases
from goalpilot.engine import atomic_json,verify,token_totals,prompt_for,run_mission
from goalpilot.model import digest,ContractError
from goalpilot.rpc import AppServerAdapter


def fingerprint():
    paths=sorted((ROOT/'goalpilot').glob('*.py'))+[Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def summarize(manifest):
    groups={}
    for mode in ('direct','goalpilot'):
        runs=[x for x in manifest['results'] if x['mode']==mode]
        groups[mode]={'runs':len(runs),'successes':sum(x['external_success'] for x in runs),
            'seconds':sum(x['seconds'] for x in runs),'agent_turns':sum(x['new_agent_turns'] for x in runs),
            'reported_tokens':sum(x['usage']['total_tokens'] for x in runs),
            'non_cached_input_plus_output':sum(x['usage']['total_tokens']-x['usage']['cached_input_tokens'] for x in runs),
            'usage_complete':all(x['usage']['usage_complete'] for x in runs)}
    a,b=groups['direct'],groups['goalpilot']
    finished=len(manifest['results'])==8
    reduction=lambda field:100*(1-b[field]/a[field]) if finished and a[field] else None
    complete=all(x['usage_complete'] for x in groups.values())
    observed={x.get('telemetry',{}).get('model',{}).get('model')
              for r in manifest['results'] for x in r['calls']}
    same_model=observed=={'gpt-6.1-sol'}
    all_verified=all(x['status']=='scope_passed' for x in manifest['results'])
    speed=reduction('seconds');tokens=reduction('reported_tokens');uncached=reduction('non_cached_input_plus_output')
    return {'kind':'real_resume_workflow_integration','finished':finished,'groups':groups,
        'time_reduction_percent':speed,'reported_token_reduction_percent':tokens,
        'non_cached_token_reduction_percent':uncached,
        'observed_models':sorted(x for x in observed if x),'same_observed_model':same_model,
        'primary_threshold_met':bool(finished and complete and same_model and all_verified and a['successes']==b['successes']==4 and ((speed or 0)>=15 or (uncached or 0)>=15)),
        'scope':'Marginal cost after a previous completed mission: three unchanged repositories and one controlled entrypoint regression. No claim about the first execution, unbounded vague goals or natural blocker frequency.',
        'results':manifest['results']}


def run(args):
    if not args.live:raise ContractError('--live required')
    output=args.output.resolve()
    if output.exists() and any(output.iterdir()):raise ContractError('Output must be new')
    output.mkdir(parents=True,exist_ok=True)
    source=args.source.resolve()
    scenario_list=[('bookmarks','unchanged'),('bundle','unchanged'),('tasks','unchanged'),('tasks','entrypoint-regression')]
    by_name={x['name']:x for x in cases()}
    manifest={'model':'gpt-6.1-sol','source':str(source),'scenarios':scenario_list,
        'source_fingerprint':fingerprint(),'results':[],
        'protocol':'Compare four fixed marginal resume scenarios, alternating condition order. Copy the first GoalPilot repetition of each project, regardless of speed, keeping its frozen inferred checks, handoff, already consumed calls and active time. Both conditions start from identical completed code and same original goal/criteria. For one additional tasks scenario, overwrite tasks.py with an explicit failing stub before either arm starts. Direct receives initial frozen-check results and the same handoff and always invokes Codex once; GoalPilot uses production resume and conditionally invokes it. Same remaining time budget and model. Hidden external checks never used for repair. No first-goal or natural-failure generalization. All prior mission costs are sunk and excluded equally; compare only additional usage/time. No failed-trial reruns.',
        'success_rule':'All four scenarios pass all hidden external checks in both conditions, complete incremental usage, and at least 15% lower aggregate time or non-cached input plus output tokens.'}
    for name in {x[0] for x in scenario_list}:
        origin=json.loads((source/'runs'/f'{name}-r1-goalpilot'/'state.json').read_text())
        if origin['status']!='scope_passed':raise ContractError(f'{name} source is not completed')
    for name,sha in manifest['source_fingerprint'].items():
        target=output/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    atomic_json(output/'preregistered-protocol.json',manifest)
    atomic_json(output/'protocol.json',manifest)
    for index,(name,condition) in enumerate(scenario_list):
        origin_run=source/'runs'/f'{name}-r1-goalpilot'
        origin_state=json.loads((origin_run/'state.json').read_text())
        for mode in (('direct','goalpilot') if index%2==0 else ('goalpilot','direct')):
            if fingerprint()!=manifest['source_fingerprint']:raise ContractError('Source changed during study')
            trial=f'{name}-{condition}-{mode}'
            repo=output/'repos'/trial
            shutil.copytree(source/'repos'/f'{name}-r1-goalpilot',repo,ignore=shutil.ignore_patterns('__pycache__','.git'))
            if condition=='entrypoint-regression':(repo/'tasks.py').write_text("raise SystemExit('controlled injected regression')\n")
            state=json.loads(json.dumps(origin_state))
            contract=state['contract'];old_repo=contract['repo'];contract['repo']=str(repo)
            # Relocate absolute repository paths, without changing check logic.
            for check in contract['checks']:check['command']=[x.replace(old_repo,str(repo)) for x in check['command']]
            state['contract_hash']=digest(contract)
            run_dir=output/'runs'/trial
            run_dir.mkdir(parents=True)
            atomic_json(run_dir/'state.json',state);atomic_json(run_dir/'mission.json',contract)
            before=len(state['calls'])
            remaining=max(.1,contract['budget']['wall_seconds']-state['active_seconds'])
            print('LIVE RESUME',trial,'remaining',round(remaining,2),flush=True)
            start=time.monotonic()
            with AppServerAdapter('gpt-6.1-sol',prepared=mode=='goalpilot') as adapter:
                if mode=='goalpilot':
                    after=run_mission(contract,adapter,run_dir,resume=True)
                    calls=[x['result'] for x in after['calls'][before:] if x.get('result')]
                    status=after['status']
                else:
                    initial=verify(contract,time.monotonic()+remaining,run_dir/'initial-checks')
                    state['verifications'].append({'checks':initial})
                    result=adapter.execute(prompt_for(state,'direct'),repo,max(.1,remaining-(time.monotonic()-start)),run_dir/'calls/new')
                    calls=[result.to_dict()]
                    local=verify(contract,start+remaining,run_dir/'final-checks')
                    status='scope_passed' if all(x['passed'] for x in local) else 'incomplete'
            seconds=time.monotonic()-start
            external=verify({'repo':str(repo),'checks':by_name[name]['checks']},time.monotonic()+60,output/'evidence'/trial)
            record={'trial_id':trial,'project':name,'condition':condition,'mode':mode,'seconds':seconds,
                'remaining_seconds':remaining,'external_success':all(x['passed'] for x in external),
                'checks_passed':sum(x['passed'] for x in external),'checks_total':len(external),'status':status,
                'new_agent_turns':len(calls),'usage':token_totals([{'result':x} for x in calls]),
                'calls':calls,'external_checks':external}
            manifest['results'].append(record);atomic_json(output/'protocol.json',manifest)
            atomic_json(output/'report.json',summarize(manifest))
            print(json.dumps({k:v for k,v in record.items() if k not in ('calls','external_checks')},ensure_ascii=False),flush=True)
            if any(x.get('fatal') for x in calls):raise ContractError('Provider unavailable; no blind retries')
    return summarize(manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--source',type=Path,default=ROOT/'reports/v21-validation-001')
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
