import argparse,csv,json,re,sqlite3,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);s=p.add_subparsers(dest='cmd',required=True)
    t=s.add_parser('transfer')
    for k in ('id','from','to','amount'):t.add_argument('--'+k,required=True)
    t=s.add_parser('import');t.add_argument('--file',required=True)
    s.add_parser('balances');s.add_parser('history');a=p.parse_args()
    try:
        Path(a.db).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(a.db,timeout=5) as db:
            db.execute('begin immediate')
            db.execute('create table if not exists accounts(name text primary key,cents integer not null)')
            db.execute('create table if not exists transfers(seq integer primary key,id text unique,src text,dst text,cents integer)')
            def obj(row):return dict(zip(('id','from','to','cents'),row))
            def transfer(row):
                assert set(row)=={'id','from','to','amount'}
                key,src,dst,amount=[row[k] for k in ('id','from','to','amount')]
                assert all(isinstance(v,str) and v.strip() for v in (key,src,dst)) and src!=dst
                assert isinstance(amount,str) and re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?',amount)
                cents=int(amount.split('.')[0])*100+int((amount.split('.')[1] if '.' in amount else '').ljust(2,'0'))
                assert cents>0
                old=db.execute('select id,src,dst,cents from transfers where id=?',(key,)).fetchone()
                if old:
                    assert old==(key,src,dst,cents);return obj(old)
                balance=db.execute('select cents from accounts where name=?',(src,)).fetchone()
                assert balance and balance[0]>=cents
                assert db.execute('select 1 from accounts where name=?',(dst,)).fetchone()
                db.execute('update accounts set cents=cents-? where name=?',(cents,src))
                db.execute('update accounts set cents=cents+? where name=?',(cents,dst))
                db.execute('insert into transfers(id,src,dst,cents) values(?,?,?,?)',(key,src,dst,cents))
                return obj((key,src,dst,cents))
            if a.cmd=='transfer':out=transfer({k:getattr(a,k) for k in ('id','from','to','amount')})
            elif a.cmd=='import':
                with open(a.file,encoding='utf-8',newline='') as f:
                    rows=csv.DictReader(f,strict=True);assert rows.fieldnames==['id','from','to','amount'];out=[transfer(row) for row in rows]
            elif a.cmd=='balances':out=[{'account':r[0],'cents':r[1]} for r in db.execute('select name,cents from accounts order by name')]
            else:out=[obj(r) for r in db.execute('select id,src,dst,cents from transfers order by seq')]
        print(json.dumps(out,ensure_ascii=False))
    except Exception as e:print('Invalid operation: '+str(e),file=sys.stderr);sys.exit(2)


if __name__=='__main__':main()
