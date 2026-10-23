---
name: goalpilot
description: Finish an explicitly requested coding goal in this session using reusable helpers and frozen behavioral checks.
---

# GoalPilot

GP = `scripts/host.py` beside this file. Build HERE; no nested agent/model/controller.

1. FIRST command (no preliminary scans):
   `python3 GP session begin --goal 'COMPLETE VERBATIM ORIGINAL GOAL' --repo REPO --run-dir RUN --helpers --context`.
   Or use --goal-file for a supplied UTF-8 file. Begin saves the goal and prepares paths;
   do not mkdir RUN or write a separate goal file. RUN outside REPO; forward requested budgets.
   Resume existing evidence with status/finish, never reset. Helper collision: same begin without --helpers.

Execution discipline: after begin supplies complete context, the NEXT command should write the implementation, tests and criteria and invoke deliver. Read an extra file only to resolve a named missing requirement/API detail; never reread this skill or supplied helper signatures. Avoid exploratory search when the provided contract suffices.
Write only the necessary implementation, one comprehensive business-journey test plus specific risk tests, and criteria. Leave existing documentation unchanged unless the goal requests documentation. Aim for <=1800 implementation+test tokens using compact idiomatic code and shared/table-driven logic; cover every workflow and guard, correctness first. Do not add one-use abstractions, duplicate tests per transport, or repeated descriptive comments. No progress narration between begin and delivery; final response <=30 words, factual evidence only.

2. Start supplies source/tests/instructions and COMPLETE helper API. Use it directly;
   read only missing/truncated/changed files or a concrete missing API detail.
   No duplicate SDK/helper reads when supplied signatures suffice.
   fields(value,schema) VALIDATES a value; it is NOT a validator factory. Nested schema example:
   row = lambda value: fields(value,{"id":text}); sequence(row) constructs a list validator.
3. Implement EVERY requested workflow/shape/guard, preserving tests/data. Resolve reversible
   ambiguities. NEW pure unspecified formats: ReplayService initial()+handle(), opaque() IDs,
   explicit request times; no external effects. Existing formats: ServiceBase+full validator.
   Prefer ONE multi-file implementation+test edit, direct dispatch, <=2500 code/test tokens
   where feasible; correctness first. No duplicate docs/contract or unneeded abstractions.
   JourneyMixin.assertJourney(flow) runs ONE authored business journey in-process, JSONL and
   HTTP with isolated fixtures. Keep meaningful business, rejection, persistence, time/actor,
   corruption and concurrency assertions. Test concrete uncertainties; avoid unchanged reruns.
4. Inventory each goal clause and constraint; group into 1–8 concise observable criteria.
   Create CRITERIA alongside implementation/tests in the SAME edit. Immediately execute deliver
   in that SAME tool command. The frozen-suite verifier is the test run: do not run unittest
   separately first or reread successful files before delivery. Repair only concrete failures.
   Save CRITERIA as JSON: {"criteria":[{"quote":"EXACT source phrase","checks":["builder-tests"]}]}.
   Quotes/statement default to the same text; choose quotes covering ALL goal requirements.
   Quotes must occur in the saved ORIGINAL GOAL, not merely in README/context.
   Use original-tests/builder-tests for behavior actually exercised there. Optional statement,
   custom checks (top-level argv check objects), assumptions and limitations. Uncheckable criteria:
   checks:[] plus blocker. Do not invent checked coverage.
   `python3 GP session deliver RUN --criteria-file CRITERIA` submits/maps criteria and verifies
   original+delivered suites locally. With completion_owner=codex_stop_hook, deliver only freezes
   acceptance: END immediately with checks pending; Stop verifies in this SAME session.
   Otherwise deliver verifies immediately. No separate unchanged final suite. On failure, repair
   implementation against SAME frozen acceptance/tests/budget, then `python3 GP session finish RUN`.
5. End immediately and concisely with verified/missing/blocked evidence. Only goal_complete:true
   supports goal completion; scope_passed+closed:true establishes frozen-check success.

Python3.11+, bounded unittest projects, Linux/macOS/Windows. service_race needs POSIX fork.
Use RUNTIME.json's interpreter. No Codex dependency for portable verification. Codex may reuse configured exact-engine Stop hooks. Zero nested
calls; caller usage UNKNOWN without external metering. No cross-host savings guarantee.
