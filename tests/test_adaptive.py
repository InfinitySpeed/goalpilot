from pathlib import Path
import tempfile
import unittest
from goalpilot.finish import run_finish,continue_finish
from tests.test_autopilot import Actor
from tests.test_finish import Auditor,Builder


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir();self.run=self.root/'run'

    def run_adaptive(self,worker,auditor):
        return run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=worker,auditor=auditor,audit_policy='on-interruption')

    def test_normal_checkable_delivery_does_not_consume_an_audit_call(self):
        worker=Actor();auditor=Auditor();state=self.run_adaptive(worker,auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(worker.calls,1);self.assertEqual(auditor.calls,0)
        self.assertEqual(state['contract']['acceptance_origin'],'builder_proposed')
        self.assertEqual(len(state['calls']),1)
        state=continue_finish(self.run,adapter=worker,auditor=auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(worker.calls,1)

    def test_non_json_handoff_falls_back_to_independent_audit_and_repair(self):
        worker=Builder();auditor=Auditor();state=self.run_adaptive(worker,auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([c['strategy'] for c in state['calls']],['build','recover-delivery','audit'])
        self.assertEqual(state['contract']['acceptance_origin'],'independent_context')

    def test_actual_timeout_ignores_even_a_parseable_partial_handoff(self):
        class TimedOutActor(Actor):
            def execute(self,*args,**kwargs):
                r=super().execute(*args,**kwargs)
                if self.calls==1:r.returncode=124;r.timed_out=True;r.usage_complete=False
                return r
        worker=TimedOutActor();auditor=Auditor();state=self.run_adaptive(worker,auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(auditor.calls,0)
        self.assertFalse(state['usage']['usage_complete'])
        self.assertEqual(len(state['calls']),2)

    def test_failed_builder_checks_are_repaired_without_unrequested_audit(self):
        worker=Actor(first='wrong');auditor=Auditor();state=self.run_adaptive(worker,auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(worker.calls,2);self.assertEqual(auditor.calls,0)

    def test_thorough_policy_checks_even_a_successful_builder(self):
        worker=Actor();auditor=Auditor()
        state=run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=worker,auditor=auditor,audit_policy='always')
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(worker.calls,1);self.assertEqual(auditor.calls,1)


if __name__=='__main__':unittest.main()
