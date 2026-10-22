"""Real storage/transport assertions; helper correctness, not product savings."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from goalpilot.runtime_kit import JsonStore, atomic_json, jsonl_main
from goalpilot.probe_helpers import json_http
from goalpilot.support import provision_runtime
from goalpilot.model import ContractError


class RuntimeKitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_transaction_roundtrip_rollback_no_write_and_corrupt_state(self):
        path=self.root/'db.json';s=JsonStore(path,{'n':0})
        self.assertEqual(s.read(),{'n':0});self.assertFalse(path.exists())
        with s.transaction() as state:state['n']=1
        before=path.read_bytes()
        with self.assertRaises(ValueError):
            with s.transaction() as state:state['n']=9;raise ValueError('no')
        self.assertEqual(path.read_bytes(),before)
        with s.transaction() as state:pass
        self.assertEqual(path.read_bytes(),before)
        detached=s.read();detached['n']=4
        self.assertEqual(JsonStore(path).read(),{'n':1})
        path.write_text('[]')
        with self.assertRaises(ValueError):s.read()
        self.assertEqual(path.read_text(),'[]')

    def test_same_path_nested_transactions_refused_across_instances(self):
        s=JsonStore(self.root/'db.json',{'n':0})
        with s.transaction():
            with self.assertRaises(RuntimeError):
                with JsonStore(self.root/'db.json').transaction():pass
        self.assertEqual(s.read(),{'n':0})

    def test_real_concurrent_transactions_lose_no_updates(self):
        path=self.root/'db.json'; errors=[]
        def update():
            try:
                s=JsonStore(path,{'n':0})
                for _ in range(15):
                    with s.transaction() as state:state['n']+=1
            except BaseException as exc:errors.append(exc)
        workers=[threading.Thread(target=update)for _ in range(4)]
        for t in workers:t.start()
        for t in workers:t.join(timeout=5)
        self.assertFalse(any(t.is_alive()for t in workers));self.assertEqual(errors,[])
        self.assertEqual(JsonStore(path).read(),{'n':60})

    def test_atomic_rejection_preserves_original(self):
        path=self.root/'x.json';path.write_bytes(b'original')
        for bad in ({'n':float('nan')},{'x':object()}):
            with self.assertRaises((TypeError,ValueError)):atomic_json(path,bad)
            self.assertEqual(path.read_bytes(),b'original')
        atomic_json(path,{'café':[1,2]});self.assertEqual(json.loads(path.read_text()),{'café':[1,2]})

    def test_jsonl_framing_errors_continue_unicode(self):
        source=io.StringIO('{"operation":"echo","data":{"x":"été"}}\ninvalid\n[]\n{"operation":"echo"}\n')
        target=io.StringIO();jsonl_main(lambda op,data:data,source,target)
        rows=[json.loads(x)for x in target.getvalue().splitlines()]
        self.assertEqual(len(rows),4);self.assertEqual(rows[0],{'ok':True,'result':{'x':'été'}})
        self.assertFalse(rows[1]['ok']);self.assertFalse(rows[2]['ok']);self.assertTrue(rows[3]['ok'])

    def test_portable_http_real_process_and_no_external_engine_imports(self):
        provision_runtime(self.root)
        script=self.root/'server.py';script.write_text('from goalpilot_runtime import serve\nserve(lambda op,data: {"op":op,"data":data})\n')
        with json_http([sys.executable,str(script)],cwd=self.root) as req:
            self.assertEqual(req('GET','/health'),{'ok':True})
            self.assertEqual(req('POST','/api',{'operation':'echo','data':{'café':2}})['result']['data'],{'café':2})
            self.assertFalse(req('POST','/api',[],status=400)['ok'])
            self.assertFalse(req('GET','/missing',status=404)['ok'])
        self.assertNotIn('from .',(self.root/'goalpilot_runtime.py').read_text())

    def test_provision_refuses_collision_before_mutating_any_helper(self):
        (self.root/'goalpilot_support.py').write_text('user source')
        with self.assertRaises(ContractError):provision_runtime(self.root)
        self.assertFalse((self.root/'goalpilot_runtime.py').exists())
        self.assertEqual((self.root/'goalpilot_support.py').read_text(),'user source')

class ServiceBaseTests(unittest.TestCase):
    def test_base_transactions_restore_validation_idempotent_and_detachment(self):
        from goalpilot.runtime_kit import ServiceBase,require,integer,idempotent
        class Counter(ServiceBase):
            def initial(self):return {'n':0,'keys':{}}
            def validate(self,s):
                require(isinstance(s,dict)and set(s)=={'n','keys'});integer(s['n']);require(isinstance(s['keys'],dict))
            def handle(self,s,op,d):
                require(op=='add');amount=integer(d.get('amount'),1)
                def apply():s['n']+=amount;return {'n':s['n']}
                return idempotent(s,d['key'],op,{'amount':amount},apply)
        with tempfile.TemporaryDirectory()as tmp:
            path=Path(tmp)/'db';s=Counter(path)
            self.assertEqual(s.call('add',{'amount':2,'key':'a'}),{'n':2})
            snap=s.call('backup',{});s.call('add',{'amount':3,'key':'b'})
            self.assertEqual(s.call('add',{'amount':2,'key':'a'}),{'n':2})
            self.assertEqual(s.call('backup',{})['n'],5)
            before=path.read_bytes()
            for op,d in [('restore',{'state':{'n':-1,'keys':{}}}),('add',{'amount':3,'key':'a'}),('add',{'amount':True,'key':'a'})]:
                with self.assertRaises(ValueError):s.call(op,d)
                self.assertEqual(path.read_bytes(),before)
            s.call('restore',{'state':snap});snap['n']=99
            self.assertEqual(s.call('backup',{})['n'],2)

    def test_json_store_does_not_confuse_boolean_with_integer_change(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'db';s=JsonStore(p,{'value':0})
            with s.transaction()as state:state['value']=1
            with s.transaction()as state:state['value']=True
            self.assertIs(s.read()['value'],True)

    def test_common_validation_revision_pagination_and_receipt_conflict(self):
        from goalpilot.runtime_kit import text,integer,identifiers,page,compare_revision,idempotent
        self.assertEqual(identifiers(['b','a','b']),['a','b'])
        for bad in [True,1.0,'1',None]:
            with self.assertRaises(ValueError):integer(bad)
        self.assertEqual(page([{'id':'c'},{'id':'a'},{'id':'b'}],limit=1),{'items':[{'id':'a'}],'next':'a'})
        self.assertEqual(page([{'id':'a'},{'id':'b'}],after='a',limit=1)['next'],None)
        with self.assertRaises(ValueError):compare_revision({'revision':2},1)
        s={};idempotent(s,'k','op',{'x':1},lambda:9)
        with self.assertRaises(ValueError):idempotent(s,'k','op',{'x':True},lambda:9)

class SchemaTests(unittest.TestCase):
    def test_nested_schema_validates_without_mutating_and_rejects_real_faults(self):
        from goalpilot.runtime_kit import fields,sequence,mapping,text,integer,boolean,choice,nullable
        schema=lambda x:fields(x,{'records':mapping(lambda r:fields(r,{'name':text,'active':boolean,'state':choice('open','closed'),'n':integer,'tags':sequence(text)}, {'parent':nullable(text)}))})
        good={'records':{'a':{'name':'A','active':True,'state':'open','n':2,'tags':['x'],'parent':None}}}
        raw=json.dumps(good);self.assertIs(schema(good),good);self.assertEqual(json.dumps(good),raw)
        import copy
        for field,value in [('active',1),('state',[]),('n',True),('tags','x'),('name',''),('parent',2)]:
            bad=copy.deepcopy(good);bad['records']['a'][field]=value
            with self.assertRaises(ValueError):schema(bad)
        for bad in ({},{'records':[]},{'records':{'a':{}}},{**good,'extra':1}):
            with self.assertRaises(ValueError):schema(bad)

    def test_iterative_dag_large_graph_cycles_missing_and_order(self):
        from goalpilot.runtime_kit import dag
        graph={str(i):[str(i-1)]if i else []for i in range(1500)}
        self.assertIs(dag(graph),graph)
        for bad in ({'a':['a']},{'a':['b'],'b':['a']},{'a':['missing']},{'a':[],'b':['a','a']}):
            with self.assertRaises(ValueError):dag(bad)

class PortableJourneyTests(unittest.TestCase):
    def test_real_portable_servicebase_cli_http_expected_results_and_negative_helper(self):
        from goalpilot.probe_helpers import transport_journey,rejected_unchanged
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);provision_runtime(root)
            (root/'app.py').write_text('''from goalpilot_runtime import ServiceBase,fields,integer,require
class Service(ServiceBase):
 def initial(self):return {'n':0}
 def validate(self,s):fields(s,{'n':integer})
 def handle(self,s,op,d):
  require(op in ('get','add'))
  if op=='add':s['n']+=integer(d.get('n'),1)
  return {'n':s['n']}
if __name__=='__main__':Service.main()
''')
            argv=[sys.executable,str(root/'app.py'),'--file',str(root/'db.json')]
            from goalpilot.probe_helpers import jsonl
            self.assertEqual(jsonl([*argv,'jsonl'],[{'operation':'add','data':{'n':2}}])[0]['result'],{'n':2})
            transport_journey(argv,[('get',{}, {'n':2}),('add',{'n':3},{'n':5}),('backup',{}, {'n':5})],cwd=root)
            self.assertEqual(json.loads((root/'db.json').read_text()),{'n':2})
            path=root/'db.json'
            rejected_unchanged(lambda: (_ for _ in ()).throw(ValueError('bad')),path)
            def corrupt():path.write_text('corrupt');raise ValueError('bad')
            with self.assertRaises(AssertionError):rejected_unchanged(corrupt,path)
