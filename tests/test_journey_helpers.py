import copy
from pathlib import Path
import tempfile
import time
import unittest

from goalpilot.probe_helpers import JourneyMixin, service_race
from goalpilot.runtime_kit import ServiceBase, fields, integer, require
from goalpilot.support import provision_runtime


class Counter(ServiceBase):
    def initial(self):
        return {'n': 0}

    def validate(self, state):
        fields(state, {'n': integer})

    def handle(self, state, operation, data):
        if operation == 'get':
            fields(data, {})
        elif operation == 'cas':
            fields(data, {'expected': integer, 'value': integer})
            require(state['n'] == data['expected'], 'Conflict')
            state['n'] = data['value']
        elif operation == 'crash':
            raise RuntimeError('Unexpected implementation error')
        elif operation == 'slow':
            time.sleep(1)
        else:
            raise ValueError('Unknown operation')
        return copy.deepcopy(state)


class JourneyHelpersTests(JourneyMixin, unittest.TestCase):
    def setUp(self):
        self.open_service(Counter)

    def test_exact_steps_restart_selected_fields_and_rejection_bytes(self):
        self.assertSteps(('get', {}, {'n': 0}),
                   ('cas', {'expected': 0, 'value': 2}, {'n': 2}))
        original = self.path.read_bytes()
        self.assertRejects('cas', expected=0, value=5)
        self.assertEqual(self.path.read_bytes(), original)
        self.restart()
        self.assertSubset(self.c('get'), n=2)
        with self.assertRaises(AssertionError):
            self.assertSteps(('get', {}, {'n': 999}))
        with self.assertRaises(AssertionError):
            self.assertSubset(self.c('get'), missing=1)

    def test_corruptions_assert_real_failures_and_never_mutate_snapshot(self):
        self.c('cas', expected=0, value=3)
        original = self.path.read_bytes()
        self.assertCorruptions(lambda s: s.update(n=True), lambda s: s.update(n=-1),
                         lambda s: s.update(extra=1))
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaises(AssertionError):
            self.assertCorruptions(lambda s: None)

    def test_two_synchronized_real_processes_preserve_one_winner(self):
        results = self.race(('cas', {'expected': 0, 'value': 5}),
                            ('cas', {'expected': 0, 'value': 6}))
        self.assertEqual(sorted(ok for ok, _ in results), [False, True])
        self.restart()
        self.assertIn(self.c('get')['n'], (5, 6))

    def test_unexpected_process_error_never_counts_as_domain_rejection(self):
        with self.assertRaisesRegex(AssertionError, 'Unexpected implementation error'):
            self.race(('crash', {}), ('get', {}))

    def test_timeout_cleans_real_processes(self):
        import multiprocessing
        before = {p.pid for p in multiprocessing.active_children()}
        start = time.monotonic()
        with self.assertRaises((AssertionError, __import__('threading').BrokenBarrierError)):
            self.race(('slow', {}), ('slow', {}), timeout=.1)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_fixture_not_silently_replaced_and_request_arguments_preserved(self):
        with self.assertRaises(RuntimeError):
            self.open_service(Counter)
        requests = [('cas', {'expected': 0, 'value': 1}), ('cas', {'expected': 0, 'value': 2})]
        original = copy.deepcopy(requests)
        service_race(Counter, self.path, requests)
        self.assertEqual(requests, original)

    def test_invalid_race_fails_before_starting_processes(self):
        for requests, timeout in [([], 8), ([('get', {})], 8), ([('get', {})] * 2, True),
                                  ([('get', {})] * 2, float('nan'))]:
            with self.assertRaises(ValueError):
                service_race(Counter, self.path, requests, timeout=timeout)

    def test_provisioned_helper_is_self_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            provision_runtime(tmp)
            source = (Path(tmp) / 'goalpilot_support.py').read_text()
            self.assertIn('class JourneyMixin:', source)
            self.assertNotIn('from goalpilot.', source)

    def test_frozen_journey_assertions_fail_and_repair_same_acceptance(self):
        from goalpilot import session
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();(repo/'tests').mkdir()
            (repo/'tests/__init__.py').write_text('')
            (repo/'tests/test_legacy.py').write_text(
                'import unittest\nclass Legacy(unittest.TestCase):\n def test_original(self):self.assertEqual(2+2,4)\n')
            implementation="""from goalpilot_runtime import ServiceBase,fields,integer,require
class Service(ServiceBase):
 def initial(self):return {'n':0}
 def validate(self,s):fields(s,{'n':integer})
 def handle(self,s,op,d):
  require(op=='add');fields(d,{'value':integer});s['n']+=integer(d['value']);return s['n']
"""
            app=repo/'app.py';app.write_text(implementation)
            goal=root/'goal.txt';goal.write_text('Persist exact additions; preserve original behavior.')
            run=root/'run';session.start(goal,repo,run,helpers=True,wall_seconds=30)
            (repo/'tests/test_journey.py').write_text("""import unittest
from app import Service
from goalpilot_support import JourneyMixin
class Additions(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_additions(self):self.assertSteps(('add',{'value':2},2),('add',{'value':3},5))
""")
            app.write_text(implementation.replace('+=integer','-=integer'))
            self.assertFalse(session.finish(run)['closed'])
            acceptance=(run/'acceptance.json').read_bytes()
            app.write_text(implementation)
            self.assertTrue(session.finish(run)['closed'])
            self.assertEqual((run/'acceptance.json').read_bytes(),acceptance)
