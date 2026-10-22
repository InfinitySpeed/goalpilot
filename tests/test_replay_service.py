"""Real replay/storage/transport checks; no scripted utility counters."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from goalpilot.runtime_kit import ReplayService, fields, integer, require, text, idempotent
from goalpilot.probe_helpers import service_race, transport_journey
from goalpilot.support import provision_runtime


class Wallet(ReplayService):
    def initial(self):
        return {'balance': 0, 'receipts': {}, 'keys': {}}

    def handle(self, state, operation, data):
        if operation == 'get':
            fields(data, {})
            return {'balance': state['balance']}
        require(operation in ('credit', 'spend'))
        fields(data, {'amount': lambda n: integer(n, 1), 'key': text})
        def apply():
            require(operation == 'credit' or state['balance'] >= data['amount'], 'Insufficient funds')
            state['balance'] += data['amount'] * (1 if operation == 'credit' else -1)
            receipt = self.opaque()
            state['receipts'][receipt] = {'operation': operation, 'amount': data['amount']}
            return {'id': receipt, 'balance': state['balance']}
        return idempotent(state, data['key'], operation, data, apply)


class ReplayServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'db.json';self.service=Wallet(self.path)

    def test_successful_history_replay_restart_idempotency_restore_and_continuation(self):
        request={'amount': 10, 'key': 'initial'};original=copy.deepcopy(request)
        first=self.service.call('credit',request)
        self.assertEqual(request,original)
        self.assertEqual(first['balance'],10)
        saved=self.service.call('backup',{})
        self.service.call('spend',{'amount':4,'key':'spend'})
        self.assertEqual(Wallet(self.path).call('credit',request),first)
        self.assertEqual(Wallet(self.path).call('get',{}),{'balance':6})
        self.service.call('restore',{'state':saved})
        next_result=Wallet(self.path).call('spend',{'amount':3,'key':'later'})
        self.assertEqual(next_result['balance'],7)
        self.assertNotEqual(next_result['id'],first['id'])
        self.assertEqual(saved['state']['balance'],10)

    def test_forged_state_and_unreachable_history_reject_without_data_loss(self):
        self.service.call('credit',{'amount':10,'key':'initial'})
        saved=self.service.call('backup',{});original=self.path.read_bytes()
        mutations=[lambda s:s['state'].update(balance=999),
                   lambda s:s.update(extra=True),
                   lambda s:s['events'][0]['data'].update(amount=True),
                   lambda s:s['events'][0].update(result={}),
                   lambda s:s['events'][0].update(operation='spend'),
                   lambda s:s['events'][0].update(entropy=[]),
                   lambda s:s['events'][0].update(entropy=['invalid']),
                   lambda s:s['events'][0].update(entropy=s['events'][0]['entropy']*2)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                candidate=copy.deepcopy(saved);mutate(candidate)
                with self.assertRaises(ValueError):self.service.call('restore',{'state':candidate})
                self.assertEqual(self.path.read_bytes(),original)
        with self.assertRaises(ValueError):self.service.call('restore',{'state':{'balance':10}})

    def test_failed_requests_never_consume_keys_entropy_or_data_bytes(self):
        self.service.call('credit',{'amount':3,'key':'initial'});original=self.path.read_bytes()
        for data in [{'amount':4,'key':'retry'},{'amount':True,'key':'retry'},{'amount':1,'key':'initial'}]:
            with self.assertRaises(ValueError):self.service.call('spend',data)
            self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(self.service.call('spend',{'amount':2,'key':'retry'})['balance'],1)

    def test_readonly_call_does_not_create_data_or_grow_log(self):
        self.assertEqual(self.service.call('get',{}),{'balance':0})
        self.assertFalse(self.path.exists())
        self.service.call('credit',{'amount':1,'key':'x'});before=self.path.read_bytes()
        self.assertEqual(len(self.service.call('backup',{})['events']),1)
        self.service.call('get',{});self.assertEqual(self.path.read_bytes(),before)

    def test_boolean_numeric_tampering_not_hidden_by_python_equality(self):
        self.service.call('credit',{'amount':1,'key':'x'})
        candidate=self.service.call('backup',{});candidate['state']['balance']=True
        with self.assertRaises(ValueError):self.service.call('restore',{'state':candidate})

    def test_duplicate_entropy_and_fabricated_query_events_are_invalid(self):
        self.service.call('credit',{'amount':2,'key':'a'})
        self.service.call('credit',{'amount':3,'key':'b'})
        saved=self.service.call('backup',{});original=self.path.read_bytes()
        duplicate=copy.deepcopy(saved)
        duplicate['events'][1]['entropy']=duplicate['events'][0]['entropy']
        with self.assertRaisesRegex(ValueError,'entropy'):
            self.service.call('restore',{'state':duplicate})
        query=copy.deepcopy(saved)
        query['events'].append({'operation':'get','data':{},'entropy':[],'result':{'balance':5}})
        with self.assertRaisesRegex(ValueError,'not a mutation'):
            self.service.call('restore',{'state':query})
        self.assertEqual(self.path.read_bytes(),original)

    def test_explicit_invariant_hook_is_never_silently_ignored(self):
        class Capped(Wallet):
            def validate(self,s):
                require(0<=integer(s['balance'])<=10,'Balance cap')
        service=Capped(self.path)
        with self.assertRaisesRegex(ValueError,'cap'):
            service.call('credit',{'amount':11,'key':'first'})
        self.assertFalse(self.path.exists())
        service.call('credit',{'amount':9,'key':'first'});before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'cap'):
            service.call('credit',{'amount':2,'key':'second'})
        self.assertEqual(self.path.read_bytes(),before)

    def test_dependent_state_machine_replay_enforces_reference_and_order_rules(self):
        class Pipeline(ReplayService):
            def initial(self):return {'nodes':{}}
            def handle(self,s,op,d):
                if op=='add':
                    fields(d,{'id':text,'parent':text});name=d['id'];parent=d['parent']
                    require(name not in s['nodes'])
                    require(parent=='root' or parent in s['nodes'])
                    s['nodes'][name]={'parent':parent,'done':False}
                else:
                    require(op=='complete');fields(d,{'id':text});node=s['nodes'][d['id']]
                    require(not node['done'])
                    require(node['parent']=='root' or s['nodes'][node['parent']]['done'])
                    node['done']=True
                return copy.deepcopy(s['nodes'][d['id']])
        path=self.root/'pipeline.json';s=Pipeline(path)
        for name,parent in [('a','root'),('b','a')]:s.call('add',{'id':name,'parent':parent})
        before=path.read_bytes()
        with self.assertRaises(ValueError):s.call('complete',{'id':'b'})
        self.assertEqual(path.read_bytes(),before)
        s.call('complete',{'id':'a'});s.call('complete',{'id':'b'})
        saved=s.call('backup',{});bad=copy.deepcopy(saved)
        bad['events'][0]['data']['parent']='missing'
        with self.assertRaises(ValueError):s.call('restore',{'state':bad})
        self.assertEqual(Pipeline(path).call('backup',{}),saved)

    def test_cache_cannot_hide_modified_envelope_and_snapshots_are_detached(self):
        result=self.service.call('credit',{'amount':4,'key':'x'});result['balance']=999
        saved=self.service.call('backup',{});saved['state']['balance']=999
        self.assertEqual(self.service.call('get',{}),{'balance':4})
        self.path.write_text(json.dumps(saved))
        with self.assertRaises(ValueError):self.service.call('get',{})

    def test_two_real_processes_cannot_overspend(self):
        self.service.call('credit',{'amount':10,'key':'x'})
        results=service_race(Wallet,self.path,[('spend',{'amount':7,'key':'a'}),('spend',{'amount':7,'key':'b'})])
        self.assertEqual(sorted(ok for ok,_ in results),[False,True])
        self.assertEqual(Wallet(self.path).call('get',{}),{'balance':3})

    def test_nondeterministic_mutation_refused_before_commit(self):
        import secrets
        class Impure(ReplayService):
            def initial(self):return {}
            def handle(self,s,op,d):s['random']=secrets.token_hex(16);return s['random']
        service=Impure(self.path)
        with self.assertRaisesRegex(ValueError,'deterministic'):service.call('change',{})
        self.assertFalse(self.path.exists())
        with self.assertRaises(RuntimeError):service.opaque()

    def test_replay_budget_never_changes_old_state_or_allows_unsafe_restore(self):
        service=Wallet(self.path,max_events=1)
        service.call('credit',{'amount':3,'key':'x'});before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'budget'):service.call('credit',{'amount':1,'key':'y'})
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(service.call('get',{}),{'balance':3})
        for bad in [True,0,-1,1.5]:
            with self.assertRaises(ValueError):Wallet(self.path,max_events=bad)

    def test_portable_reducer_real_jsonl_http_and_malformed_recovery(self):
        provision_runtime(self.root)
        app=self.root/'app.py';app.write_text('''from goalpilot_runtime import ReplayService,fields,integer,require
class Service(ReplayService):
 def initial(self):return {'n':0}
 def handle(self,s,op,d):
  require(op in ('get','add'))
  if op=='add':fields(d,{'value':integer});s['n']+=d['value']
  else:fields(d,{})
  return {'n':s['n']}
if __name__=='__main__':Service.main()
''')
        transport_journey([sys.executable,str(app),'--file',str(self.path)],
                          [('get',{}, {'n':0}),('add',{'value':2},{'n':2}),('get',{}, {'n':2})])
        self.assertFalse(self.path.exists())


if __name__=='__main__':unittest.main()
