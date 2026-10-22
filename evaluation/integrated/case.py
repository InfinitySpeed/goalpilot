from pathlib import Path
import json,sqlite3
from evaluation.triple.cases import seed_source,PUBLIC
from evaluation.triple.specs import SPECS
from .spec import SPEC


def config():
    return {'schedule':{'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2},
        'csv':'k,n\nx,0.1\nx,0.2\n','plan':{'source':'input','group_by':['k'],'aggregates':[{'as':'total','op':'sum','column':'n'}]},
        'catalog':{'app':[{'version':'1.0.0','dependencies':{}},{'version':'2.0.0','dependencies':{}}]},'requests':{'app':'*'},'tables':{},'locked':{}}

WORK_TEST='''import unittest,tempfile
from pathlib import Path
from workbench import Workspace
class PublicWorkspace(unittest.TestCase):
 def test_complete_workflow(self):
  with tempfile.TemporaryDirectory()as t:
   w=Workspace(Path(t)/'nested/work.db')
   cfg={'schedule':{'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':1},'csv':'k,n\\nx,0.1\\nx,0.2\\n',
       'plan':{'source':'input','group_by':['k'],'aggregates':[{'as':'total','op':'sum','column':'n'}]},
       'catalog':{'app':[{'version':'1.0.0','dependencies':{}}]},'requests':{'app':'*'}}
   self.assertEqual(w.register('p',cfg)['revision'],1)
   runs=w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z')
   self.assertEqual(len(runs),1)
   self.assertEqual(runs[0]['result'],{'columns':['k','total'],'rows':[['x','0.3']]})
   self.assertEqual(runs[0]['versions'],{'app':'1.0.0'})
   self.assertEqual(w.run('2026-01-01T00:00:00Z','2026-01-03T00:00:00Z'),[])
   self.assertEqual(Workspace(Path(t)/'nested/work.db').history(),runs)
'''


def materialize(repo):
    repo=Path(repo);repo.mkdir(parents=True)
    for name in SPECS:
        folder=repo/name;folder.mkdir();(folder/'__init__.py').write_text('from .core import *\n')
        (folder/'core.py').write_text(seed_source(name));(folder/'README.md').write_text(SPECS[name])
    (repo/'README.md').write_text(SPEC)
    (repo/'workbench.py').write_text('class Workspace:\n def __init__(self,path):raise NotImplementedError("workspace integration unfinished")\n')
    (repo/'tests').mkdir()
    for name,tests in PUBLIC.items():(repo/'tests'/f'test_{name}.py').write_text(tests)
    (repo/'tests/test_workspace.py').write_text(WORK_TEST)
    (repo/'USER_NOTES.txt').write_text('Mes données originales: café 東京.\n');(repo/'data').mkdir()
    (repo/'data/source.csv').write_text('name,value\n"café, 東京",0.10\n');(repo/'data/lock.json').write_text('{"local":"1.0.0"}\n')
    with sqlite3.connect(repo/'data/legacy.sqlite')as db:
        db.execute('create table schedules(id text primary key,spec text not null)')
        db.execute('insert into schedules values(?,?)',('old',json.dumps({'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2})))
        db.execute('create table notes(value text)');db.execute("insert into notes values('keep')")
    with sqlite3.connect(repo/'data/workspace.sqlite')as db:
        db.execute('create table pipelines(id text primary key,config text not null)');db.execute('insert into pipelines values(?,?)',('old',json.dumps(config())))
        db.execute('create table runs(id integer primary key,pipeline text not null,at text not null,result text not null)')
        db.execute('insert into runs values(?,?,?,?)',(41,'old','2025-12-31T09:00:00Z',json.dumps({'columns':['kept'],'rows':[['original']]})))
        db.execute('create table personal_notes(text text)');db.execute("insert into personal_notes values('keep')")
