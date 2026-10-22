"""Audit frozen sources, initial equality and emitted usage without model calls."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from goalpilot.rpc import normalize_usage


def audit(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    sources_ok=all(hashlib.sha256((output/'source_snapshot'/p).read_bytes()).hexdigest()==sha for p,sha in m['source_fingerprint'].items())
    assert m==json.loads((output/'preregistered-protocol.json').read_text())
    initial=[];findings=[];warnings=[];counters={};records=[];delegations=[];item_types={}
    for item in m['order']:
        trial=output/'trials'/item['id'];record_path=trial/'record.json'
        if not record_path.exists():continue
        record=json.loads(record_path.read_text());records.append(record)
        for path in sorted((trial/'run/calls').glob('*/events.jsonl'),key=lambda p:int(p.parent.name)):
            snapshots=[];commands=[];model=None
            for line in path.open():
                event=json.loads(line);packet=event['packet']
                if packet.get('method')=='thread/tokenUsage/updated':snapshots.append((packet['params']['threadId'],normalize_usage(packet['params']['tokenUsage']['total'])))
                if packet.get('method')=='item/completed':
                    item_type=packet['params']['item'].get('type','unknown');item_types[item_type]=item_types.get(item_type,0)+1
                    if any(word in item_type.lower()for word in ('collab','subagent')):delegations.append({'id':item['id'],'call':path.parent.name,'type':item_type})
                    if item_type=='commandExecution':commands.append(packet['params']['item'].get('command',''))
            actual=None
            if snapshots:
                thread,last=snapshots[-1];base=counters.get(thread,dict.fromkeys(last,0));actual={k:last[k]-base[k]for k in last};counters[thread]=last
            index=int(path.parent.name)-1;result=record['calls'][index].get('result',{});usage=result.get('usage')
            metadata=(result.get('telemetry')or{}).get('model')or{}
            findings.append({'id':item['id'],'call':index+1,'strategy':record['calls'][index]['strategy'],
                'usage_present':usage is not None,'usage_complete':result.get('usage_complete'),'raw_matches':usage==actual if usage is not None else None,
                'model':metadata})
            for command in commands:
                if any(marker in command for marker in ('evaluation/triple/','evaluation/integrated/','reference_daybook','reference_tablekit','reference_resolver','preregistered-protocol.json')):
                    warnings.append({'id':item['id'],'call':index+1,'marker':'Possible benchmark source path in command; inspect raw trace before a positive claim'})
    for name in m['cases']:
        for repeat in range(m['repeats']):
            paths=[output/'trials'/f'{name}-{mode}-{repeat+1}'/'started.json'for mode in ('direct','goalpilot')]
            if all(p.exists()for p in paths):initial.append({'case':name,'repeat':repeat,'byte_identical_initial_files':json.loads(paths[0].read_text())['initial_repo_fingerprint']==json.loads(paths[1].read_text())['initial_repo_fingerprint']})
    result={'complete':len(records)==len(m['order']),'source_snapshot_intact':sources_ok,'all_known_usage_matches_raw':all(x['raw_matches']is not False for x in findings),
        'all_paired_initial_files_identical':all(x['byte_identical_initial_files']for x in initial),'initial_pairs':initial,
        'model_calls':len(findings),'item_types':item_types,'possible_unmeasured_delegation':delegations,'calls':findings,'possible_hidden_source_commands':warnings,
        'known_token_lower_bound':sum(r['usage']['total_tokens']for r in records),
        'limitation':'Command markers are not an exhaustive filesystem access audit. Missing/partial usage remains incomplete. Technical pilot excluded from the primary comparison and retained separately.'}
    atomic_json(output/'audit.json',result)
    print(json.dumps({k:result[k]for k in ('complete','source_snapshot_intact','all_known_usage_matches_raw','all_paired_initial_files_identical','model_calls','known_token_lower_bound','possible_hidden_source_commands')},indent=2))
    return result


if __name__=='__main__':audit(sys.argv[1])
