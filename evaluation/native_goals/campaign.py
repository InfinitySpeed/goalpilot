import hashlib,json,shutil,time
from pathlib import Path
from goalpilot import __version__
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.finish import run_finish
from goalpilot.model import ContractError
from goalpilot.rpc import AppServerAdapter
from .adapter import NativeGoalAdapter
from .cases import GOALS,SPECS,materialize,judge
from .preflight import run as preflight
from .report import report
ROOT=Path(__file__).resolve().parents[2]


def fingerprint():return{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for folder in('goalpilot','evaluation/ambitious','evaluation/native_goals','tests')for p in sorted((ROOT/folder).glob('*.py'))}|{'validate.py':hashlib.sha256((ROOT/'validate.py').read_bytes()).hexdigest()}


def create(output):
    output=Path(output).resolve()
    if output.exists():raise ContractError('Output already exists')
    validation=json.loads((ROOT/'reports/tests.json').read_text());source=fingerprint()
    if not validation['successful']or any(validation['source_fingerprint'].get(p)!=sha for p,sha in source.items()if p.startswith(('goalpilot/','tests/'))):raise ContractError('Current source requires passing offline CI')
    smoke=json.loads((ROOT/'reports/native-goal-smoke-002/result.json').read_text())
    if not smoke['success']or smoke['model']!='gpt-6.1-sol':raise ContractError('Real native goal lifecycle/meter smoke test must pass first')
    checked=preflight();order=[]
    for i,name in enumerate(GOALS):
        for mode in(['native_goal','goalpilot']if i%2==0 else['goalpilot','native_goal']):order.append({'id':name+'-'+mode,'case':name,'mode':mode})
    m={'version':1,'product_version':__version__,'model':'gpt-6.1-sol','cases':list(GOALS),'order':order,'goals':GOALS,'public_contracts':SPECS,'seconds_per_trial':900,'max_calls_goalpilot':6,'raw_token_soft_cap_per_trial':1500000,'observed_campaign_token_cap':3000000,'source_fingerprint':source,'offline_validation':validation,'preflight':checked,'native_capability_smoke':smoke,
    'primary_rule':'Complete all four planned executions. At least one additional fully correct and normally concluded goal for GoalPilot, and zero paired regressions. Native normal completion requires native thread/goal status complete AND its final turn complete; an ordinary final assistant message does not suffice. GoalPilot requires scope_passed/completed. Both require every original behavioral group. No time/token saving substitutes for additional conclusions. This is a small descriptive criterion on two related scopes, not statistical population proof.',
    'baseline':'Real persistent thread/goal/set active via Codex 0.163 native API. Let automatic continuations run; never stop at the first normal turn. Record native goal state and all turn IDs/cumulative metering. At deadline pause only this newly created goal and interrupt/close its worker. Never manually relabel a native goal complete.',
    'budget':'Both use 900 seconds active workflow and a raw 1.5M soft token cap between turns/calls. Native continuations are server-driven, no artificially imposed six-turn cap. GoalPilot has at most six calls including reviews and recovery. Campaign cap3M is observed between complete trials; partial counters remain lower bounds.',
    'novelty':'The previous study0.5.0 stopped after three of12 executions: Flowdesk direct/GoalPilot and Stockroom GoalPilot. Its first pair already violated no-regression. That incomplete failure is retained and not relabelled. Runforge has never had a live model execution. Automation adds real frozen node tasks and bounded concurrent worker execution, defined/tested before these new outcomes. The two scopes share the Runforge core and are correlated.',
    'design':'Same seeded files/public contracts/model, alternating mode order across scopes. Core13 groups on two selected input seeds; automation adds six deterministic worker journey groups. No hidden feedback to any live worker, no code/criteria changes during campaign, failed trials never rerun. No injected runtime/process failure; product internal phase deadlines may interrupt its own turns and are counted.',
    'futility_rule':'May stop at a whole paired-case boundary after any paired regression, because the primary no-regression condition is then impossible. Keep the original planned denominator and mark incomplete; no positive primary claim allowed. Stop immediately on fatal provider/infrastructure failures or observed token cap.',
    'limits':['Only two related scopes on one synthetic workflow platform, not independent business projects.','Detailed original contracts despite broad initial goals; not a measurement of personal satisfaction.','Native model sandbox cannot open localhost sockets in the observed environment; host checks can. Both use same Codex sandbox, but product host execution is part of its workflow.','Correct artifact versus native blocked/unfinished is closure evidence, not automatically a code-quality gain.','No quota conversion or full cost savings with incomplete counters.']}
    output.mkdir(parents=True);atomic_json(output/'protocol.json',m);atomic_json(output/'preregistered-protocol.json',m)
    for name in source:
        q=output/'source_snapshot'/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,q)
    for folder in('evaluation','tools','examples'):
        for p in(ROOT/folder).rglob('*.py'):
            q=output/'source_snapshot'/p.relative_to(ROOT)
            if '__pycache__'not in p.parts and not q.exists():q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    report(output);return m


def finalize(output,m,item,trial,execution):
    path=trial/'judgments.json'
    if path.exists():checks=json.loads(path.read_text())
    else:checks=judge(item['case'],output/'repos'/item['id']);atomic_json(path,checks)
    calls=execution['calls'];native=item['mode']=='native_goal';normal=execution['status']in('complete','scope_passed','completed');artifact=len(checks)==(26 if item['case']=='runforge'else 32)and all(r['passed']for r in checks)
    models=sorted({v for c in calls if(v:=((c.get('result',{}).get('telemetry')or{}).get('model')or{}).get('model'))})
    turns=len(calls[0]['result']['telemetry']['native_turns'])if native and calls else len(calls)
    row={**item,**execution,'judgments':checks,'normal_exit':normal,'artifact_success':artifact,'success':normal and artifact,'usage':token_totals(calls),'models':models,'model_turns':turns,'fatal':any(c.get('result',{}).get('fatal')for c in calls),'infrastructure_interruption':bool(execution['error']and not calls),'human_inputs':0}
    atomic_json(trial/'record.json',row);report(output);return row


def run_next(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    if m!=json.loads((output/'preregistered-protocol.json').read_text())or fingerprint()!=m['source_fingerprint']:raise ContractError('Frozen protocol/source changed')
    with lock(output/'campaign.lock'):
        done=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
        data=report(output)
        if data['quality_losses']:
            atomic_json(output/'futility-stop.json',{'reason':'Preregistered paired regression futility rule','complete_trials':len(done),'planned_trials':4});return None
        if any(r['fatal']or r['infrastructure_interruption']for r in done)or sum(r['usage']['total_tokens']for r in done)>=m['observed_campaign_token_cap']:return None
        item=next((x for x in m['order']if x['id']not in{r['id']for r in done}),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if(trial/'execution.json').exists():return finalize(output,m,item,trial,json.loads((trial/'execution.json').read_text()))
        if trial.exists():raise ContractError('Uncommitted trial retained; never blindly rerun')
        trial.mkdir(parents=True);repo=output/'repos'/item['id'];materialize(repo,item['case']);initial={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(repo.rglob('*'))if p.is_file()and not p.is_symlink()};atomic_json(trial/'started.json',{'at':time.time(),'item':item,'initial_repo_fingerprint':initial})
        print('START',item['id'],flush=True);start=time.monotonic();calls=[];error=None;status='incomplete'
        goal=m['goals'][item['case']]+'''\nFollow all original README contracts, complete every workflow, preserve user data and resolve reversible ambiguities autonomously. Test meaningful behavior through the documented public interfaces. No human steering, deployment, external service or credentials. Work only in this repository; do not read benchmark/evaluation sources, reference implementations or sibling trials. Do not launch other agents/model sessions or nested Codex commands. Complete the whole requested goal and give a factual handoff.'''
        try:
            if item['mode']=='native_goal':
                with NativeGoalAdapter(m['model'])as worker:
                    result=worker.execute_goal(goal,repo,m['seconds_per_trial'],trial/'run/calls/1',m['raw_token_soft_cap_per_trial']);calls=[{'strategy':'native_goal','result':result.to_dict()}];observed=(result.telemetry.get('native_goal_at_stop')or{}).get('status','incomplete');status=observed if result.returncode==0 or observed in('blocked','usageLimited','budgetLimited')else'incomplete'
            else:
                with AppServerAdapter(m['model'],prepared=True)as worker:
                    state=run_finish(goal,repo,trial/'run',wall_seconds=m['seconds_per_trial'],max_calls=m['max_calls_goalpilot'],max_tokens=m['raw_token_soft_cap_per_trial'],model=m['model'],adapter=worker,audit_policy='on-interruption',notify=lambda x:print(item['id'],x,flush=True));calls=state['calls'];status=state['status']
        except(ContractError,OSError,ValueError)as exc:
            error=f'{type(exc).__name__}: {exc}'
            for name in('state.json','finish-run.json'):
                p=trial/'run'/name
                if p.exists():saved=json.loads(p.read_text());calls=saved['calls'];status=saved['status'];break
        execution={'seconds':time.monotonic()-start,'calls':calls,'error':error,'status':status};atomic_json(trial/'execution.json',execution);return finalize(output,m,item,trial,execution)
