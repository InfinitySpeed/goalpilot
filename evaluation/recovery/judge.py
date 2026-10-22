import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


def evaluate(repo):
    repo=Path(repo);checks=[]
    with tempfile.TemporaryDirectory() as t:
        root=Path(t);n=0
        def fresh():
            nonlocal n
            n+=1;return root/f'{n}.db'
        def cli(db,*args,code=0):
            p=subprocess.run([sys.executable,str(repo/'book.py'),'--db',str(db),*map(str,args)],cwd=repo,capture_output=True,text=True,timeout=10)
            assert p.returncode==code,(p.returncode,p.stdout[-1000:],p.stderr[-1000:])
            if code==2:assert not p.stdout.strip() and p.stderr.strip();return None
            return json.loads(p.stdout)
        def reserve(db,key='one',room='A',start='2026-10-21T10:00:00Z',end='2026-10-21T11:00:00Z',owner='Alice',code=0):
            return cli(db,'reserve','--id',key,'--room',room,'--owner',owner,'--start',start,'--end',end,code=code)
        def test(name,fn):
            try:fn();checks.append({'id':name,'passed':True})
            except Exception as e:checks.append({'id':name,'passed':False,'error':f'{type(e).__name__}: {e}'})
        def basic():
            db=fresh();one=reserve(db)
            assert one=={'id':'one','room':'A','owner':'Alice','start':'2026-10-21T10:00:00Z','end':'2026-10-21T11:00:00Z','status':'active'}
            reserve(db,'two',start='2026-10-21T11:00:00Z',end='2026-10-21T12:00:00Z')
            reserve(db,'other',room='B')
            assert [x['id'] for x in cli(db,'list','--room','A')]==['one','two']
            before=cli(db,'list');reserve(db,'overlap',start='2026-10-21T10:59:59Z',end='2026-10-21T12:00:00Z',code=2)
            assert cli(db,'list')==before
        test('half_open_rooms_persistence',basic)
        def replays():
            db=fresh();one=reserve(db);assert reserve(db)==one
            cancelled=cli(db,'cancel','one');assert cancelled['status']=='cancelled'
            reserve(db,'new');assert reserve(db)==cancelled
            assert cli(db,'cancel','one')==cancelled
            before=cli(db,'list');reserve(db,owner='Changed',code=2);cli(db,'cancel','missing',code=2)
            assert cli(db,'list')==before
        test('idempotency_cancelled_replay_before_conflict',replays)
        def invalid():
            db=fresh();reserve(db);before=cli(db,'list')
            for start in ('2026-02-30T10:00:00Z','2026-10-21T10:00:00+00:00','2026-10-21T10:00:00.0Z','2026-10-21T11:00:00Z'):
                reserve(db,'bad',start=start,code=2)
            reserve(db,' ',room='B',code=2);reserve(db,'blank',room=' ',code=2);reserve(db,'owner',room='B',owner=' ',code=2)
            assert cli(db,'list')==before
        test('strict_validation_no_mutation',invalid)
        def imports():
            db=fresh();file=root/'imports.json'
            row={'id':'a','room':'東京','owner':'café','start':'2026-10-21T08:00:00Z','end':'2026-10-21T09:00:00Z'}
            file.write_text(json.dumps([row,row]));out=cli(db,'import','--file',file)
            assert len(out)==2 and out[0]==out[1] and len(cli(db,'list'))==1
            before=cli(db,'list')
            for bad in ({**row,'id':'c'}, {**row,'id':'bad','start':True}, {**row,'id':'bad','extra':1}):
                file.write_text(json.dumps([{**row,'id':'b','room':'B'},bad]));cli(db,'import','--file',file,code=2)
                assert cli(db,'list')==before
            file.write_text('[]');assert cli(db,'import','--file',file)==[]
        test('import_atomicity_schema_replays',imports)
        def concurrent():
            db=fresh();cli(db,'list')
            def send(i):
                return subprocess.run([sys.executable,str(repo/'book.py'),'--db',str(db),'reserve','--id',str(i),'--room','A','--owner','Worker','--start','2026-10-21T10:00:00Z','--end','2026-10-21T11:00:00Z'],cwd=repo,capture_output=True,text=True,timeout=10).returncode
            with ThreadPoolExecutor(6) as pool:codes=list(pool.map(send,range(6)))
            assert codes.count(0)==1 and codes.count(2)==5,codes
            assert len(cli(db,'list'))==1
        test('concurrent_no_double_booking',concurrent)
        def legacy():
            db=repo/'data/legacy.sqlite';rows=cli(db,'list')
            assert rows==[{'id':'old','room':'Salle 東京','owner':'Utilisateur','start':'2026-10-01T10:00:00Z','end':'2026-10-01T11:00:00Z','status':'active'}]
            with sqlite3.connect(db) as c:assert c.execute('select content from personal_notes').fetchone()[0]=='keep'
            assert (repo/'USER_NOTES.txt').read_text()=='Réservation personnelle 東京: conserver.\n'
        test('original_migration_and_user_data',legacy)
        def corrupt():
            db=fresh();db.write_bytes(b'corrupt\x00database');cli(db,'list',code=2);assert db.read_bytes()==b'corrupt\x00database'
        test('corruption_preserved',corrupt)
    return checks
