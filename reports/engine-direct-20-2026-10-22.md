> Correction (2026-10-23): the original table below mixed strict candidate grading with reviewed controls. Applying the same two existing historical grading amendments gives direct-first **20/20**, with unchanged tokens and 0.865 s of additional local judging. See [the grading correction](engine-direct-20-2026-10-22-reviewed.json). The cost regression against the current Skill remains; retain the original strict result below as a historical record.

# GoalPilot direct-first 0.15.0: frozen 20-goal comparison

**Result: this engine version is not an improvement over GoalPilot Skill 1.3.1 on the full benchmark.** It independently passed 18 of 20 goals. GoalPilot itself closed all 20 runs, so two closures were false positives against the fixed external judge.

| Engine | Independently correct | Raw input + output tokens | Uncached input + output tokens | Time, including judge |
|---|---:|---:|---:|---:|
| GoalPilot Skill 1.3.1 (frozen control) | 20/20 | 2,151,252 | 342,356 | 1,541.6 s |
| Codex native (frozen control) | 19/20 | 4,716,581 | 720,421 | 3,919.1 s |
| GoalPilot direct-first 0.15.0 | 18/20 | 3,178,126 | 515,598 | 3,277.9 s |

Against Codex native, direct-first saved **16.36% time**, **32.62% raw tokens**, and **28.43% uncached-input-plus-output tokens**, while completing one fewer goal. It missed the accepted targets of at least 25% time savings, at least 45% token savings, and no completion regression.

Against the current Skill, direct-first took **2.13× as long**, used **47.73% more raw tokens** and **50.60% more uncached-input-plus-output tokens**, and passed two fewer goals. The current Skill remains the better measured option in this 20-goal sample.

Every direct-first run returned GoalPilot status `scope_passed`; the independent judge rejected `annotations` (concurrent claims did not return distinct receipts) and `subscriptions` (an overdue billing replay returned “Billing not due” instead of the existing invoice). Those are missed behaviors, not missing token meters: all 20 usage meters are complete. The fixed Skill and native results are historical controls from the same frozen cases, not new reruns.

Method: one fresh direct-first run per goal, gpt-6.1-sol at low reasoning effort, no retries or judge feedback, then one independent fixed judge execution. The candidate used 3,178,126 raw tokens and 515,598 uncached-input-plus-output tokens, below the campaign caps of 8,000,000 and 900,000. The detailed per-goal data, counter definitions, frozen control source hash, and comparisons are in [engine-direct-20-2026-10-22.json](engine-direct-20-2026-10-22.json). Raw trial evidence and judge logs are in `/workspace/goalpilot-research/engine20-direct-001/`.
