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
## Clinic scheduling without patient data dependencies
practitioner.put {id,skills:[STRINGS]} upserts skills; cannot remove a skill referenced by a
non-cancelled appointment. patient.put {id,consent:BOOLEAN} upserts patient. Revoking consent
is allowed, but new bookings for that patient reject. appointment.create {id,patient,practitioner,
start:NONNEGATIVE_INT,end:INT>start,skill,fee:NONNEGATIVE_CENTS,key} creates unique confirmed
appointment, patient consent true and practitioner skilled. Both practitioner AND patient cannot
have overlapping non-cancelled appointment intervals; half-open adjacency allowed. Return
{id,patient,practitioner,start,end,skill,fee,status:'confirmed',revision:1,charged:0}.
Global create keys are idempotent for identical payload, conflicting request rejects; original
snapshot returned even if appointment changed. appointment.move {id,start,end,expected_revision}
confirmed only, exact revision; all overlap checks ignoring self; one atomic revision increase.
appointment.cancel {id,expected_revision} confirmed only, exact revision; sets cancelled and
revision+1, frees interval. appointment.finish {id,expected_revision,attended:BOOLEAN} confirmed
only, exact revision; status attended or missed; charged fee when attended, fee//2 when missed;
revision+1. Completed appointments retain their occupied history for overlap checks.
appointment.get {id}; appointment.list {patient optional,practitioner optional,status optional}
filtered conjunctively and sorted by (start,id). invoice {patient} -> {charged:SUM_CHARGED,
attended:COUNT,missed:COUNT}. wait.add {id,patient,skill} unique wait ID and no duplicate
(patient,skill), consent required; stores insertion order. wait.list {skill} returns original
request objects in insertion order. wait.remove {id} removes existing request. Requests are
not automatically booked; list permits a human scheduler to choose.
appointment.import {appointments:[create-payloads]} all-or-none including conflicts inside batch,
return {imported:N}. Restore validates all references, skills, consent type, time intervals,
non-cancelled overlap histories, statuses/charges/revisions, idempotency and waitlist uniqueness.
Concurrent moves/creates cannot double-book either party. No actual patient secrets involved.
