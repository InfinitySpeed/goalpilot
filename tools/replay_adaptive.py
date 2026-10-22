"""Offline regression using existing real outputs. No new efficacy evidence/API."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.adapters import AgentResult
from goalpilot.engine import atomic_json
from goalpilot.finish import run_finish

ROOT=Path(__file__).resolve().parents[1]


class Replay:
    simulated=True
    model=None
    def __init__(self,result=None):self.result=result;self.calls=0
    def execute(self,*args,**kwargs):
        self.calls+=1
        if self.result is None:raise AssertionError('Unnecessary audit requested on a checkable normal delivery')
        allowed=AgentResult.__dataclass_fields__
        r=AgentResult(**{k:v for k,v in self.result.items() if k in allowed});r.simulated=True
        return r


def main():
    output=ROOT/'reports/adaptive-replay-001'
    if output.exists():raise RuntimeError('Replay output already exists; do not overwrite evidence')
    output.mkdir();records=[]
    for name in ('ledger','sync','book'):
        if name=='book':
            source=ROOT/'reports/recovery-live-001';trial=source/'trials/v2';repo_source=source/'repos/v2'
            flow=json.loads((source/'trials/v31/run/finish-run.json').read_text())
            audit=flow['calls'][1]['result'];goal=flow['config']['goal']
        else:
            source=ROOT/'reports/finish-live-001';trial=source/'trials'/f'{name}-v2';repo_source=source/'repos'/f'{name}-v2'
            audit=None;goal=json.loads((trial/'run/mission.json').read_text())['goal']
        builder_result=json.loads((trial/'run/bootstrap-result.json').read_text())
        destination=output/name;repo=destination/'repo';shutil.copytree(repo_source,repo,symlinks=True)
        builder=Replay(builder_result);auditor=Replay(audit)
        state=run_finish(goal,repo,destination/'run',adapter=builder,auditor=auditor,audit_policy='on-interruption')
        assert state['status']=='scope_passed',(name,state['status'])
        assert auditor.calls==(1 if name=='book' else 0),(name,auditor.calls)
        row={'case':name,'status':state['status'],'simulated_replay':True,'live_api_calls':0,
             'replayed_builder_results':builder.calls,'replayed_audit_results':auditor.calls,
             'acceptance_origin':state['contract']['acceptance_origin'],
             'note':'Existing real outputs replayed against copied real artifacts; historical token counters are not new consumption. No provider latency, new generated code or fresh efficacy measurement.'}
        records.append(row)
    result={'kind':'offline_real_trace_regression','live_api_calls':0,'cases':records,
            'claim':'The final adaptive branch skips the auditor on the two existing normal traces and reaches audit after the interrupted trace. This is deterministic regression evidence, not a fresh live comparison.'}
    atomic_json(output/'report.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
