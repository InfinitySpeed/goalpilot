# Benchmark results and limitations

This report covers skill **1.3.1**, engine **0.12.1**, and the complete calling invocation. It distinguishes observed results from general product guarantees.

## Primary comparison

Twenty fixed missions, 20 attempts per arm, matching initial application source and public requirements:

| Metric | Native Codex | GoalPilot | Reduction |
| :--- | ---: | ---: | ---: |
| Total elapsed seconds, reviewed judging included | 3,919.077429 | 1,541.619187 | 60.6637% |
| Input tokens, including cached input | 4,495,572 | 2,065,239 | 54.0606% |
| Cached input tokens | 3,996,160 | 1,808,896 | 54.7341% |
| Uncached input tokens | 499,412 | 256,343 | 48.6710% |
| Output tokens | 221,009 | 86,013 | 61.0817% |
| Raw input plus output tokens | 4,716,581 | 2,151,252 | 54.3896% |
| Uncached input plus output tokens | 720,421 | 342,356 | 52.4783% |
| Correct, normally closed goals — reviewed | 19/20 | 20/20 | Observed count preserved |
| Correct, normally closed goals — original | 17/20 | 19/20 | Observed count preserved |

![Time, token composition and both completion score definitions.](assets/benchmark.png)

The input-token percentage is recalculated by the accompanying benchmark checker; all headline reductions are derived from the included machine-readable rows. Raw tokens include cached input and output. Uncached input is input minus cached input. Savings use `100 × (1 − GoalPilot total / native total)`, with all completed attempts and failures retained. No dollar or subscription-quota conversion is inferred.

## Design and accounting

- **Workload:** 20 synthetic stateful Python standard-library services across 20 business domains, with interacting workflows, JSONL/HTTP interfaces, persistence and concurrency. Initial projects are skeletons. These are known development cases in one service family, not a novel blinded holdout or real-user sample.
- **Model and host:** `gpt-6.1-sol`, LOW reasoning effort; Codex CLI 0.163.0; Linux/POSIX; Python 3.12.14; matching `danger-full-access` execution and noninteractive approval settings. These benchmark permissions are descriptive, not an installation recommendation.
- **Native control:** real `thread/goal/set` goals and native automatic continuation. The client never forced a goal to complete.
- **Success:** normal goal closure **and** the full independent behavioral checks. Stopping, an unsupported environment, a local test pass or an infrastructure failure alone does not count. The external grader checks domain rules, atomic rejection, process races, persistence, backups, transports and original data.
- **Time:** entire caller setup and invocation plus independent judging. Includes skill installation and reading, context, coding, repairs and final Stop verification. Common fixture preparation, quota snapshots and evidence-copy overhead are outside comparative timing.
- **Tokens:** cumulative provider input, cache and output counters for the entire caller thread. All 44 complete comparative rows, including four old-skill anchors, have complete meters. Persisted CLI token metadata agrees with the wire counters on all 44.
- **Calls:** no nested/delegated model calls in either primary arm. The passive monitor launches no models. This does not make the caller free.

Some native controls preceded the final skill and were explicitly carried forward byte-for-byte, including functional failures. Remaining controls were interleaved. Cache behavior, order and host load limit causal interpretation. The nine-pair fresh/interleaved subset and paired-success analyses are included in the [original descriptive summary](../reports/skill-131-summary/summary-report.json).

## Original versus reviewed scoring

Each fraction counts **successful coding missions out of 20 attempts per tool**. Success requires normal goal closure and all independent behavioral checks, not merely an agent saying it is done. A 17/20 result means 17 successful missions and 3 unsuccessful missions.

| Stage — same 20 attempts per tool | Native Codex | GoalPilot | Change from the previous row |
| :--- | ---: | ---: | :--- |
| Initial grader | 17/20 (85%) | 19/20 (95%) | Original recorded result. |
| Correct the subscription billing test | 18/20 (90%) | 20/20 (100%) | One previously failed mission becomes a pass for each tool. |
| Accept the ambiguous annotation return format | 19/20 (95%) | 20/20 (100%) | One further native mission becomes a pass; GoalPilot's count is unchanged. |

This table is a grading sensitivity analysis of the same delivered applications. It is not a sequence of product versions, new model attempts or goals repaired after seeing external feedback. The denominator stays 20 throughout. The final observed counts do not establish a universal completion rate or statistically reliable superiority on new tasks.

The original analysis and original outcomes remain unchanged. Two post-registration reviews were applied symmetrically, with no product edits or model reruns:

1. **Subscriptions:** the original race check required both requests at a billing boundary to succeed, although the first call advanced the boundary and the documented precondition required the loser to reject. Both implementations correctly rejected that call. The corrected grader requires exactly one successful billing operation and one invoice; invalid alternatives are rejected.
2. **Annotations:** the public return contract did not type the returned `item` as an ID or record. The original judge accepted only the ID. The conservative reviewed score accepts either valid representation and does not credit GoalPilot with an advantage on that ambiguity.

All additional actual judging time is added to the corresponding arm. Original caller time, provider tokens and completion lifecycle are unchanged. The original analysis already meets the accepted thresholds; the review does not rescue a failed cost target. The remaining reviewed native failure concerns the explicitly required ticket idempotency contract.

## Acceptance targets and uncertainty

The original target was 30% time reduction and 50% reductions in each of uncached input and output. During development, the user explicitly accepted a five-percentage-point tolerance: **at least 25% time and 45% each of uncached input and output**, while preserving correct closures and old-skill anchor performance. The amendment is retained. Observed uncached input savings are 48.67%, so the original stricter 50% input target was not reached.

All accepted point-estimate targets pass with both original and reviewed scoring. They are not population guarantees. For example, the descriptive paired-bootstrap 95% interval for uncached input savings in the original analysis is approximately **35.95–58.99%**, crossing the 45% target. The completion sample is small; the observed count difference does not establish statistically reliable superiority across unseen tasks.

## Comparison with the previous installed skill

Four predefined anchors compare the new skill with skill 1.1.0 / engine 0.10.0. Both complete **4/4** correctly. The new skill reduces aggregate time by **58.92%** and uncached-input-plus-output tokens by **44.10%**. This is a four-case comparison, not a separate 20-case old-skill study.

## Interrupted attempt and research cost

An external environment restart interrupted one native ticket caller before final outcome and complete usage. Its preserved last-observed usage is a lower bound: **27,639 uncached-input-plus-output tokens**. It is censored from comparative completed attempts, not scored as a cheap native failure. A separately registered continuation retained 23 complete outcomes byte-for-byte and ran one fresh control from the original skeleton before any GoalPilot result for that case. Product, public goals, graders, thresholds and research caps were retained; completed functional failures were not rerun.

Across the development experiments, observed research consumption is **at least 11,686,329 raw tokens** and **1,776,441 uncached-input-plus-output tokens**, deduplicated by caller thread. One interrupted caller's final usage and the root development conversation remain unknown. These are research costs, not an established net saving or demonstrated R&D payback.

## Evidence and reproducibility

| Artifact | What is included |
| :--- | :--- |
| [Original analysis](../reports/skill-131-summary/analysis.json) | All 44 comparative rows, original scores, actual token totals and timing. |
| [Reviewed analysis](../reports/skill-131-summary/analysis-reviewed.json) | Conservative score sensitivity and additional judging time. |
| [Registered protocol](../reports/skill-131-summary/protocol.json) | Fixed cases, controls, thresholds, source hashes and continuation policy. |
| [Counter/contract audit](../reports/skill-131-summary/audit.json) | Retained receipt for 1,503 successful checks. |
| [Review audit](../reports/skill-131-summary/review-audit.json) | Retained receipt for 200 successful review checks. |
| [Persisted-meter audit](../reports/skill-131-summary/rollout-meter-audit.json) | Retained receipt for 44 matching complete provider/CLI counters. |
| [Uncertainty summary](../reports/skill-131-summary/summary-report.json) | Original-score bootstrap intervals and supplementary subsets. |
| [Measured source hashes](../reports/skill-131-summary/measurement.json) | Exact engine and skill-instruction identity, versions and scope. |
| [Research cost summary](../reports/skill-131-summary/research-cost-summary.json) | Deduplicated aggregate lower bounds and unknowns. |

Run `python3 tools/check_benchmark.py` to reconstruct published aggregates from the included rows and verify current source identity. Run `python3 validate.py` for offline technical regressions. These commands do not repeat paid model experiments.

The public repository contains analyses and audit receipts, not the full raw model transcripts, external judge worktrees or development-session journals. Historical receipts retain their original local paths. Aggregate arithmetic can be reproduced from this repository; independent re-auditing of the original provider telemetry requires the retained raw journals and cannot be performed from summaries alone. No fresh paid replication has been run for this public documentation release.

Engine source and skill instructions are unchanged from the measured version. Public documentation, chart/check tooling and repository packaging are publication work; they were not an additional measured treatment.
