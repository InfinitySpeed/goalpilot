"""Actual process tests: passive loop signals never substitute acceptance."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from tests.test_session import SessionTests
from goalpilot import session as gp
from goalpilot.monitor import run_check, stable_output
from goalpilot.model import ContractError


class MonitorTests(unittest.TestCase):
    setUp = SessionTests.setUp
    start = SessionTests.start
    state = SessionTests.state
    write_handoff = SessionTests.write_handoff
    def test_finish_passes_real_original_and_builder_suites(self):
        self.start()
        (self.repo/'tests/test_extra.py').write_text("import unittest\nfrom app import normalize\nclass Added(unittest.TestCase):\n def test_empty(self):self.assertEqual(normalize([]),[])\n")
        with patch('goalpilot.adapters.CodexAdapter.execute',side_effect=AssertionError('inference')):
            result=gp.finish(self.run)
        self.assertTrue(result['closed'])
        acceptance=gp.sealed_read(self.run,'acceptance.json')
        self.assertEqual([x['id']for x in acceptance['checks']],['original-tests','builder-tests'])
        self.assertEqual(self.state()['engine_model_calls'],0)
        attempts=result['attempts']
        self.assertTrue(gp.finish(self.run)['closed'])
        self.assertEqual(self.state()['verifications'].__len__(),attempts)

    def test_finish_failure_repairs_same_immutable_tests(self):
        self.start();(self.repo/'app.py').write_text('def normalize(xs):return []\n')
        failed=gp.finish(self.run)
        self.assertFalse(failed['closed'])
        self.assertIn('AssertionError',failed['failures'][0]['output'])
        frozen=(self.run/'acceptance.json').read_bytes()
        (self.repo/'app.py').write_bytes((self.run/'originals/app.py').read_bytes())
        self.assertTrue(gp.finish(self.run)['closed'])
        self.assertEqual(frozen,(self.run/'acceptance.json').read_bytes())
        self.assertEqual(len(self.state()['verifications']),2)

    def test_repeated_failure_changes_strategy_without_retries_or_model(self):
        self.start();cmd=[sys.executable,'-c',"raise ValueError('bad input 19')"]
        with patch('goalpilot.adapters.CodexAdapter.execute',side_effect=AssertionError('inference')):
            one=run_check(self.run,cmd);two=run_check(self.run,cmd)
        self.assertEqual(one['status'],'failed');self.assertEqual(two['status'],'stalled')
        self.assertTrue(two['intervention']);self.assertEqual(two['output'],'')
        self.assertIn('bad input 19',Path(two['log']).read_text())
        self.assertFalse(self.state()['closed']);self.assertEqual(len(self.state()['observations']),2)
        self.assertEqual(len(self.state()['verifications']),0)
        self.assertEqual(self.state()['engine_model_calls'],0)

    def test_changed_source_and_different_commands_reset_repetition(self):
        self.start();cmd=[sys.executable,'-c','assert False']
        run_check(self.run,cmd)
        (self.repo/'app.py').write_text('def normalize(xs):return xs\n')
        self.assertFalse(run_check(self.run,cmd)['intervention'])
        self.assertFalse(run_check(self.run,[sys.executable,'-c','assert 1==2'])['intervention'])
        self.assertEqual(len(self.state()['observations']),3)

    def test_pass_does_not_close_timeout_and_missing_command_remain_failures(self):
        self.start()
        self.assertEqual(run_check(self.run,[sys.executable,'-c','assert 1==1'])['status'],'passed')
        self.assertFalse(self.state()['closed'])
        missing=run_check(self.run,['/no/such/executable'])
        self.assertIn('Executable unavailable',missing['next_action'])
        self.assertIn('/no/such/executable',Path(missing['log']).read_text())
        timed=run_check(self.run,[sys.executable,'-c','import time;time.sleep(2)'],timeout=.1)
        self.assertIn('timed out',timed['next_action']);self.assertFalse(timed['closed'])

    def test_arguments_and_exhausted_budget_cannot_launch(self):
        self.start()
        for bad in ([], 'echo x', ['bad\0arg']):
            with self.assertRaises(ContractError):run_check(self.run,bad)
        state=self.state();state['started_at']-=100;gp.sealed_write(self.run,'session-state.json',state)
        result=run_check(self.run,[sys.executable,'-c','assert False'])
        self.assertEqual(result['status'],'budget_exhausted');self.assertFalse(result['executed'])

    def test_installed_helpers_are_immutable_acceptance_inputs(self):
        gp.start(self.goal,self.repo,self.run,wall_seconds=60,helpers=True)
        helper=self.repo/'goalpilot_runtime.py';raw=helper.read_bytes();helper.write_text('changed helper')
        with self.assertRaises(ContractError):gp.finish(self.run)
        self.assertFalse(self.state()['closed'])
        self.assertFalse((self.run/'suite-handoff.json').exists())
        helper.write_bytes(raw)
        self.assertTrue(gp.finish(self.run)['closed'])

    def test_stable_error_keeps_meaningful_numbers(self):
        self.assertEqual(stable_output('FAIL x\nRan 1 test in 0.100s'),stable_output('FAIL x\nRan 1 test in 0.200s'))
        self.assertNotEqual(stable_output('AssertionError: 19'),stable_output('AssertionError: 20'))

del SessionTests

class InitialContextTests(unittest.TestCase):
    setUp=MonitorTests.setUp
    write_handoff=MonitorTests.write_handoff
    def test_initial_context_precedes_helpers_preserves_original_source_and_is_sealed(self):
        (self.repo/'README.md').write_text('Public normalization contract')
        result=gp.start(self.goal,self.repo,self.run,helpers=True,context=True)
        self.assertFalse(result['closed']);self.assertIn('Public normalization contract',result['initial_context'])
        data=gp.sealed_read(self.run,'initial-context.json')
        self.assertTrue(data['all_candidates_included'])
        paths=[x['path']for x in data['files']]
        self.assertIn('app.py',paths);self.assertIn('tests/test_public.py',paths)
        self.assertNotIn('goalpilot_runtime.py',paths)
        self.assertTrue((self.repo/'goalpilot_runtime.py').exists())
        self.assertEqual(data['files'][next(i for i,x in enumerate(data['files'])if x['path']=='app.py')]['text'],(self.repo/'app.py').read_text())
        (self.run/'initial-context.json').write_text('{}')
        with self.assertRaises(ContractError):gp.status(self.run)
    def test_bounded_context_reports_truncation_instead_of_complete_repository(self):
        (self.repo/'README.md').write_text('x'*14000)
        gp.start(self.goal,self.repo,self.run,context=True)
        data=gp.sealed_read(self.run,'initial-context.json')
        self.assertFalse(data['all_candidates_included'])
        self.assertLessEqual(data['source_bytes'],12000)

    def test_repeated_goal_omits_verified_helpers_but_keeps_project_context_and_originals(self):
        from goalpilot.support import provision_runtime
        provision_runtime(self.repo)
        (self.repo/'README.md').write_text('Project-specific rules must stay visible.')
        result=gp.start(self.goal,self.repo,self.run,helpers=True,context=True)
        context=gp.sealed_read(self.run,'initial-context.json')
        self.assertTrue(context['all_candidates_included'])
        self.assertEqual({r['path']for r in context['verified_provided_helpers']},
                         {'goalpilot_runtime.py','goalpilot_support.py'})
        self.assertEqual({r['path']for r in context['files']},
                         {'README.md','app.py','tests/test_public.py','tests/__init__.py'})
        self.assertIn('Project-specific rules must stay visible.',result['initial_context'])
        self.assertIn('Verified supplied helpers omitted',result['initial_context'])
        self.assertNotIn('def service_race(',result['initial_context'])
        self.assertNotIn('class ReplayService(ServiceBase):',result['initial_context'])
        contract=gp.sealed_read(self.run,'session.json')
        self.assertTrue({'goalpilot_runtime.py','goalpilot_support.py'}.issubset(
            {r['path']for r in contract['original_snapshot']['files']}))
        self.assertEqual(len(contract['helpers']),2)

    def test_foreign_same_named_source_is_not_hidden_by_helper_optimization(self):
        (self.repo/'goalpilot_runtime.py').write_text('def user_policy():return "CUSTOM PROJECT RULE"\n')
        with self.assertRaises(ContractError):
            gp.start(self.goal,self.repo,self.run,helpers=True,context=True)
        self.assertFalse(self.run.exists())
        result=gp.start(self.goal,self.repo,self.run,context=True)
        self.assertIn('CUSTOM PROJECT RULE',result['initial_context'])
        self.assertNotIn('verified_provided_helpers',gp.sealed_read(self.run,'initial-context.json'))

    def test_hash_mismatch_keeps_modified_helper_in_context_even_with_known_name(self):
        from goalpilot.support import provision_runtime
        from goalpilot.dossier import prepare
        import hashlib
        provision_runtime(self.repo)
        path=self.repo/'goalpilot_runtime.py';raw=path.read_bytes()
        known={'goalpilot_runtime.py':{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}
        path.write_bytes(raw.replace(b'Portable stdlib plumbing',b'MODIFIED USER PLUMBING!!',1))
        context=prepare(self.repo,known_helpers=known)
        self.assertNotIn('verified_provided_helpers',context)
        self.assertIn('goalpilot_runtime.py',{r['path']for r in context['files']})

    def test_verified_helper_exclusion_frees_budget_for_business_tests(self):
        from goalpilot.support import provision_runtime
        from goalpilot.dossier import prepare
        from pathlib import Path
        import hashlib
        provision_runtime(self.repo)
        names=['goalpilot_runtime.py','goalpilot_support.py']
        known={name:{'sha256':hashlib.sha256((self.repo/name).read_bytes()).hexdigest(),
                     'bytes':(self.repo/name).stat().st_size}for name in names}
        before=prepare(self.repo,max_bytes=12000)
        after=prepare(self.repo,max_bytes=12000,known_helpers=known)
        self.assertFalse(before['all_candidates_included'])
        self.assertTrue(after['all_candidates_included'])
        self.assertIn('tests/test_public.py',{r['path']for r in after['files']})
        self.assertLess(after['source_bytes'],before['source_bytes'])
