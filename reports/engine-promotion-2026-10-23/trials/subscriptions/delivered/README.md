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
## Deterministic subscription billing
plan.put {id,price:NONNEGATIVE_CENTS,period:POSITIVE_INT} upserts plan. subscriber.create
{id,plan,start:NONNEGATIVE_INT} unique subscriber, snapshots plan price/period. Return
{id,plan,status:'active',start,period_end:start+period,price,period,cancel_at_end:false,
balance:0,revision:1}. No charge at create. bill {id,now:NONNEGATIVE_INT,key} active/past_due,
now>=period_end; generate ONE invoice per fully elapsed billing period, each due at period_end,
amount=snapshotted price, advance start/end period-by-period until period_end>now. Return
{invoices:[{id:OPAQUE,subscriber,due,amount,paid:0}],subscriber:SNAPSHOT}. Global keys same
normalized request return ORIGINAL result and never bill twice; conflict rejects. A cancel_at_end
subscriber cancels at its first reached period_end WITHOUT a new invoice and doesn't advance
further; bill then returns invoices[] and cancelled status.
invoice.pay {id,amount:POSITIVE_CENTS,key} amount<=unpaid, globally idempotent with operation
and payload, add paid and reduce subscriber balance. subscriber status past_due iff balance>0,
else active (cancelled stays cancelled). subscriber.get {id}; invoice.list {subscriber} sorted
by (due,id). subscriber.change {id,plan,now,expected_revision} active only, exact revision,
start<=now<period_end, new plan same period length; snapshot new price. Proration difference
(new_price-old_price)*(period_end-now)//period, integer floor (including negative). Positive
adjustment creates invoice due now; negative adjustment decreases subscriber balance but not
below zero (credit not carried); return {subscriber,adjustment}. revision+1. New price applies
to future renewals. Prior invoices unchanged. subscriber.cancel {id,expected_revision}
active/past_due exact revision, set cancel_at_end true and revision+1; no immediate refund.
invoice.import_payments {payments:[{id,amount,key}]} all-or-none, return {imported:N}.
report {} -> {subscribers:COUNT,active:COUNT_ACTIVE,past_due:COUNT_PAST_DUE,cancelled:COUNT,
invoiced:SUM_INVOICE_AMOUNT,collected:SUM_PAID,outstanding:SUM_UNPAID}. Balance always equals
invoice unpaid totals (negative adjustment reduces existing unpaid invoice amounts in oldest
due order, never below paid). Restore validates snapshots, periods, money/statuses, references
and keys. Strict ints; concurrent bill same time without keys different cannot create duplicates.
