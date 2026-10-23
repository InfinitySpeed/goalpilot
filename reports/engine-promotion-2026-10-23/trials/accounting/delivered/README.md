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
## Double-entry accounting
account.create {id,name,kind:'asset'/'liability'/'income'/'expense'} unique account, opening zero.
period.create {id,start:NONNEGATIVE_INT,end:INT>start} half-open dated period, no overlap with
existing periods. Return {id,start,end,status:'open',revision:1}. journal.post {id,date:INT,
lines:[{account,debit:NONNEGATIVE_CENTS,credit:NONNEGATIVE_CENTS}],key} unique entry, at least two
lines; each line exactly one positive side (not both or neither), all accounts known, equal
positive debit/credit totals. Date belongs to exactly one OPEN period. Preserve line order and
aggregate account balances across lines. Global idempotency key includes operation/payload;
replay same returns ORIGINAL entry, conflicts reject, failure doesn't consume key. Return
{id,date,period,lines,status:'posted',reversal:null}. journal.reverse {id,reversal_id,date,key}
creates a new balanced entry with sides swapped, current date in open period, unique new ID,
marks original status reversed and reversal ID. Cannot reverse twice, but identical key replay
returns original reversal snapshot. Cannot reverse a reversal entry. Entry history immutable.
period.close {id,expected_revision} open/exact revision, mark closed/revision+1; subsequent post
or reversal dated within it rejects. period.reopen {id,expected_revision} closed/exact revision,
mark open/revision+1. journal.get {id}; journal.list {period optional,account optional} entries
sorted by (date,id), including originals and reversals. account.balance {id} -> {debit,credit,
net:debit-credit}; trial_balance {} -> sorted [{account,debit,credit,net}] including zero accounts.
journal.import {entries:[post-payloads]} all-or-none, enforcing cumulative IDs/keys/balance/periods,
return {imported:N}. A rejected batch must not alter account balances or reserve IDs/keys.
Restore validates all accounts/periods, no overlapping dates, balanced immutable entries,
reversal references/sides, types and key snapshots. Original reversed entry still counts in
balances; its separate reversal offsets it, never remove history. Concurrent posts don't lose data.
