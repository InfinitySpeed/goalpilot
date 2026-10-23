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
## Assets, bookings and returns
asset.put {id,quantity:NONNEGATIVE_INT,rate:NONNEGATIVE_CENTS} creates/replaces stock metadata;
reject lowering quantity below concurrent confirmed/active bookings' peak capacity. asset.list
returns sorted assets. Booking intervals are half-open [start,end), strict nonnegative integer
start and end>start. booking.create {id,asset,quantity:POSITIVE_INT,start,end,key} creates a
confirmed booking when concurrent reserved quantity at EVERY instant fits the asset quantity.
Unique booking ID. Idempotency key global: same normalized create returns ORIGINAL snapshot;
changed payload rejects; rejected requests do not consume their key. Return booking
{id,asset,quantity,start,end,status:'confirmed',revision:1,fee:0}. Rate is snapshotted at booking.
booking.pickup {id,expected_revision,now} exact revision; confirmed only; start<=now<end.
Sets active, revision+1. booking.return {id,expected_revision,now,damaged:NONNEGATIVE_INT}
active only, exact revision, now>=start, damaged<=quantity. Sets returned, revision+1,
fee=quantity*(end-start)*snapshotted_rate + max(0,now-end)*quantity*snapshotted_rate + damaged*100.
Return exactly once, reject second return. booking.cancel {id,expected_revision} confirmed only,
sets cancelled, revision+1, frees capacity. Returned/cancelled bookings don't reserve capacity.
booking.get {id} returns snapshot. available {asset,start,end} returns {quantity:MINIMUM_FREE}
over the full interval, counting only confirmed/active bookings; adjacent intervals don't conflict.
booking.list {asset optional,status optional} returns sorted bookings with conjunctive filters.
booking.import {bookings:[create-payloads]} all-or-none, including overlap and key conflicts
within batch. Return {imported:N}. Replays with existing keys may appear; do not double reserve.
Restore validates references, interval/quantity types, statuses/revisions, global keys, fee and
capacity invariants; changing live rates never changes existing booking fee calculation.
