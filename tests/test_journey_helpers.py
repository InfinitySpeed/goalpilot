import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
import sys

from goalpilot.probe_helpers import JourneyMixin, service_race, rejects
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

    def test_one_flow_runs_on_three_isolated_real_interfaces(self):
        self.c('cas',expected=0,value=3)
        original=self.path.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);provision_runtime(root)
            app=root/'app.py'
            app.write_text("from goalpilot_runtime import ServiceBase,fields,integer,require\nclass Service(ServiceBase):\n def initial(self):return {'n':0}\n def validate(self,s):fields(s,{'n':integer})\n def handle(self,s,op,d):\n  if op=='get':fields(d,{})\n  else:\n   require(op=='cas');fields(d,{'expected':integer,'value':integer});require(s['n']==d['expected']);s['n']=d['value']\n  return dict(s)\nif __name__=='__main__':Service.main()\n")
            seen=[]
            def flow(c):
                self.assertEqual(c('get'),{'n':3})
                self.assertEqual(c('cas',expected=3,value=7),{'n':7})
                rejects(lambda:c('cas',expected=3,value=9))
                self.assertEqual(c('get'),{'n':7})
                seen.append(True)
            self.assertJourney(flow,[sys.executable,str(app),'--file',str(self.path)])
            self.assertEqual(len(seen),3)
        self.assertEqual(self.path.read_bytes(),original)

    def test_flow_propagates_business_assertion_failure(self):
        def flow(c):self.assertEqual(c('get'),{'n':999})
        with self.assertRaises(AssertionError):self.assertJourney(flow)
        self.assertFalse(self.path.exists())

    def test_flow_rejects_unrelated_fixture_before_execution(self):
        with self.assertRaises(ValueError):
            self.assertJourney(lambda c:self.fail('Must not execute'),[sys.executable,'app.py','--file','other.json'])

    def test_flow_supports_dynamic_ids_without_sharing_generated_state(self):
        from goalpilot.runtime_kit import ReplayService
        class Records(ReplayService):
            def initial(inner):return {'items':{}}
            def handle(inner,s,op,d):
                if op=='create':
                    identifier=inner.opaque();s['items'][identifier]={'id':identifier,'value':d['value']}
                    return s['items'][identifier]
                require(op=='get' and d['id']in s['items']);return s['items'][d['id']]
        class Fixture(JourneyMixin,unittest.TestCase):pass
        fixture=Fixture();fixture.open_service(Records)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);provision_runtime(root);app=root/'app.py'
                app.write_text("from goalpilot_runtime import ReplayService,require\nclass Service(ReplayService):\n def initial(self):return {'items':{}}\n def handle(self,s,op,d):\n  if op=='create':\n   identifier=self.opaque();s['items'][identifier]={'id':identifier,'value':d['value']};return s['items'][identifier]\n  require(op=='get' and d['id']in s['items']);return s['items'][d['id']]\nif __name__=='__main__':Service.main()\n")
                ids=[]
                def flow(c):
                    created=c('create',value='café 東京')
                    self.assertEqual(c('get',id=created['id']),created)
                    rejects(lambda:c('get',id='unknown'))
                    ids.append(created['id'])
                fixture.assertJourney(flow,[sys.executable,str(app),'--file',str(fixture.path)])
                self.assertEqual(len(set(ids)),3)
                self.assertFalse(fixture.path.exists())
        finally:fixture.doCleanups()

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
            code="from app import Service; s=object.__new__(Service); state={'n':0}; assert s.handle(state,'add',{'value':2})==2; assert s.handle(state,'add',{'value':3})==5; s.validate(state)"
            handoff=root/'handoff.json';handoff.write_text(json.dumps({'summary':'Persist additions',
                'checks':[{'id':'journey','description':'The domain test suite passes',
                           'command':[sys.executable,'-B','-c',code],
                           'timeout_seconds':8}],
                'criteria':[{'id':'additions','statement':'Persist exact additions',
                             'source_quote':'Persist exact additions','check_ids':['journey']}],
                'requirements':[{'id':'persist-additions','statement':'Persist the requested additions',
                                'source_quote':'Persist exact additions','criterion_ids':['additions']}]}))
            session.submit(run,handoff)
            self.assertFalse(session.finish(run)['closed'])
            acceptance=(run/'acceptance.json').read_bytes()
            app.write_text(implementation)
            final=session.finish(run)
            self.assertTrue(final['closed'],final)
            self.assertEqual((run/'acceptance.json').read_bytes(),acceptance)
