"""Regression guards for nonstandard tests, subprojects and impossible criteria."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'integrations/native/native.py'
class GeneralizedNative(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir();self.run=self.base/'run'
 def call(self,*args,code=0):
  r=subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True);self.assertEqual(r.returncode,code,r.stdout+r.stderr);return json.loads(r.stdout)
 def begin(self):return self.call('begin','--repo',self.repo,'--run-dir',self.run,'--goal','Implement and preserve tests.')
 def deliver(self,data,code=0):
  p=self.base/'criteria.json';p.write_text(json.dumps(data));return self.call('deliver',self.run,'--criteria-file',p,code=code)
 def data(self,argv,**extra):return {'checks':[{'id':'tests','argv':argv,**extra}],'criteria':[{'quote':'Implement','checks':['tests']}]}
 def test_subproject_command_runs_in_its_own_directory(self):
  p=self.repo/'packages/app';p.mkdir(parents=True);(p/'app.py').write_text('x=42');(p/'test_app.py').write_text('import app;assert app.x==42');self.begin()
  self.assertTrue(self.deliver(self.data([sys.executable,'test_app.py'],cwd='packages/app'))['goal_complete'])
 def test_external_or_absent_working_directory_is_rejected(self):
  self.begin()
  for cwd in ['..','/tmp','missing']:
   self.deliver(self.data([sys.executable,'-c','pass'],cwd=cwd),code=2)
  self.assertFalse((self.run/'acceptance.json').exists())
 def test_custom_original_test_cannot_be_silently_weakened(self):
  p=self.repo/'quality';p.mkdir();(p/'gate.py').write_text('assert False');self.begin();(p/'gate.py').write_text('pass')
  data=self.data([sys.executable,'quality/gate.py']);data['test_paths']=['quality'];r=self.deliver(data,code=1)
  self.assertFalse(r['goal_complete']);self.assertEqual(r['checks_total'],2)
 def test_custom_test_paths_cannot_escape_or_match_nothing(self):
  self.begin()
  for paths in [['..'],['/etc'],['missing'],['a/../b']]:
   data=self.data([sys.executable,'-c','pass']);data['test_paths']=paths;self.deliver(data,code=2)
  self.assertFalse((self.run/'acceptance.json').exists())
 def test_java_dotnet_and_framework_test_names_remain_frozen(self):
  for name in ('TestApp.java','AppTest.java','AppTests.cs','Module.Tests/Check.cs'):
   with self.subTest(name=name):
    p=self.repo/name;p.parent.mkdir(exist_ok=True);p.write_text('assert False')
    run=self.base/('run'+str(len(list(self.base.glob('run*')))));self.run=run;self.begin();p.write_text('pass')
    self.assertFalse(self.deliver(self.data([sys.executable,name]),code=1)['goal_complete'])
    p.unlink()
 def test_blocked_acceptance_stops_and_unchanged_finish_preserves_budget(self):
  self.begin();data=self.data([sys.executable,'-c','pass']);data['criteria'].append({'quote':'preserve tests','checks':[],'blocker':'Production credentials absent'})
  first=self.deliver(data,code=1);self.assertEqual(first['next_action'],'stop_blocked');self.assertFalse(first['goal_complete'])
  again=self.call('finish',self.run,code=1);self.assertEqual(again['attempts'],1);self.assertFalse(again['goal_complete'])
 def test_large_file_listing_is_bounded_without_truncating_evidence(self):
  p=self.repo/('directory_'+'x'*120);p.mkdir()
  for n in range(250):(p/(str(n)+'_'+'y'*80+'.txt')).write_text('x')
  r=subprocess.run([sys.executable,str(CLI),'begin','--repo',str(self.repo),'--run-dir',str(self.run),'--goal','Implement','--context'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout);listing=next(x for x in r.stdout.splitlines()if x.startswith('FILES:'))
  self.assertLess(len(r.stdout),26000);self.assertLess(len(listing),4300);self.assertIn('truncated',listing);self.assertEqual(len(json.loads((self.run/'session.json').read_text())['original']),250)

 def test_previous_closed_and_failed_sessions_keep_frozen_test_semantics(self):
  import zipfile
  with zipfile.ZipFile(ROOT/'reports/portability-extension-2026-10-23.zip')as archive:
   legacy=self.base/'legacy.py';legacy.write_bytes(archive.read('inputs/current/integrations/native/native.py'))
  (self.repo/'app.py').write_text('value=0')
  (self.repo/'AppTest.java').write_text('import app;assert app.value==42')
  r=subprocess.run([sys.executable,str(legacy),'begin','--repo',str(self.repo),'--run-dir',str(self.run),'--goal','Implement and preserve tests.'],capture_output=True);self.assertEqual(r.returncode,0)
  data=self.data([sys.executable,'AppTest.java']);p=self.base/'criteria.json';p.write_text(json.dumps(data))
  r=subprocess.run([sys.executable,str(legacy),'deliver',str(self.run),'--criteria-file',str(p)],capture_output=True);self.assertEqual(r.returncode,1)
  (self.repo/'app.py').write_text('value=42')
  self.assertTrue(self.call('finish',self.run)['goal_complete'])
  self.assertEqual(self.call('finish',self.run)['attempts'],2)
