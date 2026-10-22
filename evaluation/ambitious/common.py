"""Transport/storage starter: shared plumbing, no domain implementation."""
STORAGE = r'''import copy,hashlib,json,os,sqlite3,tempfile
from pathlib import Path
import engine

class Service:
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS app_state(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
            if not db.execute('SELECT 1 FROM app_state WHERE id=1').fetchone():
                db.execute('INSERT INTO app_state VALUES(1,?)',(json.dumps(engine.initial()),))
    def connect(self):return sqlite3.connect(self.path,timeout=15,isolation_level='IMMEDIATE')
    def call(self,operation,data):
        if not isinstance(operation,str) or not isinstance(data,dict):raise ValueError('Expected operation and object')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state=json.loads(db.execute('SELECT payload FROM app_state WHERE id=1').fetchone()[0])
            try:result=engine.handle(state,operation,copy.deepcopy(data))
            except (KeyError,TypeError,IndexError)as exc:raise ValueError('Invalid request')from exc
            encoded=json.dumps(state,allow_nan=False,ensure_ascii=False)
            db.execute('UPDATE app_state SET payload=? WHERE id=1',(encoded,))
            return copy.deepcopy(result)
    def backup(self,target):
        target=Path(target)
        if target.resolve()==self.path or target.exists() and os.path.samefile(target,self.path):raise ValueError('Cannot replace database')
        with self.connect()as db:raw=db.execute('SELECT payload FROM app_state WHERE id=1').fetchone()[0]
        payload={'format':1,'application':engine.APPLICATION,'state':json.loads(raw)}
        body=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        target.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(dir=target.parent,prefix='.backup-')
        try:
            with os.fdopen(fd,'w')as f:json.dump({'payload':payload,'sha256':hashlib.sha256(body.encode()).hexdigest()},f,ensure_ascii=False)
            os.replace(name,target)
        finally:
            if os.path.exists(name):os.unlink(name)
        return {'saved':True}
    def restore(self,source):
        try:
            value=json.loads(Path(source).read_text());payload=value['payload']
            body=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            if value['sha256']!=hashlib.sha256(body.encode()).hexdigest() or payload['format']!=1 or payload['application']!=engine.APPLICATION:raise ValueError('Invalid backup')
            engine.validate_state(payload['state'])
            raw=json.dumps(payload['state'],allow_nan=False,ensure_ascii=False)
        except (KeyError,TypeError,OSError,json.JSONDecodeError)as exc:raise ValueError('Invalid backup')from exc
        with self.connect()as db:
            db.execute('BEGIN IMMEDIATE');db.execute('UPDATE app_state SET payload=? WHERE id=1',(raw,))
        return {'restored':True}
'''
TRANSPORT = r'''import argparse,json,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from app import Service

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--serve',action='store_true');p.add_argument('--port',type=int,default=0);a=p.parse_args();service=Service(a.db)
    def dispatch(packet):
        try:return {'ok':True,'result':service.call(packet['operation'],packet.get('data',{}))}
        except (ValueError,KeyError,TypeError)as exc:return {'ok':False,'error':str(exc)}
    if not a.serve:
        for line in sys.stdin:
            try:response=dispatch(json.loads(line))
            except ValueError as exc:response={'ok':False,'error':str(exc)}
            print(json.dumps(response,ensure_ascii=False),flush=True)
        return
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):
            body=json.dumps({'ok':True,'application':__import__('engine').APPLICATION}).encode();self.send_response(200 if self.path=='/health'else 404);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_POST(self):
            if self.path!='/api':self.send_error(404);return
            try:response=dispatch(json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))))
            except (ValueError,TypeError)as exc:response={'ok':False,'error':str(exc)}
            body=json.dumps(response,ensure_ascii=False).encode();self.send_response(200 if response['ok']else 400);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    with ThreadingHTTPServer(('127.0.0.1',a.port),Handler)as server:
        print(json.dumps({'port':server.server_port}),flush=True);server.serve_forever()
if __name__=='__main__':main()
'''
COMMON_SPEC='''## Runtime and public entrypoints
Python 3.11+, standard library only, no external service. Implement the domain in engine.py;
the supplied transactional storage and JSONL/HTTP transport may be improved but their public
interfaces must remain. `from app import Service`; `Service(db_path).call(operation, data)`
accepts a JSON-like dictionary and returns JSON-like results. Domain rejection raises ValueError,
leaves persisted state unchanged and never mutates caller input. Concurrent calls in independent
processes must preserve invariants. Integers below exclude booleans; IDs are nonempty strings.
Do not invent required fields beyond those documented. Results may contain extra keys.

## CLI and HTTP integration
`python transport.py --db DB` accepts one {"operation":NAME,"data":OBJECT} JSON per stdin line,
returns one {"ok":true,"result":VALUE} or {"ok":false,"error":TEXT} per line and continues after
errors. `python transport.py --db DB --serve --port 0` prints {"port":BOUND_PORT} then serves
GET /health and POST /api with the same packet/result; success 200, invalid domain request 400.
These interfaces must perform the same complete domain workflows with durable state.

## Persistence, backup and original data
`Service.backup(path)` writes an atomic portable JSON backup. `restore(path)` must validate
checksum, application and domain state before replacing it; rejection changes nothing. Restore
must work in another database. The wrapper delegates state validation to engine.validate_state.
Implement that function to reject missing collections, impossible quantities/statuses and broken
references; extra object keys may be ignored. The supplied envelope format is public; payload.state must be a JSON object. A checksum-valid envelope with a non-object state must be rejected. Never
replace the active DB or its hardlink with a backup. Existing unrelated SQLite tables and
USER_NOTES.txt must remain intact; persist across Service instances and process restarts.

'''
STUB='''APPLICATION={name!r}
def initial():return {{}}
def validate_state(state):raise ValueError('Domain validation unfinished')
def handle(state,operation,data):raise ValueError('Domain operation unfinished: '+operation)
'''
