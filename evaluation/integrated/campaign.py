"""Predeclared bounded scaling extension; does not replace the failed first study."""
import hashlib,json,random,shutil,time
from pathlib import Path
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.finish import run_finish
from goalpilot.model import ContractError
from goalpilot.rpc import AppServerAdapter
from evaluation.triple.report import calculate
from .case import materialize
from .spec import GOAL,SPEC
from .judge import evaluate
from .preflight import run as preflight
ROOT=Path(__file__).resolve().parents[2]


def fingerprint():return{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for folder in ('goalpilot','evaluation/triple','evaluation/integrated')for p in sorted((ROOT/folder).glob('*.py'))}


def create(output):
    output=Path(output).resolve()
    if output.exists():raise ContractError('Output exists')
    validation=json.loads((ROOT/'reports/tests.json').read_text());source=fingerprint()
    if not validation['successful']or any(validation['source_fingerprint'].get(p)!=sha for p,sha in source.items()if p.startswith('goalpilot/')):raise ContractError('Current product must pass offline validation')
    earlier=json.loads((ROOT/'reports/triple-live-002/protocol.json').read_text())
    assert all(earlier['source_fingerprint'][p]==sha for p,sha in source.items()if p.startswith('goalpilot/'))
    checks=preflight();modes=['direct','goalpilot'];random.Random(51687).shuffle(modes)
    m={'model':'gpt-6.1-sol','seconds_per_trial':600,'max_calls':5,'max_tokens_per_trial':1000000,'observed_campaign_token_cap':1000000,
       'cases':['integrated'],'repeats':1,'order':[{'id':f'integrated-{mode}-1','case':'integrated','mode':mode,'repeat':0}for mode in modes],
       'resource_threshold_percent':15,'goal':GOAL,'public_contract':SPEC,'hidden_input_seeds':[62537,109891],
       'source_fingerprint':source,'same_product_source_as_first_study':True,'offline_tests_passed':validation['passed'],'preflight':checks,
       'primary_rule':'A complete two-trial matched pair, same observed model and complete usage. GoalPilot must deliver 1/1 while direct fails 0/1, and use at least 15% less absolute full workflow time, reported input+output tokens AND uncached input+output tokens. No retries/replacements. Costs of failures retained; denominator-zero normalized costs not invented.',
       'secondary_exploratory_rule':'Before these new outcomes, declare a pooled descriptive summary of the earlier 12 trials plus this integrated pair, same unchanged product. At least one additional delivered goal, no paired regressions and >=15% less seconds, raw tokens and uncached tokens per delivered goal, with all failure costs. Earlier study remains a failure of its own primary criterion; pooling is exploratory, not an independently held-out confirmation.',
       'design':'One larger coding goal combines the three previously evaluated components with a new persistent cross-component workflow, atomic batches, migrations, optimistic revisions, concurrent idempotence and JSON/CSV exports. Both see identical seeded files and public contracts. Product is unchanged from the first study. No process/turn interruption is injected. Hidden application tests include ordinary validation, concurrency and SQLite-trigger storage errors to verify transaction rollback. Hidden judgments never inform repair. Fixed-seed randomized arm order. Every model call/local verification counted.',
       'limitations':['One integrated task, not a sample of multi-hour personal goals.','Component code/tasks were already used; only integration and larger joint mission are new.','Extension registered after the independent-library study failed its joint criterion; never replace/relabel that result.','Single pair cannot eliminate model, cache and order variability or prove population performance.','Token cap is soft, observed between whole trials; any partial usage prevents full cost claims.']}
    output.mkdir(parents=True);atomic_json(output/'protocol.json',m);atomic_json(output/'preregistered-protocol.json',m)
    for name in source:
        p=output/'source_snapshot'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    return m


def finish(output,m,item,trial,execution):
    judgments=[]
    for seed in m['hidden_input_seeds']:
        path=trial/f'judge-{seed}.json'
        if path.exists():checks=json.loads(path.read_text())
        else:checks=evaluate(output/'repos'/item['id'],seed);atomic_json(path,checks)
        judgments.extend({**x,'seed':seed}for x in checks)
    calls=execution['calls'];artifact=all(x['passed']for x in judgments);normal=execution['status']in('delivered','completed','scope_passed')
    models=sorted({v for c in calls if(v:=((c.get('result',{}).get('telemetry')or{}).get('model')or{}).get('model'))})
    row={**item,**execution,'judgments':judgments,'usage':token_totals(calls),'models':models,'artifact_success':artifact,'normal_exit':normal,'success':normal and artifact,
       'fatal':any(c.get('result',{}).get('fatal')for c in calls),'infrastructure_interruption':False,'human_inputs':0}
    atomic_json(trial/'record.json',row);return row


def run_next(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    if m!=json.loads((output/'preregistered-protocol.json').read_text())or fingerprint()!=m['source_fingerprint']:raise ContractError('Frozen sources/protocol changed')
    with lock(output/'campaign.lock'):
        done=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
        if any(r['fatal']for r in done)or sum(r['usage']['total_tokens']for r in done)>=m['observed_campaign_token_cap']:return None
        item=next((x for x in m['order']if x['id']not in{r['id']for r in done}),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if(trial/'execution.json').exists():return finish(output,m,item,trial,json.loads((trial/'execution.json').read_text()))
        if trial.exists():raise ContractError('Uncommitted trial; never blindly rerun')
        trial.mkdir(parents=True);repo=output/'repos'/item['id'];materialize(repo)
        initial={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(repo.rglob('*'))if p.is_file()and not p.is_symlink()}
        atomic_json(trial/'started.json',{'item':item,'at':time.time(),'initial_repo_fingerprint':initial})
        start=time.monotonic();calls=[];status='incomplete';error=None
        try:
            with AppServerAdapter(m['model'],prepared=item['mode']=='goalpilot')as worker:
                if item['mode']=='direct':
                    prompt=f'''Complete this coding goal autonomously in the existing repository:
{m['goal']}
Follow all original public README contracts and repository instructions. Finish the WHOLE platform,
including each documented component and their integration, preserving user data. Resolve reversible
ambiguities yourself. Run meaningful behavioral tests, including errors and cross-component paths.
Use only this repository's implementation, do not copy another workspace's completed solution.
Finish with a concise factual handoff. No network, external services, deployment or credentials.
'''
                    result=worker.execute(prompt,repo,m['seconds_per_trial'],trial/'run/calls/1');calls=[{'strategy':'direct','result':result.to_dict()}];status='delivered'if result.returncode==0 else'incomplete'
                else:
                    state=run_finish(m['goal'],repo,trial/'run',wall_seconds=m['seconds_per_trial'],max_calls=m['max_calls'],
                       max_tokens=m['max_tokens_per_trial'],model=m['model'],adapter=worker,audit_policy='on-interruption',notify=lambda s:print(item['id'],s,flush=True))
                    calls=state['calls'];status=state['status']
        except(ContractError,OSError,ValueError)as exc:
            error=f'{type(exc).__name__}: {exc}'
            for filename in ('state.json','finish-run.json'):
                path=trial/'run'/filename
                if path.exists():saved=json.loads(path.read_text());calls=saved['calls'];status=saved['status'];break
        execution={'seconds':time.monotonic()-start,'status':status,'calls':calls,'error':error};atomic_json(trial/'execution.json',execution)
        return finish(output,m,item,trial,execution)
