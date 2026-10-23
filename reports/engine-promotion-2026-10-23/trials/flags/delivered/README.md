# Complete the local operations application
Implement the whole public contract below autonomously, with Python standard library only.
Preserve banner() == 'Local Ops — café' and the exact original USER_NOTES.txt. Expose
app.Service(path).call(operation, data) -> JSON value. Persist all application data as JSON,
survive fresh Service instances AND processes. Accepted mutations are atomic; any rejected
request leaves existing data-file bytes unchanged. Concurrent processes must not lose updates
or violate capacities/revisions. Return detached snapshots and don't mutate caller input.
Unknown operations/missing records/invalid fields raise ValueError. IDs/text nonempty strings;
strict integer fields reject booleans, floats and strings. Lists of IDs normalized sorted unique
unless an execution/insertion order is explicitly required. No external network or credentials.

Implement BOTH real public transports using the same business logic:
python app.py --file PATH jsonl consumes one {operation:STRING,data:OBJECT} per line and emits
one {ok:true,result:VALUE} or {ok:false,error:NONEMPTY_TEXT}. Bad JSON/packets/operations must not
prevent the next valid line. python app.py --file PATH serve --port 0 binds localhost, announces
{"port":PORT} as its first stdout line. GET /health ->200 {ok:true}; POST /api uses the same
packet/response envelope with HTTP200 success/400 rejected; unknown path ->404 JSON error.
Unicode supported everywhere. Include meaningful domain, rejection, persistence and real
JSONL/HTTP regression tests and brief usage documentation.

backup {} returns the complete application state as a detached JSON object. restore {state:OBJECT}
validates ALL domain/referential/capacity/history invariants before replacing it atomically.
Invalid/malformed/inconsistent backups reject without losing any current data. Restore a
valid prior snapshot and continue normal operation. Never erase unrelated customer data.
The specified business workflows must work TOGETHER; a passing legacy banner test is insufficient.
## Deterministic local feature flag service
environment.create {id} unique environment. segment.put {environment,id,members:[USER_IDS]}
upserts sorted unique membership. flag.create {environment,id,default:BOOLEAN} unique flag in
environment; return {id,environment,revision:1,published:0,enabled:false,default,rules:[]}.
flag.update {environment,id,expected_revision,enabled:BOOLEAN,rules:[RULES]} exact draft revision;
validate every rule before effects. Rules in order, each {segment:ID_OR_NULL,percent:INT0..100,
value:BOOLEAN}; segment must exist when nonnull, null means all users. revision+1, only draft
changes; live evaluations unaffected until publish. flag.publish {environment,id,expected_revision}
exact revision, stores immutable current snapshot as published revision, return flag. Republishing
same revision idempotent, no revision bump. flag.evaluate {environment,id,user} uses published
snapshot if any, otherwise default create value. Disabled live flag always yields its default.
For each live rule in order, only matching segment/all-users eligible. Compute bucket =
int.from_bytes(SHA256(UTF8(environment+'|'+flag_id+'|'+user)).digest()[:8],'big') %100.
First eligible rule with bucket<percent wins; otherwise default. Return {value:BOOLEAN,
revision:LIVE_REVISION_OR_0,bucket:INT}. Membership is evaluated from CURRENT segment state;
rule definitions/value/enable/default from immutable published snapshot.
flag.rollback {environment,id,revision:PREVIOUSLY_PUBLISHED_REVISION,expected_revision:CURRENT_DRAFT}
loads old published snapshot into a NEW draft revision current+1 and immediately publishes it.
Unknown historic revision/stale CAS rejects. flag.get {environment,id} current draft; flag.list
{environment} sorted IDs. audit.list {environment} returns append-only ordered events
{sequence,kind,flag,revision} for flag.created/updated/published/rolled_back; create/update/rollback
one each, successful publish one except idempotent replay. Segment changes produce no flag event.
segment.delete {environment,id} rejects if referenced in ANY current draft or published history.
flag.import {environment,flags:[{id,default}]} create batch all-or-none; return {imported:N}.
Restore validates environment isolation, rule/reference/types, revision history and audit sequence.
