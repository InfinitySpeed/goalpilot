"""One explicitly metered real Codex skill invocation; backend cache hit expected."""
import hashlib,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import atomic_json
from goalpilot.rpc import AppServerAdapter


def run(out):
    assert not out.exists(),'Never repeat this real caller trial';out.mkdir(parents=True)
    skill=Path.home()/'.agents/skills/goalpilot'
    cache=ROOT/'reports/reuse-current-001/caches/flowdesk'
    entryfile=next(cache.glob('*/entry.json'));entry=json.loads(entryfile.read_text())
    repo=out/'repo';shutil.copytree(entry['source_repo'],repo,ignore=shutil.ignore_patterns('__pycache__'))
    goalfile=out/'goal.txt';goalfile.write_bytes(entry['goal'].encode('utf-8'))
    dest=out/'engine-run';deny=out/'deny';deny.mkdir();marker=out/'backend-attempt.txt'
    stub=deny/'codex';stub.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("backend attempted")\nraise SystemExit(97)\n');stub.chmod(0o700)
    prompt=f'''$goalpilot
Use the explicitly selected GoalPilot skill to revalidate the already delivered coding goal.
Repository: {repo}
The EXACT original goal is in UTF-8 file {goalfile}; pass --goal-file instead of rewriting it.
Evidence directory: {dest}
Use cache {cache}, model {entry['model']}, --wall-seconds 900 --max-calls 6 --max-tokens 1500000.
This is a repeat verification, not a request to implement additional features. Do not edit repository files, inspect unrelated projects, or perform a separate planning/coding/test pass outside the controller.
For THIS local test only, prefix the controller command with PATH={deny}:$PATH so any cache miss cannot start a nested model. Do not run Codex or other model commands yourself.
Use one controller process and report its factual status, engine calls and counters. The parent conversation has a separate measured cost, so do not call the entire skill invocation free.
'''
    protocol={'at':time.time(),'planned_real_caller_turns':1,'model':'gpt-6.1-sol','effort':'low','wall_seconds':120,'raw_interrupt_threshold':150000,
              'skill':str(skill/'SKILL.md'),'skill_sha256':hashlib.sha256((skill/'SKILL.md').read_bytes()).hexdigest(),
              'selection':'Native typed skill input plus $goalpilot text, not just direct launcher execution.',
              'caller_permissions':'Host-capable danger-full-access, within this task unrestricted environment; needed for localhost checks. No global permission config changes.',
              'backend_expected_calls':0,'goal_source':str(entryfile),'source_sha256':hashlib.sha256(entryfile.read_bytes()).hexdigest(),
              'meter':'Record complete parent model counters and engine counters separately; zero engine calls does NOT imply zero skill-conversation quota. No failed trial rerun.',
              'primary':'Outer completed turn AND actual engine-run scope_passed with no engine calls AND real launcher command observed. Caller usage must be complete; no total-free claim.'}
    atomic_json(out/'protocol.json',protocol);atomic_json(out/'preregistered-protocol.json',protocol)
    class Caller(AppServerAdapter):
        interrupt_sent=False
        def _request(self,method,params,deadline):
            if method=='thread/start':params={**params,'sandbox':'danger-full-access'}
            if method=='turn/start':params={**params,'input':[*params['input'],{'type':'skill','name':'goalpilot','path':str(skill/'SKILL.md')}]}
            return super()._request(method,params,deadline)
        def _receive(self,deadline):
            packet=super()._receive(deadline)
            if not self.interrupt_sent and self.total and self.active and self.turn_id and self.total['input_tokens']+self.total['output_tokens']>=150000:
                self.interrupt_sent=True;self.counter+=1
                self._send({'id':self.counter,'method':'turn/interrupt','params':{'threadId':self.thread_id,'turnId':self.turn_id}})
            return packet
    start=time.monotonic()
    with Caller('gpt-6.1-sol',prepared=False,effort='low')as caller:
        result=caller.execute(prompt,repo,120,out/'caller')
    elapsed=time.monotonic()-start
    atomic_json(out/'caller-result.json',result.to_dict())
    state=json.loads((dest/'state.json').read_text())if(dest/'state.json').exists()else None
    commands=[];typed=False
    for l in (out/'caller/events.jsonl').read_text().splitlines():
        e=json.loads(l);p=e['packet'];a=p.get('params',{})
        if e['direction']=='send'and p.get('method')=='turn/start':typed=any(i.get('type')=='skill'and i.get('name')=='goalpilot'for i in a['input'])
        if p.get('method')=='item/completed'and a.get('item',{}).get('type')=='commandExecution':commands.append(a['item'].get('command')or'')
    engine_calls=len(state['calls'])if state else None
    total=None
    if result.usage_complete and result.usage is not None and state and state['usage']['usage_complete']:
        total={k:result.usage[k]+state['usage'][k]for k in ('input_tokens','output_tokens','cached_input_tokens')}
        total['raw_tokens']=total['input_tokens']+total['output_tokens']
        total['uncached_plus_output']=total['raw_tokens']-total['cached_input_tokens']
    observed_launcher=any('scripts/goalpilot.py' in c and '--goal-file'in c for c in commands)
    analysis={'caller_returncode':result.returncode,'caller_seconds':elapsed,'caller_usage':result.usage,'caller_usage_complete':result.usage_complete,
              'engine_status':state['status']if state else None,'engine_calls':engine_calls,'engine_usage':state['usage']if state else None,
              'typed_skill_selected':typed,'launcher_command_observed':observed_launcher,'backend_attempted':marker.exists(),
              'known_combined_usage':total,'whole_skill_free':False,'success':bool(result.returncode==0 and result.usage_complete and state and state['status']=='scope_passed'and engine_calls==0 and typed and observed_launcher and not marker.exists()),
              'limits':'One real invoking model run on an already delivered known artifact, with host-capable caller. Not a new cold efficacy benchmark, nor a universal overhead or quota conversion. Root development conversation is separate and unmetered.'}
    atomic_json(out/'analysis.json',analysis);print(json.dumps(analysis,indent=2))


if __name__=='__main__':run(Path(sys.argv[1]).resolve())
