import json
import sys
import unittest
from goalpilot.finish import run_finish,continue_finish
from tests import test_finish as fixtures

TEST="from pathlib import Path\nimport unittest\nclass Behavior(unittest.TestCase):\n def test_answer(self):self.assertEqual(Path('answer').read_text(),'42')\n"


class LocalDeliveryTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def original(self):
        (self.repo/'README.md').write_text(''.join(f'## W{i}\n'+('Documented behavior. '*30)+'\n'for i in range(9)))
        (self.repo/'tests').mkdir();(self.repo/'tests/__init__.py').write_text('')
        (self.repo/'tests/test_original.py').write_text(TEST)

    def test_strengthened_tests_are_frozen_and_cannot_be_weakened_during_repair(self):
        self.original()
        class Builder:
            calls=0
            def execute(self,prompt,repo,*args,**kwargs):
                self.calls+=1
                if self.calls==1:
                    (repo/'answer').write_text('wrong')
                    (repo/'tests/test_delivery.py').write_text(TEST.replace('test_answer','test_delivery'))
                    return fixtures.result(json.dumps({'summary':'Built','assumptions':[],'limitations':[],
                        'checks':[{'id':'suite','description':'User behavior','command':[sys.executable,'-m','unittest','discover'],'timeout_seconds':10}]}))
                if self.calls==2:
                    for p in(repo/'tests').glob('test_*.py'):p.write_text(p.read_text().replace("self.assertEqual(Path('answer').read_text(),'42')",'self.assertTrue(True)'))
                else:(repo/'answer').write_text('42')
                return fixtures.result('done')
        builder=Builder();reviewer=fixtures.Auditor()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,max_calls=6,
                         adapter=builder,auditor=reviewer,audit_policy='on-interruption',review_context='local')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(reviewer.calls,0)
        self.assertEqual(builder.calls,3)
        self.assertEqual(state['contract']['acceptance_origin'],'builder_frozen')
        self.assertTrue(any(not c['passed']for c in state['verifications'][1]['checks']))
        self.assertTrue(all(c['passed']for c in state['verifications'][-1]['checks']))
        self.assertTrue((self.run/'delivery-tree/tests/test_delivery.py').exists())
        again=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(again['status'],'scope_passed');self.assertEqual(builder.calls,3)

    def test_thin_delivery_falls_back_to_independent_review(self):
        self.original()
        class Builder:
            def execute(self,prompt,repo,*args,**kwargs):
                (repo/'answer').write_text('42')
                return fixtures.result(json.dumps({'summary':'Built','assumptions':[],'limitations':[],
                    'checks':[{'id':'suite','description':'Behavior','command':[sys.executable,'-m','unittest','discover'],'timeout_seconds':10}]}))
        reviewer=fixtures.Auditor()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,adapter=Builder(),
                         auditor=reviewer,audit_policy='on-interruption',review_context='local')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(reviewer.calls,1)
        self.assertEqual(state['contract']['acceptance_origin'],'independent_context')
