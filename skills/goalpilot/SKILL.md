---
name: goalpilot
description: Complete an explicitly requested coding goal with traced criteria and local verification. Use for $goalpilot.
---

# GoalPilot

GP = `scripts/goalpilot.py` beside this file. Work in THIS session; no nested agent/model/controller.

1. Save the COMPLETE original goal verbatim as UTF-8 in GOAL. Before editing, start a new RUN outside REPO with `python3 GP session start --goal-file GOAL --repo REPO --run-dir RUN --helpers --context`. Resume open runs; never reset budgets. If helper collision occurs, repeat the same start without `--helpers`.
   Use `implementation_window_seconds` for coding; keep `closure_reserve_seconds` for submission and verification. Check status at milestones; when the reserve is reached, stop adding scope and submit/verify.
2. Before coding, list each independently testable outcome or constraint (including negative and delivery constraints) as a `requirement` with a concise statement and exact source quote. Inspect the project to turn vague quality words into defensible measured proxies; record assumptions, or block goals that cannot be checked without inventing success. Derive 1–8 criteria; map every requirement to criteria and every criterion back to requirements. Audit coverage against the full goal.
3. Use supplied context/helper APIs; read only missing details. Implement each criterion and add focused checks. Avoid duplicate reads and unchanged reruns; one relevant suite is enough.
4. Submit a handoff with `requirements` `{id,statement,source_quote,criterion_ids}` and `criteria` `{id,statement,source_quote,check_ids}`. Map every requirement and criterion. Each criterion needs executable checks or empty `check_ids` plus an explicit `blocker`. Use argv arrays. Run `python3 GP session submit RUN --handoff HANDOFF`.
5. With a Codex Stop hook, end the turn after submit; it verifies the frozen acceptance. Otherwise run `python3 GP session finish RUN`. On missing or failed criteria, repair in THIS session and verify against the SAME goal, criteria, checks, tests and budgets. Never weaken or replace frozen acceptance.

Report requirement coverage and criterion evidence. `goal_complete:true` requires all mapped requirements, criteria and frozen tests to pass. Quotes prove traceability, not inventory completeness; audit every goal clause. `scope_passed` alone is not completion. Unsupported checks stay open. The verifier makes no model calls; caller usage is unknown without host metering.

Support: bounded Python `unittest` projects on Linux/macOS/Windows with Python 3.11+; optional `service_race` needs POSIX fork. Legacy controller: `references/session.md`.
