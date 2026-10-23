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
## Department budgets and purchase requests
department.put {id,budget:NONNEGATIVE_CENTS} creates/replaces budget; cannot set below committed
plus spent amount. member.put {id,department,role:'requester'/'approver'} upserts member, known
department; changing role/department cannot invalidate pending request creator/approvals.
request.create {id,creator,amount:POSITIVE_CENTS,approvals:POSITIVE_INT} unique request, creator
exists (either role). Return {id,creator,department,amount,approvals,approved:[],status:'pending',
revision:1,refunded:0}. Snapshot creator department; creating doesn't reserve budget.
request.approve {id,actor,expected_revision} pending only, exact revision. Actor approver in same
department, different from creator, not already approved. Add actor sorted and revision+1.
When count reaches required approvals, atomically reserve amount from department available
budget and set status approved. If insufficient funds reject the entire approval and revision.
request.reject {id,actor,expected_revision} pending/approved, same authorized different actor,
exact revision; status rejected, revision+1, release commitment if approved.
request.spend {id,key} approved only; global key same request returns original snapshot, conflict
rejects; convert committed to spent, status spent, revision+1. request.refund {id,amount,key}
spent only, amount<=amount-refunded; reduce department spent, increase refunded, revision+1.
A fully refunded request remains spent. Keys global across spend/refund; normalized payload
includes operation. Failed operations never consume keys. request.get {id} returns snapshot.
department.report {id} -> {budget,committed,spent,available:budget-committed-spent}.
request.import {requests:[create-payloads]} creates batch all-or-none, rejects unknown creator,
repeated/existing ID, invalid amounts or approvals; return {imported:N}.
Restore validates member/reference/role/status/revision/approval separation, balances, caps and
refund/idempotency history. Concurrent final approvals cannot overcommit a budget.
