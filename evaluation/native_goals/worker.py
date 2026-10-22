"""A larger, executable automation goal, sharing the previously unrun Runforge core."""
from pathlib import Path
import json
from evaluation.ambitious.specs import RUN
SPEC=RUN+'''\n## Executable node tasks, preserved across revisions
Complete the platform with an actual bounded worker, not only manual claim/finish APIs.
Every node optionally has task, a JSON object. Default is {"op":"emit","value":null}.
Normalize/retain task in workflow.get/start and EVERY run snapshot (including run.get/list).
Each run freezes its own tasks when launched; later workflow revisions must not change them.
Allowed tasks: emit (optional value, any JSON-like value), sum (sum integer results of all needs,
excluding bool), join (join string dependency results by optional string separator, default ''),
collect (object mapping dependency IDs to their JSON results), artifact (required nonempty name
and string content; attach it to this node using existing SHA256/artifact rules), fail (optional
nonempty message, default 'Task failed'). Dependency iteration uses sorted need IDs.
Reject an invalid task/op/type when defining the workflow, atomically preserving its revision.
Runtime bad dependency result types are execution failures and use the normal retry policy.

## Bounded real worker execution
`worker.tick` takes worker,now, optional lease(default30),limit(default20, integer1..100).
It performs up to limit actual claim-and-execute-and-finish jobs, following existing deterministic
claim ordering and lease/retry/dependency rules. Stop early when no job is currently eligible.
Return a list in execution order of {run,node,attempt,status} where status is succeeded/retry/failed,
plus result for success or error for failure. Do not return a live receipt. emit returns value,
sum/join/collect the computed result, artifact returns {digest,size}. Each execution uses that
run's frozen task. Runtime task failures never abort the whole tick or suppress unrelated branches.
A delay0 failing task can be retried in the same tick, but limit bounds total attempts; positive
delay waits for a later now. All resulting state is durable after the tick returns.

## Full automation journeys and concurrent workers
Expose worker.tick through the same HTTP/JSONL interfaces. A user must be able to define a graph,
launch it, run one or several ticks, fetch final results/artifacts, back up and restore, then continue
without reexecuting succeeded nodes. Two independent worker processes must not execute a job twice.
Cancelled/failed/succeeded runs never acquire new jobs. A task may execute only after all its needs
succeed. Claims made by the manual API and not expired retain their ownership; worker.tick must not
steal them. Correctly handle empty eligibility windows, expired leases and independent branches.
'''

WORKER_IMPL='''
import json

def _task(value):
    if not isinstance(value,dict):raise ValueError('Task must be an object')
    op=value.get('op')
    if op=='emit':
        payload=copy.deepcopy(value.get('value'));json.dumps(payload,allow_nan=False);return {'op':op,'value':payload}
    if op in('sum','collect'):return {'op':op}
    if op=='join':
        separator=value.get('separator','')
        if not isinstance(separator,str):raise ValueError('Join separator must be text')
        return {'op':op,'separator':separator}
    if op=='artifact':
        name=ident(value.get('name'));content=value.get('content')
        if not isinstance(content,str):raise ValueError('Artifact content must be text')
        return {'op':op,'name':name,'content':content}
    if op=='fail':return {'op':op,'message':ident(value.get('message','Task failed'))}
    raise ValueError('Unknown task')

_base_handle=handle
def handle(s,op,d):
    if op!='worker.tick':return _base_handle(s,op,d)
    worker=ident(d.get('worker'));now=number(d.get('now'));lease=number(d.get('lease',30),1);limit=number(d.get('limit',20),1,100);out=[]
    for _ in range(limit):
        job=_base_handle(s,'job.claim',{'worker':worker,'now':now,'lease':lease})
        if job is None:break
        r=s['runs'][job['run']];n=r['nodes'][job['node']];task=n['task'];args={'run':job['run'],'node':job['node'],'receipt':job['receipt'],'now':now}
        try:
            values={dep:copy.deepcopy(r['nodes'][dep]['result'])for dep in sorted(n['needs'])};kind=task['op']
            if kind=='emit':result=copy.deepcopy(task['value'])
            elif kind=='sum':
                if any(type(v)is not int for v in values.values()):raise ValueError('sum needs integer results')
                result=sum(values.values())
            elif kind=='join':
                if any(not isinstance(v,str)for v in values.values()):raise ValueError('join needs string results')
                result=task['separator'].join(values.values())
            elif kind=='collect':result=values
            elif kind=='artifact':result=_base_handle(s,'artifact.put',{**args,'name':task['name'],'content':task['content']})
            else:raise ValueError(task['message'])
            _base_handle(s,'job.succeed',{**args,'result':result});out.append({'run':job['run'],'node':job['node'],'attempt':job['attempt'],'status':'succeeded','result':result})
        except ValueError as exc:
            error=str(exc)or'Task failed';_base_handle(s,'job.fail',{**args,'error':error});out.append({'run':job['run'],'node':job['node'],'attempt':job['attempt'],'status':'retry'if n['status']=='ready'else'failed','error':error})
    return out
'''


def reference():
    text=Path(__file__).parents[1].joinpath('ambitious/reference_runforge.py').read_text()
    text=text.replace("'retry_delay':number(row.get('retry_delay',0))}","'retry_delay':number(row.get('retry_delay',0)),'task':_task(row.get('task',{'op':'emit','value':None}))}")
    text=text.replace("('id','status','attempt','not_before')","('id','status','attempt','not_before','task')")
    return text+WORKER_IMPL
