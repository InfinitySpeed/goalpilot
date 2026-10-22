"""Preregistered, bounded comparison on three complete multi-workstream goals."""
import hashlib,json,shutil,time
from pathlib import Path
from goalpilot import __version__
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.finish import run_finish
from goalpilot.model import ContractError
from goalpilot.rpc import AppServerAdapter
from .cases import materialize
from .specs import SPECS,GOALS
from .judge import GROUPS,evaluate
from .preflight import run as preflight
from .report import report
ROOT=Path(__file__).resolve().parents[2]


def fingerprint():return{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for folder in('goalpilot','evaluation/ambitious','tests')for p in sorted((ROOT/folder).glob('*.py'))}|{'validate.py':hashlib.sha256((ROOT/'validate.py').read_bytes()).hexdigest()}


def create(output):
    output=Path(output).resolve()
    if output.exists():raise ContractError('Output exists; retained trials must not be overwritten')
    validation=json.loads((ROOT/'reports/tests.json').read_text());source=fingerprint()
    if not validation['successful']or any(validation['source_fingerprint'].get(p)!=sha for p,sha in source.items()if p.startswith(('goalpilot/','tests/'))):raise ContractError('Current product and tests require passing offline validation before registration')
    checked=preflight();order=[]
    for repeat in range(2):
        for index,name in enumerate(SPECS):
            modes=['direct','goalpilot']if(index+repeat)%2==0 else['goalpilot','direct']
            for mode in modes:order.append({'id':f'{name}-{mode}-{repeat+1}','case':name,'mode':mode,'repeat':repeat})
    m={'version':1,'product_version':__version__,'model':'gpt-6.1-sol','seconds_per_trial':900,'max_calls':6,'max_tokens_per_trial':1500000,'campaign_observed_token_cap':7000000,'repeats':2,'cases':list(SPECS),'goals':GOALS,'public_contracts':SPECS,'groups':GROUPS,'hidden_input_seeds':[90173,470117],'order':order,'source_fingerprint':source,'offline_validation':validation,'preflight':checked,
    'primary_rule':'Complete all 12 planned executions with the same observed model and complete outcome evidence. Fully delivered goal = ALL 13 hidden behavioral groups pass on both seeds AND normal autonomous termination. GoalPilot must deliver at least two more complete goals and have zero paired completion regressions. Failed trials are never replaced. No outcome-informed changes of requirements or product during this campaign. No timing/token saving may substitute for additional delivered goals.',
    'secondary_metrics':['Artifact correctness without normal delivery','Fraction of documented workflow groups passed (coarse, not interchangeable with goal success)','Absolute time and reported/uncached tokens; full cost per delivered goal including failures only when denominator positive and usage complete','False completion: normal exit with at least one failed hidden group','Discordant-pair exact one-sided sign probability, explicitly not a valid independent-sample significance claim because project repeats are correlated'],
    'design':'Three previously unused complete domain platforms with a brief ambitious goal and detailed original public workflow contracts. Working standard-library SQLite transaction/backup scaffolding and JSONL/HTTP transport are supplied equally; all domain behavior starts unimplemented. Same model and full 900-second workflow budget. Direct uses one uninterrupted autonomous session; GoalPilot production auto mode detects many original workstreams, reserves independent completion review and repair time, and persists original tests, budgets and evidence. Every product model call/local preparation/check charged. Arm order alternates and reverses on repeat. No turn/process failures are injected. Judge runs after execution and never supplies repair feedback. Local domain tests exercise actual concurrent processes and business rejections. Neither model may read sibling trials, benchmark/reference source, or launch other agents/model calls.',
    'limits':['Three synthetic projects with detailed public contracts, not a sample of personal vague multi-hour goals.','Two input seeds vary selected generated scenarios; most fixed journey checks repeat. They are not independent projects.','Repeated tasks and arms share model/cache conditions and supplied infrastructure; these are descriptive paired outcomes.','At most two additional goals with no regressions is a preregistered practical criterion, not population-level statistical proof.','Soft token caps are observed after whole calls/trials and can be exceeded; partial usage blocks full cost savings claims.','No hidden feedback used for fixes or post-result replacement of failed trials.','Time excludes external hidden judging in both arms. Tokens do not translate exactly into subscription quota.']}
    output.mkdir(parents=True);atomic_json(output/'protocol.json',m);atomic_json(output/'preregistered-protocol.json',m)
    for name in source:
        q=output/'source_snapshot'/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,q)
    # Clearly separate nonregistered reproduction dependencies from frozen inputs.
    for folder in('evaluation','examples','tools'):
        for p in(ROOT/folder).rglob('*.py'):
            q=output/'source_snapshot'/p.relative_to(ROOT)
            if '__pycache__'not in p.parts and not q.exists():q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    atomic_json(output/'source_snapshot/REPRODUCTION-SUPPORT.json',{'note':'Supporting imports copied at registration. Exact experimental fingerprints are in ../protocol.json; extra support files are not experimental source inputs.'})
    report(output);return m


def finalize(output,m,item,trial,execution):
    judgments=[]
    for seed in m['hidden_input_seeds']:
        path=trial/f'judge-{seed}.json'
        if path.exists():rows=json.loads(path.read_text())
        else:rows=evaluate(item['case'],output/'repos'/item['id'],seed);atomic_json(path,rows)
        judgments.extend({**r,'seed':seed}for r in rows)
    calls=execution['calls'];normal=execution['status']in('delivered','scope_passed','completed');artifact=len(judgments)==len(m['groups'])*len(m['hidden_input_seeds'])and all(r['passed']for r in judgments)
    models=sorted({v for c in calls if(v:=((c.get('result',{}).get('telemetry')or{}).get('model')or{}).get('model'))})
    row={**item,**execution,'judgments':judgments,'usage':token_totals(calls),'models':models,'artifact_success':artifact,'normal_exit':normal,'success':normal and artifact,
    'fatal':any(c.get('result',{}).get('fatal')for c in calls),'infrastructure_interruption':bool(execution.get('error')and not calls),'human_inputs':0}
    atomic_json(trial/'record.json',row);report(output);return row


def run_next(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    if m!=json.loads((output/'preregistered-protocol.json').read_text())or fingerprint()!=m['source_fingerprint']:raise ContractError('Registered sources or protocol changed; cannot run')
    with lock(output/'campaign.lock'):
        done=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
        if any(r['fatal']or r['infrastructure_interruption']for r in done):return None
        if sum(r['usage']['total_tokens']for r in done)>=m['campaign_observed_token_cap']:return None
        item=next((x for x in m['order']if x['id']not in{r['id']for r in done}),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if(trial/'execution.json').exists():return finalize(output,m,item,trial,json.loads((trial/'execution.json').read_text()))
        if trial.exists():raise ContractError('Uncommitted trial retained; no blind rerun')
        trial.mkdir(parents=True);repo=output/'repos'/item['id'];materialize(repo,item['case'])
        initial={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(repo.rglob('*'))if p.is_file()and not p.is_symlink()}
        atomic_json(trial/'started.json',{'at':time.time(),'item':item,'initial_repo_fingerprint':initial})
        print('START',item['id'],flush=True);started=time.monotonic();calls=[];status='incomplete';error=None
        try:
            with AppServerAdapter(m['model'],prepared=item['mode']=='goalpilot')as worker:
                if item['mode']=='direct':
                    prompt=f'''Complete this coding goal autonomously in the existing repository:
{m['goals'][item['case']]}
Follow all original README contracts and applicable repository instructions. Deliver the WHOLE
platform and its documented interactions, preserve original user data, resolve reversible ambiguities
yourself and run meaningful behavioral tests, including errors and end-to-end CLI/HTTP journeys.
You have approximately 900 seconds for the complete autonomous session. Finish with a factual handoff.
Use only this repository: do not read sibling trials, benchmark/evaluation source or reference
implementations, or copy another workspace's solution. No deployment, external services or credentials.
'''
                    result=worker.execute(prompt,repo,m['seconds_per_trial'],trial/'run/calls/1');calls=[{'strategy':'direct','result':result.to_dict()}];status='delivered'if result.returncode==0 else'incomplete'
                else:
                    # A budget/isolation instruction is part of the original goal for both arms.
                    goal=m['goals'][item['case']]+'\nUse only this repository; do not read sibling trials, benchmark/evaluation sources or reference implementations. No external services or credentials.'
                    state=run_finish(goal,repo,trial/'run',wall_seconds=m['seconds_per_trial'],max_calls=m['max_calls'],max_tokens=m['max_tokens_per_trial'],model=m['model'],adapter=worker,audit_policy='on-interruption',notify=lambda text:print(item['id'],text,flush=True));calls=state['calls'];status=state['status']
        except(ContractError,OSError,ValueError)as exc:
            error=f'{type(exc).__name__}: {exc}'
            for filename in('state.json','finish-run.json'):
                p=trial/'run'/filename
                if p.exists():saved=json.loads(p.read_text());calls=saved['calls'];status=saved['status'];break
        execution={'seconds':time.monotonic()-started,'calls':calls,'status':status,'error':error};atomic_json(trial/'execution.json',execution)
        return finalize(output,m,item,trial,execution)
