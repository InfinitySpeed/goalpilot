"""Paired actual-files parity: direct CLI vs installed skill entrypoint, no inference."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import atomic_json
from evaluation.ambitious.cases import materialize
from evaluation.ambitious.judge import evaluate
from goalpilot.reuse import inventory


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(root.rglob('*'))if p.is_file()and '__pycache__'not in p.parts and p.suffix!='.pyc'}


def create(out):
    ci=json.loads((ROOT/'reports/tests.json').read_text());assert ci['successful']and ci['passed']==205
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in ci['source_fingerprint'].items())
    assert not out.exists();out.mkdir(parents=True)
    skill=Path.home()/'.agents/skills/goalpilot';manifest=json.loads((skill/'MANIFEST.json').read_text())
    assert all(hashlib.sha256((ROOT/'goalpilot'/p).read_bytes()).hexdigest()==h for p,h in manifest['engine']['files'].items())
    snap=out/'source_snapshot'
    for d in ('goalpilot','tests','evaluation','skills'):shutil.copytree(ROOT/d,snap/d,ignore=shutil.ignore_patterns('__pycache__'))
    (snap/'tools').mkdir();shutil.copy2(__file__,snap/'tools/skill_parity_study.py')
    cases={}
    for case in ('flowdesk','stockroom'):
        cache=ROOT/'reports/reuse-current-001/caches'/case;entryfile=next(cache.glob('*/entry.json'));entry=json.loads(entryfile.read_text())
        cases[case]={'cache':str(cache),'entry':str(entryfile),'entry_sha256':hashlib.sha256(entryfile.read_bytes()).hexdigest(),'source_repo':entry['source_repo'],'goal':entry['goal'],'model':entry['model']}
    order=[]
    for case in cases:
        for mode,count in [('initial',1),('delivered',3)]:
            for repeat in range(1,count+1):
                ident=f'{case}-{mode}-{repeat}';arms=['direct','skill']if len(order)%2==0 else['skill','direct']
                order.append({'id':ident,'case':case,'mode':mode,'arms':arms})
    m={'registered_at':time.time(),'engine_version':'0.9.1','skill_version':'1.0.0','installed_skill':str(skill),
       'installed_execution_hashes':{p:hashlib.sha256((skill/p).read_bytes()).hexdigest()for p in ['SKILL.md','agents/openai.yaml','scripts/goalpilot.py',*[f'runtime/goalpilot/{p}'for p in manifest['engine']['files']]]},
       'cases':cases,'order':order,'planned_pairs':8,'planned_executions':16,'source_fingerprint':hashes(snap),'offline_tests':ci,
       'primary':'All8pairs both normally closed and26independentgroups correct per execution, identical goal/budgets/check outcomes/token counters and delivered file hashes; zero backend attempts. No failed trial reruns, protocol changes or omitted arms.',
       'time_rule':'Installed skill mean elapsed <= direct mean elapsed*1.10+0.10seconds. Small-sample descriptive tolerance, not a population or statistical noninferiority claim.',
       'scope':'Real filesystem/HTTP verification using known previously learned artifacts. Launcher parity only; these timings and zero counts EXCLUDE the calling Codex model conversation. No fresh cold efficacy claim. Existing cold percentages stay attached to0.9.0.',
       'stopping':'Keep all16planned denominator. Record failures and continue remaining fixed arms if local infrastructure permits; no source changes or retries. Real Codex executable denied in both arms, zero new model research budget.'}
    atomic_json(out/'protocol.json',m);atomic_json(out/'preregistered-protocol.json',m);print('REGISTERED',out,flush=True)


def run(out):
    m=json.loads((out/'protocol.json').read_text());assert m==json.loads((out/'preregistered-protocol.json').read_text())
    assert hashes(out/'source_snapshot')==m['source_fingerprint']
    skill=Path(m['installed_skill']);assert all(hashlib.sha256((skill/p).read_bytes()).hexdigest()==h for p,h in m['installed_execution_hashes'].items())
    deny=out/'deny';deny.mkdir();stub=deny/'codex'
    marker=out/'backend-attempts.jsonl'
    stub.write_text('#!'+sys.executable+'\nimport os,sys,json\nwith open(os.environ["GP_DENY_LOG"],"a")as f:f.write(json.dumps(sys.argv)+"\\n")\nraise SystemExit(97)\n');stub.chmod(0o700)
    env=os.environ.copy();env['PATH']=str(deny)+os.pathsep+env.get('PATH','');env['PYTHONPATH']=str(ROOT);env['GP_DENY_LOG']=str(marker)
    rows=[];pairs=[]
    for item in m['order']:
        c=m['cases'][item['case']];ep=Path(c['entry']);assert hashlib.sha256(ep.read_bytes()).hexdigest()==c['entry_sha256']
        pairrows=[]
        for arm in item['arms']:
            ident=item['id']+'-'+arm;dest=out/'trials'/ident;assert not dest.exists();dest.mkdir(parents=True)
            repo=out/'repos'/ident
            if item['mode']=='initial':materialize(repo,item['case'])
            else:shutil.copytree(c['source_repo'],repo,ignore=shutil.ignore_patterns('__pycache__'))
            before=inventory(repo);atomic_json(dest/'input.json',before)
            goalfile=dest/'goal.txt';goalfile.write_bytes(c['goal'].encode('utf-8'))
            flags=['--repo',str(repo),'--run-dir',str(dest/'run'),'--cache-dir',c['cache'],'--model',c['model'],'--wall-seconds','900','--max-calls','6','--max-tokens','1500000']
            argv=[sys.executable,'-m','goalpilot','go',*flags,'--',c['goal']]if arm=='direct'else[sys.executable,str(skill/'scripts/goalpilot.py'),'go','--goal-file',str(goalfile),*flags]
            start=time.monotonic();error=None;proc=None
            try:proc=subprocess.run(argv,cwd=repo,env=env,text=True,capture_output=True,timeout=60)
            except subprocess.TimeoutExpired:error='Launcher timeout60s'
            elapsed=time.monotonic()-start
            if proc:
                (dest/'stdout.txt').write_text(proc.stdout);(dest/'stderr.txt').write_text(proc.stderr)
            sp=dest/'run/state.json';s=json.loads(sp.read_text())if sp.exists()else None
            judgments=[j for seed in (90173,470117)for j in evaluate(item['case'],repo,seed)]
            correct=len(judgments)==26 and all(j['passed']for j in judgments)
            normalized=None
            if s:
                normalized={'status':s['status'],'goal':s['contract']['goal'],'budget':s['contract']['budget'],
                    'scope':s['contract']['scope'],'acceptance_origin':s['contract']['acceptance_origin'],'usage':s['usage'],
                    'calls':len(s['calls']),'checks':[(x['id'],x['passed'],x['returncode'])for x in s['verifications'][-1]['checks']]}
            row={'id':ident,'pair':item['id'],'arm':arm,'case':item['case'],'mode':item['mode'],'seconds':elapsed,'error':error,
                 'returncode':proc.returncode if proc else None,'normalized':normalized,'judgments':judgments,'after':inventory(repo),
                 'success':bool(proc and proc.returncode==0 and s and s['status']=='scope_passed'and s['calls']==[]and correct)}
            atomic_json(dest/'record.json',row);rows.append(row);pairrows.append(row);print('RESULT',ident,row['success'],elapsed,flush=True)
        same=pairrows[0]['normalized']==pairrows[1]['normalized']and pairrows[0]['after']==pairrows[1]['after']
        pairs.append({'id':item['id'],'both_success':all(r['success']for r in pairrows),'identical_result':same})
    means={arm:sum(r['seconds']for r in rows if r['arm']==arm)/8 for arm in ('direct','skill')}
    complete=len(rows)==16 and all(r['success']for r in rows)and all(p['identical_result']for p in pairs)
    result={'planned_pairs':8,'executions':len(rows),'correct_closed':sum(r['success']for r in rows),'pairs':pairs,
       'groups_passed':sum(j['passed']for r in rows for j in r['judgments']),'groups_planned':416,
       'mean_seconds':means,'launcher_overhead_seconds':means['skill']-means['direct'],
       'time_tolerance_met':means['skill']<=means['direct']*1.10+.10,'result_parity':complete,
       'backend_attempts':len(marker.read_text().splitlines())if marker.exists()else 0,
       'backend_model_calls':sum(r['normalized']['calls']for r in rows if r['normalized']),
       'engine_sources_unchanged':True,'scope':m['scope'],'caller_model_cost_included':False,'new_model_inference_budget':0}
    result['all_preregistered_targets_met']=complete and result['time_tolerance_met']and result['backend_attempts']==0 and result['backend_model_calls']==0
    atomic_json(out/'analysis.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    action=sys.argv[1];out=Path(sys.argv[2]).resolve()
    {'create':create,'run':run}[action](out)
