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
