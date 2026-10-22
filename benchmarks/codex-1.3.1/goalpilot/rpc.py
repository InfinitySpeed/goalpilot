"""Codex app-server NDJSON client with incremental usage and reusable threads."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time

from .adapters import AgentResult
from . import __version__


class ProtocolError(RuntimeError):
    pass


def normalize_usage(value: dict) -> dict:
    fields = {'input_tokens':'inputTokens','output_tokens':'outputTokens','cached_input_tokens':'cachedInputTokens'}
    if any(type(value.get(v)) is not int or value[v] < 0 for v in fields.values()):
        raise ProtocolError('Invalid token usage counters')
    result = {key:value[source] for key,source in fields.items()}
    if result['cached_input_tokens'] > result['input_tokens']:
        raise ProtocolError('Cached tokens exceed input tokens')
    return result


class AppServerAdapter:
    simulated = False

    def __init__(self, model=None, *, executable='codex', prepared=False, effort=None):
        self.model = model
        self.executable = executable
        self.prepared = prepared
        if effort not in (None, 'low', 'medium', 'high'):
            raise ValueError('Unsupported reasoning effort')
        self.effort = effort
        self.process = None
        self.repo = None
        self.thread_id = None
        self.readonly = None
        self.total = None
        self.counter = 0
        self.inbox = queue.Queue()
        self.responses = {}
        self.writer = None
        self.active = False
        self.metadata = {}

    def _log(self, direction, packet):
        if self.writer and not str(packet.get('method','')).startswith('account/'):
            self.writer.write(json.dumps({'at':time.time(),'direction':direction,'packet':packet},ensure_ascii=False)+'\n')
            self.writer.flush()

    def _send(self, packet):
        self._log('send',packet)
        self.process.stdin.write(json.dumps(packet,ensure_ascii=False)+'\n')
        self.process.stdin.flush()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    packet = json.loads(line)
                except ValueError:
                    continue
                self.inbox.put(packet)
        finally:
            self.inbox.put(None)

    def _receive(self, deadline):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('App-server deadline')
        try:
            packet = self.inbox.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError('App-server deadline') from None
        if packet is None:
            raise ProtocolError('Codex app-server closed its output')
        self._log('receive',packet)
        if 'method' not in packet:
            self.responses[packet.get('id')] = packet
            return packet
        if 'id' in packet:
            # Preserve noninteractive approval policy; never silently grant an escalation.
            self._send({'id':packet['id'],'error':{'code':-32601,'message':'Noninteractive GoalPilot client; interactive tool requests are unavailable'}})
            return packet
        method, params = packet['method'], packet.get('params',{})
        if method == 'thread/tokenUsage/updated' and params.get('threadId') == self.thread_id:
            self.total = normalize_usage(params['tokenUsage']['total'])
            self.usage_updates += 1
        if method == 'turn/started' and params.get('threadId') == self.thread_id:
            self.turn_id = params['turn']['id']
        if method == 'item/completed' and params.get('threadId') == self.thread_id:
            item = params.get('item',{})
            if item.get('type') == 'agentMessage':
                self.messages.append(item.get('text',''))
                if item.get('phase')=='final_answer':
                    self.final_messages.append(item.get('text',''))
            if item.get('type') == 'commandExecution':
                self.command_count += 1
        if method == 'turn/completed' and params.get('threadId') == self.thread_id:
            turn = params['turn']
            if not self.turn_id or turn['id'] == self.turn_id:
                self.turn_id = turn['id']
                self.finished = turn
                self.active = False
        return packet

    def _request(self, method, params, deadline):
        self.counter += 1
        ident = self.counter
        self._send({'id':ident,'method':method,'params':params})
        while ident not in self.responses:
            self._receive(deadline)
        response = self.responses.pop(ident)
        if 'error' in response:
            raise ProtocolError(f"{method}: {response['error']}")
        return response.get('result',{})

    def _start(self, repo, planning, log_dir, deadline):
        if self.process and self.process.poll() is not None:
            self.close()
        if not self.process:
            self.inbox = queue.Queue()
            self.responses = {}
            self.stderr = (log_dir/'app-server.stderr.log').open('w')
            self.process = subprocess.Popen([self.executable,'app-server','--stdio'],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=self.stderr,text=True,bufsize=1,start_new_session=True)
            self.reader = threading.Thread(target=self._read,daemon=True)
            self.reader.start()
            self._request('initialize',{'clientInfo':{'name':'goalpilot','version':__version__},'capabilities':{'experimentalApi':True}},deadline)
            self._send({'method':'initialized'})
        if self.thread_id is None or self.repo != str(repo) or self.readonly != planning:
            params={'cwd':str(repo),'approvalPolicy':'never','sandbox':'read-only' if planning else 'workspace-write','ephemeral':True}
            if self.model:
                params['model']=self.model
            result=self._request('thread/start',params,deadline)
            self.thread_id=result['thread']['id']
            self.repo=str(repo)
            self.readonly=planning
            self.total=None
            self.metadata={key:result.get(key) for key in ('model','modelProvider','serviceTier','reasoningEffort')}

    def execute(self, prompt, repo, timeout, log_dir, *, planning=False, schema=None):
        start=time.monotonic()
        prompt=('Work within this model session. Do not launch other agents, model sessions, or nested '
                'Codex commands: their usage would bypass this mission budget.\n\n'+prompt)
        deadline=start+timeout
        repo=Path(repo).resolve()
        log_dir.mkdir(parents=True,exist_ok=True)
        self.messages=[]
        self.final_messages=[]
        self.finished=None
        self.turn_id=None
        self.usage_updates=0
        self.command_count=0
        dossier=None
        if schema:
            # Native outputSchema changes the server prompt/cache prefix. Keep
            # the final JSON contract in ordinary input so shared tool/system
            # prefixes remain reusable; the host validates the returned object.
            prompt+='\n\nRequired final output schema. Return ONLY its JSON object, without Markdown fences or explanatory text:\n'+Path(schema).read_text()
        if self.prepared and (self.thread_id is None or self.repo != str(repo)):
            from .dossier import prepare,render
            dossier=prepare(repo)
            prompt += '\n\n'+render(dossier)
            (log_dir/'context.json').write_text(json.dumps(dossier,ensure_ascii=False,indent=2))
        baseline=None
        timed_out=False
        error=None
        transport_failed=False
        with (log_dir/'events.jsonl').open('w') as writer:
            self.writer=writer
            try:
                self._start(repo,planning,log_dir,deadline)
                baseline=dict(self.total) if self.total else {'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}
                params={'threadId':self.thread_id,'input':[{'type':'text','text':prompt}]}
                if self.effort is not None:
                    params['effort']=self.effort
                self.active=True
                result=self._request('turn/start',params,deadline)
                self.turn_id=result['turn']['id']
                while self.finished is None:
                    self._receive(deadline)
            except TimeoutError:
                timed_out=True
                if self.active and self.turn_id:
                    try:
                        self._request('turn/interrupt',{'threadId':self.thread_id,'turnId':self.turn_id},time.monotonic()+5)
                        while self.finished is None:
                            self._receive(time.monotonic()+1)
                    except (TimeoutError,ProtocolError,BrokenPipeError):
                        self.close()
            except (ProtocolError,OSError) as exc:
                transport_failed=True
                error=f'{type(exc).__name__}: {exc}'
                self.close()
            finally:
                self.writer=None
        usage=None
        if baseline is not None and self.total is not None:
            usage={key:self.total[key]-baseline[key] for key in baseline}
            if any(value<0 for value in usage.values()):
                usage=None
                error='Usage counters reset unexpectedly'
        status=self.finished.get('status') if self.finished else None
        if self.finished and self.finished.get('error'):
            error=str(self.finished['error'])
        message=self.final_messages[-1] if self.final_messages else self.messages[-1] if self.messages else error or ''
        (log_dir/'last-message.txt').write_text(message)
        fatal=transport_failed or bool(error and any(x in error.lower() for x in ('unauthorized','authentication','quota','rate limit','access token','401','403','429')))
        return AgentResult(0 if status=='completed' else 124 if timed_out else 1,message,
            time.monotonic()-start,usage,timed_out,fatal,
            simulated=self.simulated,
            usage_complete=bool(status=='completed' and usage is not None and not timed_out),
            thread_id=self.thread_id,turn_id=self.turn_id,
            telemetry={'backend':'app-server','usage_updates':self.usage_updates,'command_count':self.command_count,
                       'model':self.metadata,'context_prepared':dossier is not None,
                       'context_seconds':dossier['duration_seconds'] if dossier else 0,
                       'prompt_characters':len(prompt),'turn_status':status,
                       'requested_effort':self.effort})

    def close(self):
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                try:os.killpg(self.process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                self.process.wait()
            if hasattr(self,'reader'):
                self.reader.join(timeout=1)
            self.process.stdout.close()
            self.process=None
        if hasattr(self,'stderr') and not self.stderr.closed:
            self.stderr.close()
        self.thread_id=None
        self.repo=None
        self.active=False

    def __enter__(self):return self

    def __exit__(self,*args):self.close()
