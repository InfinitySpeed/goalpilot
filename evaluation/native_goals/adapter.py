"""Drive real native /goal lifecycle, including all automatic continuation turns."""
import copy,json,time
from pathlib import Path
from goalpilot.adapters import AgentResult
from goalpilot.rpc import AppServerAdapter,ProtocolError


class NativeGoalAdapter(AppServerAdapter):
    def _request(self,method,params,deadline):
        if method=='thread/start':params={**params,'ephemeral':False}
        return super()._request(method,params,deadline)

    def _receive(self,deadline):
        packet=super()._receive(deadline);method=packet.get('method');p=packet.get('params',{})
        if p.get('threadId')==self.thread_id:
            if method=='turn/started':self.active=True
            if method=='thread/goal/updated':self.native_goal=p['goal']
            if method=='turn/completed':self.native_turns.append(copy.deepcopy(p['turn']))
        return packet

    def execute_goal(self,objective,repo,timeout,log_dir,max_tokens=1500000):
        start=time.monotonic();deadline=start+timeout;repo=Path(repo).resolve();log_dir=Path(log_dir);log_dir.mkdir(parents=True,exist_ok=True)
        self.messages=[];self.final_messages=[];self.finished=None;self.turn_id=None;self.usage_updates=0;self.command_count=0;self.native_goal=None;self.native_turns=[]
        timed_out=False;fatal=False;error=None;budget_hit=False;stopped=None;cleanup=None
        with(log_dir/'events.jsonl').open('w')as stream:
            self.writer=stream
            try:
                self._start(repo,False,log_dir,deadline)
                result=self._request('thread/goal/set',{'threadId':self.thread_id,'objective':objective,'status':'active','origin':'user','tokenBudget':None},deadline)
                if result.get('goal'):self.native_goal=result['goal']
                while True:
                    status=(self.native_goal or{}).get('status')
                    if status in('complete','blocked','paused','usageLimited','budgetLimited')and not self.active:break
                    if not self.active and self.native_turns and self.total and self.total['input_tokens']+self.total['output_tokens']>=max_tokens:
                        budget_hit=True;break
                    self._receive(deadline)
                stopped=copy.deepcopy(self.native_goal)
            except TimeoutError:
                timed_out=True;stopped=copy.deepcopy(self.native_goal)
            except(OSError,ValueError,ProtocolError)as exc:
                fatal=True;error=f'{type(exc).__name__}: {exc}';stopped=copy.deepcopy(self.native_goal)
            finally:
                if self.thread_id:
                    # A fresh benchmark goal must never continue after its trial.
                    # Keep the true observed outcome separate from this cleanup.
                    try:
                        if(stopped or{}).get('status')not in('complete','blocked','usageLimited','budgetLimited'):
                            reply=self._request('thread/goal/set',{'threadId':self.thread_id,'status':'paused','origin':'automatic'},time.monotonic()+2);cleanup=reply.get('goal')
                        if self.active and self.turn_id:self._request('turn/interrupt',{'threadId':self.thread_id,'turnId':self.turn_id},time.monotonic()+2)
                    except(OSError,ValueError,TimeoutError):pass
                self.writer=None
        status=(stopped or{}).get('status');usage=copy.deepcopy(self.total)
        normal=status=='complete'and not timed_out and not budget_hit and not self.active and bool(self.native_turns)and self.native_turns[-1].get('status')=='completed'
        if status=='usageLimited':fatal=True
        errors=json.dumps([t.get('error')for t in self.native_turns if t.get('error')]).lower()
        if any(word in errors for word in('unauthorized','authentication','quota','rate limit','access token','401','403','429')):fatal=True
        all_complete=bool(self.native_turns)and all(t.get('status')=='completed'for t in self.native_turns)
        telemetry={'backend':'app-server-native-goal','model':self.metadata,'native_goal_at_stop':stopped,'cleanup_goal':cleanup,'raw_soft_token_budget_hit':budget_hit,
        'native_turns':[{'id':t['id'],'status':t['status'],'error':t.get('error')}for t in self.native_turns],'usage_updates':self.usage_updates,'command_count':self.command_count,'context_prepared':False,'context_seconds':0,'turn_status':status,'error':error}
        message='\n'.join(self.final_messages or self.messages)
        return AgentResult(0 if normal else 124 if timed_out else 1,message,time.monotonic()-start,usage,timed_out,fatal,
        simulated=self.simulated,usage_complete=bool(usage is not None and all_complete and not timed_out and not self.active),thread_id=self.thread_id,turn_id=self.turn_id,telemetry=telemetry)
