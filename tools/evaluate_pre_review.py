"""Retrospective, API-free diagnosis; never part of the primary comparison."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.ambitious.judge import evaluate
from goalpilot.engine import atomic_json


def run(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    ended=all((output/'trials'/x['id']/'record.json').exists()for x in m['order'])or(output/'futility-stop.json').exists()
    active=any((output/'trials'/x['id']/'started.json').exists()and not(output/'trials'/x['id']/'record.json').exists()for x in m['order'])
    assert ended and not active,'Wait until the primary campaign ends; no diagnostic feedback to live workers'
    base=output/'exploratory-pre-review';rows=[]
    for item in m['order']:
        if item['mode']!='goalpilot'or not(output/'trials'/item['id']/'record.json').exists():continue
        folder=base/item['id'];meta=folder/'snapshot.json';final=json.loads((output/'trials'/item['id']/'record.json').read_text())
        if not meta.exists():rows.append({'id':item['id'],'available':False});continue
        s=json.loads(meta.read_text());repo=folder/'repo';intact=all(hashlib.sha256((repo/p).read_bytes()).hexdigest()==sha for p,sha in s['files_sha256'].items())
        portable=not s['omitted']and not s['python_files_with_original_repo_literal']
        before=[]
        if intact and portable and s['copied_files_stable']:
            for seed in m['hidden_input_seeds']:
                p=folder/f'judge-before-{seed}.json'
                if p.exists():checks=json.loads(p.read_text())
                else:checks=evaluate(item['case'],repo,seed);atomic_json(p,checks)
                before.extend({**r,'seed':seed}for r in checks)
        statepath=output/'trials'/item['id']/'run/state.json';state=json.loads(statepath.read_text())if statepath.exists()else{}
        row={'id':item['id'],'available':bool(before),'snapshot_intact':intact,'portable_by_literal_check':portable,'copy_stable':s['copied_files_stable'],
        'before_all_groups_passed':all(r['passed']for r in before)if before else None,'before_failed_groups':sorted({r['id']for r in before if not r['passed']}),'before_groups_passed':sum(r['passed']for r in before),'before_groups_total':len(before),
        'final_artifact_success':final['artifact_success'],'final_success':final['success'],'normal_delivery':final['normal_exit'],
        'failed_generated_checks_before_repair':[c['id']for c in (state.get('verifications')or[{'checks':[]}])[0]['checks']if not c['passed']],
        'repair_calls':[c['strategy']for c in final['calls']if c['strategy']not in('build','audit','challenge','planning')]}
        rows.append(row)
    result={'interpretation':'Additional exploratory retrospective diagnostic, registered after the campaign began, before these judgments. These are copies of already observed code, not independent new trials, no API usage. No feedback supplied to live workers. Before/after differences describe this workflow and do not isolate a universal causal effect of the reviewer.','live_api_calls':0,'rows':rows}
    atomic_json(base/'report.json',result);print(json.dumps(result,indent=2));return result


if __name__=='__main__':run(sys.argv[1])
