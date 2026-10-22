import hashlib
import json
import unittest
from goalpilot.finish import run_finish,continue_finish
from goalpilot.model import ContractError
from goalpilot.support import provision
from tests import test_finish as fixtures
from tests import test_local_delivery as local


class SupportTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_existing_file_is_never_overwritten(self):
        path=self.repo/'goalpilot_support.py';path.write_text('customer code')
        with self.assertRaises(ContractError):provision(self.repo)
        self.assertEqual(path.read_text(),'customer code')

    def test_symlink_is_never_followed(self):
        target=self.repo/'customer';target.write_text('private')
        (self.repo/'goalpilot_support.py').symlink_to(target)
        with self.assertRaises(ContractError):provision(self.repo)
        self.assertEqual(target.read_text(),'private')

    def test_project_without_supported_unittest_gate_gets_no_python_helper(self):
        builder=fixtures.Builder();reviewer=fixtures.Auditor()
        state=run_finish('Deliver 42',self.repo,self.run,wall_seconds=20,max_calls=6,
                         adapter=builder,auditor=reviewer,audit_policy='on-interruption',review_context='local',compact_delivery=True)
        self.assertEqual(state['status'],'scope_passed')
        self.assertFalse((self.repo/'goalpilot_support.py').exists())

    def test_compact_delivery_has_real_frozen_helper_and_survives_resume(self):
        local.LocalDeliveryTests.original(self)
        class Builder:
            calls=0
            def execute(self,prompt,repo,*args,**kwargs):
                self.calls+=1
                assert 'table-driven' in prompt
                assert (repo/'goalpilot_support.py').is_file()
                (repo/'answer').write_text('42')
                (repo/'tests/test_delivery.py').write_text(local.TEST.replace('test_answer','test_delivery'))
                return fixtures.result(json.dumps({'summary':'Built','assumptions':[],'limitations':[],
                    'checks':[{'id':'suite','description':'Behavior','command':['python','-m','unittest','discover'],'timeout_seconds':10}]}))
        builder=Builder();reviewer=fixtures.Auditor()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,max_calls=6,
                         adapter=builder,auditor=reviewer,audit_policy='on-interruption',review_context='local',compact_delivery=True)
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(builder.calls,1)
        helper=next(a for a in state['contract']['artifacts']if a['path'].endswith('goalpilot_support.py'))
        self.assertEqual(helper['sha256'],hashlib.sha256((self.repo/'goalpilot_support.py').read_bytes()).hexdigest())
        self.assertEqual(continue_finish(self.run,adapter=builder,auditor=reviewer)['status'],'scope_passed')
        self.assertEqual(builder.calls,1)
