# Goal criteria evaluation

This page retains historical 0.14/0.15 development measurements. The current default is [Skill 1.8](GENERALIZATION.md), which submits an explicit requirement inventory and criterion map.

The standalone controller engine 0.15.0 implements a frozen inventory of atomic goal requirements mapped to criteria, exact source quotes, check links, and per-requirement plus per-criterion verified/missing/blocked status. Supplied requirement maps with missing or orphaned links are rejected. Handoffs without the new field retain compatibility through a clearly labeled one-to-one criterion projection; that fallback does not claim inventory completeness. At the time of this evaluation, the portable Skill had been restored to instructions1.3.1 / engine 0.12.1 and did not submit that newer inventory schema. An explicit external blocker or failed/unavailable check keeps `goal_complete` false in the standalone controller. The checks run locally and make no model calls.

## Regression measurements

| Measure | Engine 0.14.0 / skill 1.5.0 | Engine 0.15.0 / skill 1.6.0 | Result |
| :--- | ---: | ---: | ---: |
| Offline tests | 288/288 | 291/291 | 3 added; no failures, errors or skips |
| Full suite elapsed time | 42.40 s (288 tests) | 42.52–44.64 s across 5 runs; median 43.41 s (291 tests) | Median is 2.4% above the previous run despite 3 more tests; 22.5% below the 56.04 s historical suite baseline |
| Skill instruction size | 2,376 bytes / 332 words | 2,653 bytes / 358 words | +11.7% bytes / +7.8% words for the inventory and audit protocol |

All full-suite times were measured with Python 3.12.14 using `validate.py`. GoalPilot 0.15.0 passed 291 tests in five runs: 43.4567 s, 43.4130 s, 44.6445 s, 42.5177 s and 42.5200 s (median 43.4130 s). The immediate 0.14.0 report was 42.40 s for 288 tests. The median is 2.4% slower while adding three protocol tests; local runs vary, with the slowest sample 5.3% above the 0.14.0 run. Compared with the historical 56.04 s suite baseline, the median is 22.5% faster. The earlier 0.14.0 run at 42.07 s and first-optimization measurement at 50.91 s are retained as historical results; those are not 0.15.0 measurements. All runs passed with zero failures, errors and skips. This measures local test wall time, not user-task or model-quota savings.

The budget-reporting change was also measured against a same-source control copy with only its reporting code removed. All 288 tests passed in both: control 58.98 s; reporting change 59.38–60.08 s (+0.69% to +1.88%). The subsequent test acceleration reduced the suite to 50.91 s. Small local samples should not be treated as a general speed guarantee.

## Behavior exercised

- Two criteria quoted from a natural-language goal linked to checks and closed at 100% verified coverage.
- A goal with an external blocker remained open even though both frozen project test gates passed.
- Unit checks covered missing assertions, infrastructure timeouts, pending and stale results, invalid source quotes, unknown check IDs and the eight-criterion limit.
- A Stop-hook session with no submitted criteria requested a criteria handoff and created no test-only acceptance.
- Three synthetic extraction cases (onboarding, report speed/output, flaky sync/durability) validated 6/6 exact requirement quotes and mappings. The underspecified onboarding improvement stayed blocked while its regression constraint passed; the other two examples closed with all stated criteria verified. A legacy handoff test confirms pre-1.6 submissions receive a labeled criterion-derived fallback; new skill handoffs require the full inventory. These hand-authored fixtures exercise protocol behavior, not model-extraction accuracy.
- Requirement inventories reject unsupported source quotes, missing criterion links, unknown criteria, and orphan criteria. This verifies mapping integrity, not semantic completeness of an agent's inventory.
- The historical benchmark checker passed against its archived source reference; its performance results do not apply to this release.

These are deterministic local protocol tests, not evidence that an agent always extracts every intended requirement from an ambiguous request. The calling agent still supplies the inventory; exact quotes and complete links cannot prove it did not omit an intent. The host does not expose a comparable subscription-quota measurement here, so total caller tokens and real-world task completion impact remain unmeasured. Exact tokenizer counts are host-specific.

## Current protected-gate optimization

The frozen GoalPilot original-test gate can use the already-measured four-worker
runner only for this repository and only when its report and source fingerprints
match. It passed the current 293-test suite in 21.217 s, compared with 43.953 s
for a same-scope sequential run: 51.7% less local wall time. The independent
`validate.py` and archived benchmark checks also passed; the archived benchmark
still verifies GoalPilot Skill 1.3.1 / engine 0.12.1 at 20/20, 2,151,252 raw
tokens and 1,541.62 s against native Codex at 19/20, 4,716,581 raw tokens and
3,919.08 s. Those archived results do not measure standalone engine 0.15.0.

One live Flowdesk diagnostic for the newer standalone engine did not meet the
no-regression target: direct-first used 296,689 raw tokens and 312.17 s for
26/26 checks, versus the measured old GoalPilot's 238,575 tokens and 285.95 s;
native Codex used 673,953 tokens and 314.58 s on that same mission. The
review/build variant used 344,913 tokens and 363.44 s. This single-mission
sample is not a broad completion benchmark; neither newer variant is promoted
as a model-usage improvement. The protected local test-runner change makes no
model calls and leaves task execution behavior unchanged.

After that diagnostic, a single relevant-file reading instruction was tested in
the direct-first prompt on Flowdesk and Stockroom. Both completed with 26/26
independent assertions. The two-case aggregate used 329,834 raw tokens and
363.68 s, versus 454,622 and 576.68 s for the historical 0.7.0 controls
(-27.45% tokens, -36.91% time); native Codex used 1,480,502 tokens and 675.08 s,
with both artifacts correct but neither goal normally closed. The candidate
closed both. Each arm has one run per case, so the result is a promising measured
gain on these two familiar tasks, not a statistical or general-purpose claim.
The standalone finish flow and portable Skill were not changed by this prompt
experiment. See [the protocol and per-case table](ENGINE-BENCHMARKS.md).
