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
## Workspace document vault (synthetic identities, no real credentials)
workspace.create {id,owner,quota:NONNEGATIVE_BYTES} unique workspace, owner nonempty user ID,
initial owner admin. member.put {workspace,actor,user,role:'admin'/'editor'/'viewer'} admin actor,
upserts membership, cannot demote/remove last admin. member.remove {workspace,actor,user}
admin only, same last-admin rule. document.put {workspace,actor,id,content:STRING,
expected_revision:NONNEGATIVE_INT} admin/editor, unique ID on first put expected_revision0,
updates exact current revision thereafter. UTF8 byte size counts toward workspace quota across
ALL retained versions, including deleted documents. Each accepted put creates immutable version
number current+1 and returns {id,revision,content,deleted:false,size:UTF8_BYTES}. Updating a deleted
document rejects until restored. Empty content allowed. No cross-workspace membership leakage.
document.get {workspace,actor,id,revision optional} any member, current or historical version;
deleted documents cannot be read except admin. Version returns {id,revision,content,deleted:CURRENT_DELETION,
size}. document.delete {workspace,actor,id,expected_revision} admin/editor, live/exact revision,
soft deletes without version/revision increase; repeated delete rejects. document.restore
{workspace,actor,id} admin only, deleted only, restores live without new version.
document.purge {workspace,actor,id} admin only, deleted only, removes all versions and releases quota.
document.list {workspace,actor,include_deleted optionalfalse} sorted current docs; viewers/editors
cannot set include_deleted true. quota.set {workspace,actor,quota} admin, can't reduce below used.
quota.get {workspace,actor} any member -> {quota,used,available}. document.import
{workspace,actor,documents:[{id,content}]} admin only, atomically create whole batch with quota,
existing/repeated IDs reject; return {imported:N}. Restore(whole service) validates member roles,
last admins, version sequence/content sizes/current revision/deletion, used quotas and references.
Rejected requests preserve data-file bytes. Concurrent puts same revision have one winner.
