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
## Expiring points and reservations
member.create {id} unique member. earn {member,id,points:POSITIVE_INT,expires:NONNEGATIVE_INT,key}
unique earning lot ID globally, global idempotency same normalized payload original snapshot,
changed request/operation rejects. Return {id,member,points,remaining:points,expires}.
balance {member,now:NONNEGATIVE_INT} -> {available:UNEXPIRED_UNRESERVED,held:ACTIVE_HOLD_POINTS,
expired:REMAINING_EXPIRED_UNRESERVED}. Lots with expires<=now cannot supply new redemption.
hold {member,id,points:POSITIVE_INT,now,ttl:POSITIVE_INT} unique hold, atomically allocate from
unexpired free lots sorted by(expires,id), no partial hold. Return {id,member,points,status:'held',
expires:now+ttl,allocations:[{lot,points}]}. Active held points remain held until their hold
expires, even if earning lot expires meanwhile. All operations using now lazily release expired
HOLDS at now>=hold.expires; rejected operations must not commit that cleanup.
redeem {id,now,key} unexpired held hold only, consume its reserved lot remaining, set redeemed,
return {id,member,points,status:'redeemed',refunded:0}. Global keys permit original snapshot
replay even after refund/expiry, conflict rejects. release {id,now} held only, set released,
idempotent after released; frees reservations but doesn't restore expired lot validity.
refund {id,points:POSITIVE_INT,now,key} redeemed only, cumulative <=redeemed points; restores
points to original earning lots in REVERSE allocation order, up to originally consumed quantities,
without extending lot expiry; increase refunded. Return redemption snapshot. Global keys across
earn/redeem/refund. lot.list {member} sorted by(expires,id); hold.get {id,now} returns hold,
reflecting expiry status 'expired' when reached. history {member} insertion-ordered successful
non-replayed earn/redeem/refund events {kind,id,points}, no hold/release events.
earn.import {earnings:[earn-payloads]} all-or-none, return {imported:N}. Restore validates members,
points/lots/reservations/redemption/refund allocation bounds, statuses/time and global keys;
concurrent holds cannot overreserve. Strict integers and no automatic resurrection of expired lots.
