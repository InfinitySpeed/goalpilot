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
## Lot-aware stock and fulfillment
product.put {id,name} upserts product. lot.receive {id,product,quantity:POSITIVE_INT,
expires:NONNEGATIVE_INT,key} unique lot, known product. Global idempotent key same normalized
request/operation returns original snapshot; conflicts reject. Return {id,product,on_hand:quantity,
reserved:0,expires}. order.create {id,lines:[{product,quantity:POSITIVE_INT}]} unique order,
nonempty lines, aggregate duplicates sorted product, all products exist. Return
{id,status:'draft',lines,allocations:[],shipped:[],returned:[]}.
order.allocate {id,now:NONNEGATIVE_INT} draft only; greedily allocate each product from lots
where expires>now, sorted by(expires,lot_id), quantity<=on_hand-reserved. Reject all if any line
short; no reservations left on failure. Set confirmed, allocations [{lot,quantity}] sorted by lot.
Repeated allocate confirmed returns same snapshot. order.ship {id,lines:[{lot,quantity}],key}
confirmed/partial, aggregate duplicates, <=allocated minus shipped. Atomically reduce on_hand
AND reserved, add cumulative sorted shipped lines; status shipped when all sent else partial.
order.cancel {id} draft/confirmed/partial, idempotent cancelled; release unshipped reservations,
keep historical shipments; fully shipped cannot cancel. order.return {id,lines,key} quantities
<=shipped minus returned, atomically increase original lot on_hand, reservations unchanged;
accumulate returned, preserve order status. Global keys across receive/ship/return, original
snapshot replay even after order changes. order.get {id}; lot.list {product optional,now optional}
sorted by(expires,id), optional now filters expires>now only; include {id,product,on_hand,
reserved,available:on_hand-reserved,expires}. stock.report {product,now} -> {on_hand:ALL_LOTS,
reserved:ALL_LOTS,available:NONEXPIRED_FREE,expired:EXPIRED_ON_HAND}.
lot.import {lots:[receive-payloads]} all-or-none, return {imported:N}. Restore validates all
references, nonnegative stock/capacity, allocation/shipment/return history and aggregate reservation
invariants, statuses and idempotency. Concurrent orders cannot overreserve a lot. Logical expiry
only affects new allocations; already reserved lots can ship after expiry.
