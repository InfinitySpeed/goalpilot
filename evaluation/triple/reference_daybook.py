import datetime as d
import json,re,sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo


def date(x):
    if not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x):raise ValueError('date')
    try:return d.date.fromisoformat(x)
    except Exception as e:raise ValueError('date') from e

def utc(x):
    if not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',x):raise ValueError('UTC timestamp')
    try:return d.datetime.strptime(x,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=d.timezone.utc)
    except Exception as e:raise ValueError('timestamp') from e

def validate(s):
    try:
        if not isinstance(s,dict) or set(s)-{'start_date','at','zone','until','weekdays','exclude','count','fold','gap'}:raise ValueError('schema')
        start=date(s['start_date']);until=date(s.get('until','2099-12-31'))
        if 'until' in s and (until<start or (until-start).days>20000):raise ValueError('span')
        if not isinstance(s['at'],str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',s['at']):raise ValueError('time')
        if not isinstance(s['zone'],str):raise ValueError('zone')
        zone=ZoneInfo(s['zone'])
        days=s.get('weekdays',list(range(7)));exclude=s.get('exclude',[])
        if not isinstance(days,list) or any(type(x)is not int or not 0<=x<=6 for x in days) or len(set(days))!=len(days):raise ValueError('weekdays')
        if not isinstance(exclude,list):raise ValueError('exclude')
        ex=[date(x) for x in exclude]
        if len(set(ex))!=len(ex):raise ValueError('exclude duplicates')
        if 'count'in s and (type(s['count'])is not int or s['count']<=0):raise ValueError('count')
        if s.get('fold','earlier') not in ('earlier','later') or s.get('gap','skip') not in ('skip','next_valid'):raise ValueError('policy')
        return start,until,zone,days,ex
    except (KeyError,TypeError,OverflowError) as e:raise ValueError('spec') from e
    except Exception as e:
        if isinstance(e,ValueError):raise
        raise ValueError('spec') from e

def occurrences(spec,start,end):
    lo,hi=utc(start),utc(end)
    if lo>=hi:raise ValueError('bounds')
    first,last,zone,days,exclude=validate(spec)
    final=min(last,hi.astimezone(zone).date()+d.timedelta(days=1))
    if (final-first).days>20000:raise ValueError('span')
    result=[];number=0;day=first
    hour,minute=map(int,spec['at'].split(':'))
    while day<=final:
        if day.weekday() in days and day not in exclude:
            wall=d.datetime.combine(day,d.time(hour,minute));candidates=[]
            for offset in range(1441 if spec.get('gap','skip')=='next_valid' else 1):
                local=wall+d.timedelta(minutes=offset)
                candidates=sorted({local.replace(tzinfo=zone,fold=f).astimezone(d.timezone.utc) for f in (0,1)
                    if local.replace(tzinfo=zone,fold=f).astimezone(d.timezone.utc).astimezone(zone).replace(tzinfo=None)==local})
                if candidates:break
            if candidates:
                value=candidates[-1 if spec.get('fold','earlier')=='later' else 0];number+=1
                if lo<=value<hi:result.append(value.strftime('%Y-%m-%dT%H:%M:%SZ'))
                if number>=spec.get('count',10**12):break
        day+=d.timedelta(days=1)
    return sorted(set(result))


class ScheduleStore:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self._db() as db:pass
    def _db(self):
        from contextlib import contextmanager
        @contextmanager
        def connection():
            db=None
            try:
                db=sqlite3.connect(self.path,timeout=10);db.execute('begin immediate')
                db.execute('create table if not exists schedules(id text primary key,spec text not null,revision integer not null default 1)')
                columns=[r[1]for r in db.execute('pragma table_info(schedules)')]
                for key,text in db.execute('select id,spec from schedules'):
                    self._key(key);validate(json.loads(text))
                if 'revision'not in columns:db.execute('alter table schedules add column revision integer not null default 1')
                yield db;db.commit()
            except Exception as e:
                if db:db.rollback()
                if isinstance(e,ValueError):raise
                raise ValueError(str(e))from e
            finally:
                if db:db.close()
        return connection()
    def _key(self,key):
        if not isinstance(key,str) or not key.strip():raise ValueError('id')
    def _get(self,db,key):
        row=db.execute('select spec,revision from schedules where id=?',(key,)).fetchone()
        if row is None:raise ValueError('absent')
        return {'id':key,'spec':json.loads(row[0]),'revision':row[1]}
    def put(self,key,spec):
        self._key(key);validate(spec)
        with self._db()as db:
            row=db.execute('select 1 from schedules where id=?',(key,)).fetchone()
            if row:
                old=self._get(db,key)
                if old['spec']!=spec:raise ValueError('conflicting reuse')
                return old
            db.execute('insert into schedules values(?,?,1)',(key,json.dumps(spec,sort_keys=True)))
            return self._get(db,key)
    def get(self,key):
        self._key(key)
        with self._db()as db:return self._get(db,key)
    def update(self,key,spec,expected_revision):
        self._key(key);validate(spec)
        if type(expected_revision)is not int or expected_revision<1:raise ValueError('revision')
        with self._db()as db:
            old=self._get(db,key)
            if old['revision']!=expected_revision:raise ValueError('revision mismatch')
            db.execute('update schedules set spec=?,revision=revision+1 where id=?',(json.dumps(spec,sort_keys=True),key))
            return self._get(db,key)
    def due(self,start,end):
        lo,hi=utc(start),utc(end)
        if lo>=hi:raise ValueError('bounds')
        with self._db()as db:
            values=[{'id':key,'at':at}for key,text in db.execute('select id,spec from schedules')for at in occurrences(json.loads(text),start,end)]
        return sorted(values,key=lambda x:(x['at'],x['id']))
