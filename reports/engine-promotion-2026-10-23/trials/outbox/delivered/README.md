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
## Durable queue, leases and dead letters
queue.create {id,max_attempts:POSITIVE_INT,retry_delay:NONNEGATIVE_INT} unique queue. message.publish
{queue,id,payload:JSON_VALUE,key,priority:INT optional0,not_before:NONNEGATIVE_INT optional0}
unique ID per queue. Global key same normalized publish returns original message snapshot,
conflict rejects without effects. Return {id,queue,payload,status:'pending',attempts:0,priority,
not_before,receipt:null,worker:null}. message.get {queue,id} returns detached message.
claim {queue,worker,now:NONNEGATIVE_INT,lease:POSITIVE_INT,limit:INT1..100} first expire all
leased messages with now>=expiry: pending with not_before=now+retry_delay unless attempts
>=max_attempts then dead. Eligible pending not_before<=now, order descending priority then ID.
For each acquired message increment attempts once, status leased, new opaque receipt different
on every claim, worker set and expires=now+lease. Return acquired message snapshots. No model,
network or real scheduler involved. Two concurrent claims cannot lease the same message.
ack {queue,id,receipt,now} only current leased unexpired receipt, sets done and clears lease
fields. Repeated/stale/expired/wrong receipt rejects, never completes message accidentally.
nack {queue,id,receipt,now} valid current unexpired lease only, sets pending with
not_before=now+retry_delay or dead when attempts>=max_attempts; clears lease fields.
redrive {queue,id,now} dead only; pending, attempts0, not_before=now; old receipt stays invalid.
message.cancel {queue,id} pending only, mark cancelled; done/dead/leased reject. queue.stats
{queue,now} performs expiry handling then returns counts {pending,leased,done,dead,cancelled}.
message.list {queue,status optional} sorted IDs. publish.import {messages:[publish-payloads]}
all-or-none, including ID/key conflicts, return {imported:N}. Strict types even priority bool.
Restore validates queues/references/statuses/attempt limits/lease consistency/receipts and key
snapshots, preserves opaque receipt uniqueness across restarts. Failed ack/nack never performs
unrelated mutations, including implicit expiry; stats/claim alone perform expiry changes.
