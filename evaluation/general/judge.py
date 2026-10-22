"""Independent black-box judge. Its checks never enter live agent prompts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import queue
import random
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

NOTES=b'User-owned notes: Caf\xc3\xa9 \xe6\x9d\xb1\xe4\xba\xac. Preserve these exact bytes.\n'


def call(repo,entry,*args,code=0):
    p=subprocess.Popen([sys.executable,entry,*map(str,args)],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=p.communicate(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);p.communicate();raise AssertionError('CLI command exceeded 12s')
    finally:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    assert p.returncode==code,(args,p.returncode,stdout[-1000:],stderr[-1000:])
    if code==2:assert stderr.strip() and not stdout.strip(),(stdout,stderr)
    return json.loads(stdout) if stdout.strip() else None


@contextmanager
def server(repo,db):
    with tempfile.TemporaryFile(mode='w+') as errors:
        p=subprocess.Popen([sys.executable,'desk.py','--db',str(db),'serve','--port','0'],cwd=repo,
            stdout=subprocess.PIPE,stderr=errors,text=True,start_new_session=True)
        inbox=queue.Queue()
        reader=threading.Thread(target=lambda:inbox.put(p.stdout.readline()),daemon=True);reader.start()
        try:
            try:line=inbox.get(timeout=8)
            except queue.Empty:raise AssertionError('Server did not announce its port within 8s')
            if not line:
                errors.seek(0);raise AssertionError('Server exited: '+errors.read()[-1600:])
            port=json.loads(line)['port'];assert type(port) is int and 0<port<65536
            def request(method,path,data=None,raw=None):
                conn=http.client.HTTPConnection('127.0.0.1',port,timeout=8)
                try:
                    body=raw if raw is not None else json.dumps(data,ensure_ascii=False).encode() if data is not None else None
                    conn.request(method,path,body,{'Content-Type':'application/json'})
                    response=conn.getresponse();payload=json.loads(response.read())
                    assert response.getheader('Content-Type','').startswith('application/json')
                    return response.status,payload
                finally:conn.close()
            yield request
        finally:
            if p.poll() is None:
                try:os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait()
            reader.join(timeout=1);p.stdout.close()


def desk(repo,group,tmp,rng):
    db=tmp/'desk.sqlite'
    if group=='blocker':
        with server(repo,Path(repo)/'data/legacy.sqlite') as req:
            status,rows=req('GET','/tickets')
            assert status==200 and any(x=={'id':41,'title':'Ancienne demande 東京','priority':2,'status':'open'} for x in rows),rows
        return
    with server(repo,db) as req:
        if group=='delivery':
            a=req('POST','/tickets',{'title':'Café 東京','priority':1});b=req('POST','/tickets',{'title':'Urgent','priority':3})
            assert a[0]==b[0]==201 and type(a[1]['id']) is int and a[1]['id']<b[1]['id']
            assert req('GET','/tickets')==(200,[b[1],a[1]])
            assert req('PATCH',f"/tickets/{a[1]['id']}",{'status':'closed'})[0]==200
            comment=req('POST',f"/tickets/{b[1]['id']}/comments",{'text':"O'Brien — prêt"})
            assert comment[0]==201 and comment[1]['text']=="O'Brien — prêt"
            assert req('GET',f"/tickets/{b[1]['id']}/comments")== (200,[comment[1]])
            assert req('GET','/report')==(200,{'total':2,'by_status':{'open':1,'closed':1},'by_priority':{'1':1,'2':0,'3':1}})
            out=tmp/'export.json';snapshot=call(repo,'desk.py','--db',db,'export','--output',out)
            assert json.loads(out.read_text())==snapshot
            assert snapshot['tickets']==[dict(a[1],status='closed'),b[1]] and snapshot['comments']==[comment[1]]
        elif group=='errors_integrity':
            first=req('POST','/tickets',{'title':'keep'})[1];before=req('GET','/tickets')[1]
            for data in [{'title':' '},{'title':'bad','priority':True},{'title':'bad','priority':4},{'title':3}]:
                status,value=req('POST','/tickets',data);assert status==400 and isinstance(value.get('error'),str)
            assert req('POST','/tickets',raw=b'{bad')[0]==400
            for data in [{},{'status':'missing'},{'priority':False},{'title':'not editable'}]:
                assert req('PATCH',f"/tickets/{first['id']}",data)[0]==400
            assert req('GET','/tickets?status=bad')[0]==400
            assert req('POST','/tickets/999999/comments',{'text':'x'})[0]==404
            assert req('GET','/no-such-route')[0]==404
            assert req('GET','/tickets')[1]==before
        else:
            values=[{'title':f'row-{rng.randrange(1000000)}-é','priority':rng.randrange(1,4)} for _ in range(12)]
            with ThreadPoolExecutor(max_workers=6) as pool:created=list(pool.map(lambda x:req('POST','/tickets',x),values))
            assert all(x[0]==201 for x in created),created
            ids=[x[1]['id'] for x in created];assert len(set(ids))==12
            expected=sorted([x[1] for x in created],key=lambda x:(-x['priority'],x['id']))
            assert req('GET','/tickets')==(200,expected)
            comment=req('POST',f'/tickets/{ids[0]}/comments',{'text':'persist after restart'})[1]
    if group=='restart_newdata':
        with server(repo,db) as req:
            assert req('GET','/tickets')==(200,expected)
            assert req('GET',f'/tickets/{ids[0]}/comments')==(200,[comment])
    if group=='errors_integrity':
        broken=tmp/'broken.sqlite';broken.write_bytes(b'not a sqlite database')
        output=tmp/'keep.json';output.write_bytes(b'existing export')
        call(repo,'desk.py','--db',broken,'export','--output',output,code=2)
        assert broken.read_bytes()==b'not a sqlite database' and output.read_bytes()==b'existing export'


def queue_case(repo,group,tmp,rng):
    db=tmp/'jobs.sqlite';now='2026-03-01T10:00:00Z'
    def run(*args,at=now,code=0,path=None):
        return call(repo,'queuectl.py','--db',path or db,'--now',at,*args,code=code)
    if group=='blocker':
        rows=run('list',path=Path(repo)/'data/legacy.sqlite')
        assert any(x['id']==17 and x['payload']=={'old':'café'} and x['state']=='pending' and x['attempts']==0 and x['max_attempts']==3 for x in rows),rows
    elif group=='delivery':
        first=run('enqueue','{"text":"東京"}','--key','stable','--max-attempts','2')
        assert first['state']=='pending' and first['attempts']==0 and first['available_at']==now
        assert run('enqueue','{"text":"東京"}','--key','stable','--max-attempts','2')==first
        job=run('claim','--worker','A','--lease-seconds','10')
        assert job['id']==first['id'] and job['attempts']==1 and job['lease_until']=='2026-03-01T10:00:10Z'
        assert run('claim','--worker','B','--lease-seconds','10') is None
        run('fail',job['id'],'--worker','A','--retry-after','5')
        assert run('claim','--worker','B','--lease-seconds','10',at='2026-03-01T10:00:04Z') is None
        job=run('claim','--worker','B','--lease-seconds','10',at='2026-03-01T10:00:05Z');assert job['attempts']==2
        done=run('ack',job['id'],'--worker','B','--result','{"done":"é"}',at='2026-03-01T10:00:06Z')
        assert done['state']=='done' and done['result']=={'done':'é'} and done['worker'] is None and done['lease_until'] is None
        assert run('stats')=={'pending':0,'running':0,'done':1,'failed':0}
        out=tmp/'export.json';assert run('export','--output',out)==json.loads(out.read_text())==[done]
    elif group=='errors_integrity':
        first=run('enqueue','{"a":1}','--key','x')
        job=run('claim','--worker','owner','--lease-seconds','10');before=run('list')
        run('ack',job['id'],'--worker','wrong','--result','{}',code=2)
        run('ack',job['id'],'--worker','owner','--result','{}',at=job['lease_until'],code=2)
        run('enqueue','{"a":2}','--key','x',code=2)
        for args in [('enqueue','[]'),('enqueue','{}','--max-attempts','0'),('claim','--worker','x','--lease-seconds','0'),('enqueue','{}','--available-at','2026-02-30T00:00:00Z')]:
            run(*args,code=2)
        assert run('list')==before
        broken=tmp/'corrupt.sqlite';broken.write_bytes(b'bad sqlite')
        run('list',path=broken,code=2);assert broken.read_bytes()==b'bad sqlite'
        legacy=tmp/'badlegacy.sqlite'
        with sqlite3.connect(legacy) as c:c.execute('CREATE TABLE jobs(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)');c.execute("INSERT INTO jobs VALUES(99,'not json')")
        run('list',path=legacy,code=2)
        with sqlite3.connect(legacy) as c:assert c.execute('SELECT * FROM jobs').fetchall()==[(99,'not json')]
    else:
        payload={'n':rng.randrange(1000000),'text':'café'};first=run('enqueue',json.dumps(payload),'--max-attempts','2')
        def claim(i):return run('claim','--worker',f'worker-{i}','--lease-seconds','2')
        with ThreadPoolExecutor(max_workers=6) as pool:claimed=list(pool.map(claim,range(6)))
        assert sum(x is not None for x in claimed)==1,claimed
        recovered=run('claim','--worker','recovery','--lease-seconds','2',at='2026-03-01T10:00:02Z')
        assert recovered['id']==first['id'] and recovered['attempts']==2 and recovered['payload']==payload
        assert run('claim','--worker','last','--lease-seconds','2',at='2026-03-01T10:00:04Z') is None
        assert run('stats')=={'pending':0,'running':0,'done':0,'failed':1}
        fresh=run('enqueue',json.dumps({'seed':rng.randrange(99999)}));assert fresh['id']>first['id']


def vault(repo,group,tmp,rng):
    archive=tmp/'archive';source=tmp/'source';source.mkdir()
    def run(*args,root=None,code=0):return call(repo,'vault.py','--root',root or archive,*args,code=code)
    if group=='blocker':
        original=Path(repo)/'data/archive'
        rows=run('list',root=original);assert [x['id'] for x in rows]==[7,8],rows
        assert run('verify','7',root=original)=={'id':7,'ok':True,'missing':[],'corrupt':[]}
        assert run('verify','8',root=original,code=1)=={'id':8,'ok':False,'missing':[],'corrupt':['broken.bin']}
        run('restore','8',tmp/'badrestore',root=original,code=2);assert not (tmp/'badrestore').exists()
        assert (original/'objects/KEEP.txt').read_bytes()==b'Unrelated user object note\n'
        return
    data={'.config':b'yes','nested/café 東京.txt':bytes(rng.randrange(256) for _ in range(97)),'empty.bin':b''}
    for name,raw in data.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (source/'skip-link').symlink_to(source/'.config')
    first=run('snapshot',source,'--label','first')
    assert first=={'id':1,'label':'first','files':3,'added_objects':3},first
    if group=='delivery':
        second=run('snapshot',source,'--label','duplicate');assert second=={'id':2,'label':'duplicate','files':3,'added_objects':0}
        assert run('list')==[{'id':1,'label':'first','files':3},{'id':2,'label':'duplicate','files':3}]
        assert run('verify','1')=={'id':1,'ok':True,'missing':[],'corrupt':[]}
        dest=tmp/'restored';assert run('restore','1',dest)=={'id':1,'files':3}
        assert {p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}==data
    elif group=='errors_integrity':
        manifest=json.loads((archive/'manifest.json').read_text());entries=manifest['snapshots'][0]['files']
        (archive/'objects'/entries[-1]['sha256']).write_bytes(b'wrong bytes')
        info=run('verify','1',code=1);assert info['ok'] is False and info['corrupt']==[entries[-1]['path']]
        dest=tmp/'dest';dest.mkdir();(dest/'keep').write_bytes(b'unchanged')
        run('restore','1',dest,code=2);assert sorted(x.name for x in dest.iterdir())==['keep']
        for path in ['../escape','/absolute','C:/escape','a\\b']:
            bad=json.loads(json.dumps(manifest));bad['snapshots'][0]['files'][0]['path']=path
            (archive/'manifest.json').write_text(json.dumps(bad));before=(archive/'manifest.json').read_bytes()
            run('list',code=2);assert (archive/'manifest.json').read_bytes()==before
        (archive/'manifest.json').write_text(json.dumps(manifest));before=(archive/'manifest.json').read_bytes()
        run('snapshot',archive,code=2);assert (archive/'manifest.json').read_bytes()==before
    else:
        (archive/'objects/KEEP.txt').write_bytes(b'preserve unrelated')
        (source/'.config').write_bytes(b'changed')
        second=run('snapshot',source,'--label','new');assert second['id']==2 and second['added_objects']==1
        removed=run('prune','--keep','1');assert removed=={'removed_snapshots':[1],'removed_objects':1}
        assert (archive/'objects/KEEP.txt').read_bytes()==b'preserve unrelated'
        assert run('verify','2')=={'id':2,'ok':True,'missing':[],'corrupt':[]}
        dest=tmp/'dest';dest.mkdir();outside=tmp/'outside';outside.mkdir();(dest/'nested').symlink_to(outside,target_is_directory=True)
        run('restore','2',dest,code=2);assert not (dest/'.config').exists() and not list(outside.iterdir())
        assert run('snapshot',source)['id']==3


GROUPS=('delivery','errors_integrity','blocker','restart_newdata')


def evaluate(case,repo,seed=84721):
    results=[]
    for i,group in enumerate(GROUPS):
        start=time.monotonic();error=None
        try:
            with tempfile.TemporaryDirectory() as t:
                {'desk':desk,'queue':queue_case,'vault':vault}[case['name']](Path(repo),group,Path(t),random.Random(seed+i))
            assert (Path(repo)/'USER_NOTES.txt').read_bytes()==NOTES,'Unrelated user notes changed'
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'[-5000:]
        results.append({'id':group,'passed':error is None,'error':error,'seconds':time.monotonic()-start,'seed':seed})
    return results
