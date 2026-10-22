"""Oracle erratum: remove only an undocumented empty-graph rejection assertion.

Never changes model inputs or original source/judgments. Corrected automation
analysis is registered before either automation trial starts; core is retrospective.
"""
import ast,copy,hashlib,json,random,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT)not in sys.path:sys.path.append(str(ROOT))
from goalpilot.engine import atomic_json


def check(output,repo,seed):
    output=Path(output).resolve();repo=Path(repo).resolve();m=json.loads((output/'protocol.json').read_text());rel='evaluation/ambitious/check_runforge.py';source=output/'source_snapshot'/rel;raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==m['source_fingerprint'][rel]
    tree=ast.parse(raw);removed=0
    for node in ast.walk(tree):
        if isinstance(node,ast.For)and isinstance(node.target,ast.Name)and node.target.id=='nodes'and isinstance(node.iter,ast.Tuple):
            filtered=[x for x in node.iter.elts if not(isinstance(x,ast.List)and not x.elts)];removed+=len(node.iter.elts)-len(filtered);node.iter.elts=filtered
    assert removed==1,'Only the single unsupported empty-graph case may be removed'
    namespace={};exec(compile(ast.fix_missing_locations(tree),str(source),'exec'),namespace)
    sys.path.insert(0,str(repo));from app import Service
    from evaluation.ambitious.judge import raises
    with tempfile.TemporaryDirectory()as t:namespace['check'](Service(Path(t)/'db'),'validation',random.Random(seed),raises,repo)


def evaluate(output,repo,seed):
    from goalpilot.process import run_process
    r=run_process([sys.executable,str(Path(__file__).resolve()),'check',str(output),str(repo),str(seed)],ROOT,30)
    try:value=json.loads(r.output.splitlines()[-1])
    except(ValueError,IndexError):value={'passed':False,'error':r.output[-3000:]}
    return {'id':'validation',**value,'seed':seed,'judge_seconds':r.duration_seconds,'erratum':'Only undocumented empty-graph rejection assertion removed; all other frozen validation/property logic identical.'}


def summarize(output):
    from evaluation.native_goals.report import calculate
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text());amend=json.loads((output/'fairness/oracle-erratum.json').read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==amend['corrected_grader_sha256'],'Erratum grader changed after registration'
    rows=[]
    for item in m['order']:
        trial=output/'trials'/item['id'];path=trial/'record.json'
        if not path.exists():continue
        row=copy.deepcopy(json.loads(path.read_text()));replacement=[]
        for seed in(90173,470117):
            p=trial/f'corrected-validation-{seed}.json'
            if p.exists():value=json.loads(p.read_text())
            else:value=evaluate(output,output/'repos'/item['id'],seed);atomic_json(p,value)
            replacement.append(value)
        row['original_artifact_success']=row['artifact_success'];row['original_success']=row['success']
        row['judgments']=[next(v for v in replacement if v['seed']==j['seed'])if j['id']=='validation'else j for j in row['judgments']]
        row['artifact_success']=all(j['passed']for j in row['judgments']);row['success']=row['normal_exit']and row['artifact_success'];rows.append(row)
    data=calculate(rows,m);prospective=amend['no_automation_model_started_at_registration']
    worker={r['mode']:r for r in rows if r['case']=='automation'}
    worker_full=len(worker)==2
    qualified_worker=worker_full and prospective and worker['goalpilot']['success']and not worker['native_goal']['success']and not any(r['fatal']or r['infrastructure_interruption']for r in worker.values())
    result={'classification':'Erratum analysis; original four-trial primary results retained and not claimed as proof. Core score correction is retrospective. Corrected automation comparison was registered before either automation model execution.','erratum':amend,'measurements':data,'corrected_rows':rows,'prospective_worker_pair_complete':worker_full,'prospective_worker_completion_advantage_observed':bool(qualified_worker)}
    atomic_json(output/'corrected-analysis.json',result);print(json.dumps({'corrected_groups':data['groups'],'worker_advantage_observed':bool(qualified_worker),'complete':data['complete']},indent=2));return result


if __name__=='__main__':
    if sys.argv[1]=='check':
        try:check(sys.argv[2],sys.argv[3],int(sys.argv[4]));print(json.dumps({'passed':True}))
        except Exception as e:
            import traceback
            print(json.dumps({'passed':False,'error':f'{type(e).__name__}: {e}','traceback':traceback.format_exc()[-4000:]}))
    elif sys.argv[1]=='summarize':summarize(sys.argv[2])
