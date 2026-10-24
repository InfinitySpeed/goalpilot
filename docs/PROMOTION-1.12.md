# GoalPilot 1.12.0 promotion: adaptive fast path

**Promoted behavior:** use a short direct workflow only for a single, fully specified, self-contained change whose outcomes are already covered by the project's documented full test suite. All ambiguous, multi-step, stateful, external, cross-file, or inadequately tested goals retain the full GoalPilot workflow and its certified closure.

The comparison uses two task families (slug normalization and byte conversion), two fresh runs per arm and family, with the same model (`gpt-6.1-sol`, low), exact task, fixture, and 32 unrelated Markdown files. The independent behavioral judge passed every delivered result. GoalPilot 1.11 is the current control; Codex native uses the same direct task prompts. The provider cache could not be disabled, so raw, cached-input, and uncached usage are shown separately.

| Arm | Mean uncached tokens | Mean elapsed time | Independent completions |
|---|---:|---:|---:|
| GoalPilot 1.11 | 11,908 | 24.98s | 4/4 |
| GoalPilot 1.12 fast path | 6,350 | 16.29s | 4/4; project suite 4/4 |
| Codex native | 9,807 | 20.87s | 4/4 |

On these measured fast-path tasks, GoalPilot 1.12 used **46.7% fewer uncached tokens** and was **34.8% faster** than GoalPilot 1.11. Against Codex native, it used **35.3% fewer uncached tokens** and was **21.9% faster**. These are measured uncached usage and wall time; raw token totals are not used to claim quota savings.

For the separate complex Java fallback guard, the candidate selected full GoalPilot, passed the independent judge and earned a valid GoalPilot closure certificate in **2/2** runs. Mean time was 54.03s and uncached usage 12,851; these fallback figures are not included in fast-path gains.

This is a scoped promotion, not evidence that every prompt benefits. The benchmark has only two synthetic fast-path families and two repetitions per arm. FAST DIRECT intentionally does not issue a GoalPilot certificate: it reports the existing suite run and its result. If the classification is uncertain or the suite does not cover every requested outcome, use full GoalPilot.

Evidence archive: [`../reports/skill-112-evidence.zip`](../reports/skill-112-evidence.zip), SHA-256 `cfe6522a8ee5a19b3a617eeda5393643209d205ca04a575b1a722fa4ce721db7`. Machine-readable results, all run-level rows including the rejected earlier adaptive candidate, cache meters, gates, and limitations: [`../reports/skill-112-adaptive-fast-path-2026-10-24.json`](../reports/skill-112-adaptive-fast-path-2026-10-24.json).
