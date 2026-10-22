"""Independent checks; never provided to builder or auditor. No API calls."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


def evaluate(case,repo,seed=0):
    repo=Path(repo);results=[]
    def test(name,fn):
        try:fn();results.append({'id':name,'passed':True})
        except Exception as exc:results.append({'id':name,'passed':False,'error':f'{type(exc).__name__}: {exc}'})
    def cli(args,code=0):
        p=subprocess.run([sys.executable,str(repo/case['entry']),*map(str,args)],cwd=repo,capture_output=True,text=True,timeout=10)
        assert p.returncode==code,(p.returncode,p.stdout[-1500:],p.stderr[-1500:])
        if code==2:
            assert not p.stdout.strip(),p.stdout
            assert p.stderr.strip()
            return None
        return json.loads(p.stdout)
    if case['name']=='ledger':
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def fresh():
                db=root/f'{len(list(root.iterdir()))}.sqlite'
                with sqlite3.connect(db) as c:
                    c.execute('create table accounts(name text primary key,cents integer not null)')
                    c.executemany('insert into accounts values(?,?)',[('alice',10000+seed),('bob',250),('東京, café',1000)])
                    c.execute('create table personal_notes(content text)');c.execute("insert into personal_notes values('keep me')")
                return db
            def run(db,*args,code=0):return cli(['--db',db,*args],code)
            def tx(db,key='one',amount='1.20',src='alice',dst='bob',code=0):
                return run(db,'transfer','--id',key,'--from',src,'--to',dst,'--amount',amount,code=code)
            def ledger(db):return run(db,'balances'),run(db,'history')
            def basic():
                db=fresh();out=tx(db)
                assert out=={'id':'one','from':'alice','to':'bob','cents':120}
                balances,hist=ledger(db)
                assert balances==[{'account':'alice','cents':9880+seed},{'account':'bob','cents':370},{'account':'東京, café','cents':1000}]
                assert hist==[out]
                with sqlite3.connect(db) as c:assert c.execute('select content from personal_notes').fetchone()[0]=='keep me'
            test('transfer_migration_persistence',basic)
            def exact():
                db=fresh()
                for i in range(9):tx(db,str(i),'0.01')
                assert run(db,'balances')[0]['cents']==9991+seed
                before=ledger(db)
                for amount in ('0','-1','+1','1e2','NaN','0.001',' 1','1 ','1.000','Infinity'):
                    tx(db,'bad'+amount,amount,code=2)
                assert ledger(db)==before
            test('decimal_validation_no_mutation',exact)
            def replay():
                db=fresh();first=tx(db,amount=str((10000+seed)//100)+'.'+str((10000+seed)%100).zfill(2))
                assert tx(db,amount=f'{(10000+seed)/100:.2f}')==first
                before=ledger(db)
                tx(db,amount='0.01',code=2);tx(db,'new','1',code=2)
                assert ledger(db)==before
            test('idempotency_before_balance_check',replay)
            def csv_ok():
                db=fresh();f=root/'ok.csv'
                f.write_text('id,from,to,amount\na,alice,"東京, café",0.10\na,alice,"東京, café",0.1\nb,"東京, café",bob,1.25\n')
                out=run(db,'import','--file',f);assert len(out)==3 and out[0]==out[1]
                assert len(run(db,'history'))==2
                assert run(db,'balances')[-1]['cents']==885
                assert run(db,'import','--file',f)==out
            test('csv_unicode_order_and_replay',csv_ok)
            def rollback():
                for tail in ('bad,alice,bob,100000\n','same,alice,bob,2\n','bad,alice,bob,NaN\n','broken,alice\n','extra,alice,bob,1,oops\n'):
                    db=fresh();f=root/'bad.csv';before=ledger(db)
                    f.write_text('id,from,to,amount\nsame,alice,bob,1\n'+tail)
                    run(db,'import','--file',f,code=2);assert ledger(db)==before
            test('whole_import_atomic_rollback',rollback)
            def concurrent():
                db=fresh()
                def send(i):
                    return subprocess.run([sys.executable,str(repo/'ledger.py'),'--db',str(db),'transfer','--id',f'c{i}','--from','alice','--to','bob','--amount','60.00'],cwd=repo,capture_output=True,text=True,timeout=10).returncode
                with ThreadPoolExecutor(6) as pool:codes=list(pool.map(send,range(6)))
                assert codes.count(0)==1 and codes.count(2)==5,codes
                assert sum(x['cents'] for x in run(db,'balances'))==11250+seed
                assert len(run(db,'history'))==1
            test('concurrency_no_overspend',concurrent)
            def corrupt():
                db=root/'corrupt.db';db.write_bytes(b'not a database\x00abc')
                run(db,'balances',code=2);assert db.read_bytes()==b'not a database\x00abc'
            test('corruption_preservation',corrupt)
            def original():
                db=repo/'data/legacy.sqlite'
                assert run(db,'balances')==[{'account':'alice','cents':10000},{'account':'bob','cents':250},{'account':'東京, café','cents':1000}]
                with sqlite3.connect(db) as c:assert c.execute('select content from personal_notes').fetchone()[0]=='keep me'
            test('original_user_data',original)
    else:
        def scenario(fn):
            def execute():
                with tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp);src=root/'src';dst=root/'dst';src.mkdir();dst.mkdir();state=root/'state.json'
                    def sync(code=0):return cli(['--state',state,'sync',src,dst],code)
                    fn(root,src,dst,state,sync)
            return execute
        def basic(root,src,dst,state,sync):
            (src/'.hidden').write_bytes(b'');(src/'nested').mkdir();(src/'nested/東京').write_bytes(bytes(range(256)))
            assert sync()=={'copied':['.hidden','nested/東京'],'deleted':[],'unchanged':[]}
            assert (dst/'nested/東京').read_bytes()==bytes(range(256))
            assert sync()=={'copied':[],'deleted':[],'unchanged':['.hidden','nested/東京']}
            assert cli(['--state',state,'status'])==json.loads(state.read_text())
            (src/'.hidden').unlink();(src/'new').write_text(f'new{seed}');(dst/'unmanaged').write_text('keep')
            assert sync()=={'copied':['new'],'deleted':['.hidden'],'unchanged':['nested/東京']}
            assert (dst/'unmanaged').read_text()=='keep'
        test('copy_delete_restart_binary_unicode',scenario(basic))
        def conflict(root,src,dst,state,sync):
            (src/'a').write_text('one');(src/'z').write_text('original');sync()
            before=state.read_bytes();(src/'a').write_text('two');(dst/'z').write_text('local')
            sync(2);assert state.read_bytes()==before and (dst/'a').read_text()=='one' and (dst/'z').read_text()=='local'
            (src/'z').unlink();sync(2);assert (dst/'a').read_text()=='one' and state.read_bytes()==before
        test('batch_conflict_and_delete_preflight',scenario(conflict))
        def first(root,src,dst,state,sync):
            (src/'a').write_text('same');(dst/'a').write_text('same');(src/'b').write_text('other');(dst/'b').write_text('local')
            sync(2);assert not state.exists() and (dst/'b').read_text()=='local'
            (dst/'b').unlink();out=sync();assert out['unchanged']==['a'] and out['copied']==['b']
        test('adoption_and_unmanaged_conflict',scenario(first))
        def links(root,src,dst,state,sync):
            outside=root/'outside';outside.mkdir();(outside/'secret').write_text('preserve')
            (src/'skip').symlink_to(outside,target_is_directory=True);(src/'a').write_text('a');sync()
            assert not (dst/'skip').exists()
            before=state.read_bytes();(src/'z').mkdir();(src/'z/secret').write_text('overwrite')
            (dst/'z').symlink_to(outside,target_is_directory=True);(src/'a').write_text('changed')
            sync(2);assert (outside/'secret').read_text()=='preserve' and (dst/'a').read_text()=='a' and state.read_bytes()==before
        test('symlink_safety_whole_batch',scenario(links))
        def missing(root,src,dst,state,sync):
            (src/'a').write_text('a');sync();(dst/'a').unlink();assert sync()['copied']==['a']
            (src/'a').unlink();(dst/'a').unlink();assert sync()['deleted']==[]
            assert json.loads(state.read_text())['files']=={}
        test('missing_destination_recovery',scenario(missing))
        def invalid(root,src,dst,state,sync):
            (src/'x').write_text('new');(dst/'keep').write_text('keep')
            values=[{'version':True,'files':{}},{'version':1,'files':{'../outside':'a'*64}},
                    {'version':1,'files':{'a\\b':'a'*64}},{'version':1,'files':{'a//b':'a'*64}},
                    {'version':1,'files':{'C:evil':'a'*64}},{'version':1,'files':{'ok':'X'*64}}]
            for value in values:
                state.write_text(json.dumps(value));before=state.read_bytes();sync(2)
                cli(['--state',state,'status'],2)
                assert state.read_bytes()==before and sorted(x.name for x in dst.iterdir())==['keep']
            state.write_text('{"version":1,"files":{},"files":{}}');before=state.read_bytes();sync(2);assert state.read_bytes()==before
        test('strict_state_validation',scenario(invalid))
        def overlap(root,src,dst,state,sync):
            cli(['--state',src/'state.json','sync',src,dst],2)
            cli(['--state',state,'sync',src,src/'subdir'],2)
            alias=root/'alias';alias.symlink_to(src,target_is_directory=True)
            cli(['--state',state,'sync',alias,dst],2)
            assert not state.exists()
        test('overlap_and_root_aliases',scenario(overlap))
    test('unrelated_notes_preserved',lambda: _notes(repo))
    return results


def _notes(repo):
    assert (repo/'USER_NOTES.txt').read_text()=='Mes données: café 東京\n'
