"""Audit current Flowdesk/Stockroom /goal lifecycle, metering and identical inputs."""
import hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from goalpilot.rpc import normalize_usage
ROOT=Path(__file__).resolve().parents[1]


def audit(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text());assert m==json.loads((output/'preregistered-protocol.json').read_text())
    frozen=all(hashlib.sha256((output/'source_snapshot'/p).read_bytes()).hexdigest()==sha for p,sha in m['source_fingerprint'].items());current=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in m['source_fingerprint'].items())
    rows=[];calls=[];flags=[];counters={};kinds={};pairs=[];native=[]
    for item in m['order']:
        trial=output/'trials'/item['id'];path=trial/'record.json'
        if not path.exists():continue
        row=json.loads(path.read_text());rows.append(row);stored=json.loads((trial/'judgments.json').read_text());assert stored==row['judgments']
        assert len(stored)==26
        assert row['success']==(row['normal_exit']and all(j['passed']for j in stored))and row['human_inputs']==0
        for events in sorted((trial/'run/calls').glob('*/events.jsonl'),key=lambda p:int(p.parent.name)):
            values=[];started=[];finished=[];complete_events=[];persistent=None;client_forced_complete=False
            for line in events.read_text().splitlines():
                event=json.loads(line);packet=event['packet'];method=packet.get('method');p=packet.get('params',{})
                if method=='thread/tokenUsage/updated':values.append((p['threadId'],normalize_usage(p['tokenUsage']['total'])))
                if method=='turn/started':started.append(p['turn']['id'])
                if method=='turn/completed':finished.append({'id':p['turn']['id'],'status':p['turn']['status']})
                if method=='thread/goal/updated'and p['goal']['status']=='complete':complete_events.append(p['goal'])
                if event['direction']=='send'and method=='thread/start':persistent=p.get('ephemeral')is False
                if event['direction']=='send'and method=='thread/goal/set'and p.get('status')=='complete':client_forced_complete=True
                if method=='item/completed':
                    obj=p['item'];kind=obj.get('type','unknown');kinds[kind]=kinds.get(kind,0)+1
                    if any(w in kind.lower()for w in('collab','subagent')):flags.append({'id':item['id'],'reason':'Possible unmetered delegated agent','item_type':kind})
                    if kind=='commandExecution':
                        command=obj.get('command','')
                        if any(s in command for s in('evaluation/native_goals/','evaluation/ambitious/','reference_runforge','preregistered-protocol','source_snapshot')):flags.append({'id':item['id'],'reason':'Benchmark source marker in command; inspect','command':command[:1500]})
                        if re.search(r'\b(codex|claude|gemini|aider)\s+(exec|app-server|run|code)\b',command):flags.append({'id':item['id'],'reason':'Possible nested model invocation','command':command[:1500]})
            actual=None
            if values:
                thread,last=values[-1];before=counters.get(thread,dict.fromkeys(last,0));actual={k:last[k]-before[k]for k in last};counters[thread]=last
            result=row['calls'][int(events.parent.name)-1].get('result',{});usage=result.get('usage');model=(result.get('telemetry',{}).get('model')or{}).get('model')
            calls.append({'id':item['id'],'call':int(events.parent.name),'known_usage_matches_raw':usage==actual if usage is not None else None,'usage_complete':result.get('usage_complete'),'observed_model':model,'simulated':result.get('simulated'),'initiated_turns_from_raw':len(set(started)),'finished_turns_from_raw':len(finished)})
            if item['mode']=='native_goal':
                recorded=result['telemetry']['native_turns'];match=[{'id':t['id'],'status':t['status']}for t in recorded]==finished
                normal=row['normal_exit'];validnormal=not normal or bool(complete_events)and bool(finished)and finished[-1]['status']=='completed'and set(started)=={t['id']for t in finished}
                native.append({'id':item['id'],'persistent_thread':persistent,'client_never_forced_complete':not client_forced_complete,'server_started_turns':len(started),'completed_turn_records_match':match,'normal_completion_matches_lifecycle':validnormal,'genuine_goal_status_at_stop':(result['telemetry'].get('native_goal_at_stop')or{}).get('status')})
    for name in m['cases']:
        paths=[output/'trials'/(name+'-'+mode)/'started.json'for mode in('native_goal','goalpilot')]
        if all(p.exists()for p in paths):pairs.append({'case':name,'byte_identical':json.loads(paths[0].read_text())['initial_repo_fingerprint']==json.loads(paths[1].read_text())['initial_repo_fingerprint']})
    full=len(rows)==len(m['order']);integrity=full and frozen and current and len(pairs)==len(m['cases'])and all(p['byte_identical']for p in pairs)and not flags and all(c['known_usage_matches_raw']is not False and c['observed_model']==m['model']and not c['simulated']for c in calls)and len(native)==len(m['cases'])and all(v['persistent_thread']and v['client_never_forced_complete']and v['completed_turn_records_match']and v['normal_completion_matches_lifecycle']for v in native)
    result={'complete':full,'frozen_source_hashes_intact':frozen,'current_registered_sources_intact':current,'initial_pairs':pairs,'calls':calls,'native_lifecycle':native,'item_types':kinds,'possible_violations':flags,'quality_integrity_verified':bool(integrity),'all_usage_complete':all(c['usage_complete']for c in calls),'known_token_lower_bound':sum(r['usage']['total_tokens']for r in rows),'real_model_turns':sum(c['initiated_turns_from_raw']for c in calls),'limitation':'Known usage audited against raw cumulative counters. Command marker search is not exhaustive filesystem auditing. Native automatic turn counts are separate from its single client session. Partial usage never supports full token savings.'}
    atomic_json(output/'audit.json',result);print(json.dumps(result,indent=2));return result


if __name__=='__main__':audit(sys.argv[1])
