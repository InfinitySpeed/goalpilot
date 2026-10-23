"""Offline cross-platform installation, lock, timeout and frozen-closure checks."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import lock
from goalpilot.model import ContractError
from goalpilot.process import run_process


def main():
    with tempfile.TemporaryDirectory(prefix='goalpilot-onboarding-')as folder:
        root=Path(folder).resolve();target=root/'skill with spaces';repo=root/'project café';repo.mkdir()
        installed=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'install.py'),'--host','generic','--target',str(target)],capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert installed.returncode==0,installed.stderr
        assert json.loads(installed.stdout)['verification']['ready']
        (repo/'tests').mkdir();(repo/'tests/__init__.py').write_text('',encoding='utf-8')
        (repo/'app.py').write_text('VALUE=0\n',encoding='utf-8')
        (repo/'tests/test_app.py').write_text('import unittest\nfrom app import VALUE\nclass App(unittest.TestCase):\n def test_value(self):self.assertEqual(VALUE,42)\n',encoding='utf-8')
        goal=root/'goal.txt';goal.write_text('Set VALUE to42; preserve the original test. Café 東京.',encoding='utf-8');run=root/'run'
        launcher=target/'scripts/host.py'
        def invoke(*args):
            result=subprocess.run([sys.executable,'-X','utf8',str(launcher),'session',*map(str,args)],cwd=repo,capture_output=True,text=True,encoding='utf-8',timeout=30)
            assert result.returncode==0,(result.stdout,result.stderr)
            return json.JSONDecoder().raw_decode(result.stdout.lstrip())[0]
        state=invoke('begin','--goal-file',goal,'--repo',repo,'--run-dir',run,'--helpers','--context')
        assert not state['closed']
        (repo/'app.py').write_text('VALUE=42\n',encoding='utf-8')
        criteria=root/'criteria.json'
        criteria.write_text(json.dumps({'criteria':[{'quote':'Set VALUE to42'},{'quote':'preserve the original test'}]}),encoding='utf-8')
        state=invoke('deliver',run,'--criteria-file',criteria)
        assert state['closed']and state['status']=='scope_passed'and state['goal_complete'],state
        assert json.loads((run/'session-state.json').read_text(encoding='utf-8'))['engine_model_calls']==0
        # A competing process cannot acquire the same mission lock.
        guard=root/'competing.lock'
        with lock(guard):
            result=subprocess.run([sys.executable,'-X','utf8','-c','from pathlib import Path; from goalpilot.engine import lock;\nwith lock(Path(__import__("sys").argv[1])):pass',str(guard)],cwd=ROOT,capture_output=True,text=True)
            assert result.returncode!=0 and 'already running'in result.stderr
        timed=run_process([sys.executable,'-c','import time;time.sleep(10)'],root,.2)
        assert timed.timed_out and timed.duration_seconds<5
        # Cleanup must also catch a child when its parent has already exited.
        marker=root/'orphan-marker'
        child='import time,pathlib;time.sleep(1);pathlib.Path('+repr(str(marker))+').write_text("orphan")'
        parent='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);print("done")'
        result=run_process([sys.executable,'-c',parent],root,3)
        assert result.returncode==0,result
        import time
        time.sleep(1.2)
        assert not marker.exists(),'Orphan child escaped cleanup'
    print('PASS: offline install/doctor, Unicode paths and goal, original+builder frozen gates, process lock contention, timeout and orphan cleanup;0model calls.')


if __name__=='__main__':main()
