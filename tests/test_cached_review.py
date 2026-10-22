import json
import unittest
from goalpilot.finish import run_finish,continue_finish
from goalpilot.probe_lint import issues
from goalpilot.quota import compare
from tests import test_finish as fixtures


class CachedReviewTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_single_review_keeps_frozen_independent_checks_and_repairs_bad_code(self):
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Documented behavior. '*30)+'\n'for i in range(9)))
        reviewer=fixtures.Auditor();builder=fixtures.Builder()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,adapter=builder,
                         auditor=reviewer,audit_policy='on-interruption',review_context='single')
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([c['strategy']for c in state['calls']],['audit','build','implement'])
        self.assertEqual(reviewer.calls,1)
        self.assertIn('no subsequent arithmetic-review turn',reviewer.prompt)
        self.assertFalse(state['verifications'][0]['checks'][0]['passed'])
        self.assertTrue(state['verifications'][-1]['checks'][0]['passed'])
        self.assertTrue((self.run/'acceptance/probe_helpers.py').exists())
        self.assertEqual((self.run/'acceptance/probe-1.py').read_text(),"from pathlib import Path\nassert Path('answer').read_text() == '42'\n")
        again=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(again['status'],'scope_passed');self.assertEqual(reviewer.calls,1)

    def test_reviewer_reuses_context_but_builder_remains_separate_and_checks_frozen(self):
        outer=self
        class Reviewer(fixtures.Auditor):
            def execute(self,prompt,*args,**kwargs):
                if prompt.startswith('Recheck the arithmetic'):
                    self.calls+=1
                    outer.assertFalse((outer.repo/'answer').exists())
                    return fixtures.result(json.dumps({'patches':[],'limitations':[]}))
                outer.assertIn('probe_helpers',prompt)
                return super().execute(prompt,*args,**kwargs)
        class Builder(fixtures.Builder):
            def execute(self,prompt,repo,*args,**kwargs):
                outer.assertTrue((outer.run/'acceptance/probe_helpers.py').exists())
                outer.assertIn("assert Path('answer').read_text() == '42'",prompt)
                self.calls+=1;(repo/'answer').write_text('42')
                return fixtures.result('done')
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Documented behavior. '*30)+'\n'for i in range(9)))
        reviewer=Reviewer();builder=Builder()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,adapter=builder,
                         auditor=reviewer,audit_policy='on-interruption',review_context='cached')
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual((reviewer.calls,builder.calls),(2,1))
        self.assertEqual([c['strategy']for c in state['calls']],['audit','audit-validation','build'])
        self.assertTrue(any(a['path'].endswith('probe_helpers.py')for a in state['contract']['artifacts']))
        again=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(again['status'],'scope_passed');self.assertEqual((reviewer.calls,builder.calls),(2,1))
        (self.run/'acceptance/probe_helpers.py').write_text('raise Exception("changed")')
        tampered=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(tampered['status'],'verification_unavailable')

    def test_indirect_duplicate_kwargs_are_caught_without_flagging_safe_mapping_merge(self):
        program="def packet(**data): return dict(token='admin',**data)\ndef api(op,**kw): return packet(**kw)\napi('get',token='reader')"
        self.assertTrue(issues(program))
        self.assertEqual(issues(program.replace("dict(token='admin',**data)","{'token':'admin',**data}")),[])

    def test_cold_resume_supplies_full_contract_and_programs_to_new_validation_context(self):
        class Lost(fixtures.Auditor):
            def execute(self,prompt,*args,**kwargs):
                if prompt.startswith('Recheck the arithmetic'):raise OSError('Worker lost before reply')
                return super().execute(prompt,*args,**kwargs)
        outer=self
        class NewContext:
            def execute(self,prompt,*args,**kwargs):
                outer.assertIn('Original public contract:',prompt)
                outer.assertIn("assert Path('answer').read_text() == '42'",prompt)
                return fixtures.result(json.dumps({'patches':[],'limitations':[]}))
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Documented behavior. '*30)+'\n'for i in range(9)))
        builder=fixtures.Builder()
        with self.assertRaises(OSError):
            run_finish('Complete platform',self.repo,self.run,wall_seconds=60,max_calls=6,
                       adapter=builder,auditor=Lost(),audit_policy='on-interruption',review_context='cached')
        state=continue_finish(self.run,adapter=builder,auditor=NewContext())
        self.assertEqual(state['status'],'scope_passed')
        self.assertTrue(state['calls'][1]['interrupted'])
        self.assertFalse(state['usage']['usage_complete'])

    def test_quota_display_never_becomes_exact_consumption_and_resets_are_rejected(self):
        def snap(used,reset=100):return {'buckets':{'codex':{'primary':{'usedPercent':used,'resetsAt':reset,'windowDurationMins':300}}}}
        r=compare(snap(40),snap(40));self.assertEqual(r['windows'][0]['reported_percentage_point_delta'],0)
        self.assertFalse(r['exact_attributable_quota_known'])
        self.assertIsNone(compare(snap(40),snap(1,200))['windows'][0]['reported_percentage_point_delta'])
        self.assertFalse(compare(snap(40),snap(39))['windows'][0]['usable_monotonic_observation'])
