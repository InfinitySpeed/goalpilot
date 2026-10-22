import tempfile
from pathlib import Path
from .cases import materialize,judge
from .worker_judge import evaluate


def run():
    result={}
    with tempfile.TemporaryDirectory()as t:
        for name in('runforge','automation'):
            repo=materialize(Path(t)/name,name,True);checks=judge(name,repo)
            assert all(r['passed']for r in checks),(name,[r for r in checks if not r['passed']])
            result[name]={'reference_groups_passed':len(checks)}
        repo=Path(t)/'automation';original=(repo/'engine.py').read_text()
        mutants=[('latest-task-used','worker_revisions',"task=n['task']","task=next(v for v in s['workflows'][r['workflow']]['nodes']if v['id']==n['id'])['task']"),
        ('worker-does-no-work','worker_journey',"if op!='worker.tick':return _base_handle(s,op,d)","if op!='worker.tick':return _base_handle(s,op,d)\n    return []"),
        ('bool-treated-as-int','worker_validation','type(v)is not int','not isinstance(v,int)'),
        ('worker-limit-ignored','worker_retry_cancel','for _ in range(limit):','for _ in range(100):')]
        rejected=[]
        from goalpilot.process import run_process
        import json,sys
        from . import worker_judge
        for name,group,old,new in mutants:
            assert old in original;code=original.replace(old,new);compile(code,name,'exec');(repo/'engine.py').write_text(code)
            r=run_process([sys.executable,str(Path(worker_judge.__file__).resolve()),str(repo),group],Path(__file__).resolve().parents[2],30)
            data=json.loads(r.output.splitlines()[-1]);assert not data['passed'],name;rejected.append(name)
        result['automation']['isolated_worker_faults_rejected']=rejected
    return result
