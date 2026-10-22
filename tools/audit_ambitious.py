"""Audit raw metering, immutable inputs, judgment identity and session isolation markers."""
import hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from tools.audit_triple import audit as base_audit
ROOT=Path(__file__).resolve().parents[1]


def audit(output):
    output=Path(output).resolve();result=base_audit(output);m=json.loads((output/'protocol.json').read_text())
    warnings=[];delegates=[];judgments=[];models=[]
    expected={(seed,group)for seed in m['hidden_input_seeds']for group in m['groups']}
    for item in m['order']:
        trial=output/'trials'/item['id'];path=trial/'record.json'
        if not path.exists():continue
        row=json.loads(path.read_text());persisted=[]
        for seed in m['hidden_input_seeds']:persisted.extend({**j,'seed':seed}for j in json.loads((trial/f'judge-{seed}.json').read_text()))
        actual={(j['seed'],j['id'])for j in row['judgments']};normal=row['status']in('delivered','completed','scope_passed');artifact=all(j['passed']for j in persisted)
        judgments.append({'id':item['id'],'exact_frozen_group_seed_set':actual==expected and len(row['judgments'])==len(expected),'judgments_match_saved_runs':persisted==row['judgments'],'success_matches_full_delivery_rule':row['success']==(normal and artifact),'human_inputs':row['human_inputs']})
        for events in(trial/'run/calls').glob('*/events.jsonl'):
            for line in events.read_text().splitlines():
                packet=json.loads(line)['packet'];reply=packet.get('result')
                if isinstance(reply,dict)and 'thread'in reply and 'model'in reply:models.append({'id':item['id'],'call':events.parent.name,'observed_thread_model':reply['model']})
                if packet.get('method')!='item/completed':continue
                obj=packet['params']['item']
                if obj.get('type')!='commandExecution':continue
                command=obj.get('command','')
                if any(word in command for word in('evaluation/ambitious/','reference_flowdesk','reference_stockroom','reference_runforge','preregistered-protocol.json','source_snapshot')):warnings.append({'id':item['id'],'call':events.parent.name,'reason':'Benchmark/source marker in command; manual review required','command':command[:2000]})
                if any(other['id']!=item['id']and other['id']in command for other in m['order']):warnings.append({'id':item['id'],'call':events.parent.name,'reason':'Sibling trial marker in command; manual review required','command':command[:2000]})
                if re.search(r'\b(codex|claude|aider|gemini)\s+(exec|app-server|run|code)\b',command):delegates.append({'id':item['id'],'call':events.parent.name,'command':command[:2000]})
    intact_current=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in m['source_fingerprint'].items())
    metering=all(c['usage_present']and c['usage_complete']and c['raw_matches']for c in result['calls'])
    integrity=result['complete']and result['source_snapshot_intact']and intact_current and result['all_paired_initial_files_identical']and len(result['initial_pairs'])==len(m['order'])//2 and not result['possible_unmeasured_delegation']and not result['possible_hidden_source_commands']and not warnings and not delegates and all(j['exact_frozen_group_seed_set']and j['judgments_match_saved_runs']and j['success_matches_full_delivery_rule']and j['human_inputs']==0 for j in judgments)and models and all(v['observed_thread_model']==m['model']for v in models)
    result.update({'current_registered_sources_intact':intact_current,'all_calls_fully_metered_from_raw':metering,'judgment_integrity':judgments,'observed_thread_models':models,'possible_benchmark_reads':warnings,'possible_nested_model_commands':delegates,'quality_integrity_verified':bool(integrity),
       'limitation':'Command marker inspection is not an exhaustive filesystem access audit. No technical pilot in this campaign. Historical campaigns are kept separately. Partial usage prevents complete cost savings; quality eligibility is evaluated separately.'})
    atomic_json(output/'audit.json',result)
    print(json.dumps({k:result[k]for k in('complete','model_calls','quality_integrity_verified','all_calls_fully_metered_from_raw','possible_benchmark_reads','possible_nested_model_commands')}))
    return result


if __name__=='__main__':audit(sys.argv[1])
