"""Native verification must freeze acceptance and preserve failures across repairs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'integrations/native/native.py'

class NativeWorkflow(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.repo=self.root/'repo';self.repo.mkdir();self.run=self.root/'evidence'
        (self.repo/'app.py').write_text('value = 1\n')
        (self.repo/'test_app.py').write_text('import app\nassert app.value == 1\n')
    def call(self,*args,ok=0):
        r=subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(r.returncode,ok,r.stdout+r.stderr)
        return json.loads(r.stdout)
    def begin(self,**kw):
        args=['begin','--repo',self.repo,'--run-dir',self.run,'--goal','Corriger été et préserver les tests.']
        for k,v in kw.items():args.extend(['--'+k.replace('_','-'),str(v)])
        return self.call(*args)
    def deliver(self,data=None,ok=0):
        path=self.root/'criteria.json';path.write_text(json.dumps(data or {'checks':[{'id':'tests','argv':[sys.executable,'test_app.py']}],'criteria':[{'quote':'préserver les tests','checks':['tests']}]}))
        return self.call('deliver',self.run,'--criteria-file',path,ok=ok)
    def test_pass_deduplicates_identical_suites_and_invalidates_after_edit(self):
        self.begin();r=self.deliver();self.assertTrue(r['goal_complete']);self.assertEqual(r['checks_total'],1)
        self.assertEqual(self.call('finish',self.run)['attempts'],1)
        (self.repo/'app.py').write_text('value=2\n')
        self.assertFalse(self.call('status',self.run)['goal_complete'])
        self.assertEqual(self.call('status',self.run)['status'],'stale')
    def test_original_tests_cannot_be_weakened_and_failure_preserved(self):
        self.begin();(self.repo/'app.py').write_text('value=2\n');(self.repo/'test_app.py').write_text('pass\n')
        r=self.deliver(ok=1);self.assertFalse(r['goal_complete']);self.assertEqual(r['checks_total'],2)
        (self.repo/'app.py').write_text('value=1\n')
        r=self.call('finish',self.run);self.assertTrue(r['goal_complete']);self.assertEqual(r['attempts'],2)
    def test_builder_test_mutation_during_repair_does_not_weaken_frozen_test(self):
        self.begin();(self.repo/'app.py').write_text('value=2\n');self.deliver(ok=1)
        (self.repo/'test_app.py').write_text('pass\n')
        self.assertFalse(self.call('finish',self.run,ok=1)['goal_complete'])

    def test_amend_failed_acceptance_adds_direct_check_and_seals_old_failure(self):
        (self.repo/'test_app.py').write_text('import app\ndef test_value(): assert app.value == 1\n')
        self.begin();(self.repo/'app.py').write_text('value=2\n')
        original={'checks':[{'id':'broad','argv':[sys.executable,'-m','pytest','-q']}],
                  'criteria':[{'quote':'Corriger','checks':['broad']}]}
        self.deliver(original,ok=1)
        (self.repo/'app.py').write_text('value=1\n')
        (self.repo/'test_app.py').write_text('import app\ndef test_value(): assert app.value == 1\ndef test_repair_contract(): assert app.value == 1\n')
        revised={'checks':[{'id':'broad','argv':[sys.executable,'-m','pytest','-q'],'diagnostic':True},
                           {'id':'direct','argv':[sys.executable,'-m','pytest','-q','test_app.py::test_repair_contract']}],
                 'criteria':[{'quote':'Corriger','checks':['direct']}]}
        path=self.root/'amended.json';path.write_text(json.dumps(revised))
        result=self.call('amend',self.run,'--criteria-file',path,'--reason','The broad run exposed a focused contract check missing from the original plan.')
        self.assertTrue(result['goal_complete'],result)
        history=json.loads((self.run/'acceptance-history.json').read_text())
        self.assertEqual(history[0]['acceptance']['checks'],original['checks'])
        self.assertFalse(history[0]['attempts'][-1]['checks'][0]['passed'])
        status=self.call('status',self.run);self.assertEqual(status['attempts'],2)
        self.assertEqual(status['amendment_history'][0]['failed_checks'][0]['id'],'broad')
        (self.run/'acceptance-history.json').write_text('[]')
        self.assertIn('Frozen evidence changed',self.call('status',self.run,ok=2)['error'])

    def test_amendment_cannot_remove_check_or_change_criterion(self):
        self.begin();(self.repo/'app.py').write_text('value=2\n');self.deliver(ok=1)
        path=self.root/'amended.json';path.write_text(json.dumps({'checks':[], 'criteria':[]}))
        result=self.call('amend',self.run,'--criteria-file',path,'--reason','rewrite',ok=2)
        self.assertIn('cannot remove prior checks',result['error'])

    def test_amendment_is_closed_after_success(self):
        self.begin();self.deliver()
        path=self.root/'amended.json';path.write_text(json.dumps({'checks':[{'id':'tests','argv':[sys.executable,'test_app.py']}],
            'criteria':[{'quote':'préserver les tests','checks':['tests']}]}))
        result=self.call('amend',self.run,'--criteria-file',path,'--reason','post-success',ok=2)
        self.assertIn('immutable',result['error'])
        (self.repo/'app.py').write_text('value=2\n');self.call('status',self.run)['goal_complete']
    def test_unknown_command_and_explicit_blocker_prevent_completion(self):
        self.begin();r=self.deliver({'checks':[{'id':'tests','argv':['goalpilot-no-such-executable']}],'criteria':[{'quote':'Corriger','checks':['tests']} ]},ok=1)
        self.assertEqual(r['criteria'][0]['status'],'blocked')
    def test_diagnostic_check_runs_and_is_reported_without_gating_direct_evidence(self):
        self.begin();diagnostic=[sys.executable,'-c','raise SystemExit(1)']
        data={'checks':[{'id':'focused','argv':[sys.executable,'test_app.py']},{'id':'full-suite','argv':diagnostic,'diagnostic':True}],
              'criteria':[{'quote':'préserver les tests','checks':['focused']}]}
        r=self.deliver(data);self.assertTrue(r['goal_complete']);self.assertEqual(r['checks_passed'],1)
        self.assertEqual(r['diagnostic_checks'][0]['id'],'full-suite');self.assertFalse(r['diagnostic_checks'][0]['passed'])
        self.assertFalse(any(row['id']=='full-suite' for row in r['failed_checks']))
        self.assertTrue((self.run/r['diagnostic_checks'][0]['log']).exists())
    def test_diagnostic_check_cannot_gate_a_criterion(self):
        self.begin();data={'checks':[{'id':'diagnostic','argv':[sys.executable,'-c','pass'],'diagnostic':True}],
                            'criteria':[{'quote':'préserver les tests','checks':['diagnostic']}]}
        self.deliver(data,ok=2)
    def test_status_compacts_model_feedback_but_keeps_full_failure_log(self):
        self.begin();command="print('x'*4000);raise SystemExit(1)"
        data={'checks':[{'id':'noisy','argv':[sys.executable,'-c',command]}],
              'criteria':[{'quote':'Corriger','checks':['noisy']}]}
        r=self.deliver(data,ok=1);row=r['failed_checks'][0]
        self.assertLessEqual(len(row['output_tail']),1200)
        self.assertGreater((self.run/row['log']).stat().st_size,4000)
    def test_changed_test_file_requires_a_gating_check_that_runs_it(self):
        self.begin();(self.repo/'test_app.py').write_text('import app\nassert app.value == 1\n# changed\n')
        data={'checks':[{'id':'suite','argv':[sys.executable,'-c','pass'],'diagnostic':True}],
              'criteria':[{'quote':'préserver les tests','checks':[],'blocker':'no focused test'}]}
        criteria=self.root/'criteria.json';criteria.write_text(json.dumps(data))
        result=self.call('deliver',self.run,'--criteria-file',criteria,ok=2)
        self.assertIn('Changed test file needs a required check',result['error'])
    def test_typoed_explicit_pytest_node_is_rejected_before_freezing(self):
        self.begin();(self.repo/'test_app.py').write_text('def test_existing():\n assert True\n')
        data={'checks':[{'id':'focused','argv':[sys.executable,'-m','pytest','test_app.py::test_existng']}],
              'criteria':[{'quote':'Corriger','checks':['focused']}]}
        result=self.deliver(data,ok=2)
        self.assertIn('Unknown pytest node',result['error'])
        self.assertFalse((self.run/'acceptance.json').exists())
    def test_new_pytest_node_is_skipped_only_in_original_snapshot(self):
        self.begin();(self.repo/'test_app.py').write_text('import app\ndef test_existing(): assert app.value == 1\ndef test_added(): assert app.value == 1\n')
        data={'checks':[{'id':'focused','argv':[sys.executable,'-m','pytest','-q','test_app.py::test_existing','test_app.py::test_added']},
                        {'id':'suite','argv':[sys.executable,'-m','pytest','-q'],'diagnostic':True}],
              'criteria':[{'quote':'Corriger','checks':['focused']}]}
        r=self.deliver(data)
        self.assertTrue(r['goal_complete'],r)
        self.assertEqual(r['skipped_original_checks'],[{'id':'focused','reason':'explicit pytest node is absent from the frozen original suite; the required builder check still runs'}])
        attempt=json.loads((self.run/'attempt-1/result.json').read_text())
        self.assertTrue(next(x for x in attempt['checks'] if x['suite']=='original'and x['id']=='focused')['skipped'])
    def test_exact_goal_bad_quote_budget_existing_run_and_frozen_criteria(self):
        self.begin(max_verifications=1);self.assertEqual((self.run/'goal.bin').read_bytes(),'Corriger été et préserver les tests.'.encode())
        self.deliver({'criteria':[{'quote':'invented','checks':[],'blocker':'missing'}]},ok=2)
        self.assertFalse((self.run/'acceptance.json').exists());self.deliver();self.deliver(ok=2)
        self.assertEqual(self.call('finish',self.run)['attempts'],1)
        self.call('begin','--repo',self.repo,'--run-dir',self.run,'--goal','new',ok=2)
    def test_tampered_acceptance_and_source_symlink_are_rejected(self):
        self.begin();self.deliver();(self.run/'acceptance.json').write_text('{}')
        self.call('finish',self.run,ok=2)
        if sys.platform!='win32':
            (self.repo/'linked.py').symlink_to(self.repo/'app.py')
            self.call('begin','--repo',self.repo,'--run-dir',self.root/'another','--goal','test',ok=2)
    def test_explicit_blocker_is_not_completion(self):
        self.begin();r=self.deliver({'checks':[],'criteria':[{'quote':'Corriger','checks':[],'blocker':'No production access'}]},ok=1)
        self.assertFalse(r['goal_complete'])
    def test_deadline_is_hard_and_failure_cannot_be_discarded(self):
        self.begin(wall_seconds=.15)
        self.deliver({'checks':[{'id':'wait','argv':[sys.executable,'-c','import time;time.sleep(3)']}],'criteria':[{'quote':'Corriger','checks':['wait']}]},ok=1)
        self.assertFalse(self.call('status',self.run)['goal_complete'])
    def test_additive_tests_run_the_unchanged_originals_and_new_tests_once(self):
        counter=self.root/'counter'
        old=chr(10).join(["import unittest","class Old(unittest.TestCase):"," def test_old(self):","  import app","  self.assertEqual(app.value,1)","  with open("+repr(str(counter))+",'a')as f:f.write('old'+chr(10))",""])
        (self.repo/'test_app.py').write_text(old)
        self.begin()
        new=old.replace('class Old','class New').replace('test_old','test_new').replace("'old'","'new'")
        (self.repo/'test_extra.py').write_text(new)
        r=self.deliver({'checks':[{'id':'tests','argv':[sys.executable,'-m','unittest','discover']}],'criteria':[{'quote':'Corriger','checks':['tests']}]})
        self.assertTrue(r['goal_complete']);self.assertEqual(r['checks_total'],1)
        self.assertEqual(sorted(counter.read_text().splitlines()),['new','old'])

    def test_appended_python_cases_reuse_the_full_builder_suite_without_duplicate_baseline(self):
        counter=self.root/'counter'
        old=chr(10).join(['import unittest', 'class Old(unittest.TestCase):', ' def test_old(self):', '  with open('+repr(str(counter))+",'a') as f:f.write('old\\n')", ''])
        (self.repo/'test_app.py').write_text(old);self.begin()
        appended=chr(10).join(['class Added(unittest.TestCase):',' def test_added(self):',"  with open("+repr(str(counter))+",'a') as f:f.write('added\\n')",''])
        (self.repo/'test_app.py').write_text(old+appended)
        data={'checks':[{'id':'tests','argv':[sys.executable,'-m','unittest','test_app']}],
              'criteria':[{'quote':'Corriger','checks':['tests']}]}
        r=self.deliver(data)
        self.assertTrue(r['goal_complete'],r)
        self.assertEqual(r['checks_total'],1)
        self.assertEqual(sorted(counter.read_text().splitlines()),['added','old'])

    def test_changed_originals_keep_new_check_files_available_in_both_suites(self):
        self.begin()
        original=self.repo/'test_app.py'
        original.write_text(original.read_text()+'assert app.value > 0'+chr(10))
        (self.repo/'test_extra.py').write_text('import app;assert app.value == 1')
        data={'checks':[{'id':'old','argv':[sys.executable,'test_app.py']},{'id':'new','argv':[sys.executable,'test_extra.py']}],'criteria':[{'quote':'Corriger','checks':['old','new']}]}
        r=self.deliver(data);self.assertTrue(r['goal_complete']);self.assertEqual(r['checks_total'],2)

    def test_invalid_authored_draft_can_be_corrected_once_with_full_history(self):
        self.begin();extra=self.repo/'test_extra.py';extra.write_text(chr(10).join(['import unittest,app','class Draft(unittest.TestCase):',' def test_feature(self):self.assertEqual(app.value,2)']))
        data={'checks':[{'id':'tests','argv':[sys.executable,'-m','unittest','discover']}],'criteria':[{'quote':'Corriger','checks':['tests']}]}
        self.deliver(data,ok=1)
        extra.write_text(extra.read_text().replace('value,2','value,1'))
        r=self.call('finish',self.run,ok=1);self.assertEqual(r['status'],'test_revision_required')
        r=self.call('finish',self.run,'--test-revision','Original compatibility requires value1; my new expected2 was erroneous')
        self.assertTrue(r['goal_complete']);self.assertEqual(r['test_revisions'],1);self.assertEqual(r['attempts'],2)
        self.assertIn('value,2',(self.run/'builder-tests/test_extra.py').read_text())
        self.assertIn('value,1',(self.run/'test-revisions/1/test_extra.py').read_text())
        self.assertTrue((self.run/'accepted-tests.json').exists())
        extra.write_text('pass')
        self.call('finish',self.run,'--test-revision','Cannot weaken accepted tests',ok=2)

    def test_revising_draft_cannot_bypass_frozen_original_assertions_or_delete_tests(self):
        self.begin();(self.repo/'app.py').write_text('value=2')
        extra=self.repo/'test_extra.py';extra.write_text('assert False')
        data={'checks':[{'id':'tests','argv':[sys.executable,'-m','unittest','discover']}],'criteria':[{'quote':'Corriger','checks':['tests']}]}
        self.deliver(data,ok=1);extra.write_text('pass')
        r=self.call('finish',self.run,'--test-revision','Correct invalid new test draft',ok=1)
        self.assertFalse(r['goal_complete']);self.assertTrue(any(i['suite']=='original'and not i['passed']for i in r['failed_checks'])or not r['checks_passed'])
        extra.unlink();self.call('finish',self.run,'--test-revision','Delete test to hide failure',ok=2)

    def test_intentional_contract_change_supersedes_only_named_original_file(self):
        (self.repo/'test_app.py').write_text('import app\ndef test_contract(): assert app.value == 1\n')
        (self.repo/'test_other.py').write_text('def test_original_invariant(): assert True\n')
        self.begin()
        # The user goal changes the old value contract. Preserve the test case name,
        # keep the original sealed, and retain the unrelated original test file.
        extra=self.repo/'test_extra.py';extra.write_text('import app\ndef test_unrelated(): assert app.value > 0\n')
        (self.repo/'app.py').write_text('value = 2\n')
        (self.repo/'test_app.py').write_text('import app\ndef test_contract(): assert app.value == 2\n')
        data={'checks':[{'id':'tests','argv':[sys.executable,'-m','pytest','-q']}],
              'criteria':[{'quote':'Corriger','checks':['tests']}]}
        self.deliver(data,ok=1)
        old=(self.run/'original/test_app.py').read_bytes()
        r=self.call('finish',self.run,'--test-revision','The requested behavior replaces the old value contract; the updated test keeps its case and asserts the new value.','--supersede-tests','test_app.py')
        self.assertTrue(r['goal_complete'],r)
        self.assertEqual(r['superseded_test_files'],['test_app.py'])
        self.assertEqual((self.run/'original/test_app.py').read_bytes(),old)
        self.assertTrue((self.run/'test-revisions/1/test_extra.py').exists())
        result=json.loads((self.run/'attempt-2/result.json').read_text())
        self.assertTrue(all(row['passed'] for row in result['checks']))
        self.assertEqual(result['test_snapshot'],'test-revisions/1')

    def test_original_suite_never_reintroduces_a_superseded_file(self):
        counter=self.root/'runs';app_counter=repr(str(counter))
        (self.repo/'test_app.py').write_text('import app\ndef test_contract():\n with open('+app_counter+",'a') as f:f.write('contract\\n')\n assert app.value == 1\n")
        (self.repo/'test_other.py').write_text('def test_invariant():\n with open('+app_counter+",'a') as f:f.write('invariant\\n')\n assert True\n")
        self.begin();(self.repo/'app.py').write_text('value=2\n')
        (self.repo/'test_app.py').write_text('import app\ndef test_contract():\n with open('+app_counter+",'a') as f:f.write('contract\\n')\n assert app.value == 2\n")
        (self.repo/'test_other.py').write_text('def test_invariant():\n with open('+app_counter+",'a') as f:f.write('invariant\\n')\n assert 1 == 1\n")
        data={'checks':[{'id':'suite','argv':[sys.executable,'-m','pytest','-q']}],
              'criteria':[{'quote':'Corriger','checks':['suite']}]}
        self.deliver(data,ok=1)
        counter.unlink()
        r=self.call('finish',self.run,'--test-revision','The value contract intentionally changed; preserve the test case and updated assertion.','--supersede-tests','test_app.py')
        self.assertTrue(r['goal_complete'],r)
        self.assertEqual(sorted(counter.read_text().splitlines()),['contract','invariant','invariant'])
        rows=json.loads((self.run/'attempt-2/result.json').read_text())['checks']
        self.assertEqual({row['suite'] for row in rows},{'original','builder'})

    def test_superseded_file_must_preserve_named_test_cases(self):
        self.begin();(self.repo/'app.py').write_text('value=2\n');(self.repo/'test_app.py').write_text('pass\n')
        data={'checks':[{'id':'tests','argv':[sys.executable,'test_app.py']}],
              'criteria':[{'quote':'Corriger','checks':['tests']}]}
        self.deliver(data,ok=1)
        r=self.call('finish',self.run,'--test-revision','The goal changes the existing contract intentionally.','--supersede-tests','test_app.py',ok=2)
        self.assertIn('retain every named test case',r['error'])
    def test_superseded_test_file_must_have_a_required_check(self):
        (self.repo/'test_app.py').write_text('import app\ndef test_value(): assert app.value == 1\n')
        self.begin();(self.repo/'app.py').write_text('value=2\n')
        data={'checks':[{'id':'probe','argv':[sys.executable,'-c','raise SystemExit(1)']}],
              'criteria':[{'quote':'Corriger','checks':['probe']}]}
        self.deliver(data,ok=1);(self.repo/'test_app.py').write_text('import app\ndef test_value(): assert app.value == 2\n')
        r=self.call('finish',self.run,'--test-revision','The requested contract changed.','--supersede-tests','test_app.py',ok=2)
        self.assertIn('needs a required check that runs it',r['error'])
        self.assertEqual(self.call('status',self.run)['test_revisions'],0)
    def test_revised_test_file_must_have_a_required_check(self):
        self.begin();data={'checks':[{'id':'probe','argv':[sys.executable,'-c','raise SystemExit(1)']}],
                           'criteria':[{'quote':'Corriger','checks':['probe']}]}
        self.deliver(data,ok=1);(self.repo/'test_app.py').write_text('import app\nassert app.value == 2\n')
        r=self.call('finish',self.run,'--test-revision','Correct the draft expectation after the contract change.',ok=2)
        self.assertIn('Revised test file needs a required check that runs it',r['error'])
        self.assertEqual(self.call('status',self.run)['test_revisions'],0)

    def test_full_pytest_may_report_only_preexisting_failures_when_focused_goal_test_passes(self):
        (self.repo/'test_app.py').write_text('import app\ndef test_preexisting(): assert False\n')
        self.begin();(self.repo/'app.py').write_text('value=2\n')
        with (self.repo/'test_app.py').open('a')as f:f.write('def test_requested():\n assert app.value == 2\n')
        data={'checks':[{'id':'suite','argv':[sys.executable,'-m','pytest','-q']},
                        {'id':'focused','argv':[sys.executable,'-m','pytest','-q','test_app.py','-k','test_requested']}],
              'criteria':[{'quote':'Corriger','checks':['suite','focused']}]}
        r=self.deliver(data)
        self.assertTrue(r['goal_complete'],r)
        attempt=json.loads((self.run/'attempt-1/result.json').read_text())
        suite=next(row for row in attempt['checks'] if row['id']=='suite')
        self.assertEqual(suite['baseline'],'no_new_pytest_failures')
        self.assertTrue(any('test_preexisting' in x for x in suite['preexisting_failures']))

    def test_failing_new_pytest_case_cannot_be_misclassified_as_preexisting(self):
        (self.repo/'test_app.py').write_text('import app\ndef test_preexisting(): assert False\n')
        self.begin();(self.repo/'app.py').write_text('value=2\n')
        with (self.repo/'test_app.py').open('a')as f:f.write('def test_requested():\n assert app.value == 3\n')
        data={'checks':[{'id':'suite','argv':[sys.executable,'-m','pytest','-q']},
                        {'id':'focused','argv':[sys.executable,'-m','pytest','-q','test_app.py','-k','test_requested']}],
              'criteria':[{'quote':'Corriger','checks':['suite','focused']}]}
        r=self.deliver(data,ok=1)
        self.assertFalse(r['goal_complete'])
        attempt=json.loads((self.run/'attempt-1/result.json').read_text())
        suite=next(row for row in attempt['checks'] if row['id']=='suite')
        self.assertNotIn('baseline',suite)

    def test_nested_pytest_import_errors_match_their_parent_not_changed_cases(self):
        changed={'testing/test_nodes.py::test_new_regression'}
        spec=importlib.util.spec_from_file_location('native_failure_ids',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertFalse(module.pytest_failure_is_from_changed_test('test_show_traceback_import_error.py',changed))
        self.assertFalse(module.pytest_failure_is_from_changed_test('testing/python/collect.py::TestModule::test_other[1]',changed))
        self.assertTrue(module.pytest_failure_is_from_changed_test('testing/test_nodes.py::test_new_regression[long-os]',changed))

    def test_status_checks_frozen_criteria_and_final_test_integrity(self):
        self.begin();self.deliver()
        (self.run/'accepted-tests.json').write_text('{}')
        self.call('status',self.run,ok=2)

    def test_new_test_failure_is_enforced_and_original_snapshot_intact(self):
        self.begin();(self.repo/'test_extra.py').write_text('raise AssertionError("new requirement")')
        data={'checks':[{'id':'tests','argv':[sys.executable,'-m','unittest','discover']}],'criteria':[{'quote':'Corriger','checks':['tests']}]}
        self.assertFalse(self.deliver(data,ok=1)['goal_complete'])
        (self.run/'original/app.py').write_text('value=0')
        self.call('status',self.run,ok=2)


class NativeInstallation(unittest.TestCase):
    def test_all_host_profiles_include_exact_native_runtime_and_doctor(self):
        with tempfile.TemporaryDirectory()as tmp:
            for host in ('codex','claude-code','antigravity','hermes','generic'):
                with self.subTest(host=host):
                    target=Path(tmp)/host
                    r=subprocess.run([sys.executable,str(ROOT/'install.py'),'--profile','universal','--host',host,'--target',str(target)],capture_output=True,text=True)
                    self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                    self.assertTrue(json.loads(r.stdout)['verification']['ready'])
                    self.assertEqual((target/'scripts/native.py').read_bytes(),CLI.read_bytes())
                    self.assertEqual((target/'references/native.md').read_bytes(),(ROOT/'integrations/native/SKILL.md').read_bytes())
                    self.assertIn('Native project workflow',(target/'references/native.md').read_text())
                    runtime=json.loads((target/'RUNTIME.json').read_text())
                    self.assertEqual(runtime['engine_version'],'0.16.0')


class Routing(unittest.TestCase):
    def test_pytest_baseline_can_scope_to_failing_files_and_falls_back_for_filters(self):
        spec=importlib.util.spec_from_file_location('native_pytest',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'testing').mkdir();(root/'testing/test_a.py').write_text('def test_a():pass\n')
            log=root/'candidate.log';log.write_text('FAILED testing/test_a.py::test_a - failed\nERROR generated_child.py - import error\n')
            files=module.pytest_failure_files(log,root)
            self.assertEqual(files,['testing/test_a.py'])
            argv=['/usr/bin/env','PYTHONPATH=src','python','-m','pytest','-q']
            self.assertEqual(module.selective_pytest_command(argv,files),argv+['testing/test_a.py'])
            self.assertIsNone(module.selective_pytest_command(argv+['-k','test_a'],files))
    def test_required_suite_must_cover_changed_test_file(self):
        spec=importlib.util.spec_from_file_location('native_test_scope',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'tests').mkdir();(root/'tests/test_a.py').write_text('def test_a():pass\n')
            (root/'tests/test_a_test.go').write_text('package tests\n')
            java=root/'src/test/java';java.mkdir(parents=True);(java/'TestA.java').write_text('class TestA {}\n')
            self.assertTrue(module.check_covers_test_file({'id':'focused','argv':['pytest','tests/test_a.py']},root,'tests/test_a.py'))
            self.assertTrue(module.check_covers_test_file({'id':'suite','argv':['python','-m','pytest']},root,'tests/test_a.py'))
            self.assertTrue(module.check_covers_test_file({'id':'go-suite','argv':['go','test','./...']},root,'tests/test_a_test.go'))
            self.assertTrue(module.check_covers_test_file({'id':'java-suite','argv':['./gradlew','test']},root,'src/test/java/TestA.java'))
            self.assertFalse(module.check_covers_test_file({'id':'diagnostic','argv':['python','-m','pytest'],'diagnostic':True},root,'tests/test_a.py'))

    def test_only_explicit_unimplemented_compatible_scaffold_selects_service(self):
        spec=importlib.util.spec_from_file_location('native_route',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'tests').mkdir()
            (root/'tests/test_old.py').write_text('import unittest')
            (root/'README.md').write_text('app.Service with JSONL and HTTP')
            app=root/'app.py';app.write_text("class Service:\n def call(self,op,data):raise NotImplementedError()\n")
            self.assertTrue(module.service_scaffold(root))
            app.write_text('class Service:\n def call(self,op,data):return 1\n')
            self.assertFalse(module.service_scaffold(root))
            app.write_text("class Service:\n def call(self,op,data):raise NotImplementedError()\n")
            (root/'README.md').write_text('an ordinary application')
            self.assertFalse(module.service_scaffold(root))


class ServiceDispatch(unittest.TestCase):
    def test_auto_begin_deliver_status_keep_the_exact_legacy_engine(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);target=root/'skill';repo=root/'repo';run=root/'run';(repo/'tests').mkdir(parents=True)
            (repo/'README.md').write_text('app.Service scaffolding: JSONL and HTTP')
            (repo/'app.py').write_text("def banner():return 'ok'\nclass Service:\n def call(self,op,data):raise NotImplementedError()\n")
            (repo/'tests/test_app.py').write_text("import unittest\nfrom app import banner\nclass Old(unittest.TestCase):\n def test_banner(self):self.assertEqual(banner(),'ok')\n")
            installed=subprocess.run([sys.executable,str(ROOT/'install.py'),'--profile','universal','--host','generic','--target',str(target)],capture_output=True,text=True)
            self.assertEqual(installed.returncode,0,installed.stdout+installed.stderr)
            cli=target/'scripts/native.py'
            started=subprocess.run([sys.executable,str(cli),'begin','--goal','Preserve banner','--repo',str(repo),'--run-dir',str(run),'--context'],capture_output=True,text=True)
            self.assertEqual(started.returncode,0,started.stdout+started.stderr)
            self.assertIn('SERVICE MODE ALREADY STARTED',started.stdout)
            self.assertTrue((run/'session-state.json').exists());self.assertFalse((run/'state.json').exists())
            self.assertEqual((run/'goal.bin').read_bytes(),b'Preserve banner')
            criteria=root/'criteria.json';criteria.write_text(json.dumps({'criteria':[{'quote':'Preserve banner','checks':['original-tests','builder-tests']}]}))
            delivered=subprocess.run([sys.executable,str(cli),'deliver',str(run),'--criteria-file',str(criteria)],capture_output=True,text=True)
            self.assertEqual(delivered.returncode,0,delivered.stdout+delivered.stderr)
            self.assertTrue(json.loads(delivered.stdout)['goal_complete'])
            status=subprocess.run([sys.executable,str(cli),'status',str(run)],capture_output=True,text=True)
            self.assertEqual(status.returncode,0,status.stdout+status.stderr)
            self.assertTrue(json.loads(status.stdout)['goal_complete'])
