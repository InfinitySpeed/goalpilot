"""Frozen, counterbalanced real Codex comparison with independent acceptance."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

from goalpilot.autopilot import run_autopilot
from goalpilot.benchmark import fixtures
from goalpilot.engine import atomic_json,verify,token_totals
from goalpilot.model import ContractError,digest
from goalpilot.rpc import AppServerAdapter
from .holdouts import holdouts


def development_cases():
    cases=fixtures()
    for case in cases:case['checks']+=holdouts()[case['name']]
    return cases


def code_fingerprint():
    root=Path(__file__).resolve().parents[1]
    paths=sorted((root/'goalpilot').glob('*.py'))+sorted((root/'evaluation').glob('*.py'))
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def prompt(case):
    return f"""Complete the following coding goal autonomously in this repository:
{case['goal']}

Use the existing project and README as the public interface contract. Follow applicable repository instructions.
Implement the complete usable behavior, preserve existing data, choose reasonable reversible defaults,
run meaningful local checks, and finish with a concise account of changes, checks and limitations.
Do not deploy, publish, obtain credentials or perform destructive external actions.
"""


def summarize(manifest):
    results=manifest['results']
    expected=len(manifest['cases'])*manifest.get('repeats',1)
    groups={}
    for mode in ('direct','goalpilot'):
        members=[x for x in results if x['mode']==mode]
        inputs=sum((x['usage'] or {}).get('input_tokens',0) for x in members)
        outputs=sum((x['usage'] or {}).get('output_tokens',0) for x in members)
        cached=sum((x['usage'] or {}).get('cached_input_tokens',0) for x in members)
        groups[mode]={'runs':len(members),'external_successes':sum(x['external_success'] for x in members),
            'seconds':sum(x['seconds'] for x in members),'reported_tokens':inputs+outputs,
            'input_tokens':inputs,'output_tokens':outputs,'cached_input_tokens':cached,
            'non_cached_input_plus_output':inputs+outputs-cached,
            'usage_complete':bool(members) and all(x['usage_complete'] for x in members),
            'commands':sum(x['command_count'] for x in members),
            'agent_turns':sum(x.get('agent_turns',1) for x in members)}
    a,b=groups['direct'],groups['goalpilot']
    paired={}
    for item in results:paired.setdefault((item['case'],item.get('repeat',1)),{})[item['mode']]=item
    full=[x for x in paired.values() if len(x)==2]
    finished=len(results)==2*expected
    models={model for item in results for model in item.get('models',[]) if model}
    same_model=len(models)==1 and all(x.get('models') for x in results)
    complete=finished and a['usage_complete'] and b['usage_complete'] and same_model
    all_pass=a['external_successes']==b['external_successes']==expected
    def reduction(field,requires_usage=False):
        if not finished or not a[field] or (requires_usage and not complete):return None
        return 100*(1-b[field]/a[field])
    speed=reduction('seconds')
    tokens=reduction('reported_tokens',True)
    uncached=reduction('non_cached_input_plus_output',True)
    return {'stage':manifest['stage'],'treatment':manifest.get('treatment','context'),
        'groups':groups,'expected_pairs':expected,'paired_cases':len(full),'unique_projects':len(manifest['cases']),
        'finished':finished,'same_observed_model':same_model,'observed_models':sorted(models),
        'time_reduction_percent':speed,'reported_token_reduction_percent':tokens,
        'non_cached_token_reduction_percent':uncached,
        'time_wins':sum(x['goalpilot']['seconds']<x['direct']['seconds'] for x in full),
        'primary_threshold_met':bool(complete and all_pass and ((speed or 0)>=15 or (uncached or 0)>=15)),
        'success_rule':manifest['success_rule'],
        'interpretation':'Observed result on a small synthetic corpus; repetitions are not independent projects. No inference of subscription-quota savings, personal satisfaction or success on multi-hour goals.',
        'results':results}


def run_trial(case,mode,args,root,trial_id):
    repo=root/'repos'/trial_id
    repo.mkdir(parents=True)
    for filename,content in case['files'].items():
        path=repo/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
    start=time.monotonic()
    error=None
    state=None
    with AppServerAdapter(args.model,prepared=mode=='goalpilot') as adapter:
        if mode=='goalpilot' and args.treatment=='autopilot':
            try:
                state=run_autopilot(prompt(case),repo,root/'runs'/trial_id,
                    wall_seconds=args.seconds,max_calls=2,max_tokens=1000000,model=args.model,adapter=adapter)
            except (ContractError,OSError,ValueError) as exc:
                error=str(exc)
            if state:
                calls=[x['result'] for x in state['calls'] if x.get('result')]
            else:
                bootstrap=root/'runs'/trial_id/'bootstrap-result.json'
                calls=[json.loads(bootstrap.read_text())] if bootstrap.exists() else []
        else:
            result=adapter.execute(prompt(case),repo,args.seconds,root/'calls'/trial_id)
            calls=[result.to_dict()]
    seconds=time.monotonic()-start
    usage=token_totals([{'result':x} for x in calls])
    checks=verify({'repo':str(repo),'checks':case['checks']},time.monotonic()+60,root/'evidence'/trial_id)
    return {'case':case['name'],'mode':mode,'trial_id':trial_id,'seconds':seconds,
        'external_success':all(x['passed'] for x in checks),'checks_passed':sum(x['passed'] for x in checks),
        'checks_total':len(checks),'usage':usage if calls else None,
        'usage_complete':bool(calls) and usage['usage_complete'],
        'command_count':sum((x.get('telemetry') or {}).get('command_count',0) for x in calls),
        'models':sorted({(x.get('telemetry') or {}).get('model',{}).get('model')
                        for x in calls if (x.get('telemetry') or {}).get('model',{}).get('model')}),
        'agent_turns':len(calls),'goalpilot_status':state['status'] if state else None,
        'fatal':any(x.get('fatal') for x in calls),'error':error,'checks':checks,'calls':calls}


def run(args):
    if not args.live:raise ContractError('--live required for actual Codex sessions')
    if args.repeats<1:raise ContractError('repeats must be positive')
    root=args.output.resolve()
    if root.exists() and any(root.iterdir()):raise ContractError('Study output must be new or empty')
    root.mkdir(parents=True,exist_ok=True)
    if args.stage=='development':cases=development_cases()
    else:
        if args.suite=='v21':
            from .validation_cases_v21 import cases as validation_cases
        else:
            from .validation_cases import cases as validation_cases
        cases=validation_cases()
    if args.cases:
        selected=set(args.cases.split(','))
        cases=[x for x in cases if x['name'] in selected]
    if not cases:raise ContractError('No cases selected')
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'stage':args.stage,
        'hypothesis':'Prepared context and direct-first implementation with local verification reduce repeated exploration/planning while preserving independently checked completion.',
        'success_rule':'All frozen external checks pass in both arms, complete usage and identical observed model in every trial, at least 15% reduction in aggregate full workflow time OR non-cached input plus output tokens. Total reported tokens are secondary. All preregistered repeats must finish.',
        'treatment':args.treatment,'repeats':args.repeats,'suite':args.suite,
        'code_fingerprint':code_fingerprint(),'model_requested':args.model,'seconds_per_trial':args.seconds,
        'cases':[{**x,'public_files_hash':digest(x['files']),'checks_hash':digest(x['checks'])} for x in cases],
        'results':[],'protocol':'Two repetitions, reversed order on second repeat; alternate initial order across projects. Same public goal/files, hidden checks and backend/model. Treatment is full production go, with at most two turns under the same total wall deadline, including preparation, generated-check execution and recovery. Direct gets one autonomous session under the same wall deadline. Hidden acceptance never fed back. No failed trial reruns. Partial usage retained, never treated as full. No source edits during validation.'}
    source=Path(__file__).resolve().parents[1]
    for name in manifest['code_fingerprint']:
        target=root/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,target)
    atomic_json(root/'protocol.json',manifest)
    atomic_json(root/'preregistered-protocol.json',manifest)
    for repeat in range(1,args.repeats+1):
        for index,case in enumerate(cases):
            modes=('direct','goalpilot') if (index+repeat-1)%2==0 else ('goalpilot','direct')
            for mode in modes:
                if code_fingerprint()!=manifest['code_fingerprint']:
                    raise ContractError('Source changed during study; stop rather than combine implementations')
                trial_id=f"{case['name']}-r{repeat}-{mode}"
                print(f"LIVE {args.stage} / {trial_id}",flush=True)
                record=run_trial(case,mode,args,root,trial_id)
                record['repeat']=repeat
                manifest['results'].append(record)
                atomic_json(root/'protocol.json',manifest)
                report=summarize(manifest)
                atomic_json(root/'report.json',report)
                print(json.dumps({k:v for k,v in record.items() if k not in ('checks','calls')},ensure_ascii=False),flush=True)
                if record['fatal']:
                    manifest['stopped_early']='Provider or transport unavailable; no blind retries'
                    atomic_json(root/'protocol.json',manifest)
                    return report
    return summarize(manifest)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true')
    p.add_argument('--stage',choices=['development','validation'],required=True)
    p.add_argument('--treatment',choices=['context','autopilot'],default='autopilot')
    p.add_argument('--suite',choices=['v20','v21'],default='v20')
    p.add_argument('--repeats',type=int,default=2)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cases')
    p.add_argument('--seconds',type=float,default=300)
    p.add_argument('--model')
    run(p.parse_args())
