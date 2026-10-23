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
## Logical-time incident management
team.put {id,members:[IDS]} upserts nonempty member list; cannot remove current assigned owner
of an unresolved incident. policy.put {id,response:POSITIVE_INT,resolve:POSITIVE_INT} upserts SLA,
resolve>=response. incident.open {id,team,policy,now:NONNEGATIVE_INT,title,key} creates unique
incident, snapshots policy. Return {id,team,title,status:'open',owner:null,revision:1,level:0,
acknowledged:null,resolved:null,paused:false}. Global keys same normalized open return ORIGINAL
snapshot, conflicts reject. Clock starts now; all later incident times must be >= last accepted
incident time. incident.assign {id,owner,expected_revision,now} unresolved, owner team member,
exact revision; owner set and revision+1. incident.ack {id,expected_revision,now} open only,
not yet acknowledged, sets acknowledged now and status acknowledged, revision+1.
incident.pause {id,expected_revision,now} unresolved and not paused; records pause start and
paused true, revision+1. incident.resume {id,expected_revision,now} paused only; subtract elapsed
pause from effective elapsed time, paused false and revision+1. Pauses stop BOTH SLA clocks.
incident.resolve {id,expected_revision,now} unresolved and not paused; status resolved,
resolved timestamp now, revision+1. incident.reopen {id,expected_revision,now} resolved only,
status open, resets ack/resolved/pauses and start time to now, retains owner, level0, revision+1.
incident.inspect {id,now} readonly, now>=last accepted incident time; returns public incident
plus elapsed (now-start minus completed/current pauses, frozen at resolved timestamp when
resolved), response_breached (unacknowledged AND elapsed>=snapshot.response AND unresolved),
resolve_breached (unresolved AND elapsed>=snapshot.resolve). Inspection does not advance time.
escalate {id,now,expected_revision} unresolved and currently response or resolve breached;
level+1 and revision+1, one escalation per effective elapsed value (same time rejects).
incident.list {team optional,status optional} sorted IDs. incident.import {incidents:[open-payloads]}
all-or-none, return {imported:N}. Restore validates reference/owner/status/revision/time/pauses/
policy snapshots and escalation history. No wall-clock or external service needed.
