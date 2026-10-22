import unittest
from goalpilot.scope import completion_review
from tests import test_finish as fixtures


class ScopeTests(unittest.TestCase):
    def test_small_goal_does_not_force_paid_review(self):
        self.assertFalse(completion_review('Fix the complete CSV export','## Export\nSimple public API')['required'])

    def test_multi_workstream_contract_is_detected_without_model(self):
        original=''.join(f'## Workflow {i}\n'+('Documented public behavior. '*22)+'\n'for i in range(9))
        result=completion_review('Make this reliable',original)
        self.assertTrue(result['required']);self.assertEqual(len(result['sections']),9)


class CompletionReviewTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_broad_goal_freezes_independent_review_before_builder_handoff(self):
        import json
        from goalpilot.finish import run_finish
        original=''.join(f'## Workflow {i}\n'+('Documented public behavior. '*22)+'\n'for i in range(9))
        (self.repo/'README.md').write_text(original)
        class Worker(fixtures.Builder):
            def execute(worker,*args,**kwargs):
                result=super().execute(*args,**kwargs)
                result.message=json.dumps({'checks':[{'id':'weak','description':'Builder check','command':['true']}],'assumptions':[],'limitations':[]})
                return result
        worker=Worker();auditor=fixtures.Auditor()
        state=run_finish('Deliver the platform',self.repo,self.run,adapter=worker,auditor=auditor,validator=fixtures.Validator(),wall_seconds=15,audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(auditor.calls,1)
        self.assertEqual([c['strategy']for c in state['calls']],['audit','audit-validation','build','implement'])
        flow=json.loads((self.run/'finish-run.json').read_text())
        self.assertEqual(flow['config']['audit_policy'],'on-interruption')
        self.assertEqual(flow['effective_audit_policy'],'always')
        self.assertTrue(flow['completion_review']['required'])
