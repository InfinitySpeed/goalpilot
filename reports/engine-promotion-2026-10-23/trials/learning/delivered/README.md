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
## Learning and enrollment
student.put {id,name} upserts student. course.put {id,prerequisites:[IDS],capacity:NONNEGATIVE_INT,
price:NONNEGATIVE_CENTS} upserts course; prerequisite courses must exist, no self/cyclic graph.
Reject reducing capacity below current enrolled count. Enrollment snapshots price at request.
enroll {student,course,key} global idempotency same normalized request returns original snapshot;
changed payload rejects. Student exists, all prerequisites completed; cannot enroll twice in same
course even with another key (cancelled enrollment permits a new request). Enrolled if a seat
available else waiting. Return {id:OPAQUE,student,course,status:'enrolled'/'waiting',price,score:null}.
Waitlist order is successful request insertion order, independent of student ID. enrollment.get
{id}; enrollment.list {course optional,student optional} list in insertion order.
complete {id,score:INT0..100} enrolled only; sets completed and records score; score>=60 marks
student course completed for prerequisites. A failed completed enrollment still frees seat but
is not a prerequisite pass. No completion from waiting/cancelled/completed. Completion frees
capacity and promotes the earliest valid waiting enrollment to enrolled automatically.
cancel {id} waiting/enrolled only, idempotent if already cancelled. Sets cancelled, refund equals
snapshotted price for enrolled, zero for waiting; return {id,status:'cancelled',refund:...}.
Frees seat and promotes earliest waiting enrollment. Promotion snapshots no new price.
course.report {id} returns {enrolled:COUNT,waiting:COUNT,completed:COUNT,cancelled:COUNT,
revenue:SUM_PRICE_OF_ENROLLED_AND_COMPLETED,waitlist:[STUDENT_IDS_IN_ORDER]}.
enroll.import {requests:[{student,course,key}]} all-or-none across prerequisites, duplicate
students and capacity transitions; return {imported:N}. Unknown course/student or invalid key
rolls back all requests. Restore validates DAG, enrollment references/statuses/prices/scores,
capacity, waitlist order, completed prerequisite history and idempotency snapshots.
