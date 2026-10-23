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
## Bill-of-materials manufacturing
part.put {id,name,cost:NONNEGATIVE_CENTS} upserts part; new part stock0. bom.put
{product,components:[{part,quantity:POSITIVE_INT}]} product and parts exist, nonempty component
list, aggregate duplicate parts, no self/transitive cycle across BOMs; revision increments.
Manufacturing consumes DIRECT BOM components only (not recursive expansion), finished product
may itself be a component in another BOM. receive {part,quantity:POSITIVE_INT,key} globally
idempotent same normalized request original {on_hand}; conflicts reject, increases stock.
work.create {id,product,quantity:POSITIVE_INT} unique work order, requires BOM, snapshots BOM
and costs, return {id,product,quantity,produced:0,scrapped:0,status:'draft',reserved:[],cost:0}.
work.reserve {id} draft only; atomically reserve full required direct component quantities from
available on_hand-reserved; all-or-none. confirmed if success, reserved sorted [{part,quantity}].
Repeated reserve confirmed idempotent. work.finish {id,good:NONNEGATIVE_INT,scrap:NONNEGATIVE_INT,
key} confirmed/partial only, good+scrap>0, <=quantity-produced-scrapped. Atomically consume
snapshotted component quantities for good+scrap, reduce reservations/on_hand, increase finished
product stock by good only, produced+=good, scrapped+=scrap. cost adds consumed components'
snapshotted unit costs for good AND scrap. Status complete when all units attempted else partial.
Global key original result replay, operation/payload conflicts reject. work.cancel {id}
draft/confirmed/partial only, idempotent cancelled; release remaining reservations, preserve
production/scrap/cost history; complete cannot cancel. work.get {id}; stock {part} ->
{on_hand,reserved,available}. work.list {status optional} sorted IDs. receive.import
{receipts:[receive-payloads]} all-or-none, return {imported:N}. Restore validates BOM DAGs,
references, capacities, work snapshots, consumption/production/scrap/cost histories and keys.
Live BOM/cost edits don't change existing orders. Concurrent reservations cannot oversubscribe.
