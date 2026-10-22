"""Frozen matched version comparison. No grader feedback enters either workflow."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def create(output):
    sys.path.insert(0,str(ROOT))
    from evaluation.ambitious.specs import GOALS,SPECS
    from goalpilot import __version__
    from evaluation.ambitious.preflight import run
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    assert ci['successful'] and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ci['source_fingerprint'].items())
    assert not output.exists();output.mkdir(parents=True)
    for mode,origin in [('baseline',Path('/workspace/goalpilot-baseline')),('candidate',ROOT)]:
        dest=output/'source_snapshot'/mode
        shutil.copytree(origin/'goalpilot',dest/'goalpilot',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'evaluation/ambitious',dest/'evaluation/ambitious',ignore=shutil.ignore_patterns('__pycache__'))
        (dest/'evaluation/__init__.py').write_text('')
        shutil.copytree(origin/'tests',dest/'tests',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'examples',dest/'examples',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(origin/'validate.py',dest/'validate.py')
        shutil.copy2(origin/'pyproject.toml',dest/'pyproject.toml')
        shutil.copy2(__file__,dest/'worker.py')
    m={'registered_at':time.time(),'model':'gpt-6.1-sol','versions':{'baseline':'0.5.2','candidate':__version__},
       'cases':['flowdesk','stockroom'],'goals':{k:GOALS[k]for k in ('flowdesk','stockroom')},
       'public_contracts':{k:SPECS[k]for k in ('flowdesk','stockroom')},
       'order':[{'case':c,'mode':mode,'id':c+'-'+mode}for c,modes in [('flowdesk',['baseline','candidate']),('stockroom',['candidate','baseline'])]for mode in modes],
       'seconds_per_trial':900,'max_calls':6,'max_tokens_per_trial':1500000,'observed_campaign_token_cap':6000000,
       'primary_rule':'All four planned executions; candidate fully correct AND normally concluded on both scopes; zero paired closure or artifact regressions. Significant efficiency target is >=20% less aggregate measured wall time AND >=20% less raw input+output AND >=20% less uncached-input+output. Report each threshold separately; no composite win if any misses. No population inference from two cases.',
       'definitions':{'normal':'scope_passed or completed from actual local verification','correct':'all 26 original independent groups pass (13 groups on each of two fixed seeds)','tokens':'raw=input+output; uncached=input-cached+output; not exact subscription quota or money','time':'full workflow elapsed, including model setup, review, recovery and local verification; independent research judge excluded equally'},
       'design':'Same model, initial files, original public interfaces, full900s shared wall/call/token budgets; alternating order; no artificial interruption or human steering. Candidate generates two compact independent immutable public-behavior acceptance programs before coding, supplies their full text, reuses infrastructure, avoids duplicate broad test frameworks, and checks/repairs harness plumbing before freezing. All review, plumbing repair and code repair calls are metered. Baseline audits after coding. Hidden independent judge never feeds either. No native /goal control in this incremental comparison.',
       'novelty':'These are familiar synthetic platform benchmarks exposed in previous experiments, with fresh independent model executions and fresh worktrees. They are not held-out personal goals. Both domain contracts and the judge are unchanged; known Runforge empty-graph erratum is not relevant to these two domains.',
       'stopping':'Never repeat a failed trial or tune code/protocol during campaign. Stop after a whole-trial incomplete usage meter (exact resource target then untestable), a paired closure/artifact regression (original planned denominator stays4), fatal provider/infrastructure failure, or observed whole-trial campaign token cap. Retain partials as lower bounds, never claim complete token savings from incomplete usage.',
       'offline_validation':ci,'preflight':run(),'source_fingerprints':{mode:hashes(output/'source_snapshot'/mode)for mode in ('baseline','candidate')}}
    write(output/'protocol.json',m);write(output/'preregistered-protocol.json',m)
    return m


def worker(output,ident,source):
    sys.path.insert(0,str(source))
    from goalpilot.finish import run_finish
    from goalpilot.engine import token_totals
    from goalpilot.model import ContractError
    from evaluation.ambitious.cases import materialize
    from evaluation.ambitious.judge import evaluate
    m=json.loads((output/'protocol.json').read_text());item=next(i for i in m['order']if i['id']==ident)
    assert hashes(source)==m['source_fingerprints'][item['mode']]
    trial=output/'trials'/ident;assert not trial.exists();trial.mkdir(parents=True)
    repo=output/'repos'/ident;materialize(repo,item['case'])
    write(trial/'started.json',{'at':time.time(),'initial_repo_fingerprint':hashes(repo)})
    goal=m['goals'][item['case']]+'''\nFollow all original README contracts, finish every workflow, preserve data, resolve reversible ambiguities autonomously. No human steering, external services, deployment or credentials. Work only in this repository; do not read benchmark/evaluation sources, references, sibling trials or protocol. Do not launch other agents/model sessions or nested Codex commands. Give a factual handoff.'''
    limits=m.get('case_limits',{}).get(item['case'],{})
    start=time.monotonic();error=None;status='incomplete';calls=[]
    try:
        state=run_finish(goal,repo,trial/'run',wall_seconds=limits.get('seconds_per_trial',m['seconds_per_trial']),max_calls=limits.get('max_calls',m['max_calls']),max_tokens=m['max_tokens_per_trial'],model=m['model'],audit_policy='on-interruption',notify=lambda s:print(ident,s,flush=True))
        calls=state['calls'];status=state['status']
    except(ContractError,OSError,ValueError)as exc:
        error=f'{type(exc).__name__}: {exc}'
        for name in ('state.json','finish-run.json'):
            p=trial/'run'/name
            if p.exists():data=json.loads(p.read_text());calls=data['calls'];status=data['status'];break
    execution={'seconds':time.monotonic()-start,'status':status,'calls':calls,'error':error}
    write(trial/'execution.json',execution)
    checks=[]
    for seed in (90173,470117):checks.extend(evaluate(item['case'],repo,seed))
    write(trial/'judgments.json',checks)
    row={**item,**execution,'normal_exit':status in ('scope_passed','completed'),'artifact_success':len(checks)==26 and all(c['passed']for c in checks),'judgments':checks,'usage':token_totals(calls),'human_inputs':0,'fatal':any(c.get('result',{}).get('fatal')for c in calls)}
    row['success']=row['normal_exit']and row['artifact_success'];write(trial/'record.json',row)
    print('RESULT',json.dumps({k:row[k]for k in ('id','seconds','status','artifact_success','success','usage')}),flush=True)


def run(output):
    m=json.loads((output/'protocol.json').read_text());assert m==json.loads((output/'preregistered-protocol.json').read_text())
    for item in m['order']:
        rows=[json.loads(p.read_text())for p in (output/'trials').glob('*/record.json')]if (output/'trials').exists()else[]
        if any(not r['usage']['usage_complete']for r in rows):
            write(output/'stopped.json',{'reason':'Preregistered incomplete usage futility rule','completed':len(rows),'planned':4});return
        if any(r['fatal']for r in rows)or sum(r['usage']['total_tokens']for r in rows)>=m['observed_campaign_token_cap']:break
        for case in m['cases']:
            pair={r['mode']:r for r in rows if r['case']==case}
            if len(pair)==2 and (pair['baseline']['success']and not pair['candidate']['success']or pair['baseline']['artifact_success']and not pair['candidate']['artifact_success']):
                write(output/'stopped.json',{'reason':'Preregistered paired regression','completed':len(rows),'planned':4});return
        if any(r['id']==item['id']for r in rows):continue
        source=output/'source_snapshot'/item['mode'];assert hashes(source)==m['source_fingerprints'][item['mode']]
        subprocess.run([sys.executable,str(source/'worker.py'),'worker',str(output),item['id'],str(source)],check=True,cwd=source)


if __name__=='__main__':
    action=sys.argv[1];output=Path(sys.argv[2]).resolve()
    if action=='create':create(output)
    elif action=='run':run(output)
    elif action=='worker':worker(output,sys.argv[3],Path(sys.argv[4]))
    else:raise SystemExit('Unknown action')
