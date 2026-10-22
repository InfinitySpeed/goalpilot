import copy,datetime,io,json,os,sqlite3,tempfile
from pathlib import Path
from contextlib import contextmanager
from daybook import occurrences
from tablekit import read_csv,write_csv,execute
from resolver import resolve


def timestamp(s):
    import re
    if not isinstance(s,str)or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',s):raise ValueError('timestamp')
    try:return datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:raise ValueError('timestamp')from e

def positive(n):
    if type(n)is not int or n<1:raise ValueError('positive integer')

def key(s):
    if not isinstance(s,str)or not s.strip():raise ValueError('id')


class Workspace:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db():pass
    def normalize(self,c):
        if not isinstance(c,dict)or set(c)-{'schedule','csv','plan','catalog','requests','tables','locked'}or not {'schedule','csv','plan','catalog','requests'}<=set(c):raise ValueError('config')
        c=copy.deepcopy(c);c.setdefault('tables',{});c.setdefault('locked',{})
        if not isinstance(c['tables'],dict)or 'input'in c['tables']or not isinstance(c['locked'],dict):raise ValueError('maps')
        day=datetime.date.fromisoformat(c['schedule']['start_date']);lo=day.strftime('%Y-%m-%dT00:00:00Z');hi=(day+datetime.timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
        occurrences(c['schedule'],lo,hi)
        execute(c['plan'],{'input':read_csv(c['csv']),**c['tables']});resolve(c['catalog'],c['requests'],c['locked'])
        return c
    @contextmanager
    def db(self):
        db=None
        try:
            db=sqlite3.connect(self.path,timeout=10);db.execute('begin immediate')
            db.execute('create table if not exists pipelines(id text primary key,config text not null,revision integer not null default 1)')
            db.execute("create table if not exists runs(id integer primary key autoincrement,pipeline text not null,at text not null,result text not null,revision integer not null default 1,versions text not null default '{}')")
            for ident,c in db.execute('select id,config from pipelines'):key(ident);self.normalize(json.loads(c))
            for ident,pipeline,at,result in db.execute('select id,pipeline,at,result from runs'):
                positive(ident);key(pipeline);timestamp(at)
                r=json.loads(result)
                if not isinstance(r,dict)or set(r)!={'columns','rows'}:raise ValueError('stored result')
                # Count aggregates are integer result cells, unlike CSV input.
                converted={'columns':r['columns'],'rows':[[str(x)if type(x)is int else x for x in row]for row in r['rows']]};write_csv(converted)
            for table,column,ddl in [('pipelines','revision','integer not null default 1'),('runs','revision','integer not null default 1'),('runs','versions',"text not null default '{}'")]:
                if column not in[r[1]for r in db.execute('pragma table_info('+table+')')]:db.execute('alter table '+table+' add column '+column+' '+ddl)
            for rev,versions in db.execute('select revision,versions from runs'):positive(rev);v=json.loads(versions);assert isinstance(v,dict)
            db.execute('create unique index if not exists run_identity on runs(pipeline,revision,at)')
            yield db;db.commit()
        except Exception as e:
            if db:db.rollback()
            if isinstance(e,ValueError):raise
            raise ValueError(str(e))from e
        finally:
            if db:db.close()
    def row(self,db,ident):
        row=db.execute('select config,revision from pipelines where id=?',(ident,)).fetchone()
        if not row:raise ValueError('absent')
        return {'id':ident,'revision':row[1],'config':self.normalize(json.loads(row[0]))}
    def register(self,ident,config):
        key(ident)
        with self.db()as db:
            normalized=self.normalize(config)
            if db.execute('select 1 from pipelines where id=?',(ident,)).fetchone():
                old=self.row(db,ident)
                if old['config']!=normalized:raise ValueError('conflicting reuse')
                return old
            db.execute('insert into pipelines values(?,?,1)',(ident,json.dumps(normalized,sort_keys=True)));return self.row(db,ident)
    def get(self,ident):
        key(ident)
        with self.db()as db:return self.row(db,ident)
    def replace(self,ident,config,expected_revision):
        key(ident);positive(expected_revision)
        with self.db()as db:
            normalized=self.normalize(config);old=self.row(db,ident)
            if old['revision']!=expected_revision:raise ValueError('stale revision')
            db.execute('update pipelines set config=?,revision=revision+1 where id=?',(json.dumps(normalized,sort_keys=True),ident));return self.row(db,ident)
    def decode(self,row):return {'run_id':row[0],'pipeline':row[1],'revision':row[2],'at':row[3],'versions':json.loads(row[4]),'result':json.loads(row[5])}
    def records(self,db):return[self.decode(r)for r in db.execute('select id,pipeline,revision,at,versions,result from runs order by at,pipeline,revision,id')]
    def run(self,start,end):
        if timestamp(start)>=timestamp(end):raise ValueError('bounds')
        with self.db()as db:
            new=[]
            for ident,rev,text in db.execute('select id,revision,config from pipelines order by id').fetchall():
                c=self.normalize(json.loads(text));versions=resolve(c['catalog'],c['requests'],c['locked']);result=execute(c['plan'],{'input':read_csv(c['csv']),**c['tables']})
                for at in occurrences(c['schedule'],start,end):
                    if db.execute('select 1 from runs where pipeline=?and revision=?and at=?',(ident,rev,at)).fetchone():continue
                    cursor=db.execute('insert into runs(pipeline,revision,at,versions,result)values(?,?,?,?,?)',(ident,rev,at,json.dumps(versions,sort_keys=True),json.dumps(result)))
                    new.append(cursor.lastrowid)
            return[r for r in self.records(db)if r['run_id']in new]
    def history(self):
        with self.db()as db:return self.records(db)
    def atomic(self,path,content):
        path=Path(path)
        if path.resolve()==self.path.resolve():raise ValueError('database destination')
        temp=None
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='',dir=path.parent,delete=False)as stream:
                temp=stream.name;stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path);temp=None
        except Exception as e:raise ValueError(str(e))from e
        finally:
            if temp:
                try:os.unlink(temp)
                except FileNotFoundError:pass
    def export_json(self,path):
        result=self.history();self.atomic(path,json.dumps(result,ensure_ascii=False,sort_keys=True)+'\n');return result
    def export_csv(self,run_id,path):
        positive(run_id);rows=[r for r in self.history()if r['run_id']==run_id]
        if not rows:raise ValueError('absent run')
        result=rows[0]['result'];converted={'columns':result['columns'],'rows':[[str(x)if type(x)is int else x for x in row]for row in result['rows']]}
        self.atomic(path,write_csv(converted));return len(result['rows'])
