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
## Offline ranked-choice association decisions (synthetic members)
member.put {id,active:BOOLEAN} upserts member; deactivation allowed but does not remove already
cast ballots. poll.create {id,candidates:[IDS],quorum:POSITIVE_INT} unique poll, >=2 distinct
nonempty candidates normalized sorted, draft/revision1. poll.open {id,expected_revision} draft
only/exact revision; snapshots currently active eligible member IDs, status open/revision+1.
Membership edits after opening don't alter eligibility. delegate {poll,member,to} both eligible,
member!=to, poll open, member has no ballot, no transitive delegation cycle. Delegation replaces
previous choice; a delegated member cannot cast until undelegate. undelegate {poll,member}
open, removes existing delegation. vote {poll,member,ranking:[CANDIDATE_IDS],key} open, eligible,
member not delegated, ranking nonempty unique subset of candidates in preference order. One
ballot per member; global idempotency same normalized request original result, conflict rejects.
Return {poll,member,ranking}. Voting doesn't stop other eligible members delegating to voter.
poll.close {id,expected_revision} open/exact revision; snapshot ballots/delegations, mark closed,
revision+1. tally {poll} closed only -> {quorum_met,participating,winner:ID_OR_NULL,rounds:[...]}
Each eligible member contributes weight1 to its own ballot or follows delegation transitively
to a member with a ballot; missing ballot at terminal delegate means no participation. Compute
instant-runoff: in each round count each represented voter's highest still-active ranked candidate;
return {counts:{ACTIVE_CANDIDATE:INT},exhausted:INT,eliminated:ID_OR_NULL}. Winner if strictly
more than half non-exhausted votes; if one candidate remains it wins only if non-exhausted>0.
Otherwise eliminate the lowest-count candidate, breaking ties by LEXICALLY GREATEST candidate,
and continue. If quorum not met or all ballots exhausted, winner null (may return rounds[] when
quorum fails). poll.get {id}; poll.list {} sorted IDs. vote.import {votes:[vote-payloads]}
all-or-none, return {imported:N}. Restore validates poll states/revisions/eligibility snapshots,
ballot rankings/unique voters/keys/delegation references and acyclicity; closed results stable.
