"""One fresh task under a preregistered early-turn timeout; conditional evidence."""
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
from .case import GOAL,README,materialize
from .judge import evaluate

ROOT=Path(__file__).resolve().parents[2]


def fingerprint():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('goalpilot','evaluation/recovery') for p in sorted((ROOT/folder).glob('*.py'))}


def preflight():
    with tempfile.TemporaryDirectory() as t:
        repo=Path(t)/'repo';materialize(repo)
        unfinished=evaluate(repo)
        reference=(ROOT/'evaluation/recovery/reference.py').read_text();(repo/'book.py').write_text(reference)
        good=evaluate(repo);assert all(x['passed'] for x in good),good
        (repo/'book.py').write_text(reference.replace("status='active' and start<? and end>?","status='impossible' and start<? and end>?"))
        bad=evaluate(repo);assert not all(x['passed'] for x in bad)
        return {'unfinished_failed':sum(not x['passed'] for x in unfinished),'reference_passed':len(good),'semantic_mutant_rejected_by':[x['id'] for x in bad if not x['passed']]}


class FirstCut:
    simulated=False
    def __init__(self,worker,seconds):self.worker=worker;self.seconds=seconds;self.calls=0;self.fault_triggered=False;self.model=worker.model
    def execute(self,prompt,repo,timeout,log_dir,**kwargs):
        self.calls+=1
        cut=self.calls==1
        result=self.worker.execute(prompt,repo,min(timeout,self.seconds) if cut else timeout,log_dir,**kwargs)
        if cut:self.fault_triggered=result.timed_out
        result.telemetry=result.telemetry or {}
        result.telemetry['controlled_first_turn_cutoff_seconds']=self.seconds if cut else None
        return result


def create(output):
    from goalpilot import __version__
    output=Path(output).resolve()
    if output.exists():raise ContractError('Campaign exists')
    checks=preflight();output.mkdir(parents=True)
    m={'audit_policy':'on-interruption','source_version':__version__,'model':'gpt-6.1-sol','seconds':600,'cutoff_seconds':45,'max_calls':5,'max_tokens':1000000,
       'goal':GOAL,'readme':README,'source_fingerprint':fingerprint(),'preflight':checks,'order':['v2','v31'],
       'primary_rule':'Complete both trials without provider/worker infrastructure failures on the same configured model. Both must actually time out on the first implementation turn at 45 seconds. Conditional recovery advantage requires new normal final status plus all 7 hidden groups passing, and baseline failure. No failed trial reruns, no tuning after hidden judgments.',
       'design':'A fresh room-booking CLI with legacy data. Same initial files, model and full 600-second workflow budget, max5 calls, 1M soft tokens. First builder turn is interrupted at 45s via actual app-server interrupt in both versions; all code, observed usage and elapsed time are retained. v2 receives its normal production JSON-delivery prompt; v31 its normal production finish flow. The independent auditor is not interrupted. Hidden tests never drive repairs. No human inputs.',
       'limitations':['One synthetic goal and one injected early timeout; not a sampled frequency of real agent stalls.','Demonstrates recovery under a controlled failure, not a general success-rate or subscription-quota gain.','One order and no repeats; cache/cost effects not controlled enough for savings claims.','Interrupted turns may have missing or partial usage; report known lower bounds.']}
    atomic_json(output/'protocol.json',m)
    for name in m['source_fingerprint']:
        dest=output/'source_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    return m


def run_next(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    if fingerprint()!=m['source_fingerprint']:raise ContractError('Frozen source changed')
    with lock(output/'campaign.lock'):
        mode=next((x for x in m['order'] if not (output/'trials'/x/'record.json').exists()),None)
        if mode is None:return None
        trial=output/'trials'/mode
        if trial.exists():raise ContractError('Uncommitted trial exists; no blind rerun')
        trial.mkdir(parents=True);repo=output/'repos'/mode;materialize(repo)
        atomic_json(trial/'started.json',{'at':time.time(),'mode':mode})
        start=time.monotonic();state=None;error=None;calls=[]
        with AppServerAdapter(m['model'],prepared=True) as base:
            worker=FirstCut(base,m['cutoff_seconds'])
            try:
                runner=run_autopilot if mode=='v2' else run_finish
                state=runner(m['goal'],repo,trial/'run',wall_seconds=m['seconds'],max_calls=m['max_calls'],
                    max_tokens=m['max_tokens'],model=m['model'],adapter=worker,
                    notify=lambda x:print(mode,x,flush=True),
                    **({'audit_policy':m.get('audit_policy','always')} if mode!='v2' else {}))
            except (ContractError,OSError,ValueError) as exc:error=f'{type(exc).__name__}: {exc}'
        seconds=time.monotonic()-start
        if state is None and (trial/'run/state.json').exists():state=json.loads((trial/'run/state.json').read_text())
        if state:calls=state['calls']
        elif (trial/'run/finish-run.json').exists():calls=json.loads((trial/'run/finish-run.json').read_text())['calls']
        elif (trial/'run/bootstrap-result.json').exists():calls=[{'result':json.loads((trial/'run/bootstrap-result.json').read_text())}]
        status=state['status'] if state else 'incomplete'
        execution={'mode':mode,'status':status,'seconds':seconds,'fault_triggered':worker.fault_triggered,'calls':calls,'error':error}
        atomic_json(trial/'execution.json',execution)
        checks=evaluate(repo);atomic_json(trial/'judge.json',checks)
        record={**execution,'checks':checks,'usage':token_totals(calls),'artifact_success':all(x['passed'] for x in checks),
                'autonomous_success':all(x['passed'] for x in checks) and status in ('completed','scope_passed'),
                'human_inputs':0,'fatal':any(x.get('result',{}).get('fatal') for x in calls)}
        atomic_json(trial/'record.json',record)
        return record


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('create','run'));p.add_argument('--output',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    if a.action=='create':m=create(a.output);print(json.dumps({'version':m['source_version'],'preflight':m['preflight']}));return
    if not a.live:raise ContractError('--live required')
    while True:
        r=run_next(a.output)
        if r is None:break
        print(json.dumps({k:r[k] for k in ('mode','status','seconds','fault_triggered','autonomous_success','usage','error')}),flush=True)
        if r['fatal']:break


if __name__=='__main__':main()
