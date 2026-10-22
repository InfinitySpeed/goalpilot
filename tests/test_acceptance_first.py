"""Frozen independent checks must precede coding; real assertions still gate closure."""
import json
import unittest

from goalpilot.finish import run_finish, continue_finish
from goalpilot.model import ContractError
from tests import test_finish as fixtures


class AcceptanceFirstTests(unittest.TestCase):
    setUp = fixtures.FinishTests.setUp

    def broad(self):
        (self.repo/'README.md').write_text(''.join(
            f'## Workflow {i}\n'+('Public documented behavior. '*22)+'\n' for i in range(9)))

    def run_goal(self, builder, reviewer, **kwargs):
        self.broad()
        return run_finish('Finish the platform',self.repo,self.run,adapter=builder,
                          auditor=reviewer,validator=fixtures.Validator(),wall_seconds=30,audit_policy='on-interruption',**kwargs)

    def test_prebuild_frozen_check_visible_and_no_postbuild_review(self):
        outer=self
        class Reviewer(fixtures.Auditor):
            def execute(self,*args,**kwargs):
                outer.assertFalse((outer.repo/'answer').exists())
                return super().execute(*args,**kwargs)
        class Builder(fixtures.Builder):
            def execute(self,prompt,repo,timeout,log_dir,**kwargs):
                outer.assertIn('FROZEN CHECKS',prompt)
                outer.assertEqual((outer.run/'acceptance/probe-1.py').read_text(),
                                 "from pathlib import Path\nassert Path('answer').read_text() == '42'\n")
                self.calls+=1;(repo/'answer').write_text('42')
                return fixtures.result('delivered')
        builder=Builder();reviewer=Reviewer();state=self.run_goal(builder,reviewer)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([c['strategy'] for c in state['calls']],['audit','audit-validation','build'])
        self.assertEqual(state['contract']['acceptance_origin'],'independent_prebuild')
        self.assertEqual(state['usage']['total_tokens'],330)
        again=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(again['status'],'scope_passed')
        self.assertEqual((builder.calls,reviewer.calls),(1,1))

    def test_wrong_implementation_still_requires_repair(self):
        state=self.run_goal(fixtures.Builder(),fixtures.Auditor())
        self.assertEqual([c['strategy'] for c in state['calls']],['audit','audit-validation','build','implement'])
        self.assertFalse(state['verifications'][0]['checks'][0]['passed'])
        self.assertTrue(state['verifications'][-1]['checks'][0]['passed'])

    def test_invalid_review_does_not_start_builder(self):
        class Invalid(fixtures.Auditor):
            def execute(self,*args,**kwargs):return fixtures.result('{"requirements":[]}')
        builder=fixtures.Builder()
        with self.assertRaises(ContractError):self.run_goal(builder,Invalid())
        self.assertEqual(builder.calls,0)

    def test_external_blocker_still_prevents_closure(self):
        state=self.run_goal(fixtures.Builder(),fixtures.Auditor(['External deployment access missing']))
        self.assertEqual(state['status'],'partial')

    def test_after_option_preserves_original_review_order(self):
        state=self.run_goal(fixtures.Builder(),fixtures.Auditor(),review_timing='after')
        self.assertEqual([c['strategy'] for c in state['calls']],['build','audit','implement'])

    def test_probe_tampering_prevents_repair_and_success(self):
        outer=self
        class Tamper(fixtures.Builder):
            def execute(self,*args,**kwargs):
                value=super().execute(*args,**kwargs)
                (outer.run/'acceptance/probe-1.py').write_text('assert True')
                return value
        builder=Tamper();state=self.run_goal(builder,fixtures.Auditor())
        self.assertEqual(state['status'],'verification_unavailable')
        self.assertEqual(builder.calls,1)
