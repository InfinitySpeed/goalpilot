# Native project workflow

N = scripts/native.py beside this skill's host.py. Build HERE; no nested agents/models.

FIRST tool command: python3 N begin --goal 'VERBATIM ORIGINAL GOAL' --repo REPO --run-dir RUN --context. RUN outside REPO. Forward requested --wall-seconds and --max-verifications; --goal-file accepts UTF-8. Do not reread this skill, scan files or run preliminary commands. Resume existing evidence with status/finish, never reset.

Begin supplies bounded context. NEXT command should implement, add focused native regressions, write criteria and deliver together. Extra reads only for named missing/truncated requirements/APIs. Preserve stack, existing tests/data/interfaces. Cover every workflow/guard; resolve reversible ambiguities. Aim <=2000 implementation+test tokens, correctness first. Use concise shared/table-driven logic; no speculative abstractions, duplicate transport tests, unrequested docs, narration or unchanged reruns.

Inventory ALL goal clauses/constraints into 1–8 criteria quoting the original goal. JSON: {"checks":[{"id":"tests","argv":["npm","test"]}],"criteria":[{"quote":"EXACT GOAL PHRASE","checks":["tests"]}]}.
Use actual project commands and behavioral evidence, not compilation alone. Unverifiable criteria: checks:[] plus blocker. Save JSON and run python3 N deliver RUN --criteria-file CRITERIA in the SAME implementation command. It freezes commands/tests and verifies original+delivered suites locally; this IS the test run. Repair only concrete failures against SAME frozen acceptance, then finish. Stop at budget; status rejects stale results. No success claim without goal_complete:true. Authored tests do not prove independent semantic coverage. Final <=30 words of verified/missing/blocked facts.
