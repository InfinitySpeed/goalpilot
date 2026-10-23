"""Real installed portable engine sessions; no model/network service dependency."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'skills/goalpilot-016'


class PortableEngineTests(unittest.TestCase):
    def test_embedded_source_is_exactly_the_promoted_engine(self):
        promoted=json.loads((ROOT/'PROMOTED_ENGINE.json').read_text())
        actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (BUNDLE/'runtime/goalpilot').glob('*.py')}
        self.assertEqual(actual,{Path(k).name:v for k,v in promoted['source_hashes'].items()})
        self.assertEqual(json.loads((BUNDLE/'MANIFEST.json').read_text())['engine']['files'],actual)

    def test_install_doctor_and_three_real_transports_for_each_host(self):
        hosts=('codex','claude-code','antigravity','hermes','generic')
        # Each host owns separate temp files, subprocess environments and ephemeral ports.
        with ThreadPoolExecutor(max_workers=len(hosts))as pool:
            runs={host:pool.submit(self.exercise_host,host)for host in hosts}
            for host,result in runs.items():
                with self.subTest(host=host):result.result()

    def exercise_host(self,host):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);target=root/'skill café';repo=root/'project';repo.mkdir()
            install=subprocess.run([sys.executable,str(ROOT/'install.py'),'--profile','candidate','--host',host,'--target',str(target)],capture_output=True,text=True,timeout=30)
            self.assertEqual(install.returncode,0,install.stderr)
            report=json.loads(install.stdout);self.assertTrue(report['verification']['ready'])
            runtime=json.loads((target/'RUNTIME.json').read_text())
            self.assertEqual(runtime['engine_version'],'0.16.0')
            self.assertEqual(runtime['entry_point'],'scripts/host.py')
            self.assertIn('assertJourney',(target/'SKILL.md').read_text())
            (repo/'tests').mkdir();(repo/'tests/__init__.py').write_text('')
            (repo/'tests/test_original.py').write_text('import unittest\nclass Original(unittest.TestCase):\n def test_original(self):self.assertTrue(True)\n')
            goal=root/'goal.txt';goal.write_text('Provide a persistent counter. Preserve tests. Café 東京.')
            run=root/'evidence';launcher=target/runtime['entry_point']
            fake=root/'foreign/goalpilot';fake.mkdir(parents=True)
            (fake/'__init__.py').write_text("raise RuntimeError('External GoalPilot import is forbidden')\n")
            env={**os.environ,'CODEX_THREAD_ID':'unrelated-host-thread','PYTHONPATH':str(fake.parent)}
            def invoke(*args):
                proc=subprocess.run([sys.executable,str(launcher),'session',*map(str,args)],cwd=repo,env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(proc.returncode,0,proc.stderr+proc.stdout)
                value=json.JSONDecoder().raw_decode(proc.stdout.lstrip())[0]
                value['_stdout']=proc.stdout
                return value
            run.mkdir()  # Caller-created empty directories are supported without resetting evidence.
            state=invoke('begin','--goal',goal.read_text(),'--repo',repo,'--run-dir',run,'--helpers','--context')
            repeat=subprocess.run([sys.executable,str(launcher),'session','begin','--goal','different goal','--repo',str(repo),'--run-dir',str(run)],capture_output=True,text=True)
            self.assertNotEqual(repeat.returncode,0)
            self.assertIn('Existing evidence preserved',repeat.stderr)
            self.assertIn('assertJourney',state['_stdout'])
            self.assertNotEqual(state.get('completion_owner'),'codex_stop_hook')
            self.assertEqual((run/'goal.bin').read_bytes(),goal.read_bytes())
            (repo/'app.py').write_text('''from goalpilot_runtime import ReplayService, jsonl_main, serve, require
import sys
class Service(ReplayService):
 def initial(self):return {'n':0}
 def handle(self,s,op,data):
  require(op=='inc','bad operation');s['n']+=1;return s['n']
if __name__=='__main__':Service.main()
''')
            (repo/'tests/test_counter.py').write_text('''import unittest,sys
from app import Service
from goalpilot_support import JourneyMixin
class Counter(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_persistence(self):
  def flow(call):
   self.assertEqual(call('inc'),1)
   self.assertEqual(call('inc'),2)
  self.assertJourney(flow)
''')
            criteria=root/'criteria.json';criteria.write_text(json.dumps({'criteria':[
                {'quote':'Provide a persistent counter.','checks':['builder-tests']},
                {'quote':'Preserve tests.','checks':['original-tests']}]}))
            invalid=root/'invalid.json';invalid.write_text(json.dumps({'criteria':[{'quote':'Invented success condition'}]}))
            proc=subprocess.run([sys.executable,str(launcher),'session','deliver',str(run),'--criteria-file',str(invalid)],cwd=repo,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertFalse((run/'acceptance.json').exists())
            state=invoke('deliver',run,'--criteria-file',criteria)
            self.assertTrue(state['closed']);self.assertTrue(state['goal_complete'])
            self.assertEqual(json.loads((run/'session-state.json').read_text())['engine_model_calls'],0)
            # Frozen delivered tests cannot be silently weakened after completion.
            (repo/'tests/test_counter.py').write_text('')
            proc=subprocess.run([sys.executable,str(launcher),'session','status',str(run)],cwd=repo,capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('Builder tests changed',proc.stderr)

    @unittest.skipIf(os.name=='nt','Codex Stop integration is POSIX-only; explicit path is tested above')
    def test_configured_codex_stop_hook_verifies_once_after_delivery(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);target=root/'skill';repo=root/'repo';repo.mkdir()
            proc=subprocess.run([sys.executable,str(ROOT/'install.py'),'--profile','candidate','--host','codex','--target',str(target)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            env={**os.environ,'CODEX_THREAD_ID':'portable-unit-hook','GOALPILOT_HOOK_STATE_DIR':str(root/'hooks')}
            native=target/'scripts/goalpilot.py';portable=target/'scripts/host.py';run=root/'evidence'
            def hook(kind):
                event={'hook_event_name':kind,'session_id':env['CODEX_THREAD_ID'],'cwd':str(repo),
                       'tool_use_id':'start-command','tool_input':{'command':'fixture command'}}
                proc=subprocess.run([sys.executable,str(native),'hook'],input=json.dumps(event),env=env,cwd=repo,capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
                return json.loads(proc.stdout)
            hook('PreToolUse')
            (repo/'tests').mkdir();(repo/'tests/__init__.py').write_text('')
            (repo/'app.py').write_text('VALUE=0\n')
            (repo/'tests/test_app.py').write_text('import unittest\nfrom app import VALUE\nclass App(unittest.TestCase):\n def test_value(self):self.assertEqual(VALUE,42)\n')
            proc=subprocess.run([sys.executable,str(portable),'session','begin','--goal','Set VALUE to 42.','--repo',str(repo),'--run-dir',str(run)],env=env,cwd=repo,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['completion_owner'],'codex_stop_hook')
            (repo/'app.py').write_text('VALUE=42\n')
            criteria=root/'criteria.json';criteria.write_text(json.dumps({'criteria':[{'quote':'Set VALUE to 42.'}]}))
            proc=subprocess.run([sys.executable,str(portable),'session','deliver',str(run),'--criteria-file',str(criteria)],env=env,cwd=repo,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            state=json.loads((run/'session-state.json').read_text())
            self.assertFalse(state['closed']);self.assertEqual(state['verifications'],[])
            result=hook('Stop');self.assertIn('goal_complete=true',result['systemMessage'])
            state=json.loads((run/'session-state.json').read_text())
            self.assertTrue(state['closed']);self.assertEqual(len(state['verifications']),1)
            self.assertEqual(state['engine_model_calls'],0)
            hook('Stop')
            self.assertEqual(len(json.loads((run/'session-state.json').read_text())['verifications']),1)

    def test_portable_entrypoint_rejects_controller_commands(self):
        proc=subprocess.run([sys.executable,str(BUNDLE/'scripts/host.py'),'go','unsafe'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,2);self.assertIn('local session commands only',proc.stderr)


if __name__=='__main__':unittest.main()
