"""Bounded paired live evaluation. Frozen sources, no failed trial reruns."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from goalpilot.autopilot import run_autopilot
from goalpilot.finish import run_finish
from goalpilot.engine import atomic_json,lock,token_totals
from goalpilot.model import ContractError
from goalpilot.rpc import AppServerAdapter
from .cases import cases,materialize
from .judge import evaluate

ROOT=Path(__file__).resolve().parents[2]


def fingerprint():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('goalpilot','evaluation/finish') for p in sorted((ROOT/folder).glob('*.py'))}


def preflight():
    records=[]
    for case in cases():
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t)/'repo';materialize(case,repo)
            unfinished=evaluate(case,repo)
            assert not all(x['passed'] for x in unfinished)
            reference=(ROOT/'evaluation/finish'/('reference_'+case['name']+'.py')).read_text()
            (repo/case['entry']).write_text(reference)
            checks=evaluate(case,repo,7)
            assert all(x['passed'] for x in checks),checks
            if case['name']=='ledger':mutant=reference.replace('assert old==(key,src,dst,cents);return obj(old)','return obj(old)')
            else:mutant=reference.replace('assert current==new or base is not None and current==base','pass')
            assert mutant!=reference
            (repo/case['entry']).write_text(mutant)
            mutation=evaluate(case,repo,7)
            rejected=[x['id'] for x in mutation if not x['passed']]
            assert rejected
            records.append({'case':case['name'],'unfinished_failed':sum(not x['passed'] for x in unfinished),
                'reference_passed':len(checks),'semantic_mutation_rejected_by':rejected})
    return records


def create(output):
    output=Path(output).resolve()
    if output.exists():raise ContractError('Campaign already exists')
    checks=preflight();output.mkdir(parents=True)
    from goalpilot import __version__
    manifest={'product_version':__version__,'audit_policy':'on-interruption','version':1,'model':'gpt-6.1-sol','seconds':600,'max_calls':5,'max_tokens':1000000,
        'seeds':[0,7],'source_fingerprint':fingerprint(),'cases':cases(),'preflight':checks,
        'order':[{'id':'ledger-v2','case':'ledger','mode':'v2'}, {'id':'ledger-v3','case':'ledger','mode':'v3'},
                 {'id':'sync-v3','case':'sync','mode':'v3'}, {'id':'sync-v2','case':'sync','mode':'v2'}],
        'primary_rule':'Complete all 4 trials without infrastructure omissions on the same model. Improvement in delivery requires >=1 additional fully correct goal with no paired regression. All hidden groups on both seeds and normal final product status required. No tuning after seeing judgments. No statistical/general real-user claim from 2 projects.',
        'design':'Compare legacy v0.2.1 direct-first vs current production adaptive recovery. Stronger systematic auditing is optional outside this campaign. Same model, source repository and 600s full workflow ceiling. Same max5 calls and 1M observed soft token threshold. Audit overhead charged. Alternate order. Hidden judge and reference implementations never provided in prompts or repair feedback. No human inputs. All failures retained; no failed-trial reruns.',
        'limitations':['Two synthetic fresh CLI projects, not personal goals of hours.','Detailed original README makes vague user goals objectively judgeable.','Same model audits itself in separate contexts; correlated errors remain possible.','Tokens do not equal subscription quota.','One repetition per project; order/cache effects are not eliminated.']}
    atomic_json(output/'protocol.json',manifest)
    for name in manifest['source_fingerprint']:
        dest=output/'source_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return manifest


def run_next(output):
    output=Path(output).resolve();manifest=json.loads((output/'protocol.json').read_text())
    if fingerprint()!=manifest['source_fingerprint']:raise ContractError('Source changed after registration')
    with lock(output/'campaign.lock'):
        item=next((x for x in manifest['order'] if not (output/'trials'/x['id']/'record.json').exists()),None)
        if item is None:return None
        trial=output/'trials'/item['id']
        if trial.exists():raise ContractError('Uncommitted trial exists; do not silently rerun')
        trial.mkdir(parents=True)
        case=next(x for x in manifest['cases'] if x['name']==item['case'])
        repo=output/'repos'/item['id'];materialize(case,repo)
        atomic_json(trial/'started.json',{'at':time.time(),'item':item})
        start=time.monotonic();state=None;error=None;calls=[]
        try:
            with AppServerAdapter(manifest['model'],prepared=True) as worker:
                runner=run_autopilot if item['mode']=='v2' else run_finish
                state=runner(case['goal'],repo,trial/'run',wall_seconds=manifest['seconds'],
                    max_calls=manifest['max_calls'],max_tokens=manifest['max_tokens'],model=manifest['model'],
                    adapter=worker,notify=lambda x:print(item['id'],x,flush=True),
                    **({'audit_policy':manifest.get('audit_policy','always')} if item['mode']=='v3' else {}))
        except (ContractError,OSError,ValueError) as exc:error=f'{type(exc).__name__}: {exc}'
        seconds=time.monotonic()-start
        if state is None and (trial/'run/state.json').exists():state=json.loads((trial/'run/state.json').read_text())
        if state is not None:calls=state['calls']
        elif (trial/'run/finish-run.json').exists():calls=json.loads((trial/'run/finish-run.json').read_text())['calls']
        elif (trial/'run/bootstrap-result.json').exists():calls=[{'result':json.loads((trial/'run/bootstrap-result.json').read_text())}]
        status=state['status'] if state else 'incomplete'
        execution={'seconds':seconds,'status':status,'calls':calls,'error':error}
        atomic_json(trial/'execution.json',execution)
        judgments=[]
        for seed in manifest['seeds']:
            checks=evaluate(case,repo,seed);atomic_json(trial/f'judge-{seed}.json',checks)
            judgments.extend({**x,'seed':seed} for x in checks)
        record={**item,**execution,'judgments':judgments,'usage':token_totals(calls),
                'artifact_success':all(x['passed'] for x in judgments),
                'autonomous_success':all(x['passed'] for x in judgments) and status in ('scope_passed','completed'),
                'human_inputs':0,'fatal':any(x.get('result',{}).get('fatal') for x in calls)}
        atomic_json(trial/'record.json',record)
        return record


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('create','run'));p.add_argument('--output',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    if a.action=='create':
        m=create(a.output);print(json.dumps({'trials':len(m['order']),'preflight':m['preflight']}));return
    if not a.live:raise ContractError('--live required')
    while True:
        r=run_next(a.output)
        if r is None:break
        print(json.dumps({k:r[k] for k in ('id','status','seconds','autonomous_success','usage','error')},ensure_ascii=False),flush=True)
        if r['fatal']:break


if __name__=='__main__':main()
