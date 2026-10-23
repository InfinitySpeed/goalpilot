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
## Time tracking, approval and budgets
project.put {id,budget:NONNEGATIVE_MINUTES,rate:NONNEGATIVE_CENTS_PER_MINUTE} upserts project;
reject budget below total approved minutes (pending minutes don't reserve budget). worker.put
{id,role:'worker'/'manager'} upserts role. entry.create {id,worker,project,start:NONNEGATIVE_INT,
end:INT>start,note:NONEMPTY_TEXT} unique entry, worker/project exist. No overlapping active
entries for same worker across projects, half-open adjacency allowed. Return {id,worker,project,
start,end,note,status:'draft',revision:1,rate:CURRENT_PROJECT_RATE}. Snapshot rate at creation.
entry.edit {id,start,end,note,expected_revision} draft/rejected only, exact revision, overlap
checks ignoring self, status draft, revision+1. entry.submit {id,expected_revision} draft only,
exact revision, status submitted/revision+1. entry.review {id,actor,approve:BOOLEAN,
expected_revision} submitted only, actor manager different from entry.worker, exact revision.
If approve, atomically reserve duration from project budget and set approved, else rejected;
revision+1. Budget rejection leaves entry submitted/revision unchanged. entry.delete
{id,expected_revision} draft/rejected only, exact revision, removes and frees overlap interval.
entry.get {id}; entry.list {worker optional,project optional,status optional} sorted by(start,id).
period.lock {id,start,end} unique lock interval, no overlap with existing locks; all overlapping
entries must be approved, and no approved entry can straddle its boundaries. Locks prevent
create/edit/delete/review/submit touching their interval. invoice.export {lock} returns
{items:[{entry,worker,project,minutes,amount}],total:SUM_AMOUNT}, entries contained in lock,
sorted by entry ID, amount=minutes*snapshotted rate. project.report {id} returns
{approved:MINUTES,remaining:budget-approved,amount:APPROVED_SNAPSHOT_AMOUNT}.
entry.import {entries:[create-payloads]} all-or-none, including overlap among imported rows;
return {imported:N}. Restore validates references, intervals/statuses/revisions/rates, per-worker
non-overlap, approved budgets and lock invariants. Concurrent approvals cannot exceed budget.
