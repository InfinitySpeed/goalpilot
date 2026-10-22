import json
from pathlib import Path
import shutil
import unittest
from goalpilot.reuse import inventory,run_cached_finish
from tests import test_finish as fixtures

TEST="import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n def test_value(self):self.assertEqual(Path('answer.py').read_text(),'42')\n"


class Builder:
    simulated=True
    calls=0
    def execute(self,prompt,repo,*args,**kwargs):
        self.calls+=1
        (repo/'answer.py').write_text('42')
        (repo/'tests/test_delivery.py').write_text(TEST.replace('test_value','test_delivery'))
        return fixtures.result(json.dumps({'summary':'Built','assumptions':[],'limitations':[],
                    'checks':[{'id':'suite','description':'Behavior','command':['python','-m','unittest','discover'],'timeout_seconds':10}]}))


class ReuseTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def prepare(self):
        (self.repo/'tests').mkdir();(self.repo/'tests/__init__.py').write_text('')
        (self.repo/'tests/test_original.py').write_text(TEST)
        self.clone=self.root/'clone';shutil.copytree(self.repo,self.clone)
        self.cache=self.root/'cache';self.builder=Builder()

    def call(self,repo,run,goal='Deliver 42'):
        return run_cached_finish(goal,repo,run,cache=self.cache,wall_seconds=20,max_calls=6,
            adapter=self.builder,auditor=fixtures.Auditor(),audit_policy='on-interruption',review_context='local',compact_delivery=True)

    def test_exact_repeat_rechecks_behavior_without_any_model_call(self):
        self.prepare();cold=self.call(self.repo,self.run)
        self.assertTrue(cold['reuse']['published'])
        warm=self.call(self.clone,self.root/'repeat')
        self.assertEqual(warm['status'],'scope_passed');self.assertTrue(warm['reuse']['hit'])
        self.assertEqual(self.builder.calls,1);self.assertEqual(warm['calls'],[])
        self.assertEqual(warm['usage']['total_tokens'],0);self.assertTrue(warm['usage']['usage_complete'])
        self.assertTrue(warm['simulated']) # Never disguise a test-double training run as live evidence.
        self.assertTrue(all(c['passed']for c in warm['verifications'][-1]['checks']))
        self.assertEqual(inventory(self.clone),inventory(self.repo))
        from goalpilot.metrics import summarize
        self.assertTrue(summarize(warm)['reuse']['hit'])

    def test_changed_goal_requires_fresh_execution(self):
        self.prepare();self.call(self.repo,self.run)
        warm=self.call(self.clone,self.root/'repeat','Deliver 42 with a changed requirement')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)

    def test_request_for_independent_review_is_never_bypassed_by_cache(self):
        self.prepare();self.call(self.repo,self.run)
        class Reviewer:
            calls=0
            def execute(self,*args,**kwargs):
                self.calls+=1
                return fixtures.result(json.dumps({'assumptions':[],'blockers':[],'limitations':[],
                    'requirements':[{'id':'behavior','source':'Original goal','requirement':'Deliver 42',
                    'python':"from pathlib import Path\nassert Path('answer.py').read_text()=='42'\n"}]}))
        reviewer=Reviewer()
        state=run_cached_finish('Deliver 42',self.repo,self.root/'repeat',cache=self.cache,
            wall_seconds=20,max_calls=6,adapter=self.builder,auditor=reviewer,
            audit_policy='always',review_context='fresh')
        self.assertFalse(state['reuse']['hit']);self.assertEqual(reviewer.calls,1)
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(state['contract']['acceptance_origin'],'independent_context')

    def test_cached_run_keeps_new_limits_for_future_resume(self):
        self.prepare();self.call(self.repo,self.run)
        warm=run_cached_finish('Deliver 42',self.clone,self.root/'repeat',cache=self.cache,
            wall_seconds=8,max_calls=3,max_tokens=999,max_uncached_tokens=100,
            adapter=self.builder,auditor=fixtures.Auditor(),audit_policy='on-interruption',review_context='local')
        self.assertTrue(warm['reuse']['hit']);self.assertEqual(warm['contract']['budget']['max_calls'],3)
        self.assertEqual(warm['contract']['budget']['max_tokens'],999)
        self.assertEqual(warm['contract']['budget']['max_uncached_tokens'],100)
        self.assertEqual(warm['contract']['budget']['wall_seconds'],8)

    def test_invalid_budget_is_rejected_even_for_a_cache_hit(self):
        from goalpilot.model import ContractError
        self.prepare();self.call(self.repo,self.run)
        with self.assertRaises(ContractError):
            run_cached_finish('Deliver 42',self.repo,self.root/'repeat',cache=self.cache,
                max_tokens=-1,adapter=self.builder,audit_policy='on-interruption',review_context='local')
        self.assertEqual(self.builder.calls,1)

    def test_reissuing_goal_on_unchanged_delivered_project_only_revalidates(self):
        self.prepare();self.call(self.repo,self.run)
        warm=self.call(self.repo,self.root/'repeat')
        self.assertTrue(warm['reuse']['hit']);self.assertEqual(warm['reuse']['kind'],'already_delivered')
        self.assertEqual(warm['usage']['total_tokens'],0);self.assertEqual(self.builder.calls,1)

    def test_changed_final_data_requires_fresh_execution(self):
        self.prepare();self.call(self.repo,self.run)
        (self.repo/'customer.sqlite').write_bytes(b'new data since delivery')
        warm=self.call(self.repo,self.root/'repeat')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)
        self.assertEqual((self.repo/'customer.sqlite').read_bytes(),b'new data since delivery')

    def test_invalid_final_alias_is_rejected(self):
        self.prepare();self.call(self.repo,self.run)
        alias=next(self.cache.glob('*.json'));alias.write_text('{"primary_key":"../outside"}')
        warm=self.call(self.repo,self.root/'repeat')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)
        self.assertIn('alias',json.loads((self.root/'repeat/reuse-miss.json').read_text())['reason'])

    def test_changed_original_data_requires_fresh_execution(self):
        self.prepare();self.call(self.repo,self.run)
        (self.clone/'customer.sqlite').write_bytes(b'different customer data')
        warm=self.call(self.clone,self.root/'repeat')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)
        self.assertEqual((self.clone/'customer.sqlite').read_bytes(),b'different customer data')

    def test_corrupt_cached_patch_is_rejected_before_workspace_mutation(self):
        self.prepare();self.call(self.repo,self.run)
        patch=next(self.cache.glob('*/patch/answer.py'));patch.write_text('corrupt')
        warm=self.call(self.clone,self.root/'repeat')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)
        self.assertIn('integrity',json.loads((self.root/'repeat/reuse-miss.json').read_text())['reason'])

    def test_changed_frozen_acceptance_requires_fresh_execution(self):
        self.prepare();self.call(self.repo,self.run)
        (self.run/'delivery-tree/tests/test_delivery.py').write_text('tampered')
        warm=self.call(self.clone,self.root/'repeat')
        self.assertFalse(warm['reuse']['hit']);self.assertEqual(self.builder.calls,2)

    def test_failed_staged_verification_never_applies_cached_patch(self):
        from unittest.mock import patch
        self.prepare();self.call(self.repo,self.run)
        from goalpilot.reuse import replay
        before=inventory(self.clone)
        with patch('goalpilot.reuse.verify',return_value=[{'passed':False}]):
            self.assertIsNone(replay(self.cache,'Deliver 42',None,before,self.clone,self.root/'repeat',5))
        self.assertEqual(inventory(self.clone),before);self.assertFalse((self.clone/'answer.py').exists())

    def test_secret_or_symlink_disables_reuse(self):
        self.prepare();p=self.clone/'.env';p.write_text('dummy fixture only')
        with self.assertRaises(ValueError):inventory(self.clone)
        p.unlink();p.symlink_to(self.repo/'README.md')
        with self.assertRaises(ValueError):inventory(self.clone)
