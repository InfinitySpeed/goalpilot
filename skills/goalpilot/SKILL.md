---
name: goalpilot
description: Complete an explicitly requested coding goal in this session with frozen checks and passive loop diagnosis. Use for $goalpilot.
---

# GoalPilot

GP = `scripts/goalpilot.py` beside this file. Build HERE; no nested agent/model/controller.

1. Save the COMPLETE original goal verbatim as UTF-8 in GOAL (or use its supplied file).
   Before edits: `python3 GP session start --goal-file GOAL --repo REPO --run-dir RUN --helpers --context`.
   RUN new/outside REPO; forward requested budgets. Resume existing open runs, never reset.
   Helper collision: repeat the SAME start without --helpers.
2. Start supplies initial source/tests/README, instruction checks and the COMPLETE applicable
   helper API. Use it directly. Read only missing/truncated/changed files or a concrete missing
   API detail; do not reread sdk.md or helper source when these signatures suffice.
3. Implement EVERY workflow, return shape and business rule; preserve original tests/data.
   Decide reversible ambiguities. For NEW pure apps with unspecified storage/backup format,
   prefer ReplayService: initial()+handle(), opaque() IDs, explicit request times, no external
   effects. Replay validates restores; retain all normal business guards. Existing formats:
   use ServiceBase with a full validator. Use JourneyMixin/transport_journey/race for matching
   interfaces, keeping explicit business assertions, rejection, actor/time, persistence and
   concurrency cases. Prefer ONE multi-file edit for implementation AND tests; avoid separate
   generation/readback rounds and copies of unchanged code/docs. Aim <=3500 emitted code/test
   tokens where feasible; complete behavior and correctness take precedence.
4. Check concrete uncertainties with targeted tests. After implementation, one relevant suite
   is enough; repair failures, avoid unchanged reruns. `python3 GP session check RUN -- COMMAND`
   supplies local diagnosis when needed. Original checks always remain protected.
5. If start reports completion_owner=codex_stop_hook, END with brief factual status/checks pending.
   No separate finish/final full-suite: Stop freezes/verifies acceptance and continues THIS
   session on failure. Repair implementation against SAME tests/deadline/budgets, end again.
   Otherwise `python3 GP session finish RUN`; repair and repeat against the same acceptance.

Only scope_passed+closed:true means supported frozen checks passed. Unsupported/infrastructure
stays open. Support: bounded Python unittest projects. Zero nested calls does not mean free
caller usage; total tokens UNKNOWN without external metering. Legacy: references/session.md.
