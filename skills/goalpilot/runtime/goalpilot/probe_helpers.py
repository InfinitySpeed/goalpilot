"""Reusable stdlib plumbing for frozen behavioral probes; no domain policy."""
import contextlib
import copy
import tempfile
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import urllib.error
import urllib.request


def service_race(factory, path, requests, *, timeout=8):
    """Run requests against ONE datastore in synchronized real OS processes.

    Returns (accepted, result/error) in request order. Only ValueError is an
    expected rejection. Crashes, unexpected exceptions and timeouts fail the
    check. Requires POSIX fork; unsupported platforms fail explicitly.
    No business winner/count rule is assumed by this plumbing.
    """
    import multiprocessing
    if 'fork' not in multiprocessing.get_all_start_methods():
        raise RuntimeError('service_race requires POSIX fork')
    requests = copy.deepcopy(list(requests))
    if not 2 <= len(requests) <= 32:
        raise ValueError('A race needs 2..32 requests')
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 60:
        raise ValueError('Expected timeout in (0, 60]')
    ctx = multiprocessing.get_context('fork')
    barrier = ctx.Barrier(len(requests) + 1)
    receivers, workers = [], []

    def execute(sender, operation, data):
        try:
            service = factory(path)
            barrier.wait(timeout=timeout)
            try:
                result = (True, service.call(operation, data))
            except ValueError as error:
                result = (False, str(error))
            sender.send(('result', result))
        except BaseException as error:
            sender.send(('error', type(error).__name__ + ': ' + str(error)))
        finally:
            sender.close()

    deadline = time.monotonic() + timeout
    try:
        for operation, data in requests:
            receiver, sender = ctx.Pipe(duplex=False)
            worker = ctx.Process(target=execute, args=(sender, operation, data))
            receivers.append(receiver)
            workers.append(worker)
            try:
                worker.start()
            finally:
                sender.close()
        barrier.wait(timeout=max(.001, deadline - time.monotonic()))
        results = []
        for receiver in receivers:
            if not receiver.poll(max(0, deadline - time.monotonic())):
                raise AssertionError('Concurrent service request timed out')
            try:
                kind, value = receiver.recv()
            except EOFError as error:
                raise AssertionError('Concurrent service process died without a result') from error
            if kind != 'result':
                raise AssertionError('Concurrent service process failed: ' + value)
            results.append(value)
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
            if worker.exitcode != 0:
                raise AssertionError('Concurrent service process failed or remained alive')
        return results
    finally:
        for worker in workers:
            if worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=.5)
                if worker.is_alive():
                    worker.kill()
                    worker.join(timeout=.5)
        for receiver in receivers:
            receiver.close()


class JourneyMixin:
    """Test fixture plumbing, used with an explicit unittest.TestCase base.

    Domain operations, expected results and rejection cases remain authored by
    the test. No implicit business assertions or completion claim.
    """

    def open_service(self, factory, **defaults):
        if hasattr(self, '_journey_factory'):
            raise RuntimeError('Service fixture already open')
        directory = tempfile.TemporaryDirectory(prefix='goalpilot-journey-')
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'data.json'
        self._journey_factory = factory
        self._journey_defaults = copy.deepcopy(defaults)
        self.service = factory(self.path)
        return self.service

    def c(self, operation, **overrides):
        return self.service.call(operation, {**self._journey_defaults, **overrides})

    def assertSteps(self, *rows):
        """Assert exact expected output for every (op, data, expected) row."""
        for operation, data, expected in rows:
            self.assertEqual(self.c(operation, **data), expected, operation)

    def assertSubset(self, actual, **expected_fields):
        """Explicit selected-field assertions, useful for snapshots with IDs."""
        self.assertIsInstance(actual, dict)
        for key, expected in expected_fields.items():
            self.assertIn(key, actual)
            self.assertEqual(actual[key], expected, key)

    def assertRejects(self, operation, **data):
        rejected_unchanged(lambda: self.c(operation, **data), self.path)

    def restart(self):
        self.service = self._journey_factory(self.path)
        return self.service

    def assertCorruptions(self, *mutators):
        """Reject each explicit corruption; prove data bytes never changed."""
        snapshot = self.service.call('backup', {})
        for mutate in mutators:
            candidate = copy.deepcopy(snapshot)
            mutate(candidate)
            rejected_unchanged(lambda: self.service.call('restore', {'state': candidate}), self.path)

    def race(self, *requests, timeout=8):
        return service_race(self._journey_factory, self.path,
                            [(op, {**self._journey_defaults, **data}) for op, data in requests],
                            timeout=timeout)

API='''Optional trusted frozen module probe_helpers is available beside every probe.
Use it instead of recreating subprocess/network/default-field helpers:
from probe_helpers import dispatch, rejects, jsonl, json_http
dispatch(callback, **defaults) -> call(operation, **overrides): calls callback(operation,
    merged_dict). Overrides replace defaults correctly; no duplicate keyword errors.
rejects(callback, exception=ValueError): assert callback raises the declared exception.
jsonl(argv, packets, cwd=None, timeout=8) -> decoded JSON response list; nonzero exit fails.
with json_http(argv, cwd=None, timeout=7) as request:
    request('GET','/health') -> decoded JSON
    request('POST','/api', {'operation':'x','data':{}}, status=400) -> decoded JSON
json_http starts a LOCAL server whose first stdout line is {"port":PORT}, verifies the
announced port, bounds HTTP requests, and kills the whole server group on exit/failure.
For example c=dispatch(service.call,workspace='w',token='admin'); c('get',token='viewer').
Use dispatch for context defaults; do NOT create packet/api/kwarg forwarding helpers.
If a dict is necessary, use {**defaults, **overrides}, NEVER dict(a=1, **overrides).
Use the documented original API only; helpers do not imply additional business requirements.
The host freezes this helper module with its SHA-256. Do not copy/reimplement its plumbing.
Programs still need their own actual business assertions. Other interfaces may use stdlib.
'''


def dispatch(callback,**defaults):
    def call(operation,**overrides):return callback(operation,{**defaults,**overrides})
    return call


def rejects(callback,exception=ValueError):
    try:callback()
    except exception:return
    raise AssertionError(f'Expected {exception.__name__}')


def _stop(process):
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=1)
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    for stream in (process.stdout,process.stderr,process.stdin):
        if stream is not None:stream.close()


def jsonl(argv,packets,*,cwd=None,timeout=8):
    return jsonl_lines(argv,[json.dumps(p,ensure_ascii=False)for p in packets],cwd=cwd,timeout=timeout)


def jsonl_lines(argv,lines,*,cwd=None,timeout=8):
    """Send literal lines, including malformed JSON, and decode actual replies."""
    raw=''.join(line+'\n'for line in lines)
    process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        out,err=process.communicate(raw,timeout=timeout)
        if process.returncode:raise AssertionError(f'JSONL process failed ({process.returncode}): {err[-2000:]}')
        return [json.loads(line)for line in out.splitlines()]
    finally:_stop(process)


@contextlib.contextmanager
def json_http(argv,*,cwd=None,timeout=7):
    # stderr goes to DEVNULL so noisy servers cannot block on an unread pipe.
    process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)
    try:
        until=time.monotonic()+timeout;line=b''
        with selectors.DefaultSelector()as ready:
            ready.register(process.stdout,selectors.EVENT_READ)
            while b'\n'not in line:
                remaining=until-time.monotonic()
                if remaining<=0 or not ready.select(remaining):raise AssertionError('Local HTTP server startup timeout')
                block=os.read(process.stdout.fileno(),4096)
                if not block:raise AssertionError('Local HTTP server exited before announcing port')
                line+=block
                if len(line)>8192:raise AssertionError('Server port announcement too large')
        announcement=json.loads(line.split(b'\n',1)[0]);port=announcement['port']
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        if type(port)is not int or not 0<port<65536:raise AssertionError('Invalid localhost port')
        def request(method,path,data=None,*,status=200):
            if not isinstance(path,str)or not path.startswith('/')or path.startswith('//'):
                raise ValueError('Expected local absolute URL path')
            body=None if data is None else json.dumps(data,ensure_ascii=False).encode()
            req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=body,method=method,headers={'Content-Type':'application/json'})
            try:response=opener.open(req,timeout=min(4,timeout))
            except urllib.error.HTTPError as exc:response=exc
            with response:
                raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:raise AssertionError('HTTP probe response too large')
                if response.status!=status:raise AssertionError(f'HTTP expected {status}, got {response.status}: {raw[:1000]!r}')
                return json.loads(raw)
        yield request
    finally:_stop(process)


def rejected_unchanged(callback, path, exception=ValueError):
    """Real negative assertion: the application's data-file bytes must survive."""
    path = Path(path)
    before = path.read_bytes() if path.exists() else None
    rejects(callback, exception)
    after = path.read_bytes() if path.exists() else None
    if after != before:
        raise AssertionError('Rejected operation changed stored data')


def transport_journey(argv, packets, *, cwd=None, isolate=True):
    """Assert real domain results on independent datastore copies by default.

    Original data stays unchanged. isolate=False instead uses the same live store
    twice, for explicit shared-state/readonly flows or caller-managed resets.
    """
    argv=list(argv)
    with tempfile.TemporaryDirectory(prefix='goalpilot-transports-') as tmp:
        args=[list(argv),list(argv)]
        if isolate:
            indices=[i for i,x in enumerate(argv)if x=='--file']
            if len(indices)!=1 or indices[0]+1>=len(argv):
                raise ValueError('Isolated transport_journey needs one --file PATH; or use isolate=False')
            i=indices[0]+1;source=Path(argv[i])
            source=source if source.is_absolute()else Path(cwd or Path.cwd())/source
            if source.is_symlink()or source.exists()and not source.is_file():raise ValueError('Expected regular fixture datastore')
            if source.exists()and source.stat().st_size>4000000:raise ValueError('Fixture datastore exceeds helper limit')
            snapshot=source.read_bytes()if source.exists()else None
            for j in range(2):
                target=Path(tmp)/str(j)/'data.json';target.parent.mkdir()
                if snapshot is not None:target.write_bytes(snapshot)
                args[j][i]=str(target)
        rows=[{'operation':op,'data':data}for op,data,expected in packets]
        lines=['bad-json','[]']+[json.dumps(p,ensure_ascii=False)for p in rows]
        replies=jsonl_lines([*args[0],'jsonl'],lines,cwd=cwd)
        if len(replies)!=len(packets)+2:raise AssertionError('JSONL response count mismatch')
        for response in replies[:2]:
            if not isinstance(response,dict)or response.get('ok')is not False or not isinstance(response.get('error'),str)or not response['error']:
                raise AssertionError('JSONL accepted malformed input or omitted error')
        got=replies[2:]
        for response,(_,_,expected)in zip(got,packets):
            if response!={'ok':True,'result':expected}:raise AssertionError(f'JSONL mismatch: {response!r}')
        with json_http([*args[1],'serve','--port','0'],cwd=cwd)as request:
            if request('GET','/health')!={'ok':True}:raise AssertionError('HTTP health failed')
            for op,data,expected in packets:
                if request('POST','/api',{'operation':op,'data':data})!={'ok':True,'result':expected}:raise AssertionError('HTTP domain response mismatch')
            if request('POST','/api',[],status=400).get('ok')is not False:raise AssertionError('HTTP accepted malformed request')
            if request('GET','/missing',status=404).get('ok')is not False:raise AssertionError('HTTP accepted unknown path')
