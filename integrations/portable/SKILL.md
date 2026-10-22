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
   Use the implementation window for coding; keep the closure window for submission
   and verification. Check status at milestones; when it is reached, stop adding scope
   and submit/verify.
2. Before coding, inventory each atomic outcome and constraint in the complete goal,
   including negative requirements and delivery instructions. Quote each source phrase.
   For vague quality words, inspect the project and baseline for a defensible measurable
   proxy, state the assumption, and add a check; otherwise keep it blocked rather than
   inventing success. Derive 1–8 concise criteria and map every requirement to criteria.
   Map every criterion back to a requirement and audit the map against the full goal.
   Start supplies initial source/tests/README and the applicable helper API.
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
5. Submit a handoff before finishing. Include `requirements` entries with `id`, `statement`,
   exact `source_quote`, and `criterion_ids`; every requirement and criterion must be mapped.
   Each `criteria` entry has `id`, `statement`, an exact `source_quote`, and `check_ids` referencing submitted executable checks. If a criterion
   cannot be checked, use `check_ids: []` and an explicit `blocker`. Keep argv commands.
   Run `python3 GP session submit RUN --handoff HANDOFF`.
6. Run `python3 GP session finish RUN` and inspect its result. On missing or failed criteria,
   repair in THIS session and verify against the SAME goal, criteria, checks, tests, deadline
   and budget. Do not reset. Inspect `python3 GP session status RUN` when resuming.

Report requirement-map coverage and each criterion as verified, missing or blocked with its
evidence. Only `goal_complete:true` means all inventoried requirements, criteria and frozen
tests passed. Exact quotes prove traceability, not inventory completeness; audit every goal
clause before submission. `scope_passed` alone does not claim the natural-language goal is
complete. Only `scope_passed` with `closed:true` means supported frozen checks passed.
Unsupported/infrastructure/budget-exhausted stays open; explain the actual blocker.
Support: bounded Python unittest projects on Linux/macOS/Windows with Python 3.11+.
The optional service_race helper requires POSIX fork; do not use it on Windows.
The local verifier launches no models; calling-agent token usage is not zero.
Published performance figures concern the Codex integration, not this host adapter.
