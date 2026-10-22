"""Independent lease-queue reference for verifier preflight only."""
import argparse
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile


def stamp(s):
    assert isinstance(s,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',s)
    return datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ')


def later(now,seconds):return (stamp(now)+timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%SZ')
def obj(s):
    value=json.loads(s);assert isinstance(value,dict);return value
def row(value):
    d=dict(value);d['payload']=json.loads(d['payload']);d['result']=json.loads(d['result']) if d['result'] is not None else None;return d


def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(path,timeout=20);c.row_factory=sqlite3.Row;c.execute('BEGIN IMMEDIATE')
    cols=[x[1] for x in c.execute('PRAGMA table_info(jobs)')]
    legacy=None
    if cols==['id','payload']:
        legacy=[dict(x) for x in c.execute('SELECT * FROM jobs')]
        for x in legacy:obj(x['payload'])
        c.execute('ALTER TABLE jobs RENAME TO old_jobs')
    if not cols or legacy is not None:
        c.execute("CREATE TABLE jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL,key TEXT UNIQUE,state TEXT NOT NULL,attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,available_at TEXT NOT NULL,worker TEXT,lease_until TEXT,result TEXT)")
    if legacy is not None:
        for x in legacy:c.execute("INSERT INTO jobs(id,payload,state,attempts,max_attempts,available_at) VALUES(?,?,'pending',0,3,'1970-01-01T00:00:00Z')",(x['id'],x['payload']))
        c.execute('DROP TABLE old_jobs')
    for x in c.execute('SELECT payload FROM jobs'):obj(x['payload'])
    return c


def atom(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--now',default=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'));s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('enqueue');a.add_argument('payload');a.add_argument('--key');a.add_argument('--max-attempts',type=int,default=3);a.add_argument('--available-at')
    a=s.add_parser('claim');a.add_argument('--worker',required=True);a.add_argument('--lease-seconds',type=int,required=True)
    for cmd in ('ack','fail'):
        a=s.add_parser(cmd);a.add_argument('id',type=int);a.add_argument('--worker',required=True)
        if cmd=='ack':a.add_argument('--result',required=True)
        else:a.add_argument('--retry-after',type=int,required=True)
    a=s.add_parser('list');a.add_argument('--state',choices=['pending','running','done','failed'])
    s.add_parser('stats');a=s.add_parser('export');a.add_argument('--output',required=True)
    a=p.parse_args();stamp(a.now)
    if a.cmd=='enqueue':
        payload=obj(a.payload);assert a.max_attempts>0 and (a.key is None or a.key.strip())
        available=a.available_at or a.now;stamp(available)
    if a.cmd in ('claim','ack','fail'):assert a.worker.strip()
    if a.cmd=='claim':assert a.lease_seconds>0
    if a.cmd=='fail':assert a.retry_after>=0
    if a.cmd=='ack':result=obj(a.result)
    c=connect(a.db)
    try:
        if a.cmd=='enqueue':
            prior=c.execute('SELECT * FROM jobs WHERE key=?',(a.key,)).fetchone() if a.key is not None else None
            if prior:
                assert json.loads(prior['payload'])==payload and prior['max_attempts']==a.max_attempts;value=row(prior)
            else:
                i=c.execute("INSERT INTO jobs(payload,key,state,attempts,max_attempts,available_at) VALUES(?,?,'pending',0,?,?)",(json.dumps(payload),a.key,a.max_attempts,available)).lastrowid
                value=row(c.execute('SELECT * FROM jobs WHERE id=?',(i,)).fetchone())
        elif a.cmd=='claim':
            c.execute("UPDATE jobs SET state='failed',worker=NULL,lease_until=NULL WHERE state='running' AND lease_until<=? AND attempts>=max_attempts",(a.now,))
            found=c.execute("SELECT * FROM jobs WHERE (state='pending' AND available_at<=?) OR (state='running' AND lease_until<=? AND attempts<max_attempts) ORDER BY id LIMIT 1",(a.now,a.now)).fetchone()
            value=None
            if found:
                c.execute("UPDATE jobs SET state='running',attempts=attempts+1,worker=?,lease_until=? WHERE id=?",(a.worker,later(a.now,a.lease_seconds),found['id']))
                value=row(c.execute('SELECT * FROM jobs WHERE id=?',(found['id'],)).fetchone())
        elif a.cmd in ('ack','fail'):
            found=c.execute('SELECT * FROM jobs WHERE id=?',(a.id,)).fetchone()
            assert found and found['state']=='running' and found['worker']==a.worker and found['lease_until']>a.now
            if a.cmd=='ack':c.execute("UPDATE jobs SET state='done',result=?,worker=NULL,lease_until=NULL WHERE id=?",(json.dumps(result),a.id))
            else:
                state='failed' if found['attempts']>=found['max_attempts'] else 'pending'
                c.execute('UPDATE jobs SET state=?,available_at=?,result=NULL,worker=NULL,lease_until=NULL WHERE id=?',(state,later(a.now,a.retry_after),a.id))
            value=row(c.execute('SELECT * FROM jobs WHERE id=?',(a.id,)).fetchone())
        else:
            rows=[row(x) for x in c.execute('SELECT * FROM jobs ORDER BY id')]
            if a.cmd=='stats':value={state:sum(x['state']==state for x in rows) for state in ('pending','running','done','failed')}
            elif a.cmd=='list':value=[x for x in rows if a.state is None or x['state']==a.state]
            else:value=rows
        if a.cmd=='export':atom(a.output,value)
        c.commit();print(json.dumps(value,ensure_ascii=False))
    except BaseException:c.rollback();raise
    finally:c.close()


if __name__=='__main__':
    try:main()
    except (ValueError,AssertionError,TypeError,KeyError,OSError,sqlite3.Error) as e:print(str(e) or 'invalid input/transition/database',file=sys.stderr);sys.exit(2)
