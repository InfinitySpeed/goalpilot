import json
import unittest
from goalpilot.finish import run_finish,continue_finish
from goalpilot.rpc import AppServerAdapter
from tests import test_finish as fixtures
from tests import test_local_delivery as local
from tests import test_v2 as rpc


class ReasoningPolicyTests(unittest.TestCase):
    setUp=fixtures.FinishTests.setUp

    def test_low_build_escalates_only_when_host_checks_fail_and_survives_resume(self):
        local.LocalDeliveryTests.original(self)
        class Builder:
            effort='low'
            efforts=[]
            def execute(self,prompt,repo,*args,**kwargs):
                self.efforts.append(self.effort)
                if len(self.efforts)==1:
                    (repo/'answer').write_text('wrong')
                    (repo/'tests/test_delivery.py').write_text(local.TEST.replace('test_answer','test_delivery'))
                    return fixtures.result(json.dumps({'summary':'Built','assumptions':[],'limitations':[],
                        'checks':[{'id':'suite','description':'Behavior','command':['python','-m','unittest','discover'],'timeout_seconds':10}]}))
                (repo/'answer').write_text('42');return fixtures.result('fixed')
        builder=Builder();reviewer=fixtures.Auditor()
        state=run_finish('Complete platform',self.repo,self.run,wall_seconds=30,max_calls=6,
                         adapter=builder,auditor=reviewer,audit_policy='on-interruption',review_context='local',initial_effort='low')
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(builder.efforts,['low','medium'])
        self.assertEqual(state['contract']['repair_effort'],'medium');self.assertEqual(reviewer.calls,0)
        (self.repo/'answer').write_text('regressed');builder.effort='low'
        again=continue_finish(self.run,adapter=builder,auditor=reviewer)
        self.assertEqual(again['status'],'scope_passed');self.assertEqual(builder.efforts,['low','medium','medium'])


class ReasoningWireTests(unittest.TestCase):
    setUp=rpc.V2Tests.setUp

    def test_requested_effort_reaches_actual_turn_request(self):
        self.shim.write_text(self.shim.read_text().replace("elif method=='turn/start':", "elif method=='turn/start':\n  assert p['params']['effort']=='low'"))
        with AppServerAdapter(executable=str(self.shim),effort='low')as adapter:
            result=adapter.execute('Test effort',self.repo,2,self.root/'call')
        self.assertEqual(result.returncode,0);self.assertEqual(result.telemetry['requested_effort'],'low')
