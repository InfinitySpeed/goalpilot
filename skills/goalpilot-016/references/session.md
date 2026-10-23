# In-session lifecycle

Use scripts/host.py and the interpreter in RUNTIME.json. These commands launch no coding models.

1. `session begin --goal 'COMPLETE ORIGINAL GOAL' --repo REPO --run-dir RUN --helpers --context` saves the original goal verbatim and freezes initial tests. `--goal-file FILE` also works. RUN is outside the project. A pre-created empty container is accepted; existing evidence is never reset. Helper collisions require the same begin without --helpers.
2. Implement and write meaningful tests. The complete helper API and initial source are supplied; avoid reading them repeatedly.
3. Write a criteria JSON document with `criteria: [{quote: "exact original-goal phrase", checks: ["builder-tests"]}]`. Include all requested goal clauses. Quotes from README are not original-goal quotes unless the goal contained them. Custom checks use argv arrays, and can be supplied under top-level checks. Uncheckable criteria need checks: [] and blocker. Optional statements default to their source quotes. Exact quotes establish traceability, not that every implicit intent was inventoried.
4. `session deliver RUN --criteria-file FILE` expands the explicit criteria into a requirement map and submits acceptance. It verifies locally, or returns verification ownership to an already configured exact-engine Codex Stop hook. It does not launch or configure Codex hooks automatically. End immediately when the hook owns completion. Other hosts always verify explicitly.
5. If verification fails, repair implementation and use `session finish RUN` against the same frozen acceptance and deadline. Do not resubmit or weaken tests. `session status RUN` reports verified, missing or blocked evidence. Only goal_complete:true supports the inventoried goal; scope_passed+closed:true means the frozen suites passed.

The saved original goal, original tests and final acceptance are retained. Unsupported tests, blocked requirements, infrastructure failures and expired budgets keep the goal open. Total calling-agent usage is unknown unless measured externally.
