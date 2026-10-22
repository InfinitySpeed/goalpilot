---
name: goalpilot
description: Complete an explicitly requested coding goal in the current session with frozen checks and local verification. Use when the user explicitly asks for GoalPilot.
---

# GoalPilot

GP is `scripts/host.py` beside this skill's SKILL.md. Resolve it from the skill
directory, not from the project cwd. Work in THIS agent session; no nested agents,
models or Codex controller. Do not run hook-config: this adapter needs no Codex CLI.

1. Save the COMPLETE original goal verbatim as UTF-8 in GOAL (or use its supplied file).
   Before edits: `python3 GP session start --goal-file GOAL --repo REPO --run-dir RUN --helpers --context`.
   RUN must be new and outside REPO; forward requested budgets. Resume an existing
   open run without resetting it. On helper collision, repeat the SAME start without --helpers.
2. Start supplies initial source/tests/README and the applicable helper API.
   Use that API directly; read only missing/truncated/changed files or concrete missing
   details. Avoid duplicate SDK reads and unchanged full-suite reruns.
3. Implement EVERY requested workflow and business rule; preserve original tests/data.
   Resolve reversible ambiguities. For NEW pure apps with unspecified storage/backup
   format, prefer ReplayService: initial()+handle(), opaque() IDs, explicit request
   times and no external effects. Existing formats: use ServiceBase with a full validator.
   Use JourneyMixin/transport_journey/race where their interfaces match, with explicit
   business assertions, rejection, persistence, actor/time and concurrency cases.
   Prefer one multi-file edit for implementation and meaningful tests.
4. Check concrete uncertainties with targeted tests. Use
   `python3 GP session check RUN -- COMMAND` for local diagnosis when useful.
5. Before reporting completion, run `python3 GP session finish RUN` and inspect its result.
   The calling agent owns completion: no host Stop hook is assumed. On failure, repair
   the implementation in THIS session and repeat finish against the SAME tests,
   acceptance, deadline and verification budget. Do not reset the run to renew a budget.
   Inspect `python3 GP session status RUN` when resuming or when closure is uncertain.

Only `scope_passed` with `closed:true` means the supported frozen checks passed.
Unsupported/infrastructure/budget-exhausted stays open; explain the actual blocker.
Support remains bounded Python unittest projects on POSIX with Python 3.11+.
The local verifier launches no models; calling-agent token usage is not zero.
Published performance figures concern the Codex integration, not this host adapter.
