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
## Structured document branches and review
document.create {id,fields:OBJECT_STRING_KEYS_TO_STRING_VALUES} unique document; at least one
field and all keys nonempty, values may empty. Return {id,revision:1,fields,status:'draft',
approved:[],published:0}. document.edit {id,expected_revision,changes:OBJECT_OF_STRINGS}
exact revision, nonempty changes, update/add fields, revision+1, reset approved[], status draft.
branch.create {id,document} unique branch, snapshots document revision/fields as base and current
branch fields. Return {id,document,base_revision,revision:1,fields,status:'open'}.
branch.edit {id,expected_revision,changes} open/exact revision, update/add fields and revision+1.
branch.merge {id,expected_revision,document_revision} open branch exact branch/doc revisions;
three-way merge field-wise: for every field changed in branch from base, reject if document
also changed it to a DIFFERENT value; equal concurrent change is compatible. Unchanged branch
fields preserve live document edits. Entire merge atomic. Accepted merge increments document
revision once, clears approvals/status draft, branch status merged/revision+1. Return document.
branch.get {id}; document.get {id}. document.approve {id,actor,expected_revision} draft/approved,
exact revision, unique nonempty actor. Duplicate approval idempotent and no revision increase;
new approval DOES NOT change content revision. status approved when at least TWO different
actors, otherwise draft. document.publish {id,expected_revision} approved only/exact revision;
stores immutable current revision snapshot, published=current revision, status published.
Published documents may be edited, which creates a new draft revision while published snapshot
remains. document.live {id} returns {id,revision:LAST_PUBLISHED,fields:SNAPSHOT}, reject never
published. document.list {} sorted IDs. document.import {documents:[create-payloads]} all-or-none,
return {imported:N}. Restore validates document/branch IDs/revisions, string fields, base snapshots,
merged branch references/statuses, approval uniqueness and immutable published history.
Concurrent edits same revision have exactly one winner, and no successful merge loses a live edit.
