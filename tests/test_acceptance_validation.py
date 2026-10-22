import json
import unittest
from goalpilot.acceptance_validation import apply_validation
from goalpilot.finish import run_finish
from tests import test_finish as fixtures

PROGRAM="from pathlib import Path\nvalues=list(range(3))\nassert len(values)==4\nassert Path('answer').read_text()=='42'\n"


class ArithmeticValidationTests(unittest.TestCase):
    def audit(self,program=PROGRAM):
        return {'assumptions':[],'blockers':[],'limitations':[], 'requirements':[{'id':'p','source':'Original three inputs','requirement':'Return all three values','python':program}]}

    def patch(self,old='assert len(values)==4',new='assert len(values)==3'):
        return {'patches':[{'id':'p','old':old,'new':new,'source':'Original three inputs','reason':'range(3) has three values, so 3 not4'}],'limitations':[]}

    def test_only_calculated_expectation_changes_and_original_is_retained(self):
        audit=self.audit();fixed=apply_validation(audit,self.patch())
        self.assertIn('==4',audit['requirements'][0]['python'])
        self.assertIn('==3',fixed['requirements'][0]['python'])
        self.assertEqual(fixed['requirements'][0]['source'],audit['requirements'][0]['source'])

    def test_cannot_delete_assertion_change_operator_or_fixture(self):
        for old,new in [('assert len(values)==4','assert True'),('==4','>=4'),('range(3)','range(4)'),("=='42'","=='wrong'")]:
            with self.assertRaises(ValueError):apply_validation(self.audit(),self.patch(old,new))

    def test_cannot_change_control_flow_or_inequality_threshold(self):
        for program,old,new in [('if 1==2: pass\nassert True','==2','==1'),('assert len([1,2,3])>4','>4','>0')]:
            with self.assertRaises(ValueError):apply_validation(self.audit(program),self.patch(old,new))

    def test_unknown_id_and_missing_justification_are_rejected(self):
        for field,value in [('id','missing'),('reason',''),('source','')]:
            patch=self.patch();patch['patches'][0][field]=value
            with self.assertRaises(ValueError):apply_validation(self.audit(),patch)


class ArithmeticFlowTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_fresh_validation_corrects_expectation_before_builder_sees_probe(self):
        outer=self
        class Auditor(fixtures.Auditor):
            def execute(self,*args,**kwargs):return fixtures.result(json.dumps(ArithmeticValidationTests().audit()))
        class Validator(fixtures.Validator):
            def execute(self,prompt,*args,**kwargs):
                outer.assertFalse((outer.repo/'answer').exists())
                outer.assertFalse((outer.run/'acceptance/probe-1.py').exists())
                return fixtures.result(json.dumps(ArithmeticValidationTests().patch()))
        class Builder(fixtures.Builder):
            def execute(self,prompt,repo,*args,**kwargs):
                outer.assertIn('assert len(values)==3',prompt)
                (repo/'answer').write_text('42');return fixtures.result('complete')
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Original documented behavior. '*30)+'\n'for i in range(9)))
        state=run_finish('Finish the platform',self.repo,self.run,wall_seconds=30,adapter=Builder(),auditor=Auditor(),validator=Validator(),audit_policy='on-interruption')
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([c['strategy']for c in state['calls']],['audit','audit-validation','build'])
        before=json.loads((self.run/'pre-validation-audit.json').read_text())
        self.assertIn('==4',before['requirements'][0]['python'])
        self.assertIn('==3',(self.run/'acceptance/probe-1.py').read_text())
