"""Explicit protocol doubles, not live efficacy measurements."""
import json,sys,tempfile,unittest
from pathlib import Path
from evaluation.native_goals.adapter import NativeGoalAdapter

SHIM=r'''
import json,sys
status='active'
def send(x):print(json.dumps(x),flush=True)
def event(method,**p):send({'method':method,'params':{'threadId':'t',**p}})
def goal(s):return {'threadId':'t','objective':'Test','status':s,'tokensUsed':65,'timeUsedSeconds':1,'createdAt':0,'updatedAt':1,'tokenBudget':None}
for line in sys.stdin:
 r=json.loads(line);m=r.get('method');i=r.get('id')
 if m=='initialize':send({'id':i,'result':{}})
 elif m=='thread/start':
  assert r['params']['ephemeral']is False
  send({'id':i,'result':{'thread':{'id':'t'},'model':'fixture'}})
 elif m=='thread/goal/set':
  requested=r['params']['status'];send({'id':i,'result':{'goal':goal(requested)}})
  if requested!='active':continue
  for n in range(1,3):
   event('turn/started',turn={'id':str(n),'status':'inProgress'})
   total={'inputTokens':100,'outputTokens':10,'cachedInputTokens':80}if n==1 else{'inputTokens':250,'outputTokens':25,'cachedInputTokens':210}
   event('thread/tokenUsage/updated',tokenUsage={'total':total})
   event('item/completed',item={'id':'a'+str(n),'type':'agentMessage','phase':'final_answer','text':'Turn '+str(n)+' finished'})
   if n==2 and 'TERMINAL'!='active':event('thread/goal/updated',goal=goal('TERMINAL'))
   event('turn/completed',turn={'id':str(n),'status':'completed','error':None})
 elif m=='turn/interrupt':send({'id':i,'result':{}})
'''


class NativeGoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
    def execute(self,status,timeout=2,turn_status='completed'):
        script=self.root/'fixture-codex';script.write_text('#!'+sys.executable+'\n'+SHIM.replace('TERMINAL',status).replace("'status':'completed'","'status':"+repr(turn_status)));script.chmod(0o755)
        with NativeGoalAdapter('fixture',executable=str(script))as worker:
            worker.simulated=True;return worker.execute_goal('Complete this test',self.repo,timeout,self.root/'logs')
    def test_waits_for_real_goal_completion_and_counts_all_automatic_turns_once(self):
        r=self.execute('complete');self.assertEqual(r.returncode,0);self.assertEqual(len(r.telemetry['native_turns']),2)
        self.assertEqual(r.usage,{'input_tokens':250,'output_tokens':25,'cached_input_tokens':210});self.assertTrue(r.usage_complete)
        self.assertEqual(r.telemetry['native_goal_at_stop']['status'],'complete');self.assertTrue(r.simulated)
    def test_native_blocked_goal_is_never_relabelled_as_complete(self):
        r=self.execute('blocked');self.assertNotEqual(r.returncode,0);self.assertEqual(r.telemetry['native_goal_at_stop']['status'],'blocked');self.assertTrue(r.usage_complete)
    def test_goal_flag_before_failed_final_turn_is_not_normal_delivery(self):
        r=self.execute('complete',turn_status='failed');self.assertNotEqual(r.returncode,0);self.assertFalse(r.usage_complete)
    def test_time_cap_pauses_its_own_goal_and_keeps_counters_incomplete(self):
        r=self.execute('active',.25);self.assertTrue(r.timed_out);self.assertFalse(r.usage_complete)
        self.assertEqual(r.telemetry['native_goal_at_stop']['status'],'active');self.assertEqual(r.telemetry['cleanup_goal']['status'],'paused')

class NativeGoalCaseTests(unittest.TestCase):
    def test_real_worker_reference_passes_and_behavioral_faults_are_detected(self):
        from evaluation.native_goals.preflight import run
        data=run();self.assertEqual(data['runforge']['reference_groups_passed'],26);self.assertEqual(data['automation']['reference_groups_passed'],32)
        self.assertEqual(len(data['automation']['isolated_worker_faults_rejected']),4)
