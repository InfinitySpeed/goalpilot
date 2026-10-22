import json
import unittest
from pathlib import Path
from goalpilot.finish import run_finish
from goalpilot.probe_lint import issues,merge_repair
from tests import test_finish as fixtures

BROKEN="""from pathlib import Path
def packet(**kw): return dict(token='default', **kw)
assert packet(token='replacement')['token'] == 'replacement'
assert Path('answer').read_text() == '42'
"""
FIXED=BROKEN.replace("dict(token='default', **kw)","dict({'token':'default'}, **kw)")


class ProbeLintTests(unittest.TestCase):
    def test_duplicate_helper_keywords_are_detected(self):
        self.assertIn('token',issues(BROKEN)[0])
        self.assertEqual(issues(FIXED),[])

    def test_shadowed_http_module_is_detected(self):
        self.assertTrue(issues('import http.client\ndef http(): return http.client.HTTPConnection("localhost")\nhttp()'))
        self.assertEqual(issues('import http.client\ndef serve(): return http.client.HTTPConnection("localhost")\nserve()'),[])

    def test_safe_nonoverriding_helper_is_not_rejected(self):
        self.assertEqual(issues("def f(**kw): return dict(token='a',**kw)\nf(id='x')"),[])

    def test_formal_parameters_are_not_forwarded_into_kwargs(self):
        program="def call(op,token='a',workspace='w',**d): return dict(token=token,workspace=workspace,**d)\ncall('get',token='reader',workspace='other')"
        self.assertEqual(issues(program),[])

    def test_module_bindings_in_with_and_try_still_shadow_imports(self):
        program="import http.client\nwith open('/dev/null') as file:\n try:\n  def http(): return http.client.HTTPConnection('localhost')\n  http()\n finally: pass"
        self.assertTrue(issues(program))

    def test_nested_function_kwargs_do_not_belong_to_outer_function(self):
        self.assertEqual(issues("def outer(**kw):\n def inner(**kw): return dict(token='a',**kw)\n return kw\nouter(token='r')"),[])

    def test_requirements_and_assertions_cannot_be_removed(self):
        old={'assumptions':[],'blockers':[],'limitations':[], 'requirements':[{'id':'p','source':'original','requirement':'r','python':BROKEN}]}
        item={**old['requirements'][0],'python':FIXED}
        self.assertEqual(merge_repair(old,{'requirements':[item]})['requirements'][0]['python'],FIXED)
        for replacement in ({'requirements':[]},{'requirements':[{**item,'source':'different'}]},{'requirements':[{**item,'python':FIXED.replace("assert Path('answer').read_text() == '42'",'assert True')}]}):
            with self.assertRaises(ValueError):merge_repair(old,replacement)


class ProbeRepairFlowTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_bad_harness_is_repaired_before_freeze_and_before_coding(self):
        outer=self
        class Reviewer:
            calls=0
            def execute(self,prompt,repo,timeout,log_dir,**kw):
                self.calls+=1
                outer.assertFalse((outer.run/'acceptance/probe-1.py').exists())
                outer.assertFalse((repo/'answer').exists())
                requirement={'id':'p','source':'original goal','requirement':'Deliver 42','python':BROKEN if self.calls==1 else FIXED}
                return fixtures.result(json.dumps({'requirements':[requirement],**({'assumptions':[],'blockers':[],'limitations':[]}if self.calls==1 else{})}))
        class Builder(fixtures.Builder):
            def execute(self,prompt,repo,*args,**kw):
                self.calls+=1;(repo/'answer').write_text('42');return fixtures.result('done')
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Documented behavior. '*30)+'\n'for i in range(9)))
        reviewer=Reviewer();builder=Builder()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,adapter=builder,auditor=reviewer,validator=fixtures.Validator(),audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([c['strategy']for c in state['calls']],['audit','audit-repair','audit-validation','build'])
        self.assertEqual(state['usage']['total_tokens'],440)
        self.assertEqual((self.run/'acceptance/probe-1.py').read_text(),FIXED)
        self.assertTrue((self.run/'pre-repair-audit.json').exists())
