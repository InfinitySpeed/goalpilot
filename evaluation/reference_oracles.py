"""Independent reference executables to validate the held-out checks before use.

These files are never included in the coding repositories or model prompts.
They verify the test harness, not the efficacy of GoalPilot.
"""

import json
from pathlib import Path
import tempfile
import time

from goalpilot.process import run_process
from .validation_cases import cases


INVENTORY = r'''
import sys,json,csv,re
from pathlib import Path
def quantity(x):
    if not re.fullmatch(r'[+-]?\d+',str(x)):raise ValueError('integer required')
    return int(x)
def validate(rows):
    if not isinstance(rows,list):raise ValueError('array required')
    seen=set()
    for x in rows:
        if not isinstance(x,dict) or not isinstance(x.get('sku'),str) or not x['sku'].strip() or not isinstance(x.get('name'),str) or not x['name'].strip() or type(x.get('quantity')) is not int or x['quantity']<0 or x['sku'] in seen:raise ValueError('invalid inventory')
        seen.add(x['sku'])
try:
    _,path,op,*args=sys.argv[1:];path=Path(path)
    rows=json.loads(path.read_text()) if path.exists() else []
    validate(rows)
    if op in ('list','export'):print(json.dumps(sorted(rows,key=lambda x:x['sku']),ensure_ascii=False))
    else:
        if op=='add':
            sku,name,q=args;rows.append({'sku':sku,'name':name,'quantity':quantity(q)})
        elif op=='adjust':
            sku,q=args;item=next((x for x in rows if x['sku']==sku),None)
            if item is None:raise ValueError('unknown SKU')
            item['quantity']+=quantity(q)
        elif op=='import':
            with open(args[0],newline='') as stream:
                reader=csv.DictReader(stream)
                if not set(('sku','name','quantity')).issubset(reader.fieldnames or []):raise ValueError('headers')
                for x in reader:rows.append({'sku':x['sku'],'name':x['name'],'quantity':quantity(x['quantity'])})
        else:raise ValueError('command')
        validate(rows);path.write_text(json.dumps(rows,ensure_ascii=False))
except (ValueError,OSError,KeyError,TypeError) as e:
    print(str(e),file=sys.stderr);sys.exit(2)
'''

AGENDA = r'''
import sys,sqlite3,json
from datetime import datetime
def date(x):
    d=datetime.strptime(x,'%Y-%m-%dT%H:%M')
    if d.strftime('%Y-%m-%dT%H:%M')!=x:raise ValueError('format')
    return d
try:
    _,path,op,*args=sys.argv[1:]
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,room TEXT,start TEXT,end TEXT,title TEXT)')
    if op=='add':
        room,start,end,title=args
        if not room.strip() or not title.strip() or date(start)>=date(end):raise ValueError('input')
        if db.execute('SELECT 1 FROM events WHERE room=? AND start<? AND end>?',(room,end,start)).fetchone():raise ValueError('conflict')
        db.execute('INSERT INTO events(room,start,end,title) VALUES(?,?,?,?)',args);db.commit()
    elif op=='delete':
        cursor=db.execute('DELETE FROM events WHERE id=?',(int(args[0]),));db.commit()
        if not cursor.rowcount:sys.exit(1)
    elif op in ('list','export'):
        query='SELECT * FROM events';params=()
        if args:query+=' WHERE room=?';params=(args[1],)
        rows=db.execute(query+' ORDER BY start,id',params).fetchall()
        print(json.dumps([dict(x) for x in rows],ensure_ascii=False))
    else:raise ValueError('command')
except (ValueError,OSError,sqlite3.Error) as e:
    print(str(e),file=sys.stderr);sys.exit(2)
'''

PIPELINE = r'''
import sys,json,re
from pathlib import Path
from decimal import Decimal
try:
    source=Path(sys.argv[1]);output=Path(sys.argv[sys.argv.index('--output')+1]);strict='--strict' in sys.argv
    totals={};users=set();seen=set();invalid=0;duplicates=0
    for line in source.read_text().splitlines():
        if not line.strip():continue
        try:
            x=json.loads(line)
            if not isinstance(x,dict) or any(not isinstance(x.get(k),str) or not x[k].strip() for k in ('id','user')):raise ValueError()
            if not isinstance(x.get('currency'),str) or not re.fullmatch('[A-Z]{3}',x['currency']):raise ValueError()
            if not isinstance(x.get('amount'),str) or not re.fullmatch(r'[+-]?\d+(?:\.\d{1,2})?',x['amount']):raise ValueError()
            amount=Decimal(x['amount'])
        except (ValueError,TypeError):
            invalid+=1
            if strict:raise ValueError('invalid line')
            continue
        if x['id'] in seen:duplicates+=1;continue
        seen.add(x['id']);users.add(x['user'])
        totals[x['currency']]=totals.get(x['currency'],Decimal(0))+amount
    report={'records':len(seen),'totals':{k:format(v,'.2f') for k,v in totals.items()},'users':sorted(users),'invalid_rows':invalid,'duplicate_rows':duplicates}
    text=json.dumps(report,ensure_ascii=False);output.write_text(text);print(text)
except (ValueError,OSError) as e:
    print(str(e),file=sys.stderr);sys.exit(2)
'''


def preflight():
    references={'inventory':('inventory.py',INVENTORY),'agenda':('agenda.py',AGENDA),'pipeline':('pipeline.py',PIPELINE)}
    records=[]
    for case in cases():
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d)
            for filename,content in case['files'].items():(repo/filename).write_text(content)
            for criterion in case['checks']:
                compile(criterion['command'][2],criterion['id'],'exec')
                stub=run_process(criterion['command'],repo,10)
                if stub.returncode==0:raise AssertionError('Seed incorrectly passed: '+criterion['id'])
            name,code=references[case['name']]
            (repo/name).write_text(code)
            for criterion in case['checks']:
                result=run_process(criterion['command'],repo,10)
                if result.returncode:raise AssertionError(criterion['id']+'\n'+result.output)
            records.append({'case':case['name'],'reference_checks_passed':len(case['checks']),'unfinished_seed_rejected':True})
    return {'kind':'independent_verifier_preflight','live_model_calls':0,'cases':records}


if __name__=='__main__':print(json.dumps(preflight(),ensure_ascii=False,indent=2))
