from .common import COMMON_SPEC
GOALS={
'flowdesk':'Turn this prototype into a complete local multi-team support platform that a small company can actually use end to end. Finish every original workflow, preserve existing data, and make it reliable without asking me to steer the work.',
'stockroom':'Finish this whole inventory and order-fulfilment platform so a small distributor can run daily operations from purchase receipt through sale, shipment, cancellation and returns. Make all documented workflows work together and preserve the data autonomously.',
'runforge':'Make this prototype a complete durable workflow execution platform: dependency graphs, workers, retries, expiring claims, cancellation, scheduled runs and artifact retention, all usable through its API and command line. Finish the whole goal autonomously.'}
FLOW='''# Flowdesk — offline multi-team support platform
Complete the public contract below, with meaningful local tests and usage instructions.

'''+COMMON_SPEC+'''## Workspace, identity and access
Operations use `workspace` and `token` except bootstrap. `bootstrap` takes {workspace,token}
and creates its first admin; same pair is idempotent, different token for an existing workspace
is rejected. `member.add` takes role admin/agent/viewer and new_token, requires admin and returns
{role}; duplicate token is rejected. Token identity is global: a token in one workspace must not
access another. Viewers read public tickets/comments but cannot write; agents can write normal
tickets/comments. Membership management, imports and event claiming/ack require admin.

## Ticket creation and idempotency
`ticket.create` takes id,title, optional tags(default []), idempotency_key(optional), plus context.
Title must be nonempty text. Tags are nonempty strings, normalized to sorted unique values.
Return {id,title,status:'open',revision:1,tags}. Idempotency is scoped to workspace, token and
key. Repeating the same normalized request returns its ORIGINAL result without another ticket
or event, even after the ticket changes. Reusing a key with different content is rejected.
IDs are unique per workspace; the same ID in a different workspace is independent.

## Ticket workflow and optimistic updates
`ticket.change` takes id,expected_revision and optional title,tags,status. Allowed transitions:
open -> pending/closed; pending -> open/closed; closed -> open. Keeping status is allowed.
Every accepted change increments revision exactly once including identical changes. Stale
revision is rejected atomically. The creator or agents/admins may edit; viewer never may.
`ticket.get` takes id and returns the ticket. No internal tokens/secret comments in ticket data.

## Comments and private notes
`comment.add` takes ticket,id,text, internal(optional false). Nonempty text, boolean internal.
IDs unique within ticket; agents/admins write, viewers cannot. `comment.list` takes ticket;
returns a list in insertion order of {id,text,internal}. Viewers must never see internal notes.
A ticket revision does not change when adding comments. Workspace separation always applies.

## Filtering and stable cursor pagination
`ticket.list` takes optional status,tag,after,limit(default20, integer1..100). Filter first;
sort tickets by id using Python string order; after is an exclusive ID boundary, not an index.
Return {items:[ticket...],next:LAST_ID_OR_NULL}; next is last returned ID only when more matching
items exist. This permits continuing after the boundary ticket is deleted or new earlier IDs
arrive. Unknown status, invalid limits and wrongly typed filters are rejected.

## Deletion and reference integrity
`ticket.delete` takes id,expected_revision, admin only. Remove ticket and its comments. Preserve
existing audit/outbox entries, including snapshots. The ID can be reused for a new ticket.
Reject stale revision/missing ticket with no side effects.

## Atomic CSV intake and export
`ticket.import` (admin) takes csv text with exact header id,title,tags. CSV quoting/newlines and
Unicode supported. tags is a JSON array of strings. Parse and validate ALL rows before inserting;
existing/repeated IDs or any invalid row rejects the whole import with no events. Return {imported:N}.
`ticket.export` (any member) returns a CSV string with the same header, tickets sorted by id;
it must roundtrip titles/tags exactly. Export represents current tickets regardless of status.

## Append-only audit and snapshots
`audit.list` (admin) returns ordered event objects {sequence,kind,ticket,snapshot}; sequence is a
positive increasing integer per workspace, kind ticket.created/ticket.changed/ticket.deleted/
comment.added. One event per accepted mutation; bootstrap/member changes produce no events.
Snapshots are independent immutable copies of the ticket for ticket events, or comment for
comment events. Failed/idempotent requests produce no additional events. No secret tokens.

## Durable outbox claims and expiry
Each audit event is also deliverable once to a simulated downstream consumer. `event.claim`
(admin) takes worker,now(integer>=0),lease(integer>=1),limit(integer1..100), returns a list of
{sequence,receipt,event}. Claim in sequence order. Unacked claims can be claimed again by any
worker at `now >= claimed_now+lease`; each new claim has a fresh opaque receipt. `event.ack`
takes sequence,receipt; only the current receipt is valid and it may be acknowledged once.
Acked events never reappear. Bad/stale receipt rejection must not acknowledge an event.

## Cross-process invariants and recoverable state
Two concurrent changes with the same revision have exactly one winner. Two concurrent claims
must not both acquire the same currently leased event. Restore validation rejects malformed
tickets, comments referring to missing tickets, invalid role values and malformed event states.
An end-to-end journey combines private notes, revision conflicts, export/import, outbox retry,
backup/restore and HTTP access without relaxing earlier rules.
'''
STOCK='''# Stockroom — daily inventory and fulfilment platform
Complete the public contract below, with meaningful local tests and usage instructions.

'''+COMMON_SPEC+'''## Product catalog and warehouse setup
`product.put` takes sku,name,reorder_point(optional0), returns {sku,name,reorder_point}.
Nonempty text, nonnegative integer reorder point. Creating/replacing metadata preserves stock.
`warehouse.add` takes id, creates a warehouse idempotently and returns {id}. `catalog` takes {}
and returns products sorted by sku. IDs are nonempty; unknown products/warehouses are rejected.

## Stock receipts and immutable movements
`stock.receive` takes sku,warehouse,quantity(positive int),key(nonempty idempotency key).
The key is global across stock-mutating commands. Same operation and identical normalized
payload returns original result; changed payload/operation rejects. Return {on_hand:NEW_TOTAL}.
Record one movement {sequence,kind,sku,warehouse,delta} where kind='receive'. Accepted stock
changes get a globally increasing positive sequence; failures/idempotent replays add nothing.
`movement.list` takes optional sku, returns matching ordered movements. For transfer/ship/return
use kind transfer/ship/return. Reservations do not create physical movements.

## Stock visibility and reorder dashboard
`stock.get` takes sku,warehouse and returns {on_hand,reserved,available}; available=on_hand-reserved.
Missing balance for known product/warehouse is zero. `reorder` takes {} and returns sorted SKUs
whose sum of available over ALL warehouses is STRICTLY below reorder_point.

## Order drafts and durable line aggregation
`order.create` takes id,lines:[{sku,quantity}], lines nonempty with positive integer quantities.
Duplicate SKUs aggregate; normalized lines sorted by sku. Return order {id,status:'draft',lines,
allocations:[],shipped:[],returned:[]}. `order.get` returns it. Unknown sku rejects whole request;
caller input unchanged; IDs unique. Lines cannot be edited after creation.

## Atomic multi-warehouse allocation
`order.confirm` takes id; draft only. Allocate each SKU from warehouses sorted by ID using
available stock, splitting across warehouses as needed. If ANY line is unavailable reject all
reservations and keep draft. Return order status='confirmed', allocations:[{sku,warehouse,quantity}]
sorted by sku then warehouse. Repeated confirm on already confirmed returns same order; other
states reject. Concurrency must never overreserve even across separate Service processes.

## Partial shipments and idempotency
`order.ship` takes id,lines:[{sku,warehouse,quantity}],key. Order must be confirmed or partial.
Aggregate duplicate (sku,warehouse) lines; only its reserved unshipped allocation can ship.
Atomically reduce on_hand and reserved, record ship movements, and update cumulative `shipped`
list in the same shape/order as allocations. Status becomes partial or shipped when all sent.
One bad line rejects the whole batch. Repeating the same key/payload returns its original order
snapshot even if later shipments or returns changed the order. Key normalization ignores line order.

## Cancellation and reservation release
`order.cancel` takes id. Draft/confirmed/partial can be cancelled, releasing only remaining
unshipped allocations. Preserve physical shipments/history. Repeated cancellation is idempotent.
Shipped orders cannot be cancelled. A cancelled partial order may still receive valid returns.

## Returns bounded by shipment history
`order.return` takes id,lines in the shipment shape,key. Only quantities previously shipped
and not already returned can return; add on_hand, leave reserved unchanged, record return movements.
Aggregate duplicate lines. Apply atomically and use the global idempotency rules. `returned` is
cumulative sorted. Returns do not alter the order's status.

## Warehouse transfers without stealing reservations
`stock.transfer` takes sku,source,target,quantity,key. Different known warehouses, positive int,
quantity <= source.available. Atomically decrement/increment on_hand and record two transfer
movements with opposite delta. No reservation changes. Return {source:stock_snapshot,target:...}.

## Stocktake with compare-and-set and audit
`stock.count` takes sku,warehouse,expected_on_hand,new_on_hand,key. Nonnegative integers; expected
must match live on_hand, and new_on_hand >= reserved. Record a movement kind='count' with delta
(including zero). Return stock snapshot. Stale count rejects; replaying its accepted key returns
original result even if expected no longer matches. Competing counts have one winner.

## Purchase orders and partial receiving
`purchase.create` takes id,warehouse,lines like order.create, returns {id,warehouse,lines,received:[],status:'open'}.
`purchase.receive` takes id,lines:[{sku,quantity}],key. Aggregate lines; cannot receive unrequested
sku or more than ordered minus already received. Atomically increase warehouse stock and record
receive movements; received is cumulative, sorted, status partial/received. Return purchase snapshot.
Same global key semantics; operation failure never consumes its key. `purchase.get` takes id.

## Integrity, atomicity and state restoration
Validate every line before effects. IDs/SKUs/context keys cannot be bool/int placeholders.
Restore rejects negative balances, reserved>on_hand, orders referencing unknown SKUs/warehouses,
impossible statuses or shipped/returned quantities, and orphan reservations. Physical on_hand
must reflect receipts, shipment, transfers, counts and returns across process restarts. Preserve
all original user data and unrelated SQLite tables through every operation and restore.
'''
RUN='''# Runforge — durable local workflow execution platform
Complete the public contract below, with meaningful local tests and usage instructions.

'''+COMMON_SPEC+'''## Workflow graph definitions and immutable revisions
`workflow.put` takes id,nodes:[{id,needs:[],max_attempts(optional1),retry_delay(optional0)}].
All node IDs unique/nonempty; needs unique existing IDs with no self edge/cycle; attempts positive
integers, delay nonnegative integers. Reject the ENTIRE invalid definition. First revision1;
each replacement increments revision, including identical definition. Return {id,revision,nodes}
with nodes sorted by id and needs sorted. Running executions preserve their original revision.
`workflow.get` takes id and returns latest definition.

## Launch idempotency and run snapshots
`run.start` takes workflow,id,key. Run IDs global unique. Same key and identical payload returns
ORIGINAL start snapshot; changed payload rejects. Return {id,workflow,revision,status,nodes:[...]}
where nodes sorted by id expose id,status,attempt,not_before plus result(optional),error(optional).
Initial root nodes ready, others blocked, attempt0, not_before0, run status active. `run.get` takes id.

## Durable worker claims and deterministic ordering
`job.claim` takes worker,now(nonnegative int),lease(positive int) and returns null or
{run,node,attempt,receipt,expires}. Choose ready job with not_before<=now by (run.id,node.id)
lexicographic order. Atomically move to running, increment attempt and issue a fresh receipt.
Expired claims are recovered before selection: at now>=expires, either ready with not_before=
expires+retry_delay if attempts remain, or failed if exhausted. Receipt never repeats for a job.
No two processes may hold the same current claim. Expired receipts are invalid even if not yet
reclaimed; finish operations take now and must enforce that boundary.

## Finish success and dependency release
`job.succeed` takes run,node,receipt,now,result(any JSON-like value); current unexpired claim only.
Mark succeeded and store a deep copy of result. A blocked node becomes ready only when all needs
succeeded. When all nodes succeeded, run status succeeded. Running unrelated nodes continue.
Duplicate/old completion rejects with no state changes or artifacts. Return current run snapshot.

## Explicit failures and scheduled retries
`job.fail` takes run,node,receipt,now,error(nonempty string). Same claim validation. If attempt
<max_attempts mark ready, not_before=now+retry_delay; otherwise failed and recursively mark its
blocked/ready descendants skipped. Unrelated branches remain runnable. Run status failed only
when all nodes are terminal (succeeded/failed/skipped/cancelled) and any failed/skipped; status
active otherwise. Error detail is retained across retries. Return run snapshot.

## Cancellation propagation and late acknowledgements
`run.cancel` takes id, marks every nonterminal node cancelled, invalidates receipts and sets run
status cancelled. Repeating is idempotent. Cannot cancel succeeded/failed run. Late succeed/fail
rejects and must not revive it. Already succeeded nodes/results remain in a cancelled run.

## Artifact content addressing and atomic attachment
`artifact.put` takes run,node,receipt,now,name,content(text); same current claim validation.
Nonempty name; content UTF-8, may be empty. Compute sha256 of content bytes. Return {digest,size}.
Store/replace name within that node, immutable content by digest, deduplicated across all runs.
`artifact.get` takes run,node,name and returns {digest,size,content}. Artifacts remain readable
after success/failure. Invalid/stale claims create no blobs or attachment side effects.

## Retention and garbage collection
`run.delete` takes id; terminal runs only. Remove the run, its artifacts, and launch keys bound
to it so its ID/key can be reused. Other runs referencing the same blob keep it readable.
`artifact.gc` takes {}, deletes unreferenced blobs, returns {removed:N,remaining:N} (counts of
unique content digests, never attachment count). Delete itself does not run GC.

## Interval schedules and bounded catch-up
`schedule.put` takes id,workflow,start(nonnegative int),interval(positive int),limit(positive int).
Create only; identical request idempotent, changed request rejects. `schedule.tick` takes now,
max_runs(integer1..100), visits all due slots <=now sorted by (slot_timestamp,schedule.id),
creates at most max_runs runs total. Slot k=0..limit-1 creates id '@'+schedule_id+':'+str(k), using
the workflow revision current AT TICK. Return a list of newly created run snapshots, preserving
that order. Already ticked slots never duplicate. A conflicting existing run ID rejects the entire
tick (no earlier slot consumed); fix conflict then retry. `schedule.get` returns definition plus
emitted integer count. Schedules and emitted state survive restart and backup.

## Run listing and monitoring
`run.list` takes optional status and after and limit(default20, integer1..100), returns
{items:[run...],next:LAST_ID_OR_NULL}. Filter first, sort by run ID, exclusive after boundary.
Unknown status/invalid types reject. Status is a deterministic function of current job state,
updated by claim/finish/cancel; reads must not expire claims using actual wall clock.

## Cross-process consistency and restoration
All graph, lease, schedule, artifact and idempotency effects are transactional. Restore rejects
cycles/broken needs, invalid states/attempt counts, references to missing workflows/blobs, wrong
artifact hashes/sizes and malformed schedules. HTTP and CLI must expose full launches, claims,
artifacts, retries and schedules; process restarts cannot forget idempotency or ownership.
'''
SPECS={'flowdesk':FLOW,'stockroom':STOCK,'runforge':RUN}
