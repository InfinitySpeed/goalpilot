import json
from pathlib import Path
import sys
import tempfile
import unittest

from goalpilot.adapters import AgentResult
from goalpilot.autopilot import run_autopilot
from goalpilot.model import ContractError


class Actor:
    simulated=True
    def __init__(self,first='42'):
        self.calls=0
        self.first=first
        self.schemas=[]
    def execute(self,prompt,repo,timeout,log_dir,**kwargs):
        self.calls+=1
        self.schemas.append(kwargs.get('schema'))
        (repo/'answer').write_text(self.first if self.calls==1 else '42')
        check={'id':'answer','description':'The actual answer is correct',
               'command':[sys.executable,'-c',"from pathlib import Path; assert Path('answer').read_text()=='42'"],
               'timeout_seconds':1}
        message=json.dumps({'summary':'answer delivered','assumptions':[],'limitations':[],'checks':[check]}) if kwargs.get('schema') else 'Corrected the answer'
        return AgentResult(0,message,.001,{'input_tokens':100,'output_tokens':10,'cached_input_tokens':50},simulated=True)


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/'repo';self.repo.mkdir()

    def test_one_session_delivers_and_verifies_without_a_planning_call(self):
        actor=Actor()
        state=run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,wall_seconds=10)
        self.assertEqual(actor.calls,1)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(state['contract']['scope'],'inferred')
        self.assertEqual([x['strategy'] for x in state['calls']],['implement'])
        self.assertEqual(state['usage']['total_tokens'],110)
        self.assertTrue((self.root/'run/mission.json').is_file())

    def test_failed_check_is_repaired_with_same_adapter_and_charged_budget(self):
        actor=Actor(first='wrong')
        state=run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,wall_seconds=10,max_calls=2)
        self.assertEqual(actor.calls,2)
        self.assertIsNotNone(actor.schemas[0])
        self.assertIsNone(actor.schemas[1])
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(state['usage']['total_tokens'],220)

    def test_bootstrap_consumes_the_call_budget(self):
        actor=Actor(first='wrong')
        state=run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,wall_seconds=10,max_calls=1)
        self.assertEqual(actor.calls,1)
        self.assertEqual(state['status'],'budget_exhausted')

    def test_explicit_empty_contract_is_not_silently_replaced(self):
        actor=Actor()
        with self.assertRaises(ContractError):
            run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,checks=[])
        self.assertEqual(actor.calls,0)

    def test_trusted_contract_skips_bootstrap_schema(self):
        actor=Actor()
        checks=[{'id':'answer','description':'Answer is correct','command':[sys.executable,'-c',"from pathlib import Path; assert Path('answer').read_text()=='42'"]}]
        state=run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,checks=checks,wall_seconds=10)
        self.assertEqual(actor.calls,1)
        self.assertEqual(actor.schemas,[None])
        self.assertEqual(state['status'],'completed')

    def test_second_start_does_not_reset_budget_or_overwrite_artifacts(self):
        actor=Actor()
        run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,wall_seconds=10)
        with self.assertRaises(ContractError):
            run_autopilot('Make an answer',self.repo,self.root/'run',adapter=actor,wall_seconds=10)
        self.assertEqual(actor.calls,1)


if __name__=='__main__':unittest.main()
