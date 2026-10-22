"""Skill integration: real subprocesses with an explicitly offline wire fixture."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/goalpilot'


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


WIRE=r'''import json,os,pathlib,sys
# Deliberately scripted counters. No API/model inference; never utility evidence.
repo=None
for line in sys.stdin:
 p=json.loads(line)
 with open(os.environ['GOALPILOT_WIRE_LOG'],'a')as f:f.write(json.dumps(p)+'\n')
 method=p.get('method')
 if method=='initialize':reply={'userAgent':'OFFLINE_TEST_FIXTURE'}
 elif method=='thread/start':
  repo=pathlib.Path(p['params']['cwd']);reply={'thread':{'id':'fixture-thread'},'model':'OFFLINE_TEST_FIXTURE'}
 elif method=='turn/start':
  (repo/'app.py').write_text('VALUE=42\n')
  (repo/'tests/test_delivery.py').write_text('import unittest\nfrom app import VALUE\nclass Delivery(unittest.TestCase):\n def test_type(self):self.assertIsInstance(VALUE,int)\n')
  handoff={'summary':'Fixture only','assumptions':[],'limitations':['Offline fixture; not model evidence'],
  'checks':[{'id':'behavior','description':'Exercise real value behavior','command':[sys.executable,'-m','unittest','discover'],'timeout_seconds':5}]}
  print(json.dumps({'id':p['id'],'result':{'turn':{'id':'fixture-turn'}}}),flush=True)
  print(json.dumps({'method':'thread/tokenUsage/updated','params':{'threadId':'fixture-thread','tokenUsage':{'total':{'inputTokens':500,'outputTokens':50,'cachedInputTokens':200}}}}),flush=True)
  print(json.dumps({'method':'item/completed','params':{'threadId':'fixture-thread','item':{'type':'agentMessage','phase':'final_answer','text':json.dumps(handoff)}}}),flush=True)
  print(json.dumps({'method':'turn/completed','params':{'threadId':'fixture-thread','turn':{'id':'fixture-turn','status':'completed','items':[]}}}),flush=True)
  continue
 else:reply={}
 if 'id'in p:print(json.dumps({'id':p['id'],'result':reply}),flush=True)
'''


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.launcher=SKILL/'scripts/goalpilot.py'
        self.env=os.environ.copy()
        self.bin=self.root/'bin';self.bin.mkdir()
        self.env['PATH']=str(self.bin)+os.pathsep+self.env.get('PATH','')

    def test_embedded_engine_is_exactly_current_engine(self):
        manifest=json.loads((SKILL/'MANIFEST.json').read_text())
        source={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (ROOT/'goalpilot').glob('*.py')}
        embedded={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (SKILL/'runtime/goalpilot').glob('*.py')}
        self.assertEqual(source,embedded);self.assertEqual(source,manifest['engine']['files'])

    def test_bundle_install_is_self_contained_and_runs_outside_project(self):
        installer=load(SKILL/'scripts/install.py','gp_install_test')
        target=self.root/'installed/goalpilot';result=installer.install(SKILL,target)
        from goalpilot import __version__
        self.assertEqual(result['engine_version'],__version__)
        # A conflicting installed module must never replace the embedded engine.
        fake=self.root/'wrong/goalpilot';fake.mkdir(parents=True)
        (fake/'__init__.py').write_text("raise RuntimeError('wrong global package')")
        env={**self.env,'PYTHONPATH':str(fake.parent)}
        p=subprocess.run([sys.executable,str(target/'scripts/goalpilot.py'),'--help'],cwd=self.root,env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('GoalPilot',p.stdout)
        self.assertTrue(installer.install(target,target)['already_installed'])

    def test_install_refuses_to_overwrite_unrelated_skill(self):
        installer=load(SKILL/'scripts/install.py','gp_collision_test')
        target=self.root/'goalpilot';target.mkdir();(target/'SKILL.md').write_text('customer skill')
        with self.assertRaises((OSError,ValueError)):installer.install(SKILL,target)
        self.assertEqual((target/'SKILL.md').read_text(),'customer skill')

    def test_corrupt_runtime_is_rejected_without_global_fallback(self):
        target=self.root/'goalpilot';shutil.copytree(SKILL,target,ignore=shutil.ignore_patterns('__pycache__'))
        (target/'runtime/goalpilot/cli.py').write_text("raise RuntimeError('should not execute')")
        p=subprocess.run([sys.executable,str(target/'scripts/goalpilot.py'),'--help'],env=self.env,capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn('invalid or missing bundled runtime',p.stderr)
        self.assertNotIn('should not execute',p.stderr)

    def prepare(self):
        repo=self.root/'repo';repo.mkdir()
        (repo/'README.md').write_text('Expose app.VALUE as integer42 and preserve existing tests.')
        (repo/'app.py').write_text('VALUE=0\n');(repo/'tests').mkdir()
        (repo/'tests/__init__.py').write_text('')
        (repo/'tests/test_public.py').write_text('import unittest\nfrom app import VALUE\nclass Public(unittest.TestCase):\n def test_value(self):self.assertEqual(VALUE,42)\n')
        return repo

    def launch_pair(self,fatal=False):
        repo=self.prepare();initial=self.root/'initial';shutil.copytree(repo,initial)
        run=self.root/'run';wire=self.root/'wire.jsonl';self.env['GOALPILOT_WIRE_LOG']=str(wire)
        codex=self.bin/'codex';codex.write_text(f'#!{sys.executable}\n'+('raise SystemExit(97)\n'if fatal else WIRE));codex.chmod(0o700)
        goal="--keep full goal ' $(touch should-never-exist) `touch nor-this` ; café\r\nSecond line"
        file=self.root/'goal.txt';file.write_bytes(goal.encode('utf-8'))
        flags=['--repo',str(repo),'--run-dir',str(run),'--no-reuse','--wall-seconds','30','--max-calls','5','--max-tokens','9999','--max-uncached-tokens','777']
        results=[]
        for mode in ('cli','skill'):
            if mode=='skill':
                shutil.rmtree(repo);shutil.copytree(initial,repo);shutil.rmtree(run)
                wire.unlink(missing_ok=True)
            argv=[sys.executable,'-m','goalpilot','go',*flags,'--',goal]if mode=='cli'else[sys.executable,str(self.launcher),'go','--goal-file',str(file),*flags]
            proc=subprocess.run(argv,cwd=ROOT,env=self.env,capture_output=True,text=True,timeout=35)
            state=json.loads((run/('finish-run.json'if fatal else'state.json')).read_text())
            packets=[json.loads(l)for l in wire.read_text().splitlines()]if wire.exists()else[]
            results.append((proc,state,packets))
        self.assertFalse((ROOT/'should-never-exist').exists());self.assertFalse((ROOT/'nor-this').exists())
        return goal,results

    def test_cold_offline_wire_keeps_goal_budgets_calls_and_counters(self):
        goal,results=self.launch_pair()
        for proc,state,packets in results:
            self.assertEqual(proc.returncode,0,proc.stderr);self.assertEqual(state['status'],'scope_passed')
            self.assertEqual(state['contract']['goal'],goal);self.assertEqual(len(state['calls']),1)
            self.assertEqual(state['usage']['total_tokens'],550) # Scripted fixture, NOT actual usage.
            self.assertEqual(state['contract']['budget']['max_tokens'],9999)
            self.assertEqual(state['contract']['budget']['max_uncached_tokens'],777)
            turn=next(p for p in packets if p.get('method')=='turn/start')
            self.assertIn(goal,turn['params']['input'][0]['text']);self.assertEqual(turn['params']['effort'],'low')
        self.assertEqual(results[0][1]['usage'],results[1][1]['usage'])
        self.assertEqual(results[0][1]['contract']['checks'],results[1][1]['contract']['checks'])

    def test_backend_failure_remains_fatal_with_unknown_usage_and_no_retry(self):
        goal,results=self.launch_pair(fatal=True)
        for proc,state,packets in results:
            self.assertNotEqual(proc.returncode,0);self.assertEqual(state['status'],'agent_unavailable')
            self.assertEqual(len(state['calls']),1);self.assertIsNone(state['calls'][0]['result']['usage'])
            self.assertFalse(state['usage']['usage_complete'])

    def test_invalid_goal_file_fails_before_any_backend_work(self):
        p=subprocess.run([sys.executable,str(self.launcher),'go','--goal-file',str(self.root/'missing')],env=self.env,capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn('GoalPilot skill:',p.stderr)
