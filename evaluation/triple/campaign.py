"""Frozen matched campaign with explicit global cost cap and immutable failures."""
import hashlib,json,shutil,time
from pathlib import Path
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.finish import run_finish
from goalpilot.model import ContractError
from goalpilot.rpc import AppServerAdapter
from .cases import materialize
from .specs import GOALS,SPECS
from .judge import evaluate
from .preflight import run as preflight
from .report import report

ROOT=Path(__file__).resolve().parents[2]


def fingerprint():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for folder in ('goalpilot','evaluation/triple')for p in sorted((ROOT/folder).glob('*.py'))}


def create(output):
    from goalpilot import __version__
    output=Path(output).resolve()
    if output.exists():raise ContractError('Campaign already exists')
    validation=json.loads((ROOT/'reports/tests.json').read_text())
    if not validation.get('successful') or any(validation.get('source_fingerprint',{}).get(str(p.relative_to(ROOT)))!=hashlib.sha256(p.read_bytes()).hexdigest()for p in (ROOT/'goalpilot').glob('*.py')):
        raise ContractError('Run passing offline validation on the current product before registering live work')
    checks=preflight();output.mkdir(parents=True)
    order=[]
    for repeat in range(2):
        for index,name in enumerate(GOALS):
            modes=['direct','goalpilot']if(index+repeat)%2==0 else['goalpilot','direct']
            for mode in modes:order.append({'id':f'{name}-{mode}-{repeat+1}','case':name,'mode':mode,'repeat':repeat})
    m={'version':1,'product_version':__version__,'model':'gpt-6.1-sol','seconds_per_trial':300,'max_calls':5,'max_tokens_per_trial':700000,
       'campaign_observed_token_cap':3000000,'resource_threshold_percent':15,'repeats':2,'cases':list(GOALS),'goals':GOALS,'public_specs':SPECS,
       'hidden_input_seeds':[62537,109891],'order':order,'source_fingerprint':fingerprint(),'preflight':checks,
       'decision_rule':'Full planned 12-trial campaign, no infrastructure omissions, identical observed model, full usage. At least one more fully delivered goal and zero paired completion regressions. At least 15% less full workflow time per fully delivered goal, 15% fewer reported input+output tokens per delivered goal AND 15% fewer uncached input+output per delivered goal. All failed trials remain in costs. Both arms must have a positive success count to calculate finite per-goal savings. Absolute costs reported alongside, not rebranded as savings. All conditions must hold jointly.',
       'design':'Three previously unused synthetic libraries with four static documented semantic faults each; two original public tests expose some faults, additional hidden groups cover documented interactions. Same files, goal, model, 300s active budget in both arms. Direct receives one uninterrupted autonomous turn. Production CLI GoalPilot adaptive workflow uses preflight, frozen original tests, at most two focused model-generated public-API probes before implementation, same-thread report recovery and up to five total model calls under the same deadline. Every preparation, model call and local check is charged. Alternate arm order and invert on second repeat. No hidden judge output is used for repair. No injected runtime failures, failed-trial reruns, or post-start source changes. No human intervention inside trials. Stop on fatal provider failure or campaign observed token cap.',
       'limitations':['Three synthetic projects with detailed public contracts; not a sample of personal vague multi-hour goals.','Repeated projects are correlated; paired descriptive results are not population-level causal proof.','The original semantic faults were authored and frozen, not naturally sampled production incidents.','Resource savings per delivered goal differ from absolute time/token savings.','Soft token limits are observed between calls; incomplete usage blocks full cost claims.','No exact subscription quota or personal satisfaction measurement.']}
    m['offline_validation']={'passed':validation['passed'],'tests_run':validation['tests_run'],'recorded_at_utc':validation['recorded_at_utc'],'source_fingerprint':validation['source_fingerprint']}
    pilot=ROOT/'reports/triple-live-001/technical-pilot.json'
    if pilot.exists():
        m['prior_technical_pilot']=json.loads(pilot.read_text())
        previous=json.loads((pilot.parent/'protocol.json').read_text())
        paths=[name for name in m['source_fingerprint']if name.startswith('evaluation/triple/')and('reference_'in name or name.endswith(('specs.py','cases.py','judge.py')))]
        m['case_and_judge_sources_unchanged_from_pilot']=all(previous['source_fingerprint'].get(name)==m['source_fingerprint'][name]for name in paths)
    atomic_json(output/'protocol.json',m);atomic_json(output/'preregistered-protocol.json',m)
    for name in m['source_fingerprint']:
        dest=output/'source_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return m


def records(output,m):return[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]


def finalize(output,m,item,trial,execution):
    judgments=[];judge_start=time.monotonic()
    for seed in m['hidden_input_seeds']:
        path=trial/f'judge-{seed}.json'
        if path.exists():checks=json.loads(path.read_text())
        else:checks=evaluate(item['case'],output/'repos'/item['id'],seed);atomic_json(path,checks)
        judgments.extend({**x,'seed':seed}for x in checks)
    normal=execution['status']in('delivered','completed','scope_passed');artifact=all(x['passed']for x in judgments)
    calls=execution['calls'];models=sorted({model for c in calls if(model:=((c.get('result',{}).get('telemetry')or{}).get('model')or{}).get('model'))})
    row={**item,**execution,'judgments':judgments,'judge_seconds':time.monotonic()-judge_start,'normal_exit':normal,
       'artifact_success':artifact,'success':normal and artifact,'usage':token_totals(calls),'models':models,
       'human_inputs':0,'infrastructure_interruption':False,'fatal':any(c.get('result',{}).get('fatal')for c in calls)}
    atomic_json(trial/'record.json',row);report(output);return row


def run_next(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    if m!=json.loads((output/'preregistered-protocol.json').read_text()):raise ContractError('Preregistered protocol changed')
    if fingerprint()!=m['source_fingerprint']:raise ContractError('Frozen source changed; cannot continue this campaign')
    with lock(output/'campaign.lock'):
        done=records(output,m)
        if any(r['fatal']for r in done):return None
        if sum(r['usage']['total_tokens']for r in done)>=m['campaign_observed_token_cap']:return None
        item=next((x for x in m['order']if x['id']not in{r['id']for r in done}),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if (trial/'execution.json').exists():return finalize(output,m,item,trial,json.loads((trial/'execution.json').read_text()))
        if trial.exists():raise ContractError('Uncommitted trial exists; retain interruption, never blindly rerun')
        trial.mkdir(parents=True);repo=output/'repos'/item['id'];materialize(item['case'],repo)
        initial={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(repo.rglob('*'))if p.is_file()and not p.is_symlink()}
        atomic_json(trial/'started.json',{'at':time.time(),'item':item,'initial_repo_fingerprint':initial})
        start=time.monotonic();state=None;calls=[];error=None;status='incomplete'
        try:
            with AppServerAdapter(m['model'],prepared=item['mode']=='goalpilot')as worker:
                if item['mode']=='direct':
                    prompt=f'''Complete this coding goal autonomously in the existing repository:
{m['goals'][item['case']]}
Follow the original README public contract and repository instructions. Preserve user data,
implement all documented behavior, resolve reversible ambiguities yourself, run meaningful local
behavioral checks and finish with a concise factual handoff. No deployment or external services.
'''
                    result=worker.execute(prompt,repo,m['seconds_per_trial'],trial/'run/calls/1')
                    calls=[{'strategy':'direct','result':result.to_dict()}];status='delivered'if result.returncode==0 else'incomplete'
                else:
                    state=run_finish(m['goals'][item['case']],repo,trial/'run',wall_seconds=m['seconds_per_trial'],
                        max_calls=m['max_calls'],max_tokens=m['max_tokens_per_trial'],model=m['model'],adapter=worker,
                        audit_policy='on-interruption',notify=lambda s:print(item['id'],s,flush=True))
                    calls=state['calls'];status=state['status']
        except(ContractError,OSError,ValueError)as exc:
            error=f'{type(exc).__name__}: {exc}'
            for filename in ('state.json','finish-run.json'):
                path=trial/'run'/filename
                if path.exists():saved=json.loads(path.read_text());calls=saved['calls'];status=saved['status'];break
        execution={'seconds':time.monotonic()-start,'status':status,'calls':calls,'error':error}
        atomic_json(trial/'execution.json',execution)
        return finalize(output,m,item,trial,execution)
