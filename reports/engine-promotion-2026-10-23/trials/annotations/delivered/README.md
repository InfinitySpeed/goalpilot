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
## Dataset annotation with independent reviewers
dataset.create {id,labels:[STRINGS],reviews:POSITIVE_INT} unique dataset; nonempty normalized
labels. annotator.put {id,active:BOOLEAN} creates/upserts reviewer; deactivation prevents claims
and submissions but preserves history. item.add {dataset,id,payload:JSON_VALUE} unique ID within
dataset. Return {id,dataset,payload,status:'pending',votes:[],revision:1,consensus:null}.
claim {dataset,annotator,now:NONNEGATIVE_INT,lease:POSITIVE_INT} active known annotator; chooses
lexical first pending/reviewing item with fewer than required votes, annotator hasn't voted,
and no unexpired claim by that annotator on it. Different annotators may claim the same item
only if votes+live claims<reviews, preventing overclaim. Return null if none, otherwise
{item,receipt:NEW_OPAQUE,expires:now+lease}; each claim receipt unique across restarts.
submit {dataset,item,annotator,receipt,now,label} current unexpired claim, active annotator,
known label, one vote per annotator. Append {annotator,label} in submission order, revision+1,
release claim. With required vote count, status complete; consensus is label only if all votes
agree, otherwise null. Before complete status reviewing. Claims expire at now>=expires and
may be replaced without counting as votes; stale receipts always reject, no side effects.
item.reopen {dataset,id,expected_revision} complete only/exact revision, clears votes/claims/
consensus, status pending, revision+1; retain prior completed vote rounds in immutable history.
item.get {dataset,id}; item.list {dataset,status optional} sorted IDs. history {dataset,id}
returns prior rounds in completion order, each {votes,consensus}; reopening records one round.
report {dataset} -> {pending:COUNT,reviewing:COUNT,complete:COUNT,disputed:COUNT_COMPLETE_NULL}.
item.import {dataset,items:[{id,payload}]} all-or-none, return {imported:N}. Restore validates
all references/statuses/revisions/vote uniqueness/known labels, consensus, live claim ownership/
receipt uniqueness/capacity and histories. Concurrent claims/submissions cannot overfill reviews.
