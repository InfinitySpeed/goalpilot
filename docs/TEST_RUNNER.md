# Faster offline test runs

`python3 validate.py` runs independent test modules in separate Python processes,
using up to four workers (capped by available CPUs and the number of work groups).
Use `python3 validate.py --jobs 1` for serial execution or `--jobs N` to choose a
worker limit. The four modules that share expensive reference preflights remain in
one worker so their in-process cache still avoids duplicate setup. Test output and
counts are collected in deterministic module order; failures and errors still make
the command fail. The report records the worker count and hashes for both the tested
source and runner.

## Measurement

On Python 3.12.14 in the same workspace, the previous sequential runner took
41.5862 seconds for 291/291 passing tests. The parallel runner passed 291/291 on
three runs at 21.4451, 22.0164 and 21.8831 seconds, with four workers each. The
median was 21.8831 seconds, a 47.4% lower wall time than that sequential sample.
The exact runs and runner fingerprints are recorded in
[`reports/test-runner-benchmark.json`](../reports/test-runner-benchmark.json).
There were zero failures, errors, skips and live API calls.

This comparison is one sequential run against three parallel runs on one machine;
it measures local suite wall time, not coding time or model quota. Test modules now
run in separate processes, so their isolation differs from the prior single-process
runner. The full suite passed in the new mode on all three measured runs; projects
can use `--jobs 1` if a local test relies on shared in-process state.

## Protected GoalPilot gate

The frozen original-test gate now selects this four-worker runner only when the
repository is GoalPilot itself and the benchmark report, runner, and source hashes
match the measured artifacts above. All other repositories keep the existing
sequential gate. On the current 293-test suite, the protected gate passed in
21.217 s; a sequential same-scope run passed in 43.953 s, a 51.7% wall-time
reduction (22.736 s saved). A separate `validate.py` run passed 293/293 in
21.199 s. These are local test-runner measurements, not coding-session time,
model tokens, or task-completion evidence.

## Portable adapter matrix

The new engine's five installation profiles run in isolated temporary directories,
subprocess environments and ephemeral localhost ports. Those independent profile
checks now run concurrently inside their test module. The same four test methods
and host assertions passed in a one-run same-SDK comparison: **8.646 s sequentially
versus 3.032 s concurrently, 64.93% less module wall time**. Both runs had zero
failures, errors or skips and made zero model calls. This measures that module,
not a 64.93% improvement to the full suite or coding sessions. The complete
312-test suite passed separately in 25.082 s.

[Machine-readable comparison](../reports/portable-test-matrix-speed.json).

## Reuse-fixture optimization (321 → 320 tests)

The 13 cache tests previously rebuilt the same verified cold result12 times. They now build it once, then restore an untouched private snapshot to the same absolute paths before each scenario. Every test uses a fresh simulated actor and independent restored files. Receipt paths and hashes remain valid; cache invalidation, data preservation, budgets, independent review, corruption and staged verification still execute normally. This is fixture reuse, not caching a test verdict.

The module passed all 13 scenarios in 8.631 s before and 3.895 s after (54.9% less time). A separate counting run measured9.035 s versus4.294 s and confirmed12 →1 cold fixtures and 19 →8 simulated builder executions. Those actors are test doubles, not real model calls.

Three paired full-suite measurements, using the unchanged four-worker runner, were 25.850/25.706/24.924 s before and 23.736/25.468/23.987 s after: **4.30% less aggregate wall time**, or 6.69% comparing the separate medians. All runs passed. The 321 →320 change removes one source-text presence test; actual copied-helper execution is retained and strengthened with a deliberately unusable global GoalPilot package across five host profiles. All13 cache scenarios remain. Five injected cache defects were rejected by the exact same tests before and after; this is a bounded mutation check, not proof of exhaustive coverage.

The original runner and worker remain byte-identical so their frozen-gate recognition is preserved. The engine and promoted skill files are unchanged. No coding-session token, quota or completion improvement is inferred from local test timings. The rejected earlier scheduling/discovery candidate remains documented separately.

[Measurements, fixture counts and mutation results](../reports/test-optimization-2026-10-23.json).

After timing, fixture accounting was strengthened to retain the cold actor's actual call count instead of assigning 1. An injected extra cold call is rejected by both the original tests and the final tests; the preliminary shared-fixture version missed it and was corrected before publication. The final suite passed 320/320 in 24.712 s. All five original cache mutants were rerun against that final version and rejected by the same tests.

GoalPilot's short final-accounting subtask exhausted the remaining shared deadline during its second frozen suite and remains unclosed in the evidence. The final full suite and defect checks were subsequently completed independently; that timeout was not erased or relabelled as a successful GoalPilot closure.
