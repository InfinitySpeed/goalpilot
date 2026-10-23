"""Reusable stdlib plumbing for frozen behavioral probes; no domain policy."""
import contextlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import urllib.error
import urllib.request

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
    process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        raw=''.join(json.dumps(p,ensure_ascii=False)+'\n'for p in packets)
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


def transport_journey(argv, packets, *, cwd=None):
    """Assert JSONL + HTTP results agree for domain packets in THIS scenario.

    Caller supplies expected results in packets as (operation,data,expected) rows.
    Use readonly operations or isolated fixture stores: this executes both paths.
    """
    rows = [{'operation': op, 'data': data} for op, data, expected in packets]
    got = jsonl([*argv, 'jsonl'], rows, cwd=cwd)
    if len(got) != len(packets):
        raise AssertionError('JSONL response count mismatch')
    for response, (_, _, expected) in zip(got, packets):
        if response != {'ok': True, 'result': expected}:
            raise AssertionError(f'JSONL mismatch: {response!r}')
    with json_http([*argv, 'serve', '--port', '0'], cwd=cwd) as request:
        if request('GET', '/health') != {'ok': True}:
            raise AssertionError('HTTP health failed')
        for op, data, expected in packets:
            if request('POST', '/api', {'operation': op, 'data': data}) != {'ok': True, 'result': expected}:
                raise AssertionError('HTTP domain response mismatch')
        if request('POST', '/api', [], status=400).get('ok') is not False:
            raise AssertionError('HTTP accepted malformed request')
        if request('GET', '/missing', status=404).get('ok') is not False:
            raise AssertionError('HTTP accepted unknown path')
