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
    def test_unknown_command_and_explicit_blocker_prevent_completion(self):
        self.begin();r=self.deliver({'checks':[{'id':'tests','argv':['goalpilot-no-such-executable']}],'criteria':[{'quote':'Corriger','checks':['tests']} ]},ok=1)
        self.assertEqual(r['criteria'][0]['status'],'blocked')
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

    def test_changed_originals_keep_new_check_files_available_in_both_suites(self):
        self.begin()
        original=self.repo/'test_app.py'
        original.write_text(original.read_text()+'assert app.value > 0'+chr(10))
        (self.repo/'test_extra.py').write_text('import app;assert app.value == 1')
        data={'checks':[{'id':'old','argv':[sys.executable,'test_app.py']},{'id':'new','argv':[sys.executable,'test_extra.py']}],'criteria':[{'quote':'Corriger','checks':['old','new']}]}
        r=self.deliver(data);self.assertTrue(r['goal_complete']);self.assertEqual(r['checks_total'],4)

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
