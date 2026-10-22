# Contributing

Use English for user-facing documentation, issues and pull requests. Keep changes focused and describe observable behavior, compatibility and relevant checks.

## Local verification

Python 3.11+ on a POSIX host is required. The runtime has no third-party dependencies.

```bash
python3 validate.py
python3 tools/check_benchmark.py
python3 tools/build_skill.py
```

The offline suite uses explicit test doubles where model transport is involved. It must not require a Codex account, network access or model calls. Test output is written to `reports/tests.json` and `reports/tests.txt`.

## Charts

Chart generation is optional development tooling and requires Matplotlib, not a runtime dependency:

```bash
python3 -m pip install matplotlib
python3 tools/plot_benchmark.py
```

Charts read the included benchmark rows; do not enter performance numbers by hand. Keep axes at zero, label units, include the workload scope and show both completion score definitions.

## Measurement rules

Preserve original goals, tests, registered criteria and failed outcomes. Count whole-caller setup, reading, corrections and verification. Report uncached input, cached input and output separately. Zero nested calls must never be described as zero total inference cost.

Do not reuse published savings for changed engine or skill instructions. `tools/build_skill.py` marks current-measurement applicability false when their hashes differ. Archived observations remain observations of the recorded version.

New model studies require separate recorded protocols, complete metering, appropriate native controls and independent behavioral judging. A local regression test or scripted wire fixture is not model-performance evidence. Explain unsupported cases, interruptions, unknown usage, scoring amendments and development-case reuse.

Do not commit credentials, account/session files or raw private user conversations. The existing benchmark artifacts are historical evidence; preserve original records and publish explicit supplementary analysis rather than silently rewriting outcomes.
