"""Current-version exact-initial replay and already-delivered idempotence; zero inference."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import atomic_json
from goalpilot.reuse import publish,run_cached_finish
from evaluation.ambitious.cases import materialize
from evaluation.ambitious.judge import evaluate


def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(root.rglob('*'))if p.is_file()and '__pycache__'not in p.parts}


def create(out):
    from goalpilot import __version__
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    assert ci['successful']and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in ci['source_fingerprint'].items())
    assert __version__=='0.9.1'and not out.exists();out.mkdir(parents=True)
    snap=out/'source_snapshot'
    for d in ('goalpilot','tests','evaluation'):shutil.copytree(ROOT/d,snap/d,ignore=shutil.ignore_patterns('__pycache__'))
    (snap/'tools').mkdir();shutil.copy2(__file__,snap/'tools/current_reuse_study.py')
    for f in ('pyproject.toml','validate.py'):shutil.copy2(ROOT/f,snap/f)
    source=ROOT/'reports/quota-native-live-007'
    controls={}
    for case in ('flowdesk','stockroom'):
        p=source/'trials'/(case+'-goalpilot')/'record.json';r=json.loads(p.read_text());assert r['success']and r['usage']['usage_complete']
        controls[case]={'record':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_product_version':'0.9.0','source_usage':r['usage'],'learning_charged_again':False}
    m={'registered_at':time.time(),'version':__version__,'source_fingerprint':hashes(snap),'offline_tests':ci,'training':controls,
       'order':[{'case':case,'mode':mode,'id':f'{case}-{mode}-{i}'}for case in ('flowdesk','stockroom')for mode,count in [('initial',1),('delivered',3)]for i in range(1,count+1)],
       'primary':'8of8 actual filesystem executions correct26groups each and normally closed, zero model calls or app-server starts; no trial retries or protocol/source edits. Initial-mode inputs equal learned original contents; delivered-mode inputs equal existing final verified artifacts. Different modes reported separately.',
       'limits':'Both domains and learned artifacts are known. No new cold candidate or new native model run. Cached data and original acceptance from0.9.0, replay implementation0.9.1. Delivered-mode timing is NOT directly comparable to cold native initial inputs. Learning costs retained, not free. No general guarantee for new/changed goals.',
       'quota':'Model inference is guarded off. Successful hits consume zero new Codex model quota; no subscription-quota percentage or monetary conversion inferred. Host checks still consume local CPU/time.',
       'wall_seconds_per_repeat':900,'planned':8,'new_model_raw_budget':0}
    atomic_json(out/'protocol.json',m);atomic_json(out/'preregistered-protocol.json',m)
    print('REGISTERED',out,flush=True)


def run(out):
    m=json.loads((out/'protocol.json').read_text());assert m==json.loads((out/'preregistered-protocol.json').read_text())
    assert hashes(out/'source_snapshot')==m['source_fingerprint']
    # Repackage existing, fully metered learning into a current-version cache; never train again.
    caches={};goals={}
    for case,source in m['training'].items():
        p=Path(source['record']);assert hashlib.sha256(p.read_bytes()).hexdigest()==source['sha256']
        trial=p.parent;cache=out/'caches'/case
        original_entry=next((trial/'isolated-cache').glob('*/entry.json'));entry=json.loads(original_entry.read_text())
        state=json.loads((trial/'run/state.json').read_text());goals[case]=entry['goal'];caches[case]=cache
        assert publish(cache,entry['goal'],entry['model'],entry['before'],Path(entry['source_repo']),trial/'run',state)
    rows=[]
    for item in m['order']:
        case=item['case'];dest=out/'trials'/item['id'];assert not dest.exists();dest.mkdir(parents=True)
        source=json.loads(Path(m['training'][case]['record']).read_text())
        # Source repo is read from the original cache receipt, never a reference implementation.
        original_trial=Path(m['training'][case]['record']).parent
        entry=json.loads(next((original_trial/'isolated-cache').glob('*/entry.json')).read_text())
        repo=out/'repos'/item['id']
        if item['mode']=='initial':materialize(repo,case)
        else:shutil.copytree(entry['source_repo'],repo,ignore=shutil.ignore_patterns('__pycache__'))
        launches=[];attempts=[];error=None;state=None;real_popen=subprocess.Popen
        def guarded(args,*a,**kw):
            argv=args if isinstance(args,list)else[args];launches.append([str(x)for x in argv])
            if any(Path(str(x)).name in ('codex','claude','gemini','aider')for x in argv):raise AssertionError('Model process forbidden')
            return real_popen(args,*a,**kw)
        def forbidden(*a,**kw):attempts.append('model-or-server');raise AssertionError('Inference forbidden')
        start=time.monotonic()
        try:
            with patch('goalpilot.rpc.AppServerAdapter.execute',side_effect=forbidden),patch('goalpilot.rpc.AppServerAdapter._start',side_effect=forbidden),patch('subprocess.Popen',side_effect=guarded):
                state=run_cached_finish(goals[case],repo,dest/'run',cache=caches[case],wall_seconds=900,max_calls=6,max_tokens=1500000,model=entry['model'],audit_policy='on-interruption',review_context='local',initial_effort='low',compact_delivery=True)
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        elapsed=time.monotonic()-start
        checks=[j for seed in (90173,470117)for j in evaluate(case,repo,seed)]
        correct=len(checks)==26 and all(j['passed']for j in checks)
        row={**item,'seconds':elapsed,'model_attempts':attempts,'process_launches':launches,'error':error,'judgments':checks,'artifact_correct':correct,
             'status':state['status']if state else'incomplete','usage':state['usage']if state else None,'reuse':state.get('reuse')if state else None,
             'success':bool(state and state['status']=='scope_passed'and state.get('reuse',{}).get('hit')and not state['calls']and correct and not attempts)}
        atomic_json(dest/'record.json',row);rows.append(row)
        print('RESULT',item['id'],row['success'],elapsed,flush=True)
    result={'version':m['version'],'planned':8,'executed':len(rows),'correct_closed':sum(r['success']for r in rows),
            'independent_groups_passed':sum(j['passed']for r in rows for j in r['judgments']),'independent_groups_planned':208,
            'model_attempts':sum(len(r['model_attempts'])for r in rows),'raw_tokens':sum(r['usage']['total_tokens']for r in rows if r['usage']),
            'complete':len(rows)==8 and all(r['success']for r in rows),'modes':{},'source_version':'0.9.0','replay_version':'0.9.1',
            'new_inference_cost':0,'known_learning_raw_tokens':sum(v['source_usage']['total_tokens']for v in m['training'].values()),
            'limits':m['limits'],'quota':m['quota']}
    for mode in ('initial','delivered'):
        group=[r for r in rows if r['mode']==mode]
        result['modes'][mode]={'planned':2 if mode=='initial'else 6,'correct_closed':sum(r['success']for r in group),
                             'mean_seconds':sum(r['seconds']for r in group)/len(group),'min_seconds':min(r['seconds']for r in group),'max_seconds':max(r['seconds']for r in group)}
    atomic_json(out/'analysis.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    action=sys.argv[1];out=Path(sys.argv[2]).resolve()
    if action=='create':create(out)
    elif action=='run':run(out)
