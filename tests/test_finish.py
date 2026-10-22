"""Mechanism tests; actors are explicitly simulated, never efficacy evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from goalpilot.adapters import AgentResult
from goalpilot.finish import continue_finish, parse_audit, run_finish
from goalpilot.model import ContractError


def result(message='', code=0, fatal=False):
    return AgentResult(code, message, .001,
        {'input_tokens':100,'output_tokens':10,'cached_input_tokens':50},
        fatal=fatal, simulated=True, usage_complete=True)


class Builder:
    simulated=True
    model=None
    def __init__(self, interrupt=False, timeout=False):
        self.calls=0;self.interrupt=interrupt;self.timeout=timeout
    def execute(self,prompt,repo,timeout,log_dir,**kwargs):
        self.calls+=1
        (repo/'answer').write_text('wrong' if self.calls==1 else '42')
        if self.interrupt:
            self.interrupt=False
            raise KeyboardInterrupt()
        return result('Built it',124 if self.timeout and self.calls==1 else 0)


class Auditor:
    simulated=True
    def __init__(self,unverified=None,code=0,fatal=False):
        self.calls=0;self.unverified=unverified or [];self.code=code;self.fatal=fatal
    def execute(self,prompt,repo,timeout,log_dir,**kwargs):
        self.calls+=1
        assert kwargs['planning'] is True
        self.prompt=prompt
        self.timeout=timeout
        return result(json.dumps({'assumptions':[], 'blockers':self.unverified, 'limitations':[],
            'requirements':[{'id':'correctness','requirement':'Deliver 42','source':'Original goal',
                'python':"from pathlib import Path\nassert Path('answer').read_text() == '42'\n"}]}),self.code,self.fatal)


class FinishTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        (self.repo/'README.md').write_text('Original interface')
        self.run=self.root/'run'

    def run_finish(self,builder=None,auditor=None,**kwargs):
        self.builder=builder or Builder();self.auditor=auditor or Auditor()
        return run_finish('Deliver 42',self.repo,self.run,adapter=self.builder,
                          auditor=self.auditor,wall_seconds=10,**kwargs)

    def test_audit_finds_builder_missed_behavior_and_repair_is_charged(self):
        state=self.run_finish()
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual([x['strategy'] for x in state['calls']],['build','audit','implement'])
        self.assertEqual(state['usage']['total_tokens'],330)
        self.assertEqual(self.builder.calls,2)
        self.assertEqual(self.auditor.calls,1)
        self.assertIn('Original interface',self.auditor.prompt)
        self.assertFalse(state['verifications'][0]['checks'][0]['passed'])
        self.assertTrue(state['verifications'][-1]['checks'][0]['passed'])
        self.assertLess(self.auditor.timeout,5)

    def test_timed_out_builder_without_json_is_still_audited_and_repaired(self):
        state=self.run_finish(Builder(timeout=True))
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(len(state['calls']),3)

    def test_interrupt_before_contract_resumes_without_rebuilding_or_resetting_calls(self):
        builder=Builder(interrupt=True);auditor=Auditor()
        with self.assertRaises(KeyboardInterrupt):self.run_finish(builder,auditor)
        self.assertTrue((self.run/'finish-run.json').exists())
        state=continue_finish(self.run,adapter=builder,auditor=auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(len(state['calls']),3)
        self.assertTrue(state['calls'][0]['interrupted'])
        self.assertEqual(state['usage']['calls_without_usage'],1)
        self.assertGreaterEqual(state['active_seconds'],5)

    def test_unverifiable_requirement_prevents_success_claim(self):
        state=self.run_finish(auditor=Auditor(['Production deployment requires access']))
        self.assertEqual(state['status'],'partial')

    def test_tampered_external_tests_block_completion_and_model_retries(self):
        self.run_finish()
        (self.run/'acceptance/probe-1.py').write_text('assert True')
        state=continue_finish(self.run,adapter=self.builder,auditor=self.auditor)
        self.assertEqual(state['status'],'verification_unavailable')
        self.assertEqual(self.builder.calls,2)

    def test_resume_completed_repo_uses_no_model_but_revalidates(self):
        self.run_finish()
        state=continue_finish(self.run,adapter=self.builder,auditor=self.auditor)
        self.assertEqual(state['status'],'scope_passed')
        self.assertEqual(self.builder.calls,2)
        self.assertEqual(self.auditor.calls,1)

    def test_fatal_provider_error_has_no_hidden_retry(self):
        with self.assertRaises(ContractError):self.run_finish(auditor=Auditor(code=1,fatal=True))
        flow=json.loads((self.run/'finish-run.json').read_text())
        self.assertEqual(flow['status'],'agent_unavailable')
        self.assertEqual(len(flow['calls']),2)

    def test_invalid_or_assertion_free_audit_is_not_success(self):
        data={'assumptions':[],'blockers':[], 'limitations':[],'requirements':[{'id':'a','requirement':'r','source':'goal','python':'print("ok")'}]}
        with self.assertRaises(ContractError):parse_audit(json.dumps(data))

    def test_insufficient_budget_rejected_before_any_calls(self):
        with self.assertRaises(ContractError):self.run_finish(max_calls=2)
        self.assertEqual(self.builder.calls,0)
        self.assertEqual(self.auditor.calls,0)

    def test_second_start_cannot_overwrite_evidence(self):
        self.run_finish()
        with self.assertRaises(ContractError):self.run_finish()


if __name__=='__main__':unittest.main()


class Validator:
    simulated=True
    calls=0
    def execute(self,*args,**kwargs):
        self.calls+=1
        return result('{"patches":[],"limitations":[]}')
