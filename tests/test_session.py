"""Offline behavior of the calling-session protocol; no model or utility claims."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from goalpilot import session as gp
from goalpilot.engine import atomic_json
from goalpilot.model import ContractError

ROOT = Path(__file__).resolve().parents[1]


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text('def normalize(xs):\n return sorted(set(x.strip().casefold() for x in xs))\n')
        (self.repo / 'tests').mkdir()
        (self.repo / 'tests/__init__.py').write_text('')
        (self.repo / 'tests/test_public.py').write_text(
            "import unittest\nfrom app import normalize\nclass Public(unittest.TestCase):\n def test_labels(self):self.assertEqual(normalize([' B ','b','A']),['a','b'])\n")
        self.goal = self.root / 'goal.txt'
        self.goal.write_bytes("--Goal ' café\r\n$(touch never) `touch nor` ; preserve everything\n".encode())
        self.run = self.root / 'run'
        self.handoff = self.root / 'handoff.json'
        self.checks = [{'id': 'behavior', 'description': 'Unicode, whitespace and empty behavior',
                        'command': [sys.executable, '-B', '-c',
                                    "from app import normalize; assert normalize(['ÉTÉ',' été ',' B']) == ['b','été']; assert normalize([]) == []"],
                        'timeout_seconds': 3}]
        self.write_handoff()

    def write_handoff(self, **extra):
        self.handoff.write_text(json.dumps({'summary': 'Claim only; not trusted', 'checks': self.checks,
            'criteria': [{'id':'behavior','statement':'Normalize labels and handle empty input',
                          'source_quote':'preserve everything','check_ids':['behavior']}],
            'requirements': [{'id':'coverage','statement':'Preserve the complete request',
                              'source_quote':'preserve everything','criterion_ids':['behavior']}], **extra}))

    def start(self, **options):
        return gp.start(self.goal, self.repo, self.run, wall_seconds=60, **options)

    def state(self):
        return gp.sealed_read(self.run, 'session-state.json')

    def test_full_protocol_and_real_failure_repair_without_model(self):
        with patch('goalpilot.adapters.CodexAdapter.execute', side_effect=AssertionError('nested model')):
            started = self.start()
            self.assertEqual(started['status'], 'ready')
            self.assertEqual(started['closure_reserve_seconds'], 21.0)
            self.assertEqual(started['implementation_window_seconds'], 39.0)
            self.assertEqual(started['remaining_seconds_estimate'], 60.0)
            self.assertEqual((self.run / 'goal.bin').read_bytes(), self.goal.read_bytes())
            (self.repo / 'tests/test_unicode.py').write_text(
                "import unittest\nfrom app import normalize\nclass Unicode(unittest.TestCase):\n def test_unicode(self):self.assertEqual(normalize([' ÉTÉ ','été']),['été'])\n")
            (self.repo / 'app.py').write_text('def normalize(xs):return []\n')
            self.assertEqual(gp.submit(self.run, self.handoff)['status'], 'awaiting_verification')
            frozen = (self.run / 'acceptance.json').read_bytes()
            self.assertEqual(gp.verify_session(self.run)['status'], 'failed')
            self.assertFalse(self.state()['closed'])
            self.assertEqual(gp.repair(self.run)['status'], 'repairing')
            (self.repo / 'app.py').write_bytes((self.run / 'originals/app.py').read_bytes())
            result = gp.verify_session(self.run)
            self.assertTrue(result['closed'])
            self.assertEqual(result['status'], 'scope_passed')
            self.assertEqual(result['checks_passed'], 3)
            self.assertEqual(frozen, (self.run / 'acceptance.json').read_bytes())
            self.assertEqual(result['caller_usage'], 'UNKNOWN')
            self.assertIsNone(result['total_tokens'])
            state = self.state()
            self.assertEqual(state['engine_model_calls'], 0)
            self.assertGreater(state['active_seconds'], 0)
            self.assertGreater(state['verifications'][0]['duration_seconds'], 0)
            self.assertTrue(all(e['lock'] == 'exclusive' for e in state['events']))
            self.assertEqual(gp.status(self.run)['status'], 'scope_passed')
            (self.repo / 'app.py').write_text('def normalize(xs):return []\n')
            self.assertFalse(gp.status(self.run)['closed'])
            self.assertEqual(gp.status(self.run)['status'], 'source_drift')

    def test_original_gate_survives_builder_weakening(self):
        self.start()
        (self.repo / 'tests/test_public.py').write_text('import unittest\nclass Weak(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n')
        (self.repo / 'app.py').write_text('def normalize(xs):return []\n')
        self.checks[0]['command'] = [sys.executable, '-c', 'assert True']
        self.write_handoff()
        gp.submit(self.run, self.handoff)
        result = gp.verify_session(self.run)
        self.assertFalse(result['closed'])
        self.assertFalse(self.state()['verifications'][-1]['checks'][0]['passed'])

    def test_regular_project_metadata_preserved_in_original_and_builder_gates(self):
        (self.repo/'.gitignore').write_text('__pycache__/\n')
        (self.repo/'.editorconfig').write_text('root = true\n')
        started=self.start()
        self.assertEqual(started['status'],'ready')
        self.assertEqual((self.run/'originals/.gitignore').read_text(),'__pycache__/\n')
        self.assertEqual(gp.finish(self.run)['status'],'criteria_required')
        self.assertFalse((self.run/'acceptance.json').exists())
        gp.submit(self.run,self.handoff)
        result=gp.finish(self.run)
        self.assertTrue(result['closed'])
        self.assertEqual((self.run/'builder/originals/.editorconfig').read_text(),'root = true\n')

    def test_goal_criteria_are_traced_and_only_verified_criteria_close_the_goal(self):
        self.goal.write_text('Make export restore the saved report; preserve exact user wording.')
        checks=[{'id':'export','description':'Exported report restores correctly',
                 'command':[sys.executable,'-c','assert 2 + 2 == 4'],'timeout_seconds':3},
                {'id':'wording','description':'Original goal text is retained',
                 'command':[sys.executable,'-c','assert 2 + 2 == 4'],'timeout_seconds':3}]
        criteria=[{'id':'restore','statement':'Restore the saved report','source_quote':'restore the saved report','check_ids':['export']},
                  {'id':'wording','statement':'Preserve the exact wording','source_quote':'preserve exact user wording','check_ids':['wording']}]
        requirements=[{'id':'restore-report','statement':'The saved report can be restored',
                       'source_quote':'restore the saved report','criterion_ids':['restore']},
                      {'id':'preserve-wording','statement':'Keep the exact original wording',
                       'source_quote':'preserve exact user wording','criterion_ids':['wording']}]
        self.start();self.handoff.write_text(json.dumps({'summary':'Mapped goal','checks':checks,
                                                          'criteria':criteria,'requirements':requirements}))
        gp.submit(self.run,self.handoff)
        result=gp.verify_session(self.run)
        self.assertTrue(result['closed']);self.assertTrue(result['goal_complete'])
        self.assertEqual(result['goal_assessment']['coverage_percent'],100)
        self.assertEqual(result['goal_assessment']['verified'],2)
        self.assertEqual(result['goal_assessment']['requirements_coverage_percent'],100)
        self.assertEqual(result['goal_assessment']['requirements_verified'],2)
        self.assertEqual([x['source_quote'] for x in result['goal_assessment']['criteria']],
                         ['restore the saved report','preserve exact user wording'])

    def test_external_blocker_stays_open_after_all_project_tests_pass(self):
        self.start()
        handoff={'summary':'Deployment needs access','checks':[],
                 'criteria':[{'id':'deploy','statement':'Deploy the release',
                              'source_quote':'preserve everything','check_ids':[],
                              'blocker':'No deployment credentials in this environment'}],
                 'requirements':[{'id':'deployment','statement':'Deploy the release',
                                  'source_quote':'preserve everything','criterion_ids':['deploy']} ]}
        self.handoff.write_text(json.dumps(handoff));gp.submit(self.run,self.handoff)
        result=gp.verify_session(self.run)
        self.assertEqual(result['checks_passed'],2)
        self.assertEqual(result['status'],'criteria_blocked')
        self.assertFalse(result['closed']);self.assertFalse(result['goal_complete'])

    def test_invalid_and_duplicate_submissions_cannot_change_acceptance(self):
        self.start()
        for data in ('[]', '{', '{"summary":"claim","checks":[]}'):
            self.handoff.write_text(data)
            with self.assertRaises((ValueError, ContractError)):
                gp.submit(self.run, self.handoff)
            self.assertFalse((self.run / 'acceptance.json').exists())

        self.checks[0]['id'] = 'original-tests'
        self.write_handoff()
        with self.assertRaises(ContractError):gp.submit(self.run, self.handoff)
        self.checks[0]['id'] = 'behavior'
        self.write_handoff()
        gp.submit(self.run, self.handoff)
        original = (self.run / 'acceptance.json').read_bytes()
        self.checks[0]['command'] = [sys.executable, '-c', 'assert True']
        self.write_handoff()
        with self.assertRaises(ContractError):gp.submit(self.run, self.handoff)
        self.assertEqual(original, (self.run / 'acceptance.json').read_bytes())
        self.assertTrue(gp.verify_session(self.run)['closed'])

    def test_legacy_handoffs_are_compatible_but_supplied_orphan_maps_are_rejected(self):
        self.start()
        handoff={'summary':'Mapped goal','checks':self.checks,
                 'criteria':[{'id':'behavior','statement':'Normalize labels',
                              'source_quote':'preserve everything','check_ids':['behavior']}]}
        self.handoff.write_text(json.dumps(handoff))
        gp.submit(self.run,self.handoff)
        frozen=gp.sealed_read(self.run,'acceptance.json')
        self.assertEqual(frozen['requirements_source'],'legacy_criterion_fallback')
        self.assertEqual(frozen['requirements'][0]['criterion_ids'],['behavior'])
        self.run=self.root/'run-invalid-map'
        self.start()
        handoff['requirements']=[{'id':'unmapped','statement':'Invented requirement',
                                  'source_quote':'preserve everything','criterion_ids':['unknown']}]
        self.handoff.write_text(json.dumps(handoff))
        with self.assertRaises(ContractError):gp.submit(self.run,self.handoff)
        self.assertFalse((self.run/'acceptance.json').exists())

    def test_test_drift_refused_and_restoration_allows_normal_repair(self):
        self.start();gp.submit(self.run, self.handoff)
        test = self.repo / 'tests/test_public.py'
        frozen = test.read_bytes()
        test.write_text('')
        with self.assertRaises(ContractError):gp.verify_session(self.run)
        self.assertEqual(self.state()['status'], 'integrity_failed')
        test.write_bytes(frozen)
        gp.repair(self.run)
        self.assertTrue(gp.verify_session(self.run)['closed'])
        (self.repo / 'tests/test_extra.py').write_text('')
        with self.assertRaises(ContractError):gp.status(self.run)
        self.assertFalse(self.state()['closed'])

    def test_corrupt_goal_source_runner_and_receipt_are_not_success(self):
        for name in ('goal.bin', 'originals/app.py', 'original-tests/runner.py', 'session.json', 'session-state.json'):
            with self.subTest(name=name):
                run = self.root / ('run-' + name.replace('/', '-'))
                gp.start(self.goal, self.repo, run)
                path = run / name
                path.write_bytes(path.read_bytes() + b'corrupt')
                with self.assertRaises((ContractError, ValueError)):
                    gp.status(run)

    def test_missing_acceptance_is_not_a_new_submission_opportunity(self):
        self.start();gp.submit(self.run, self.handoff)
        (self.run / 'acceptance.json').unlink()
        with self.assertRaises(ContractError):gp.submit(self.run, self.handoff)
        self.assertEqual(self.state()['status'], 'integrity_failed')
        self.assertFalse(self.state()['closed'])

    def test_script_check_is_frozen_and_uses_repaired_project_imports(self):
        self.start()
        script = self.root / 'assert_behavior.py'
        script.write_text("from app import normalize\nassert normalize([' B ','b']) == ['b']\n")
        self.checks[0]['command'] = [sys.executable, '-B', str(script)]
        self.write_handoff();gp.submit(self.run, self.handoff)
        script.write_text('raise RuntimeError("mutable external script")\n')
        (self.repo / 'app.py').write_text('def normalize(xs):return []\n')
        self.assertFalse(gp.verify_session(self.run)['closed'])
        gp.repair(self.run)
        (self.repo / 'app.py').write_bytes((self.run / 'originals/app.py').read_bytes())
        self.assertTrue(gp.verify_session(self.run)['closed'])
        (self.run / 'check-0.py').write_text('assert True\n')
        with self.assertRaises(ContractError):gp.verify_session(self.run)
        self.assertFalse(self.state()['closed'])

    def test_unsupported_no_tests_never_closes_even_with_passing_handoff(self):
        import shutil
        shutil.rmtree(self.repo / 'tests')
        self.assertEqual(self.start()['status'], 'unsupported')
        result = gp.submit(self.run, self.handoff)
        self.assertEqual(result['status'], 'unsupported')
        self.assertFalse(result['closed'])
        with self.assertRaises(ContractError):gp.verify_session(self.run)

    def test_validation_before_any_mutation(self):
        invalid = [dict(wall_seconds=0), dict(wall_seconds=float('nan')),
                   dict(max_verifications=True), dict(max_tokens=-1)]
        for options in invalid:
            with self.assertRaises((ContractError, ValueError)):
                gp.start(self.goal, self.repo, self.run, **options)
            self.assertFalse(self.run.exists())
        for repo, run in ((self.repo, self.repo / 'evidence'), (self.root / 'missing', self.run), (self.repo, self.root)):
            with self.assertRaises(ContractError):gp.start(self.goal, repo, run)
        self.goal.write_bytes(b'\xff')
        with self.assertRaises(UnicodeError):self.start()
        self.assertFalse(self.run.exists())

    def test_attempt_and_wall_budgets_cannot_renew(self):
        self.start(max_verifications=1)
        gp.submit(self.run, self.handoff)
        (self.repo / 'app.py').write_text('def normalize(xs):return []\n')
        self.assertEqual(gp.verify_session(self.run)['status'], 'failed')
        self.assertEqual(gp.repair(self.run)['status'], 'budget_exhausted')
        self.assertFalse(gp.verify_session(self.run)['closed'])
        with self.assertRaises(ContractError):self.start()
        state = self.state();state['started_at'] -= 100
        gp.sealed_write(self.run, 'session-state.json', state)
        self.assertEqual(gp.status(self.run)['status'], 'budget_exhausted')

    def test_timeout_missing_verifier_and_mutating_checks_remain_open(self):
        for kind, command, expected in (
                ('timeout', [sys.executable, '-c', 'import time;time.sleep(2)'], 'timed_out'),
                ('missing', ['/not/a/real/verifier'], 'verification_unavailable'),
                ('mutation', [sys.executable, '-c', "from pathlib import Path;Path('app.py').write_text('changed')"], 'integrity_failed')):
            run = self.root / kind
            gp.start(self.goal, self.repo, run, wall_seconds=30)
            self.checks[0].update(command=command, timeout_seconds=.1)
            self.write_handoff();gp.submit(run, self.handoff)
            if kind == 'mutation':
                with self.assertRaises(ContractError):gp.verify_session(run)
                result = gp.status(run)
            else:
                result = gp.verify_session(run)
            self.assertEqual(result['status'], expected)
            self.assertFalse(result['closed'])

    def test_lock_contention_and_interrupted_attempt(self):
        self.start();gp.submit(self.run, self.handoff)
        with (self.run / 'session.lock').open('a+') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            p = self.cli('status', str(self.run))
            self.assertEqual(p.returncode, 2)
            self.assertIn('already running', p.stderr)
        with patch('goalpilot.session.verify', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):gp.verify_session(self.run)
        self.assertEqual(gp.status(self.run)['status'], 'interrupted')
        self.assertEqual(len(self.state()['verifications']), 1)
        self.assertTrue(gp.verify_session(self.run)['closed'])

    def cli(self, *args, portable=False):
        prefix = [sys.executable, str(ROOT / 'skills/goalpilot/scripts/goalpilot.py')] if portable else [sys.executable, '-m', 'goalpilot']
        return subprocess.run([*prefix, 'session', *args], cwd=ROOT, capture_output=True, text=True, timeout=20)

    def test_cli_portable_end_to_end_and_resume_flags_refused(self):
        p = self.cli('start', '--goal-file', str(self.goal), '--repo', str(self.repo), '--run-dir', str(self.run), portable=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.cli('submit', str(self.run), '--handoff', str(self.handoff), portable=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.cli('verify', str(self.run), portable=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)['closed'])
        p = self.cli('repair', str(self.run), '--wall-seconds', '9999')
        self.assertEqual(p.returncode, 2)
        self.assertTrue(json.loads(self.cli('status', str(self.run)).stdout)['closed'])
        self.assertEqual(gp.sealed_read(self.run, 'session.json')['goal'], self.goal.read_bytes().decode())

    def test_real_bounded_http_behavior_in_protocol(self):
        # The host runs this real socket integration. A denied sandbox remains
        # explicitly skipped here, not an alternative simulated HTTP success.
        try:
            with socket.socket() as sock:sock.bind(('127.0.0.1', 0))
        except PermissionError as exc:
            self.skipTest(f'Host socket permission required: {exc}')
        self.start()
        self.checks[0]['command'] = [sys.executable, '-c', '''import http.server,json,threading,urllib.request
from app import normalize
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path != '/labels':self.send_error(404);return
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps(normalize([' ÉTÉ ','été','B'])).encode())
 def log_message(self,*args):pass
server=http.server.HTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 base='http://127.0.0.1:'+str(server.server_port)
 with urllib.request.urlopen(base+'/labels',timeout=2) as r:assert json.load(r)==['b','été']
 try:urllib.request.urlopen(base+'/missing',timeout=2)
 except urllib.error.HTTPError as e:assert e.code==404
 else:raise AssertionError('missing endpoint must fail')
finally:server.shutdown();server.server_close();thread.join(2)
''']
        self.write_handoff();gp.submit(self.run, self.handoff)
        self.assertTrue(gp.verify_session(self.run)['closed'])
