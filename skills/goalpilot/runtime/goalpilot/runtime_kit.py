"""Portable stdlib plumbing. Domain policy belongs to the application.

Copied intact into an opting-in project; no dependency on GoalPilot at runtime.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_ACTIVE = threading.local()


def atomic_json(path, data):
    """Same-directory replacement; failed serialization never alters the destination."""
    path = Path(path)
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True).encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


class JsonStore:
    """JSON-object store with serializable local transactions and detached results.

    Holds process + advisory OS locks through read/validate/replace. Exceptions
    never commit; read-only transactions do not create/rewrite the data file.
    No lock against programs which ignore the sidecar lock; not a distributed DB.
    """
    def __init__(self, path, initial=None):
        self.path = Path(path).resolve()
        self.initial = copy.deepcopy({} if initial is None else initial)
        if not isinstance(self.initial, dict):
            raise ValueError('Initial state must be an object')
        with _LOCKS_GUARD:
            self.lock = _LOCKS.setdefault(str(self.path), threading.RLock())

    @contextmanager
    def transaction(self):
        with self.lock:
            active = getattr(_ACTIVE, 'paths', set())
            if str(self.path) in active:
                raise RuntimeError('Nested transactions are unsupported')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.with_name(self.path.name + '.lock').open('a+b') as guard:
                fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
                _ACTIVE.paths = active | {str(self.path)}
                try:
                    if self.path.exists():
                        state = json.loads(self.path.read_text(encoding='utf-8'))
                        if not isinstance(state, dict):
                            raise ValueError('Stored state must be an object')
                    else:
                        state = copy.deepcopy(self.initial)
                    before = json.dumps(state, ensure_ascii=False, sort_keys=True, allow_nan=False)
                    yield state
                    if json.dumps(state, ensure_ascii=False, sort_keys=True, allow_nan=False) != before:
                        atomic_json(self.path, state)
                finally:
                    _ACTIVE.paths = active
                    fcntl.flock(guard.fileno(), fcntl.LOCK_UN)

    def read(self):
        with self.transaction() as state:
            return copy.deepcopy(state)


def packet(handler, request):
    if not isinstance(request, dict) or not isinstance(request.get('operation'), str):
        raise ValueError('Request needs a string operation')
    data = request.get('data', {})
    if not isinstance(data, dict):
        raise ValueError('Request data must be an object')
    return handler(request['operation'], data)


def jsonl_main(handler, source=None, target=None):
    """One response per input line; errors do not kill subsequent requests."""
    source, target = source or sys.stdin, target or sys.stdout
    for line in source:
        try:
            response = {'ok': True, 'result': packet(handler, json.loads(line))}
            # Serialize before any write: unserializable results cannot corrupt framing.
            raw = json.dumps(response, ensure_ascii=False, allow_nan=False)
        except (ValueError, KeyError, TypeError) as exc:
            raw = json.dumps({'ok': False, 'error': str(exc) or type(exc).__name__}, ensure_ascii=False)
        target.write(raw + '\n')
        target.flush()


def serve(handler, host='127.0.0.1', port=0):
    """Bounded JSON HTTP adapter: GET /health and POST /api only, no redirects."""
    class HTTP(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def respond(self, status, data):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.respond(200, {'ok': True}) if self.path == '/health' else self.respond(404, {'ok': False, 'error': 'Unknown path'})

        def do_POST(self):
            if self.path != '/api':
                return self.respond(404, {'ok': False, 'error': 'Unknown path'})
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= 1048576:
                    raise ValueError('Invalid body length')
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('Incomplete request')
                result = packet(handler, json.loads(raw))
                # Validate before emitting headers; even an invalid result gets one response.
                json.dumps(result, allow_nan=False)
            except (ValueError, KeyError, TypeError) as exc:
                return self.respond(400, {'ok': False, 'error': str(exc) or type(exc).__name__})
            self.respond(200, {'ok': True, 'result': result})

    server = ThreadingHTTPServer((host, port), HTTP)
    server.daemon_threads = True
    print(json.dumps({'port': server.server_port}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def require(condition, message='Invalid request'):
    if not condition:
        raise ValueError(message)


def text(value):
    require(isinstance(value, str) and bool(value), 'Expected nonempty text')
    return value


def integer(value, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and
            (maximum is None or value <= maximum), 'Invalid integer')
    return value


def identifiers(value, nonempty=False):
    require(isinstance(value, list) and (bool(value) or not nonempty), 'Expected ID list')
    return sorted({text(x) for x in value})


def get_record(records, key):
    text(key)
    require(key in records, 'Missing record: ' + key)
    return records[key]


def compare_revision(record, expected):
    require(integer(expected, 1) == record['revision'], 'Stale revision')


def page(rows, *, after=None, limit=20):
    integer(limit, 1, 100)
    if after is not None:
        text(after)
    rows = sorted((x for x in rows if after is None or x['id'] > after), key=lambda x: x['id'])
    items = rows[:limit]
    return {'items': items, 'next': items[-1]['id'] if len(rows) > limit else None}


def idempotent(state, key, operation, request, callback, *, field='keys'):
    """Use inside a transaction; requests must already be normalized by the domain.

    Never consumes a key on callback failure; returns detached ORIGINAL snapshots.
    """
    text(key)
    if key in state.get(field, {}):
        prior = state[field][key]
        require(prior['operation'] == operation and
                json.dumps(prior['request'], sort_keys=True, allow_nan=False) == json.dumps(request, sort_keys=True, allow_nan=False), 'Idempotency conflict')
        return copy.deepcopy(prior['result'])
    result = callback()
    state.setdefault(field, {})[key] = {'operation': operation, 'request': copy.deepcopy(request),
                                      'result': copy.deepcopy(result)}
    return copy.deepcopy(result)


class ServiceBase:
    """Subclass initial(), validate(state), handle(state, operation, data).

    Validation MUST implement the application's full domain invariants. No domain
    rules, entity names, permissions or hidden acceptance knowledge in this base.
    """
    def __init__(self, path):
        self.store = JsonStore(path, self.initial())

    def initial(self):
        raise NotImplementedError

    def validate(self, state):
        raise NotImplementedError

    def handle(self, state, operation, data):
        raise NotImplementedError

    def call(self, operation, data):
        text(operation)
        require(isinstance(data, dict), 'Expected data object')
        with self.store.transaction() as state:
            try:
                self.validate(state)
                if operation == 'backup':
                    fields(data, {})
                    result = state
                elif operation == 'restore':
                    fields(data, {'state': self.validate})
                    candidate = copy.deepcopy(data['state'])
                    state.clear()
                    state.update(candidate)
                    result = state
                else:
                    result = self.handle(state, operation, copy.deepcopy(data))
                self.validate(state)
                json.dumps(result, allow_nan=False)
            except (KeyError, TypeError, IndexError, AttributeError) as exc:
                raise ValueError(str(exc) or 'Invalid request/state') from exc
            return copy.deepcopy(result)

    @classmethod
    def main(cls):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--file', required=True)
        parser.add_argument('mode', choices=['jsonl', 'serve'])
        parser.add_argument('--port', type=int, default=0)
        args = parser.parse_args()
        service = cls(args.file)
        if args.mode == 'jsonl':
            jsonl_main(service.call)
        else:
            serve(service.call, port=args.port)


class ReplayService(ServiceBase):
    """Opt-in event storage for NEW pure, deterministic in-memory reducers.

    Subclass initial() and handle(state, operation, data). A backup contains the
    derived state AND accepted mutation requests/results/entropy. A restore is
    valid only if replay reaches that exact state through those same rules.
    No second handwritten restore validator is necessary. An optional validate
    invariant hook is honored before/after transitions and during replay;
    never remove rules on which normal operations depend. Existing data formats,
    external effects, clock/random access and arbitrary legacy handlers do NOT
    fit this API. Use opaque() for recorded random IDs; times belong in requests.

    Replay is linear in history on a cold process; a verified full-envelope hash
    caches subsequent reads in this instance. max_events bounds replay work.
    This is reachable-state validation, not authentication or a proof that the
    application's rules themselves meet a user's business requirements.
    """
    FORMAT = 'goalpilot-replay-1'

    def __init__(self, path, *, max_events=4096):
        integer(max_events, 1)
        self.max_events = max_events
        self._verified = None
        initial = self.initial()
        require(isinstance(initial, dict), 'Initial state must be an object')
        self.store = JsonStore(path, {'format': self.FORMAT, 'state': initial, 'events': []})

    @staticmethod
    def _canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':'))

    def _remember(self, envelope, state, seen):
        import hashlib
        self._verified = (hashlib.sha256(self._canonical(envelope).encode()).digest(),
                          copy.deepcopy(state), set(seen))

    def validate(self, state):
        """Optional invariant hook, honored when supplied; no duplicate needed."""
        require(isinstance(state, dict), 'Reducer state must be an object')

    def opaque(self):
        """Opaque ID recorded in the event and consumed identically on replay."""
        if not hasattr(self, '_entropy_seen'):
            raise RuntimeError('opaque() is only available inside a reducer')
        if self._entropy_source is None:
            import secrets
            token = secrets.token_hex(16)
            while token in self._entropy_seen:
                token = secrets.token_hex(16)
        else:
            index = len(self._entropy_used)
            require(index < len(self._entropy_source), 'Missing recorded entropy')
            token = self._entropy_source[index]
            require(isinstance(token, str) and len(token) == 32 and
                    all(c in '0123456789abcdef' for c in token), 'Invalid recorded entropy')
            require(token not in self._entropy_seen, 'Reused recorded entropy')
        self._entropy_seen.add(token)
        self._entropy_used.append(token)
        return token

    def _execute(self, state, operation, data, entropy, seen):
        self._entropy_source = entropy
        self._entropy_used = []
        self._entropy_seen = seen
        try:
            self.validate(state)
            result = copy.deepcopy(self.handle(state, operation, copy.deepcopy(data)))
            self.validate(state)
            self._canonical(result)
            self._canonical(state)
            if entropy is not None:
                require(len(self._entropy_used) == len(entropy), 'Unused recorded entropy')
            return result, list(self._entropy_used)
        finally:
            del self._entropy_source, self._entropy_used, self._entropy_seen

    def _validate_envelope(self, envelope):
        import hashlib
        fields(envelope, {'format': text, 'state': lambda s: require(isinstance(s, dict)),
                          'events': sequence(lambda e: require(isinstance(e, dict)))})
        require(envelope['format'] == self.FORMAT, 'Unknown replay storage format')
        require(len(envelope['events']) <= self.max_events, 'Replay event budget exceeded')
        fingerprint = hashlib.sha256(self._canonical(envelope).encode()).digest()
        if self._verified is not None and fingerprint == self._verified[0]:
            return copy.deepcopy(self._verified[1]), set(self._verified[2])
        state = copy.deepcopy(self.initial())
        self.validate(state)
        seen = set()
        for event in envelope['events']:
            fields(event, {'operation': text, 'data': lambda d: require(isinstance(d, dict)),
                           'entropy': sequence(text), 'result': lambda x: None})
            require(event['operation'] not in ('backup', 'restore'), 'Invalid replay operation')
            before = self._canonical(state)
            result, _ = self._execute(state, event['operation'], event['data'], event['entropy'], seen)
            require(self._canonical(state) != before, 'Recorded operation was not a mutation')
            require(self._canonical(result) == self._canonical(event['result']), 'Replay result differs')
        require(self._canonical(state) == self._canonical(envelope['state']), 'Replay state differs')
        self._remember(envelope, state, seen)
        return state, seen

    def call(self, operation, data):
        text(operation)
        require(isinstance(data, dict), 'Expected data object')
        with self.store.transaction() as envelope:
            try:
                state, seen = self._validate_envelope(envelope)
                if operation == 'backup':
                    fields(data, {})
                    result = envelope
                elif operation == 'restore':
                    fields(data, {'state': lambda s: require(isinstance(s, dict))})
                    candidate = copy.deepcopy(data['state'])
                    self._validate_envelope(candidate)
                    envelope.clear()
                    envelope.update(candidate)
                    result = envelope
                else:
                    before, seen_before = copy.deepcopy(state), set(seen)
                    result, entropy = self._execute(state, operation, data, None, seen)
                    if self._canonical(state) != self._canonical(before):
                        require(len(envelope['events']) < self.max_events, 'Replay event budget exceeded')
                        replayed = copy.deepcopy(before)
                        again, _ = self._execute(replayed, operation, data, entropy, seen_before)
                        require(self._canonical(replayed) == self._canonical(state) and
                                self._canonical(again) == self._canonical(result),
                                'Reducer must be deterministic; use opaque() for IDs')
                        envelope['events'].append({'operation': operation, 'data': copy.deepcopy(data),
                                                   'entropy': entropy, 'result': copy.deepcopy(result)})
                        envelope['state'] = state
                        self._remember(envelope, state, seen)
            except (KeyError, TypeError, IndexError, AttributeError) as exc:
                raise ValueError(str(exc) or 'Invalid request/replay state') from exc
            return copy.deepcopy(result)


def boolean(value):
    require(type(value) is bool, 'Expected boolean')
    return value


def fields(value, required, optional=None, *, extra=False):
    """Validate an object using {field: callable} maps; never normalize/mutate it."""
    optional = optional or {}
    require(isinstance(value, dict), 'Expected object')
    require(set(required) <= set(value), 'Missing required fields')
    require(extra or set(value) <= set(required) | set(optional), 'Unknown fields')
    for key, validator in {**required, **optional}.items():
        if key in value:
            validator(value[key])
    return value


def sequence(validator, *, nonempty=False):
    def check(value):
        require(isinstance(value, list) and (bool(value) or not nonempty), 'Expected list')
        for item in value:
            validator(item)
        return value
    return check


def mapping(validator):
    def check(value):
        require(isinstance(value, dict), 'Expected record map')
        for key, item in value.items():
            text(key)
            validator(item)
        return value
    return check


def choice(*values):
    def check(value):
        require(isinstance(value, str) and value in values, 'Invalid choice')
        return value
    return check


def nullable(validator):
    def check(value):
        return value if value is None else validator(value)
    return check


def dag(graph):
    """Validate a dependency map without recursion or running project code."""
    require(isinstance(graph, dict), 'Expected dependency graph')
    for key, deps in graph.items():
        text(key)
        require(identifiers(deps) == deps and key not in deps and all(x in graph for x in deps),
                'Missing, duplicate, unsorted or self dependency')
    degrees = {key: len(deps) for key, deps in graph.items()}
    children = {key: [] for key in graph}
    for key, deps in graph.items():
        for dep in deps:
            children[dep].append(key)
    ready = [key for key, count in degrees.items() if not count]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for child in children[key]:
            degrees[child] -= 1
            if not degrees[child]:
                ready.append(child)
    require(visited == len(graph), 'Cyclic dependencies')
    return graph


API = """COMPLETE PROVISIONED API: use directly; inspect references only for a concrete missing detail.
Import needed names from goalpilot_runtime:
ReplayService(path,max_events=4096): implement initial()->dict, PURE handle(state,op,data)->result. All business/input guards apply here (optional validate(state) invariants also honored). self.opaque() supplies recorded random IDs; use explicit request times, no external I/O/clock/random. call() locks/commits atomically, detaches values, backup {} / restore {state} validate a versioned {format,state,events} envelope by exact accepted-mutation replay. No duplicate restore validator. Cold replay linear; NEW unspecified formats only.
ServiceBase(path): same call/transports, existing domain JSON format; implement initial(),handle() AND full validate(state) before/after calls and restore.
Either: if __name__=='__main__': Service.main(). --file PATH jsonl / serve --port 0. {operation,data}->{ok,result/error}; GET /health, POST /api, HTTP400/404.
require(condition,message='Invalid request'); text(x) nonempty str; integer(x,minimum=0,maximum=None) strict int; boolean(x); identifiers(list,nonempty=False) sorted unique; get_record(map,id); compare_revision(record,expected); page(rows,after=None,limit=20)->{items,next}; dag({id:sorted_dependencies}).
fields(value,{required:validator},optional=None,extra=False); sequence(validator,nonempty=False),mapping(validator),choice(*strings),nullable(validator) create validators.
idempotent(state,key,op,NORMALIZED_REQUEST,callback,field='keys'): validate fields FIRST; successful result snapshot replay, conflicting keys reject.
Import from goalpilot_support: JourneyMixin,dispatch,rejects,rejected_unchanged,jsonl,json_http,transport_journey.
class Tests(JourneyMixin,unittest.TestCase): setUp(): self.open_service(Service,**defaults). self.c(op,**data); self.assertSteps(*[(op,data,EXACT_EXPECTED),...]); self.assertSubset(actual,**fields); self.assertRejects(op,**data) checks ValueError+unchanged bytes; self.restart(); self.assertCorruptions(*[lambda backup:explicit_mutation,...]); self.race(*[(op,data),...])->[(accepted,result/error),...] synchronized POSIX processes; assert business winners/count/final state.
dispatch(callback,**defaults)->call(op,**overrides); rejects(callable,exception=ValueError); rejected_unchanged(callable,path). jsonl(argv,packets,cwd=None); with json_http(argv,cwd=None) as req: req(method,path,data=None,status=200).
transport_journey(argv,[(op,data,EXPECTED),...],cwd=None): REAL JSONL/HTTP domain results, malformed JSON/packet recovery, HTTP400/404/health, independent copies of --file datastore; original unchanged. isolate=False for explicit shared/reset flows. Business expectations remain YOUR assertions.
"""
