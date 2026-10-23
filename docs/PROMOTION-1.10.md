# GoalPilot 1.10: raw-token target promotion

GoalPilot **1.10.0**, native adapter **0.3.0**, frozen service engine **0.16.0**.
This promotion targets an aggregate near **200,000 raw provider tokens** on the
same four synthetic coding goals used by the audited 1.9 comparison.

## Results

| Four goals per arm | Native Codex | GoalPilot 1.9 | GoalPilot 1.10 |
| :--- | ---: | ---: | ---: |
| Independent behavioral checks | 4/4 | 4/4 | 4/4 |
| Certified GoalPilot closure | N/A | 4/4 | 4/4 |
| Raw tokens, including cached input | 374,651 | 241,136 | **209,047** |
| Uncached input + output | 41,723 | 30,704 | **34,455** |
| Caller seconds | 244.50 | 210.78 | **192.91** |

The observed raw count is **4.52% above 200,000**, within the preregistered
190,000–210,000 band. It is **13.31% below 1.9** and **44.20% below native**.
Elapsed time is **8.48% lower than 1.9** and **21.10% lower than native**.

The uncached-input-plus-output count is **12.22% higher than 1.9** (and 17.42%
lower than native). This is an aggregate regression, and TypeScript also regresses
against 1.9 on raw and uncached counts. Cached input fell from 210,432 to 174,592;
cache state was not controlled. Therefore these observations establish the raw
count target for this run, not lower subscription quota or a generalized token
saving. The promotion is specifically for the requested raw-token target; it does
not pass a no-regression gate for uncached tokens.

| Case | Raw tokens | Uncached + output | Seconds | Status |
| :--- | ---: | ---: | ---: | :--- |
| Python planner repair | 50,002 | 5,714 | 44.01 | Correct, certified, preserved |
| Java interval arithmetic | 57,354 | 10,762 | 50.49 | Correct, certified, preserved |
| Go quota limiter | 50,484 | 6,068 | 45.46 | Correct, certified, preserved |
| TypeScript transactional store | 51,207 | 11,911 | 52.96 | Correct, certified, preserved |

## What changed

The native begin protocol is shorter and directs the agent to use the project's
documented full check runner, avoiding assumptions that standalone compiler
commands are on `PATH`. The routed skill carries the same instruction. This
addresses an observed Java waste: 1.9 spent a full generation trying `javac`
although the repository documented a Python test runner. The Java candidate used
20.0% fewer raw tokens and 6.26% more uncached tokens than 1.9. Go used 26.0% fewer
raw tokens; the exact cause of its prior extra generation is not established.

## Method and limits

Four fixed developer-authored synthetic goals, one fresh 1.10 caller each, using
Codex / gpt-6.1-sol / low effort. Native and 1.9 controls are reused from the
source-bound 1.9 report; they were not rerun. Provider whole-caller counters
include skill context and verification. Four business judges and GoalPilot closure
receipts passed. This is a single small series, not a blind or statistical study,
production evidence, cross-host live evidence, or an exact account-quota measure.

## Reproduce

```bash
python tools/audit_skill110.py reports/skill-110-2026-10-23.json \
  --evidence reports/skill-110-evidence.zip --require-promotion
```

The audit checks source identities, provider receipts, reused controls, target
window, completion and evidence hashes. The ZIP contains frozen source, the
protocol, selected caller receipts and delivered repositories, plus the original
1.9 report and evidence. The historical 1.9 report and audit remain available.
