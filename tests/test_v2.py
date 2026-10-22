from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import unittest

from goalpilot.dossier import prepare,render
from goalpilot.engine import token_totals
from goalpilot.rpc import AppServerAdapter,ProtocolError,normalize_usage


SHIM = r'''import json,sys
turn=0
def emit(value):
 print(json.dumps(value),flush=True)
for line in sys.stdin:
 p=json.loads(line)
 method=p.get('method')
 if method=='initialize':emit({'id':p['id'],'result':{'userAgent':'test-double'}})
 elif method=='thread/start':
  assert p['params']['approvalPolicy']=='never'
  assert p['params']['sandbox']=='workspace-write'
  emit({'id':p['id'],'result':{'thread':{'id':'thread-one'},'model':'fixture-model'}})
 elif method=='turn/start':
  turn+=1
  prompt=p['params']['input'][0]['text']
  if 'PREPARED_TEST' in prompt:
   assert ('LOCAL REPOSITORY SNAPSHOT' in prompt)==(turn==1)
  emit({'id':p['id'],'result':{'turn':{'id':f'turn-{turn}'}}})
  emit({'method':'thread/tokenUsage/updated','params':{'threadId':'thread-one','turnId':f'turn-{turn}','tokenUsage':{'total':{'inputTokens':100*turn,'outputTokens':10*turn,'cachedInputTokens':50*turn}}}})
  emit({'method':'item/completed','params':{'threadId':'thread-one','item':{'type':'agentMessage','text':'fixture handoff'}}})
  if 'TIMEOUT_TEST' not in prompt:
   emit({'method':'turn/completed','params':{'threadId':'thread-one','turn':{'id':f'turn-{turn}','status':'completed','items':[]}}})
 elif method=='turn/interrupt':
  emit({'id':p['id'],'result':{}})
  emit({'method':'turn/completed','params':{'threadId':'thread-one','turn':{'id':f'turn-{turn}','status':'interrupted','items':[]}}})
'''


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/'repo'
        self.repo.mkdir()
        self.shim=self.root/'fixture-codex'
        self.shim.write_text(f'#!{sys.executable}\n'+SHIM)
        self.shim.chmod(0o755)

    def test_dossier_includes_context_not_credentials_or_symlinks(self):
        (self.repo/'README.md').write_text('public interface')
        (self.repo/'main.py').write_text('print(42)')
        (self.repo/'.env').write_text('do not read')
        (self.repo/'credentials.json').write_text('do not read')
        (self.repo/'auth.json').write_text('do not read')
        (self.repo/'link.py').symlink_to(self.repo/'main.py')
        dossier=prepare(self.repo)
        self.assertEqual({x['path'] for x in dossier['files']},{'main.py','README.md'})
        self.assertTrue(dossier['all_candidates_included'])
        self.assertNotIn('do not read',render(dossier))

    def test_dossier_explicitly_labels_truncation(self):
        (self.repo/'large.py').write_text('x'*200)
        dossier=prepare(self.repo,max_bytes=50)
        self.assertEqual(dossier['source_bytes'],50)
        self.assertFalse(dossier['files'][0]['complete'])
        self.assertFalse(dossier['all_candidates_included'])

    def test_rpc_reuses_thread_and_counts_incremental_not_cumulative_twice(self):
        with AppServerAdapter(executable=str(self.shim),prepared=True) as adapter:
            first=adapter.execute('PREPARED_TEST',self.repo,2,self.root/'call1')
            second=adapter.execute('PREPARED_TEST',self.repo,2,self.root/'call2')
        self.assertEqual(first.thread_id,second.thread_id)
        self.assertEqual(first.usage['input_tokens'],100)
        self.assertEqual(second.usage['input_tokens'],100)
        self.assertTrue(first.usage_complete and second.usage_complete)
        usage=token_totals([{'result':asdict(x)} for x in [first,second]])
        self.assertEqual(usage['total_tokens'],220)
        self.assertTrue(usage['usage_complete'])
        self.assertTrue(first.telemetry['context_prepared'])
        self.assertFalse(second.telemetry['context_prepared'])

    def test_interrupted_usage_is_preserved_but_not_falsely_complete(self):
        with AppServerAdapter(executable=str(self.shim)) as adapter:
            result=adapter.execute('TIMEOUT_TEST',self.repo,.2,self.root/'timeout')
        self.assertTrue(result.timed_out)
        self.assertEqual(result.usage['input_tokens'],100)
        self.assertFalse(result.usage_complete)
        totals=token_totals([{'result':asdict(result)}])
        self.assertEqual(totals['calls_with_partial_usage'],1)
        self.assertEqual(totals['total_tokens'],110)
        self.assertFalse(totals['usage_complete'])

    def test_invalid_usage_is_rejected(self):
        with self.assertRaises(ProtocolError):normalize_usage({'inputTokens':10,'outputTokens':2,'cachedInputTokens':20})
        with self.assertRaises(ProtocolError):normalize_usage({'inputTokens':True,'outputTokens':2,'cachedInputTokens':0})

    def test_final_contract_uses_prompt_and_preserves_server_cache_prefix(self):
        schema=self.root/'schema.json'
        schema.write_text(json.dumps({'type':'object','properties':{'answer':{'type':'string'}}}))
        logs=self.root/'schema-call'
        with AppServerAdapter(executable=str(self.shim)) as adapter:
            result=adapter.execute('Complete task',self.repo,2,logs,schema=schema)
        self.assertEqual(result.returncode,0)
        packets=[json.loads(line)['packet'] for line in (logs/'events.jsonl').read_text().splitlines()]
        turn=next(x for x in packets if x.get('method')=='turn/start')
        self.assertNotIn('outputSchema',turn['params'])
        text=turn['params']['input'][0]['text']
        self.assertIn(schema.read_text(),text)
        self.assertIn('Return ONLY',text)

    def test_missing_backend_is_fatal_without_retries(self):
        with AppServerAdapter(executable='/no/such/codex') as adapter:
            result=adapter.execute('do work',self.repo,1,self.root/'missing')
        self.assertTrue(result.fatal)
        self.assertIsNone(result.usage)


if __name__=='__main__':unittest.main()
