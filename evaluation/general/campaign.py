"""Checkpointed, frozen paired evaluation of complete autonomous missions."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

from goalpilot.autopilot import run_autopilot
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.model import ContractError,digest
from goalpilot.rpc import AppServerAdapter
from .cases import cases,materialize
from .judge import evaluate

ROOT=Path(__file__).resolve().parents[2]
SEEDS=(84721,917113)


def fingerprint():
    paths=sorted((ROOT/'goalpilot').glob('*.py'))+sorted(Path(__file__).parent.glob('*.py'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def public_prompt(case):
    return f"""Complete this coding mission autonomously:
{case['goal']}

The README is the public interface and data-preservation contract. Deliver all its behavior, documentation
and your own meaningful tests. Choose reversible defaults without asking clarification. Preserve existing
user records and unrelated files. Work only inside this repository; benchmark/supervisor files outside
it are not task inputs and must not be inspected. Use the Python standard library and loopback only
for application tests. No installation, deployment, publishing, credentials or external services.
Finish with the actual delivered behavior, checks and remaining limitations.
"""


def events(root):
    for path in sorted(root.rglob('events.jsonl')):
        with path.open() as stream:
            for line in stream:
                try:yield json.loads(line)['packet']
                except (ValueError,KeyError):continue


def telemetry(root):
    commands=[];requests=[];models=set();totals={};turns=set()
    for packet in events(root):
        method=packet.get('method','');params=packet.get('params',{})
        if 'method' in packet and 'id' in packet and method!='initialize':
            if method not in ('thread/start','turn/start','turn/interrupt'):
                requests.append(method)
        if method=='thread/tokenUsage/updated':
            thread=params['threadId'];value=params['tokenUsage']['total']
            prior=totals.get(thread)
            if prior is None or value['inputTokens']+value['outputTokens']>=prior['inputTokens']+prior['outputTokens']:totals[thread]=value
            turns.add((thread,params.get('turnId')))
        if method=='item/completed' and params.get('item',{}).get('type')=='commandExecution':
            item=params['item'];commands.append({'command':item.get('command',''),'exit_code':item.get('exitCode'),
                'output_hash':hashlib.sha256((item.get('aggregatedOutput') or '').encode()).hexdigest()})
        if 'result' in packet and isinstance(packet['result'],dict) and packet['result'].get('model'):
            models.add(packet['result']['model'])
    failed={}
    for c in commands:
        if c['exit_code'] not in (None,0):
            k=(c['command'].strip(),c['output_hash']);failed[k]=failed.get(k,0)+1
    lower={'input_tokens':sum(x['inputTokens'] for x in totals.values()),
           'output_tokens':sum(x['outputTokens'] for x in totals.values()),
           'cached_input_tokens':sum(x['cachedInputTokens'] for x in totals.values())}
    return {'command_count':len(commands),'repeated_identical_failed_commands':sum(max(0,n-1) for n in failed.values()),
        'server_requests':requests,'observed_models':sorted(models),'observed_turns':len(turns),'usage_lower_bound':lower}


def plan(output,seconds=600,repeats=2,model='gpt-6.1-sol'):
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise ContractError('Campaign output must be new')
    if seconds<=0 or repeats<1:raise ContractError('Budgets and repeats must be positive')
    output.mkdir(parents=True,exist_ok=True)
    from .preflight import run as preflight_run
    preflight=preflight_run()
    atomic_json(output/'preflight.json',preflight)
    tasks=cases();order=[]
    for repetition in range(1,repeats+1):
        for index,case in enumerate(tasks):
            modes=('direct','goalpilot') if (index+repetition)%2 else ('goalpilot','direct')
            for mode in modes:order.append({'id':f"{case['name']}-r{repetition}-{mode}",'case':case['name'],'repeat':repetition,'mode':mode})
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'kind':'autonomous_multicomponent_campaign',
        'model':model,'seconds_per_trial':seconds,'max_goalpilot_turns':3,'soft_tokens_per_trial':1000000,
        'repeats':repeats,'seeds':SEEDS,'cases':tasks,'case_hash':digest(tasks),'preflight_hash':digest(preflight),'source_fingerprint':fingerprint(),'order':order,
        'protocol':"Same initial source/data, public goal, model, backend and full wall deadline. Direct gets one uninterrupted autonomous Codex turn; GoalPilot uses production go, up to 3 turns inside the same deadline. Hidden black-box checks never sent to either agent or used for repair. Two precommitted input seeds, process restarts and concurrent requests check stability. No human input after initial prompt; automatic feedback generated by GoalPilot is allowed and charged. Alternate order across projects and invert on second repetition. No failed-trial reruns. A lost worker is recovered explicitly as an interrupted trial, retains streamed lower-bound usage and is never replaced. Other trials continue; infrastructure interruptions are reported separately. Source cannot change after registration.",
        'decision_rule':"A primary efficacy improvement requires the complete planned campaign, no infrastructure omissions, identical observed model, no paired completion regressions and either at least 2 additional fully delivered goals OR equal complete success with >=15% lower total workflow time or non-cached input+output. Cost claims additionally require complete usage for every trial. No significance/generalization claim from three projects.",
        'scope':"Three synthetic multi-component tasks with ten-minute budgets, not representative human goals of several hours. Objective acceptance, no personal satisfaction or exact subscription quota conversion."}
    for name in manifest['source_fingerprint']:
        path=output/'source_snapshot'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    atomic_json(output/'preregistered-protocol.json',manifest)
    atomic_json(output/'manifest.json',manifest)
    return manifest


def read_records(output,manifest):
    return [json.loads((output/'trials'/item['id']/'record.json').read_text())
            for item in manifest['order'] if (output/'trials'/item['id']/'record.json').exists()]


def outcome(case,repo,trial_dir):
    start=time.monotonic();checks=[]
    for phase,seed in enumerate(SEEDS):
        saved=trial_dir/f'judge-{phase+1}.json'
        # A completed judgment, including a failure, is immutable. Recovery must
        # not replace it with a second judgment of a now-migrated data store.
        results=json.loads(saved.read_text()) if saved.exists() else evaluate(case,repo,seed)
        checks.extend({**x,'phase':'fresh_inputs' if phase else 'acceptance'} for x in results)
        if not saved.exists():atomic_json(saved,results)
    return checks,time.monotonic()-start


def run_next(output,*,live=False,adapter_factory=None):
    if not live:raise ContractError('--live required; campaign uses the authenticated Codex account')
    output=Path(output).resolve();manifest=json.loads((output/'manifest.json').read_text())
    if manifest!=json.loads((output/'preregistered-protocol.json').read_text()):raise ContractError('Preregistered protocol changed')
    if fingerprint()!=manifest['source_fingerprint']:raise ContractError('Frozen source changed; start a separate campaign')
    with lock(output/'campaign.lock'):
        completed={x['id'] for x in read_records(output,manifest)}
        item=next((x for x in manifest['order'] if x['id'] not in completed),None)
        if item is None:return None
        trial=output/'trials'/item['id'];trial.mkdir(parents=True,exist_ok=True)
        if (trial/'started.json').exists():raise ContractError('Interrupted/uncommitted trial exists; recover it, do not repeat it')
        case=next(x for x in manifest['cases'] if x['name']==item['case'])
        repo=output/'repos'/item['id'];materialize(case,repo)
        atomic_json(trial/'started.json',{'item':item,'started_at':time.time(),'repo':str(repo),
            'budget_seconds':manifest['seconds_per_trial'],'source_fingerprint':manifest['source_fingerprint']})
        start=time.monotonic();calls=[];state=None;error=None;fatal=False;status='incomplete'
        factory=adapter_factory or AppServerAdapter
        try:
            with factory(manifest['model'],prepared=item['mode']=='goalpilot') as adapter:
                if item['mode']=='direct':
                    result=adapter.execute(public_prompt(case),repo,manifest['seconds_per_trial'],trial/'calls/1')
                    calls=[result.to_dict()];status='delivered' if result.returncode==0 else 'incomplete'
                else:
                    state=run_autopilot(public_prompt(case),repo,trial/'run',wall_seconds=manifest['seconds_per_trial'],
                        max_calls=3,max_tokens=manifest['soft_tokens_per_trial'],model=manifest['model'],adapter=adapter)
                    calls=[x.get('result',{'usage':None,'usage_complete':False}) for x in state['calls']]
                    status=state['status']
        except (ContractError,OSError,ValueError) as exc:
            error=str(exc)
            state_path=trial/'run/state.json';bootstrap=trial/'run/bootstrap-result.json'
            if state_path.exists():
                state=json.loads(state_path.read_text());calls=[x.get('result',{'usage':None,'usage_complete':False}) for x in state['calls']]
            elif bootstrap.exists():calls=[json.loads(bootstrap.read_text())]
        seconds=time.monotonic()-start
        fatal=any(x.get('fatal') for x in calls)
        atomic_json(trial/'execution.json',{'seconds':seconds,'status':status,'calls':calls,'error':error,'fatal':fatal})
        checks,judge_seconds=outcome(case,repo,trial)
        usage=token_totals([{'result':x} for x in calls]);observed=telemetry(trial)
        success=all(x['passed'] for x in checks)
        record={**item,'status':status,'seconds':seconds,'judge_seconds':judge_seconds,'calls':calls,'new_agent_turns':len(calls),
            'usage':usage,'checks':checks,'artifact_success':success,
            'autonomous_success':success and status in ('delivered','scope_passed','completed'),
            'blocker_resolved':all(x['passed'] for x in checks if x['id']=='blocker'),
            'stable_on_new_inputs':all(x['passed'] for x in checks if x['phase']=='fresh_inputs'),
            'human_inputs_after_start':0,'infrastructure_interrupted':False,'fatal':fatal,'error':error,
            'simulated':any(x.get('simulated',False) for x in calls),'telemetry':observed}
        atomic_json(trial/'record.json',record)
        return record


def recover(output,reason):
    """Account for a genuinely lost worker without rerunning its trial."""
    output=Path(output).resolve();manifest=json.loads((output/'manifest.json').read_text())
    with lock(output/'campaign.lock'):
        completed={x['id'] for x in read_records(output,manifest)}
        item=next((x for x in manifest['order'] if x['id'] not in completed),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if not (trial/'started.json').exists():raise ContractError('No started trial to recover')
        telemetry_data=telemetry(trial);known=telemetry_data['usage_lower_bound']
        usage=token_totals([{'result':{'usage':known,'usage_complete':False}}])
        execution=trial/'execution.json'
        if execution.exists():
            # Model execution had already finished; only the independent judge
            # was interrupted. Finish that judge without another model call.
            saved=json.loads(execution.read_text());case=next(x for x in manifest['cases'] if x['name']==item['case'])
            checks,judge_seconds=outcome(case,output/'repos'/item['id'],trial)
            usage=token_totals([{'result':x} for x in saved['calls']]);success=all(x['passed'] for x in checks)
            record={**item,**saved,'new_agent_turns':len(saved['calls']),'usage':usage,'checks':checks,
                'artifact_success':success,'autonomous_success':success and saved['status'] in ('delivered','scope_passed','completed'),
                'judge_seconds':judge_seconds,'blocker_resolved':all(x['passed'] for x in checks if x['id']=='blocker'),
                'stable_on_new_inputs':all(x['passed'] for x in checks if x['phase']=='fresh_inputs'),
                'human_inputs_after_start':0,'infrastructure_interrupted':False,
                'simulated':any(x.get('simulated',False) for x in saved['calls']),'telemetry':telemetry_data,'judge_recovery_reason':reason}
        else:
            record={**item,'status':'infrastructure_interruption','seconds':None,'judge_seconds':0,'calls':[],
                'new_agent_turns':max(1,telemetry_data['observed_turns']),'usage':usage,'checks':[],
                'artifact_success':False,'autonomous_success':False,'blocker_resolved':False,'stable_on_new_inputs':False,
                'human_inputs_after_start':0,'infrastructure_interrupted':True,'fatal':False,'error':reason,'simulated':False,'telemetry':telemetry_data}
        atomic_json(trial/'record.json',record);return record
