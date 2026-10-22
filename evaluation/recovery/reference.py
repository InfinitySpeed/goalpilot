import argparse,datetime,json,re,sqlite3,sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('reserve')
    for k in ('id','room','owner','start','end'):q.add_argument('--'+k,required=True)
    s.add_parser('cancel').add_argument('id');s.add_parser('list').add_argument('--room');s.add_parser('import').add_argument('--file',required=True);a=p.parse_args()
    try:
        Path(a.db).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(a.db,timeout=5) as db:
            db.execute('begin immediate')
            db.execute("create table if not exists bookings(id text primary key,room text not null,owner text not null,start text not null,end text not null,status text not null default 'active')")
            columns=[x[1] for x in db.execute('pragma table_info(bookings)')]
            if 'status' not in columns:db.execute("alter table bookings add column status text not null default 'active'")
            def obj(row):return dict(zip(('id','room','owner','start','end','status'),row))
            def get(key):return db.execute('select id,room,owner,start,end,status from bookings where id=?',(key,)).fetchone()
            def reserve(row):
                assert isinstance(row,dict) and set(row)=={'id','room','owner','start','end'}
                key,room,owner,start,end=[row[k] for k in ('id','room','owner','start','end')]
                assert all(isinstance(x,str) and x.strip() for x in (key,room,owner))
                for value in (start,end):
                    assert isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',value)
                    datetime.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ')
                assert start<end
                old=get(key)
                if old:
                    assert old[:5]==(key,room,owner,start,end);return obj(old)
                assert not db.execute("select 1 from bookings where room=? and status='active' and start<? and end>?",(room,end,start)).fetchone()
                db.execute('insert into bookings(id,room,owner,start,end,status) values(?,?,?,?,?,?)',(key,room,owner,start,end,'active'))
                return obj(get(key))
            if a.cmd=='reserve':out=reserve({k:getattr(a,k) for k in ('id','room','owner','start','end')})
            elif a.cmd=='import':
                rows=json.loads(Path(a.file).read_text());assert isinstance(rows,list);out=[reserve(row) for row in rows]
            elif a.cmd=='cancel':
                assert get(a.id);db.execute("update bookings set status='cancelled' where id=?",(a.id,));out=obj(get(a.id))
            else:
                rows=db.execute('select id,room,owner,start,end,status from bookings order by start,id').fetchall();out=[obj(r) for r in rows if a.room is None or r[1]==a.room]
        print(json.dumps(out,ensure_ascii=False))
    except Exception as e:print('Invalid reservation: '+str(e),file=sys.stderr);sys.exit(2)


if __name__=='__main__':main()
