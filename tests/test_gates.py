import json
from pathlib import Path
import sys
import tempfile
import unittest
from goalpilot.adapters import AgentResult
from goalpilot.finish import run_finish
from tests.test_finish import Auditor


class QuietReviewer:
    simulated=True
    calls=0
    def execute(self,*args,**kwargs):
        self.calls+=1
        return AgentResult(0,'{"counterexamples":[]}',.001,{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0},simulated=True)


class ExistingGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'tests').mkdir()
        (self.repo/'tests/test_answer.py').write_text('import unittest\nimport app\nclass Tests(unittest.TestCase):\n def test_answer(self): self.assertEqual(app.answer(),42)\n')
        (self.repo/'app.py').write_text('def answer():return 0\n')

    def test_weakened_working_tests_cannot_bypass_original_acceptance(self):
        class Worker:
            simulated=True;model=None;calls=0
            def execute(worker,prompt,repo,timeout,log_dir,**kwargs):
                worker.calls+=1
                self.assertIn('original',prompt.lower())
                (repo/'app.py').write_text(f'def answer():return {0 if worker.calls==1 else 42}\n')
                (repo/'tests/test_answer.py').write_text('print("weakened")\n')
                message=json.dumps({'checks':[{'id':'weak','description':'untrustworthy builder check', 'command':[sys.executable,'-c','assert True']}],'assumptions':[],'limitations':[]})
                return AgentResult(0,message,.001,{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0},simulated=True)
        worker=Worker();auditor=QuietReviewer()
        state=run_finish('Deliver answer',self.repo,self.root/'run',adapter=worker,auditor=auditor,wall_seconds=60,audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(worker.calls,2);self.assertEqual(auditor.calls,1)
        self.assertEqual(len(state['contract']['checks']),2)
        self.assertFalse(state['verifications'][0]['checks'][-1]['passed'])
        self.assertTrue(state['verifications'][-1]['checks'][-1]['passed'])
        flow=json.loads((self.root/'run/finish-run.json').read_text())
        self.assertFalse(flow['baseline'][0]['passed'])
        self.assertEqual((self.root/'run/original-tree/tests/test_answer.py').read_text().count('assertEqual'),1)
        from goalpilot.view import status
        self.assertEqual(status(self.root/'run')['review_calls'],1)

    def test_pytest_assertions_are_not_mistaken_for_discoverable_unittest(self):
        from goalpilot.gates import make_gate
        from goalpilot.originals import capture
        (self.repo/'tests/test_answer.py').write_text('import app\ndef test_answer(): assert app.answer()==42\n')
        run=self.root/'run';snapshot=capture(self.repo,run/'original-tree')
        self.assertIsNone(make_gate(self.repo,run,snapshot))

    def test_imported_aliased_unittest_base_is_supported(self):
        from goalpilot.gates import make_gate
        from goalpilot.originals import capture
        (self.repo/'tests/test_answer.py').write_text('from unittest import TestCase as Case\nclass Tests(Case):\n def test_answer(self): self.assertTrue(True)\n')
        run=self.root/'run';snapshot=capture(self.repo,run/'original-tree')
        self.assertIsNotNone(make_gate(self.repo,run,snapshot))

    def test_original_tests_never_mutate_original_user_data(self):
        (self.repo/'USER.txt').write_text('keep')
        (self.repo/'tests/test_answer.py').write_text('import unittest\nfrom pathlib import Path\nclass Tests(unittest.TestCase):\n def test_sandbox(self):\n  Path("USER.txt").write_text("changed in clone")\n  self.assertTrue(True)\n')
        from goalpilot.gates import make_gate
        from goalpilot.originals import capture
        from goalpilot.engine import verify
        import time
        run=self.root/'run';snapshot=capture(self.repo,run/'original-tree');gate=make_gate(self.repo,run,snapshot)
        checks=verify({'repo':str(self.repo),'checks':[gate['check']],'artifacts':gate['artifacts']},time.monotonic()+10,run/'logs')
        self.assertTrue(checks[0]['passed']);self.assertEqual((self.repo/'USER.txt').read_text(),'keep')

    def test_cached_delivery_recovery_avoids_separate_reviewer(self):
        from tests.test_autopilot import Actor
        class Worker(Actor):
            def execute(self,*args,**kwargs):
                result=super().execute(*args,**kwargs)
                if self.calls==1:result.message='Code written, final report lost'
                return result
        # No original gate for this small answer protocol.
        import shutil
        shutil.rmtree(self.repo/'tests')
        worker=Worker();auditor=Auditor()
        state=run_finish('Deliver answer',self.repo,self.root/'run',adapter=worker,auditor=auditor,wall_seconds=30,audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(worker.calls,2);self.assertEqual(auditor.calls,0)
        self.assertEqual([x['strategy'] for x in state['calls']],['build','recover-delivery'])



class ChallengeTests(unittest.TestCase):
    setUp=ExistingGateTests.setUp
    def test_focused_counterexample_is_frozen_before_builder_and_drives_repair(self):
        (self.repo/'app.py').write_text('def answer():return 0\ndef hidden():return -1\n')
        class Reviewer:
            simulated=True;calls=0
            def execute(worker,*args,**kwargs):
                worker.calls+=1
                body="import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path.cwd()))\nfrom app import hidden\nassert hidden()==7\n"
                return AgentResult(0,json.dumps({'counterexamples':[{'id':'edge','requirement':'Hidden interaction works','source':'original public API','python':body}]}),.001,{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0},simulated=True)
        class Worker:
            simulated=True;model=None;calls=0
            def execute(worker,prompt,repo,timeout,log_dir,**kwargs):
                worker.calls+=1
                (repo/'app.py').write_text(f'def answer():return 42\ndef hidden():return {7 if worker.calls>1 else -1}\n')
                return AgentResult(0,json.dumps({'checks':[{'id':'original-tests','description':'collision cannot replace host gate','command':[sys.executable,'-c','assert True']}],'assumptions':[],'limitations':[]}),.001,{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0},simulated=True)
        worker=Worker();reviewer=Reviewer()
        state=run_finish('Complete the two public APIs',self.repo,self.root/'run',wall_seconds=120,adapter=worker,auditor=reviewer,audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(worker.calls,2);self.assertEqual(reviewer.calls,1)
        self.assertEqual([x['strategy']for x in state['calls']],['challenge','build','implement'])
        self.assertFalse(next(c for c in state['verifications'][0]['checks']if c['id']=='challenge-1')['passed'])
        self.assertTrue(all(c['passed']for c in state['verifications'][-1]['checks']))
        self.assertIn('original-tests',[c['id']for c in state['contract']['checks']])


if __name__=='__main__':unittest.main()
