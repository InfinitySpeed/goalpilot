# Structural context-ranking experiment (2026-10-23)

The candidate ranks repository instructions first, then file paths whose tokens overlap the original goal, then project configuration, tests, and other files. It keeps the existing 18,000-character context budget and 6,000-character per-file cap. The displayed file index stops at 4,096 characters on complete path boundaries and reports the exact number omitted. The full inventory remains frozen for change detection.

## Measurements

| Measure | Current behavior | Candidate |
|---|---:|---:|
| Synthetic relevant files retained under 18,000 chars | 0/2 | 2/2 |
| Context characters used in that fixture | 17,982 | 17,982 |
| Frozen inventory entries in the bounded-list test | 250/250 | 250/250 |
| Focused native workflow and listing tests | — | 19/19 pass, 4.74 s |
| Full suite on clean current checkout | 365/365 pass, 26.69 s | — |
| Candidate full suite in scratch copy | — | 353 pass, 4 failures, 9 errors, 24.45 s |

The local fixture is a retrieval proxy, not a model benchmark. It proves that relevant filenames enter the same-sized context in this synthetic case; it does **not** prove fewer model tokens, fewer uncached tokens, lower latency, or better completion.

This experiment changes only the native adapter path; GoalPilot’s service-route context builder remains unchanged. The candidate full-suite run is not clean: installer/promotion checks correctly reject a changed native engine hash, while some evidence tests need report archives larger than GoalPilot's per-file inventory limit that were omitted from the isolated scratch copy. A compatibility assertion also caught a missing `truncated` marker; the marker was restored and the focused 19-test run then passed.

**Decision: do not promote.** The active version stays unchanged until a representative model comparison confirms token and completion outcomes and the complete project suite can run with its required evidence. Candidate source and GoalPilot run logs are included in the [evidence archive](../reports/context-rank-structural-evidence-2026-10-23.zip). Machine-readable metrics: [`context-rank-structural-2026-10-23.json`](../reports/context-rank-structural-2026-10-23.json).
