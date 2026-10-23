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
## Versioned CSV normalization jobs
schema.put {id,columns:[{name,type:'text'/'integer'/'money',required:BOOLEAN}],key:PRIMARY_COLUMN}
creates/replaces schema revision+1; unique nonempty column names, key must be required text column.
Return {id,revision,columns,key}. job.create {id,schema,csv:STRING} unique job, snapshots current
schema, stores raw input, status draft. CSV header must match column names in exact order,
quoting/newlines/Unicode supported; validate header BEFORE committing creation. job.run {id,key}
draft only, global idempotency same operation/payload original result, conflict rejects. Process
rows in order: trim all cells; required text nonempty; integer optional empty ->null else strict
signed base10 integer text (no decimal/exponent/bool); money optional empty->null else nonnegative
decimal with at most TWO fractional digits, convert exactly to integer cents (no floats).
Missing/extra cells, invalid values, empty primary key or duplicate valid key reject that row.
First VALID row for a key wins; invalid earlier row doesn't reserve key. Return
{id,status:'processed',accepted:N,rejected:N,rows:[NORMALIZED_OBJECTS],rejects:[{row:CSV_LINE,
reason:NONEMPTY}],schema_revision:SNAPSHOT_REVISION}. row uses csv.reader.line_num including
physical embedded-newline lines, captured after reading current row. No partial publication.
job.publish {id,expected_revision:1} processed only, once; set published/revision2 and replace
schema's current published dataset atomically with normalized rows. job.get {id} includes
revision (initial1), result fields after run, original input stays available as csv.
dataset.get {schema} returns {job:LAST_PUBLISHED_ID,rows:SNAPSHOT,schema_revision}; reject no
publication. job.export {id} processed/published returns CSV string with original column names,
normalized integers/cents rendered as integer decimal strings, null empty, original row order.
job.retry {id,csv:STRING} processed but not published only, validate header against SNAPSHOT,
replace input and reset draft/result, revision stays1; old run keys retain original result.
job.import {jobs:[{id,schema,csv}]} all-or-none, return {imported:N}. Restore validates schema
column types/revisions, job snapshots/results/counts/keys, dataset publication references and
normalized types. New schema changes don't reinterpret an existing job.
