# GoalPilot 1.12.0: matched results against Codex native

GoalPilot 1.12 adds a narrow **FAST DIRECT** route for a single, fully specified, self-contained change when the project’s documented full test suite already covers every requested outcome. Ambiguous, multi-step, stateful, external, cross-file, or under-tested goals continue through the full GoalPilot workflow. FAST DIRECT runs the project suite and reports its result; it does not issue a GoalPilot completion certificate.

## Comparison

This release comparison uses **Codex native `/goal` only** as its control. The same two task families (slug normalization and byte conversion), exact task prompts, fixtures, model (`gpt-6.1-sol`, low), and 32 unrelated Markdown files were used. Each arm ran twice per task family. An independent behavioral judge evaluated each result. The provider cache could not be disabled, so uncached tokens and wall time are shown; raw token counts are not interpreted as subscription-quota savings.

| Equal-weight mean across the two task families | Codex native | GoalPilot 1.12 fast path |
| :--- | ---: | ---: |
| Uncached tokens | 9,807 | **6,350** |
| Elapsed time | 20.87 s | **16.29 s** |
| Independent checks passed | 4/4 | **4/4** |
| Project suite passed | — | **4/4** |

On this limited set, GoalPilot used **35.3% fewer uncached tokens** and took **21.9% less time** than Codex native. The Java full-workflow fallback passed the independent judge and earned a valid GoalPilot certificate in **2/2** runs; its mean was 54.03 s and 12,851 uncached tokens, excluded from the fast-path averages.

## Limits and evidence

This result covers only two synthetic task families with two fresh runs each. It does not show that vague, large, stateful, or cross-file goals will be faster or cheaper. The FAST DIRECT route is deliberately limited to goals whose requested outcomes are already covered by the documented suite; otherwise GoalPilot uses the full workflow. Cache state was uncontrolled. No quota-saving claim is inferred from raw tokens.

The immutable [evidence archive](../reports/skill-112-evidence.zip) retains complete run records from the original experiment for auditability. The public release comparison in this report uses Codex native only. Machine-readable source data remains at [skill-112-adaptive-fast-path-2026-10-24.json](../reports/skill-112-adaptive-fast-path-2026-10-24.json).
