# Portable helper API

Helpers are opt-in and protected by exact hashes. Use the complete API printed by session begin; read this reference only for a concrete missing detail.

```text
COMPLETE PROVISIONED API: use directly; inspect references only for a concrete missing detail.
Import needed names from goalpilot_runtime:
ReplayService(path,max_events=4096): implement initial()->dict, PURE handle(state,op,data)->result. All business/input guards apply here (optional validate(state) invariants also honored). self.opaque() supplies recorded random IDs; use explicit request times, no external I/O/clock/random. call() locks/commits atomically, detaches values, backup {} / restore {state} validate a versioned {format,state,events} envelope by exact accepted-mutation replay. No duplicate restore validator. Cold replay linear; NEW unspecified formats only.
ServiceBase(path): same call/transports, existing domain JSON format; implement initial(),handle() AND full validate(state) before/after calls and restore.
Either: if __name__=='__main__': Service.main(). --file PATH jsonl / serve --port 0. {operation,data}->{ok,result/error}; GET /health, POST /api, HTTP400/404.
require(condition,message='Invalid request'); text(x) nonempty str; integer(x,minimum=0,maximum=None) strict int; boolean(x); identifiers(list,nonempty=False) sorted unique; get_record(map,id); compare_revision(record,expected); page(rows,after=None,limit=20)->{items,next}; dag({id:sorted_dependencies}).
fields(value,{required:validator},optional=None,extra=False); sequence(validator,nonempty=False),mapping(validator),choice(*strings),nullable(validator) create validators.
idempotent(state,key,op,NORMALIZED_REQUEST,callback,field='keys'): validate fields FIRST; successful result snapshot replay, conflicting keys reject.
Import from goalpilot_support: JourneyMixin,dispatch,rejects,rejected_unchanged,jsonl,json_http,transport_journey.
class Tests(JourneyMixin,unittest.TestCase): setUp(): self.open_service(Service,**defaults). self.c(op,**data); self.assertSteps(*[(op,data,EXACT_EXPECTED),...]); self.assertSubset(actual,**fields); self.assertRejects(op,**data) checks ValueError+unchanged bytes; self.restart(); self.assertCorruptions(*[lambda backup:explicit_mutation,...]); self.race(*[(op,data),...])->[(accepted,result/error),...] synchronized POSIX processes; assert business winners/count/final state.
open_service sets self.path (datastore Path) and self.service (Service instance). Use self.path, not self.service.path.
self.assertJourney(flow,argv=None): write ONE flow(c), calling c(op,**data) and asserting actual results including dynamic IDs and rejects(lambda:c(...)). Runs SAME flow in-process, in real JSONL (fresh process per step) and HTTP on independent fixture copies; original unchanged. Default argv=[sys.executable,'app.py','--file',str(self.path)]; override only for a different entrypoint. Flow must use its c argument, not self.c. Add separate explicit corruption/race checks when needed. This replaces repeated transport-specific workflow code; all business assertions remain yours.
dispatch(callback,**defaults)->call(op,**overrides); rejects(callable,exception=ValueError); rejected_unchanged(callable,path). jsonl(argv,packets,cwd=None); with json_http(argv,cwd=None) as req: req(method,path,data=None,status=200).
transport_journey([python,app.py,'--file',db_path],[(op,data,EXPECTED),...],cwd=None): helper appends jsonl/serve; include exactly one --file PATH and no subcommand when isolate=True (default). Tests REAL JSONL/HTTP, malformed-line recovery, HTTP400/404/health, and separate database copies; original unchanged. Use isolate=False for explicit shared/reset flows. Keep business assertions. When replacing fixture fields, merge dictionaries rather than pass duplicate keyword arguments.

```

`fields(value, schema)` validates an existing object. For nested validator factories use `lambda value: fields(value, schema)`; `fields(schema)` is not supported.
