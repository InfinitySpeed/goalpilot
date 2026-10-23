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
## Invoice lifecycle and exact money
customer.put {id,name} upserts customer; customer.list {} sorted. invoice.create
{id,customer,lines:[{description,quantity:POSITIVE_INT,unit_cents:NONNEGATIVE_INT}],tax_bps:INT0..10000}
creates unique draft, returns {id,customer,status:'draft',lines,subtotal,tax,total,paid:0,credited:0,
balance:total,revision:1}. Lines nonempty, preserve order; subtotal=sum(quantity*unit_cents),
tax=(subtotal*tax_bps+5000)//10000 (round half up), total=subtotal+tax. Customer must exist.
invoice.issue {id,expected_revision} draft only, exact revision, status issued, revision+1.
invoice.pay {id,amount:POSITIVE_CENTS,key} issued/partial only, amount<=balance. Global keys:
same operation and payload returns original snapshot, changed request rejects without effects.
Increase paid; balance=total-paid-credited, status paid if zero else partial, revision+1.
invoice.credit {id,amount:POSITIVE_CENTS,key} issued/partial/paid allowed, amount<=total-credited;
credit cannot make balance negative (thus amount<=current balance); update credited, balance,
status credited if balance zero and paid zero, paid if balance zero otherwise partial; revision+1.
No payment/credit on draft/void/credited. invoice.void {id,expected_revision} draft/issued only,
no paid or credited money, exact revision; sets void, balance0, revision+1. No further money ops.
invoice.get {id}; invoice.list {customer optional,status optional} sorted IDs.
payment.import {payments:[{id,amount,key}]} atomically apply all payment operations, including
idempotency and cumulative limits; return {imported:N}. statement {customer} returns
{invoiced:SUM_TOTAL_EXCLUDING_VOID,paid:SUM_PAID,credited:SUM_CREDITED,due:SUM_BALANCE}.
Restore validates customers, line totals/tax rounding, nonnegative money, statuses/revisions,
referential integrity and key snapshots. No floats for arithmetic. Failed batch never reserves keys.
