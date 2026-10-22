import copy,importlib,io,json,sqlite3,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT)not in sys.path:sys.path.append(str(ROOT))
from evaluation.triple.judge import check as component,raises,oracle
from evaluation.triple.judge import GROUPS as COMPONENT_GROUPS
from evaluation.integrated.case import config,WORK_TEST
WORK_GROUPS=['public','lifecycle','atomicity','exports','concurrency','legacy_userdata']
GROUPS=[f'{name}/{g}'for name in ('daybook','tablekit','resolver')for g in COMPONENT_GROUPS]+['workspace/'+g for g in WORK_GROUPS]


def check(repo,group,seed):
    sys.path.insert(0,str(repo));from workbench import Workspace
    if group=='public':
        module=types.ModuleType('public_workspace');exec(compile(WORK_TEST,'original_workspace_test','exec'),module.__dict__)
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(module))
        assert result.wasSuccessful(),stream.getvalue();return
    with tempfile.TemporaryDirectory()as t:
        root=Path(t);db=root/'work.db';w=Workspace(db);c=config()
        if group=='lifecycle':
            c['requests']={'app':'>=2.0.0'};c['locked']={'app':'1.0.0'};before=copy.deepcopy(c)
            one=w.register('p',c);assert one['revision']==1;assert c==before
            same=w.register('p',copy.deepcopy(c));assert same==one
            runs=w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z');assert len(runs)==2
            assert all(r['versions']=={'app':'2.0.0'}and r['result']=={'columns':['k','total'],'rows':[['x','0.3']]}for r in runs)
            assert len({r['run_id']for r in runs})==2 and all(type(r['run_id'])is int and r['run_id']>0 for r in runs)
            assert w.run('2026-01-02T00:00:00Z','2026-01-04T00:00:00Z')==[]
            runs[0]['result']['rows'][0][1]='tamper';assert Workspace(db).history()[0]['result']['rows'][0][1]=='0.3'
            returned=w.get('p');returned['config']['csv']='changed outside';assert w.get('p')['config']['csv']==c['csv']
            changed=copy.deepcopy(c);changed['csv']='k,n\nx,1\nx,2\n'
            assert w.replace('p',changed,1)['revision']==2
            new=w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z');assert len(new)==2 and all(r['revision']==2 and r['result']['rows']==[['x','3']]for r in new)
            hist=w.history();assert len(hist)==4 and hist==sorted(hist,key=lambda r:(r['at'],r['pipeline'],r['revision'],r['run_id']))
            assert w.replace('p',changed,2)['revision']==3
            original=w.history();raises(lambda:w.replace('p',changed,True));raises(lambda:w.replace('p',changed,2));assert w.history()==original
        elif group=='atomicity':
            w.register('a',c);w.register('z',c)
            with sqlite3.connect(db)as sql:sql.execute("CREATE TRIGGER reject_z BEFORE INSERT ON runs WHEN NEW.pipeline='z' BEGIN SELECT RAISE(ABORT,'controlled storage failure');END")
            raises(lambda:w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z'))
            with sqlite3.connect(db)as sql:assert sql.execute('select count(*)from runs').fetchone()[0]==0;sql.execute('drop trigger reject_z')
            old=w.get('a');raises(lambda:w.replace('a',{**c,'schedule':{**c['schedule'],'count':True}},1));assert w.get('a')==old
            with sqlite3.connect(db)as sql:sql.execute("update pipelines set config='invalid JSON'where id='z'")
            raises(lambda:w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z'))
            with sqlite3.connect(db)as sql:assert sql.execute('select count(*)from runs').fetchone()[0]==0
        elif group=='exports':
            codec=oracle('tablekit');c['csv']=codec.write_csv({'columns':['k','n'],'rows':[['x','1'],['x','2'],[None,None],['\\N','4']]})
            c['plan']={'source':'input','group_by':['k'],'aggregates':[{'as':'count','op':'count','column':'*'},{'as':'sum','op':'sum','column':'n'}]}
            w.register('p',c);runs=w.run('2026-01-01T00:00:00Z','2026-01-02T00:00:00Z');assert len(runs)==1
            run=runs[0];out=root/'nested/out.csv';assert w.export_csv(run['run_id'],out)==3
            assert codec.read_csv(out.read_text())=={'columns':['k','count','sum'],'rows':[['x','2','3'],[None,'1',None],['\\N','1','4']]}
            js=root/'all.json';assert w.export_json(js)==w.history();assert json.loads(js.read_text())==w.history()
            out.write_text('OLD');raises(lambda:w.export_csv(True,out));raises(lambda:w.export_csv(999999,out));assert out.read_text()=='OLD'
            raises(lambda:w.export_json(db));assert Workspace(db).history()==w.history()
            alias=root/'alias.db';alias.symlink_to(db);raises(lambda:w.export_csv(run['run_id'],alias));assert Workspace(db).history()==w.history()
            js.write_text('OLD')
            with sqlite3.connect(db)as sql:sql.execute("update runs set result='not JSON'")
            raises(lambda:w.export_json(js));assert js.read_text()=='OLD'
        elif group=='concurrency':
            c['csv']='k,n\n'+''.join(f'x,{i}\n'for i in range(1200));w.register('p',c)
            code="""import sys,json,time
from pathlib import Path
sys.path.insert(0,sys.argv[1]);from workbench import Workspace
w=Workspace(sys.argv[2]);Path(sys.argv[3]).write_text('ready')
while not Path(sys.argv[4]).exists():time.sleep(.002)
print(json.dumps(w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z')))
"""
            jobs=[subprocess.Popen([sys.executable,'-c',code,str(repo),str(db),str(root/f'ready{i}'),str(root/'GO')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)for i in range(4)]
            import time
            limit=time.monotonic()+8
            while len(list(root.glob('ready*')))<4:
                if time.monotonic()>limit:raise AssertionError('workers did not initialize')
                time.sleep(.01)
            (root/'GO').write_text('go');all_runs=[]
            for job in jobs:
                out,err=job.communicate(timeout=15);assert job.returncode==0,(out,err);all_runs.extend(json.loads(out))
            assert len(all_runs)==2 and len({r['run_id']for r in all_runs})==2
            assert len(Workspace(db).history())==2
        else:
            import shutil
            legacy=root/'legacy.sqlite';shutil.copyfile(repo/'data/workspace.sqlite',legacy);old=Workspace(legacy)
            hist=old.history();assert len(hist)==1 and hist[0]['run_id']==41 and hist[0]['revision']==1 and hist[0]['versions']=={} and hist[0]['result']=={'columns':['kept'],'rows':[['original']]}
            assert old.get('old')['revision']==1
            old.register('new',c);runs=old.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z');assert len(runs)==4 and all(r['run_id']>41 for r in runs)
            with sqlite3.connect(legacy)as sql:assert sql.execute('select text from personal_notes').fetchone()[0]=='keep'
            with sqlite3.connect(repo/'data/workspace.sqlite')as sql:
                rows=sql.execute('select id,config from pipelines').fetchall();assert len(rows)==1 and rows[0][0]=='old'and json.loads(rows[0][1])==config()
                rows=sql.execute('select id,pipeline,at,result from runs').fetchall();assert len(rows)==1 and rows[0][:3]==(41,'old','2025-12-31T09:00:00Z')and json.loads(rows[0][3])=={'columns':['kept'],'rows':[['original']]}
            corrupt=root/'corrupt.db';corrupt.write_bytes(b'not sqlite\x00original');raises(lambda:Workspace(corrupt));assert corrupt.read_bytes()==b'not sqlite\x00original'
            empty=Workspace(root/'empty.db');raises(lambda:empty.run('bad','also bad'))


def evaluate(repo,seed=62537,groups=None):
    from goalpilot.process import run_process
    results=[]
    for group in(groups or GROUPS):
        result=run_process([sys.executable,str(Path(__file__).resolve()),str(Path(repo).resolve()),group,str(seed)],ROOT,35)
        try:value=json.loads(result.output.splitlines()[-1])
        except(ValueError,IndexError):value={'passed':False,'error':result.output[-4000:]or 'judge incomplete'}
        results.append({'id':group,**value,'judge_seconds':result.duration_seconds,'judge_timed_out':result.timed_out})
    return results


if __name__=='__main__':
    try:
        repo,group,seed=Path(sys.argv[1]),sys.argv[2],int(sys.argv[3]);name,part=group.split('/')
        if name=='workspace':check(repo,part,seed)
        else:component(name,repo,part,seed)
        print(json.dumps({'passed':True}))
    except Exception as exc:
        import traceback
        print(json.dumps({'passed':False,'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()[-5000:]}))
