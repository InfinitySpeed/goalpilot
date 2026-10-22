# Local calling-session protocol (skill 1.1.0 / engine 0.10.0)

Commands work through `python3 scripts/goalpilot.py session ...` in the portable
skill, or `python3 -m goalpilot session ...` from an installed source package.
The existing standalone `go`, `continue`, `status` commands retain their behavior.

```text
session start --goal-file /tmp/goal.txt --repo /path/project --run-dir /tmp/new-evidence
              [--wall-seconds 900] [--max-verifications 5]
              [--max-tokens N] [--max-uncached-tokens N]
session submit /tmp/new-evidence --handoff /tmp/handoff.json
session verify /tmp/new-evidence
session status /tmp/new-evidence
session repair /tmp/new-evidence
```

Start before edits. Goal bytes (including CRLF, quotes and metacharacters) are data,
not shell code. Repository, goal, budget and evidence location are validated before
creation. Existing directories are refused, including empty ones. Resume commands
accept no replacement goal, repository, scope or budgets. Wall time includes coding,
waiting and verification since start. Every verification reserves one attempt before
executing; interruptions consume it. `repair` authorizes no model call: edit code in
the same caller, then `verify` without another submit. Exhausted budgets cannot renew.
Token ceilings are persisted for the external caller/harness, not enforceable by a
local process which cannot observe caller inference. Its usage stays `UNKNOWN`;
`total_tokens:null` is never a zero-cost assertion. Engine nested calls are zero.

Example handoff (use the current Python executable or available `python3`):

```json
{"summary":"Implement label normalization","assumptions":[],"limitations":[],"checks":[{"id":"labels","description":"Unicode normalization, duplicate and empty cases","command":["python3","-B","-c","from app import normalize; assert normalize([' ÉTÉ ','été','B']) == ['b','été']; assert normalize([]) == []"],"timeout_seconds":5}]}
```

Checks execute with repository cwd and the caller's permissions. Use self-contained
assertions in `python -c`, Python assertion scripts (copied and frozen at submit),
or the frozen tests under `tests/`. Dependencies outside
that tree are implementation, not independently frozen acceptance. These are trusted
local commands, not a sandbox for hostile handoffs. The verifier cannot infer whether
an assertion adequately covers a natural-language goal. Use real CLI subprocesses,
data round trips, negative inputs and bounded HTTP on localhost where relevant.
Do not replace assertion programs with success markers or existence checks.

Original bounded source copies and an original unittest gate are captured at start.
At first valid submit, current builder tests/fixtures and check argv are frozen too.
Verification runs BOTH gates (in disposable copies) plus submitted checks; weakening
working original tests cannot remove the initial gate. Builder test bytes and the
entire tests inventory must remain unchanged during repair; restore accidental edits
from `builder/originals/tests`, then repair implementation. Submission is single-use;
invalid JSON/check schemas do not freeze acceptance. Explicit completion claims in
handoffs are ignored. Unsupported unittest discovery, missing tests, excluded inputs
or capture limits cannot produce supported verified completion. Current support is
bounded Python unittest projects, not arbitrary test frameworks or large worktrees.

`session.json` and `goal.bin` preserve the immutable contract and exact input;
`acceptance.json` preserves the first accepted handoff, both gates and artifact hashes.
`session-state.json` preserves statuses, attempts, check results, durations and lock
ownership events. JSON receipts detect accidental corruption; they are not signatures
against an attacker who can rewrite the entire evidence directory. Keep evidence
outside the repository and do not edit it. The OS exclusive lock prevents overlapping
protocol operations; it is released on process death. Stale `verifying` is reported
as interrupted, never closed. SIGKILL may leave a running attempt without its final
duration; retained start time and wall deadline remain authoritative.

Source changes after successful verification invalidate closure on the next status
or protocol operation. Test-induced source drift refuses closure. Tests, original
snapshots and runners are hash checked before/after execution. Failures, timeouts,
missing verifiers and integrity errors remain open; repair uses the original deadline
and remaining attempts. Restoring corrupt frozen bytes is required before proceeding.
The protocol does not lock editors or make concurrently edited databases a backup.

## Explicit legacy controller

Only when the user explicitly requests the standalone/thorough controller, use:

```text
python3 GP go --goal-file GOAL --repo REPO --run-dir NEW_RUN [--thorough] [requested budgets/policy]
python3 GP continue RUN
python3 GP status RUN
```

This launches additional Codex coding/review sessions, consumes engine AND caller
usage, and requires authenticated Codex. Unsupported default sessions do not switch
automatically. Preserve their failed evidence. A separately authorized controller
needs a distinct run directory; its budget/cost is additional, not a free resume.
Legacy goal-file handling, shared reuse cache and policy flags are unchanged.
