"""Independent desk reference, copied only into disposable oracle preflights."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import os
import re
import sqlite3
import sys
import tempfile
from urllib.parse import urlsplit,parse_qs


def init(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path,timeout=20) as c:
        cols=[x[1] for x in c.execute('PRAGMA table_info(tickets)')]
        if not cols:c.execute("CREATE TABLE tickets(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,priority INTEGER NOT NULL,status TEXT NOT NULL)")
        elif cols==['id','subject']:
            c.execute('ALTER TABLE tickets RENAME COLUMN subject TO title')
            c.execute('ALTER TABLE tickets ADD COLUMN priority INTEGER NOT NULL DEFAULT 2')
            c.execute("ALTER TABLE tickets ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
        else:assert set(('id','title','priority','status'))<=set(cols)
        c.execute('CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,ticket_id INTEGER NOT NULL,text TEXT NOT NULL)')


def records(c,table,order='id'):
    c.row_factory=sqlite3.Row
    return [dict(x) for x in c.execute(f'SELECT * FROM {table} ORDER BY {order}')]


def atom(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def handler(db):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,value):
            data=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def body(self):
            size=int(self.headers.get('Content-Length','0'));assert 0<size<2000000
            value=json.loads(self.rfile.read(size));assert isinstance(value,dict);return value
        def dispatch(self,method):
            try:
                url=urlsplit(self.path);path=url.path
                with sqlite3.connect(db,timeout=20) as c:
                    c.row_factory=sqlite3.Row
                    if path=='/tickets' and method=='GET':
                        query=parse_qs(url.query,keep_blank_values=True);assert not set(query)-{'status'}
                        if query:
                            assert len(query['status'])==1 and query['status'][0] in ('open','closed')
                            data=[dict(x) for x in c.execute('SELECT * FROM tickets WHERE status=? ORDER BY priority DESC,id',(query['status'][0],))]
                        else:data=records(c,'tickets','priority DESC,id')
                        return self.respond(200,data)
                    if path=='/tickets' and method=='POST':
                        data=self.body();assert not set(data)-{'title','priority'}
                        title=data.get('title');priority=data.get('priority',2)
                        assert isinstance(title,str) and title.strip() and type(priority) is int and priority in (1,2,3)
                        i=c.execute("INSERT INTO tickets(title,priority,status) VALUES(?,?,'open')",(title,priority)).lastrowid
                        data=dict(c.execute('SELECT * FROM tickets WHERE id=?',(i,)).fetchone());c.commit();return self.respond(201,data)
                    match=re.fullmatch(r'/tickets/(\d+)(/comments)?',path)
                    if match:
                        ident=int(match[1]);row=c.execute('SELECT * FROM tickets WHERE id=?',(ident,)).fetchone()
                        if row is None:return self.respond(404,{'error':'ticket not found'})
                        if match[2] and method=='GET':
                            return self.respond(200,[dict(x) for x in c.execute('SELECT * FROM comments WHERE ticket_id=? ORDER BY id',(ident,))])
                        if match[2] and method=='POST':
                            data=self.body();assert set(data)=={'text'} and isinstance(data['text'],str) and data['text'].strip()
                            i=c.execute('INSERT INTO comments(ticket_id,text) VALUES(?,?)',(ident,data['text'])).lastrowid
                            value=dict(c.execute('SELECT * FROM comments WHERE id=?',(i,)).fetchone());c.commit();return self.respond(201,value)
                        if not match[2] and method=='PATCH':
                            data=self.body();assert data and not set(data)-{'status','priority'}
                            if 'status' in data:assert data['status'] in ('open','closed')
                            if 'priority' in data:assert type(data['priority']) is int and data['priority'] in (1,2,3)
                            for key,value in data.items():c.execute(f'UPDATE tickets SET {key}=? WHERE id=?',(value,ident))
                            value=dict(c.execute('SELECT * FROM tickets WHERE id=?',(ident,)).fetchone());c.commit();return self.respond(200,value)
                    if path=='/report' and method=='GET':
                        rows=records(c,'tickets')
                        return self.respond(200,{'total':len(rows),'by_status':{k:sum(x['status']==k for x in rows) for k in ('open','closed')},'by_priority':{str(k):sum(x['priority']==k for x in rows) for k in (1,2,3)}})
                    self.respond(404,{'error':'route not found'})
            except (ValueError,AssertionError,TypeError,KeyError):self.respond(400,{'error':'invalid input'})
        def do_GET(self):self.dispatch('GET')
        def do_POST(self):self.dispatch('POST')
        def do_PATCH(self):self.dispatch('PATCH')
    return Handler


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('serve');a.add_argument('--port',type=int,required=True)
    a=s.add_parser('export');a.add_argument('--output',required=True)
    a=p.parse_args();init(a.db)
    if a.cmd=='serve':
        server=ThreadingHTTPServer(('127.0.0.1',a.port),handler(a.db));print(json.dumps({'port':server.server_port}),flush=True);server.serve_forever()
    else:
        with sqlite3.connect(a.db) as c:value={'tickets':records(c,'tickets'),'comments':records(c,'comments')}
        atom(a.output,value);print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,AssertionError,OSError,sqlite3.Error) as e:print(str(e) or 'invalid database/input',file=sys.stderr);sys.exit(2)
