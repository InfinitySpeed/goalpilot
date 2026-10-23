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
## Events, holds and admission
event.create {id,seats:[NONEMPTY_STRINGS],price:NONNEGATIVE_CENTS} creates event with unique seats,
normalized sorted; duplicate event rejects. event.get {id,now:NONNEGATIVE_INT} returns
{id,seats,price,available:[SEAT_IDS_SORTED]}. Holds cease reserving at now>=expires; purchases
reserve until refunded. hold.create {id,event,seats:[IDS],now,ttl:POSITIVE_INT} nonempty selection,
unique hold ID, all seats known/free; all-or-none. Return {id,event,seats,expires:now+ttl,
status:'held',price:NUMBER_OF_SEATS*event_price}. hold.cancel {id} held only, idempotent after
cancelled; mark cancelled. purchase {hold,now,key} valid held and now<expires only, global key
idempotent same request returns original result even after later changes/expiry. Key conflict
rejects. Return order {id:OPAQUE,event,seats,total,status:'paid',used:[]}. Mark hold purchased.
order.get {id}. order.refund {id} paid only, rejects if ANY seat used, marks refunded and releases
seats. Replayed refund idempotent; total unchanged. checkin {order,seat} paid order and contained
seat not previously used; add sorted used, return {order,seat,admitted:true}. Duplicate admission
rejects with no effects. Refunded orders cannot check in. Seat resale after refund is allowed.
hold.import {holds:[hold-create-payloads]} all-or-none including conflicts between rows and
expiry evaluated using each row's own now. Return {imported:N}. sales.report {event} returns
{paid:SUM_TOTAL_PAID,refunded:SUM_TOTAL_REFUNDED,admitted:SUM_USED_SEATS_PAID}.
Strict time/TTL/int/ID validation; bool not accepted. Concurrent holds for same seat at same
logical time have exactly one winner. Restore validates all references, seats/amounts/statuses,
no duplicate active sales, used-seat membership and receipts; expiry remains logical-time driven.
