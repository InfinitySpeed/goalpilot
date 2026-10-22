from pathlib import Path
import json,sqlite3
from .specs import SPECS,GOALS

DAY_TEST='''import unittest
from daybook import occurrences,ScheduleStore
import tempfile
from pathlib import Path
class PublicTests(unittest.TestCase):
 def test_utc_daily(self):
  s={'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2}
  self.assertEqual(occurrences(s,'2026-01-01T00:00:00Z','2026-01-03T00:00:00Z'),['2026-01-01T09:00:00Z','2026-01-02T09:00:00Z'])
 def test_count_is_lifetime(self):
  s={'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2}
  self.assertEqual(occurrences(s,'2026-01-03T00:00:00Z','2026-01-08T00:00:00Z'),[])
 def test_later_fold(self):
  s={'start_date':'2026-11-01','until':'2026-11-01','at':'01:30','zone':'America/New_York','fold':'later'}
  self.assertEqual(occurrences(s,'2026-11-01T00:00:00Z','2026-11-02T00:00:00Z'),['2026-11-01T06:30:00Z'])
 def test_weekdays_and_validation(self):
  s={'start_date':'2026-01-01','at':'09:00','zone':'UTC','weekdays':[]}
  self.assertEqual(occurrences(s,'2026-01-01T00:00:00Z','2026-01-03T00:00:00Z'),[])
  with self.assertRaises(ValueError):occurrences({**s,'weekdays':[True]},'2026-01-01T00:00:00Z','2026-01-03T00:00:00Z')
 def test_store_revision_and_reopen(self):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t)/'nested/x.db';store=ScheduleStore(p);s={'start_date':'2026-01-01','at':'09:00','zone':'UTC'}
   self.assertEqual(store.put('a',s)['revision'],1)
   self.assertEqual(store.update('a',{**s,'at':'10:00'},1)['revision'],2)
   self.assertEqual(ScheduleStore(p).get('a')['spec']['at'],'10:00')
   with self.assertRaises(ValueError):store.update('a',s,1)
'''
TABLE_TEST='''import unittest
from tablekit import execute,read_csv,write_csv
class PublicTests(unittest.TestCase):
 def test_csv_quotes(self):
  t={'columns':['name','value'],'rows':[['café, 東京','x\\ny'],['','']]}
  self.assertEqual(read_csv(write_csv(t)),t)
 def test_sql_null_join(self):
  tables={'a':{'columns':['k'],'rows':[[None],['x']]},'b':{'columns':['k','v'],'rows':[[None,'bad'],['x','yes']]}}
  plan={'source':'a','joins':[{'table':'b','left_on':['k'],'right_on':['k'],'kind':'left','prefix':'b'}]}
  self.assertEqual(execute(plan,tables)['rows'],[[None,None,None],['x','x','yes']])
 def test_descending_null_placement(self):
  t={'a':{'columns':['x'],'rows':[[None],['a'],['z']]}}
  self.assertEqual(execute({'source':'a','order_by':[{'column':'x','descending':True,'nulls':'last'}]},t)['rows'],[['z'],['a'],[None]])
 def test_group_and_projection(self):
  tables={'a':{'columns':['k','n'],'rows':[['x','0.1'],['x','0.2'],['y',None]]}}
  p={'source':'a','group_by':['k'],'aggregates':[{'as':'total','op':'sum','column':'n'}],'select':['k','total']}
  self.assertEqual(execute(p,tables),{'columns':['k','total'],'rows':[['x','0.3'],['y',None]]})
 def test_rejected_schema(self):
  with self.assertRaises(ValueError):read_csv('a,a\\n1,2\\n')
  with self.assertRaises(ValueError):execute({'source':'a','limit':True},{'a':{'columns':['x'],'rows':[]}})
'''
RESOLVE_TEST='''import unittest
from resolver import resolve,satisfies,compare_versions,ResolutionError
class PublicTests(unittest.TestCase):
 def test_semver(self):
  self.assertEqual(compare_versions('1.0.0-alpha.2','1.0.0-alpha.10'),-1)
  self.assertEqual(compare_versions('1.0.0+a','1.0.0+b'),0)
  with self.assertRaises(ValueError):compare_versions('01.0.0','1.0.0')
 def test_zero_caret(self):
  self.assertTrue(satisfies('0.2.9','^0.2.3'))
  self.assertFalse(satisfies('0.3.0','^0.2.3'))
  self.assertFalse(satisfies('0.0.4','^0.0.3'))
 def test_backtracking(self):
  c={'a':[{'version':'2.0.0','dependencies':{'b':'>=2.0.0'}},{'version':'1.0.0','dependencies':{'b':'1.0.0'}}], 'b':[{'version':'1.0.0','dependencies':{}}]}
  self.assertEqual(resolve(c,{'a':'*'}),{'a':'1.0.0','b':'1.0.0'})
 def test_lock_preference_and_yanked(self):
  c={'a':[{'version':'1.0.0','dependencies':{}},{'version':'2.0.0','dependencies':{}},{'version':'3.0.0','dependencies':{},'yanked':True}]}
  self.assertEqual(resolve(c,{'a':'*'},{'a':'1.0.0'}),{'a':'1.0.0'})
  self.assertEqual(resolve(c,{'a':'*'}),{'a':'2.0.0'})
 def test_unsatisfiable_and_invalid(self):
  with self.assertRaises(ResolutionError):resolve({}, {'missing':'*'})
  with self.assertRaises(ValueError):satisfies('1.0.0','* || nonsense')
'''

PUBLIC={'daybook':DAY_TEST,'tablekit':TABLE_TEST,'resolver':RESOLVE_TEST}


def reference(name):return Path(__file__).with_name('reference_'+name+'.py').read_text()


def faults(name):
    if name=='daybook':return [
        ('number+=1','number+=int(lo<=value<hi)'),
        ("value=candidates[-1 if spec.get('fold','earlier')=='later' else 0]","value=candidates[0]"),
        ("range(1441 if spec.get('gap','skip')=='next_valid' else 1)","([0,60] if spec.get('gap','skip')=='next_valid' else [0])"),
        ("db.execute('update schedules set spec=?,revision=revision+1 where id=?'", "\n            if old['spec']==spec:return old\n            db.execute('update schedules set spec=?,revision=revision+1 where id=?'")]
    if name=='tablekit':return [
        ("None not in key and all(r[b]is not None and a==r[b]for a,b in zip(key,join['right_on']))", "all(a==r[b]for a,b in zip(key,join['right_on']))"),
        ("(1 if order.get('nulls','last')=='first'else -1)","(1 if order.get('nulls','last')=='first'else -1)*(-1 if order.get('descending',False)else 1)"),
        ("ctx.prec=max(100,sum(len(v.as_tuple().digits)+abs(v.as_tuple().exponent)for v in numbers)+10)","ctx.prec=28"),
        ("'\\\\'+x if x.startswith('\\\\')else x", "x")]
    return [
        ('if answer is not None:return answer','return answer'),
        ("elif b:upper=f'0.{b+1}.0'","elif b:upper=f'1.0.0'"),
        ('core in pres)and all','core in set().union(*(p for _,p in parts)))and all'),
        ("not r.get('yanked',False)and valid(r['version'],constraints[package])", "not r.get('yanked',False)and valid(r['version'],constraints[package])and(package not in locked or r['version']==locked[package])")]


def seed_source(name):
    text=reference(name)
    for before,after in faults(name):
        assert before in text,(name,before)
        text=text.replace(before,after,1)
    compile(text,name,'exec');return text


def materialize(name,repo):
    repo=Path(repo);repo.mkdir(parents=True)
    (repo/name).mkdir();(repo/name/'__init__.py').write_text('from .core import *\n')
    (repo/name/'core.py').write_text(seed_source(name))
    (repo/'tests').mkdir();(repo/'tests/test_public.py').write_text(PUBLIC[name])
    (repo/'README.md').write_text(SPECS[name]);(repo/'USER_NOTES.txt').write_text('Mes données originales: café 東京.\n')
    (repo/'data').mkdir()
    if name=='daybook':
        with sqlite3.connect(repo/'data/legacy.sqlite')as db:
            db.execute('create table schedules(id text primary key,spec text not null)')
            db.execute('insert into schedules values(?,?)',('old',json.dumps({'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2})))
            db.execute('create table notes(value text)');db.execute("insert into notes values('keep')")
    elif name=='tablekit':(repo/'data/source.csv').write_text('name,value\n"café, 東京",0.10\n')
    else:(repo/'data/lock.json').write_text('{"local":"1.0.0"}\n')
