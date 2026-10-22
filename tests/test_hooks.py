"""Real local subprocess/verification tests, no paid model or utility assertions."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from goalpilot import hooks,session as gp
from goalpilot.model import ContractError
from tests.test_session import SessionTests


class HookTests(unittest.TestCase):
    setUp=SessionTests.setUp
    write_handoff=SessionTests.write_handoff
    state=SessionTests.state
    start=SessionTests.start

    def activate(self):
        self.registry=self.root/'registry';self.ident='offline-fixture-codex-thread'
        self.enterContext(patch.dict(os.environ,{'GOALPILOT_HOOK_STATE_DIR':str(self.registry),'CODEX_THREAD_ID':self.ident}))
        hooks.handle(self.event('PreToolUse',command='first tool',ident='first'))
        return self.start()

    def event(self,kind,command='',ident='fixture-tool',output=None):
        return {'session_id':self.ident,'cwd':str(self.repo),'hook_event_name':kind,
                'tool_use_id':ident,'tool_input':{'command':command},'tool_response':output}

    def test_inactive_hook_does_not_call_model_or_touch_repo(self):
        self.registry=self.root/'registry';self.ident='inactive'
        with patch.dict(os.environ,{'GOALPILOT_HOOK_STATE_DIR':str(self.registry)}),patch('goalpilot.adapters.CodexAdapter.execute',side_effect=AssertionError('model')):
            self.assertEqual(hooks.handle(self.event('PreToolUse')), {})
            self.assertEqual(hooks.handle(self.event('Stop')), {})
        self.assertFalse(self.run.exists())

    def test_stop_owns_verification_without_a_model_or_fake_closure(self):
        self.assertEqual(self.activate()['completion_owner'],'codex_stop_hook')
        self.write_handoff();gp.submit(self.run,self.handoff)
        with patch('goalpilot.adapters.CodexAdapter.execute',side_effect=AssertionError('model')):
            out=hooks.handle(self.event('Stop'))
        self.assertIn('goal_complete=true',out['systemMessage'])
        self.assertTrue(self.state()['closed']);self.assertEqual(self.state()['engine_model_calls'],0)
        frozen=(self.run/'acceptance.json').read_bytes()
        hooks.handle(self.event('Stop'))
        self.assertEqual(len(self.state()['verifications']),1)
        self.assertEqual((self.run/'acceptance.json').read_bytes(),frozen)
        (self.repo/'app.py').write_text('def normalize(xs):return []\n')
        self.assertEqual(hooks.handle(self.event('Stop')),{})
        self.assertEqual(len(self.state()['verifications']),1)

    def test_failed_stop_requests_same_session_repair_and_same_checks(self):
        self.activate();self.write_handoff();gp.submit(self.run,self.handoff)
        (self.repo/'app.py').write_text('def normalize(xs):return []\n')
        failed=hooks.handle(self.event('Stop'))
        self.assertEqual(failed['decision'],'block');self.assertIn('SAME original goal',failed['reason'])
        self.assertFalse(self.state()['closed']);frozen=(self.run/'acceptance.json').read_bytes()
        (self.repo/'app.py').write_bytes((self.run/'originals/app.py').read_bytes())
        hooks.handle({**self.event('Stop'),'stop_hook_active':True})
        self.assertTrue(self.state()['closed']);self.assertEqual((self.run/'acceptance.json').read_bytes(),frozen)
        self.assertEqual(len(self.state()['verifications']),2)

    def test_stop_without_criteria_requires_mapping_before_it_can_close(self):
        self.activate();out=hooks.handle(self.event('Stop'))
        self.assertEqual(out['decision'],'block');self.assertIn('inventory every atomic outcome',out['reason'])
        self.assertFalse(self.state()['closed']);self.assertFalse((self.run/'acceptance.json').exists())

    def test_budget_expiry_never_requests_more_model_work_or_marks_complete(self):
        self.activate();state=self.state();state['started_at']-=100;gp.sealed_write(self.run,'session-state.json',state)
        out=hooks.handle(self.event('Stop'));self.assertFalse(out['continue']);self.assertNotIn('decision',out)
        self.assertIn('OPEN',out['stopReason']);self.assertFalse(self.state()['closed'])

    def test_two_real_observations_replace_only_repeated_failure_output(self):
        self.activate();command='python3 -m unittest'
        for i in range(2):
            hooks.handle(self.event('PreToolUse',command,ident=str(i)))
            out=hooks.handle(self.event('PostToolUse',command,ident=str(i),output={'exit_code':1,'output':'AssertionError: 19\n'}))
            self.assertEqual('decision'in out,i==1)
        self.assertEqual(out['decision'],'block');self.assertIn('really ran both times',out['reason'])
        self.assertFalse(self.state()['closed'])
        journal=json.loads((self.run/'hook-journal.json').read_text());self.assertEqual(journal['model_calls'],0)
        self.assertEqual(journal['interventions'],1)
        (self.repo/'app.py').write_text('def normalize(xs):return []\n')
        hooks.handle(self.event('PreToolUse',command,ident='changed'))
        self.assertEqual(hooks.handle(self.event('PostToolUse',command,ident='changed',output={'exit_code':1,'output':'AssertionError: 19\n'})),{})

    def test_unknown_tool_response_never_becomes_a_failure(self):
        self.activate();command='echo sample'
        for i in range(2):
            hooks.handle(self.event('PreToolUse',command,ident=str(i)))
            self.assertEqual(hooks.handle(self.event('PostToolUse',command,ident=str(i),output={'arbitrary':'value'})),{})
        self.assertEqual(hooks.response('Process exited with code 2\nOutput: error')[0],2)
        self.assertEqual(hooks.response({'output':'error','metadata':{'exit_code':2}}),(2,'error'))

    def test_real_codex_string_responses_detect_unittest_failure_without_inventing_exit_code(self):
        self.activate();command='python3 -m unittest tests.test_public -q'
        for i,seconds in enumerate(['0.001','0.005']):
            hooks.handle(self.event('PreToolUse',command,ident=str(i)))
            output='FAIL: test_x\nAssertionError: 19 != 20\nRan 1 test in '+seconds+'s\nFAILED (failures=1)\n'
            out=hooks.handle(self.event('PostToolUse',command,ident=str(i),output=output))
        self.assertEqual(out['decision'],'block')
        journal=json.loads((self.run/'hook-journal.json').read_text())
        self.assertIsNone(journal['observations'][-1]['returncode'])
        self.assertEqual(journal['observations'][-1]['failure_evidence'],'unittest_summary')
        self.assertFalse(hooks.test_failure('API payload says error or FAILED'))

    def test_cannot_replace_an_open_goal_binding_with_another_run(self):
        self.activate();another=self.root/'another'
        with self.assertRaises(ContractError):gp.start(self.goal,self.repo,another)
        original=json.loads((self.registry/(hooks.key(self.ident)+'.binding.json')).read_text())
        self.assertEqual(original['run_dir'],str(self.run))
        self.assertFalse(another.exists())


del SessionTests
