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
