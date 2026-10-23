# Measurements

The current complete-skill report is [Skill 1.7.0 / engine 0.16.0](docs/PORTABLE-ENGINE.md#measured-results). It includes the fresh20-goal old/new comparison, historical native/old/standalone controls, provider counters, completion definitions, research costs and limitations.

Recompute all current promotion gates without model calls:

```bash
python3 tools/audit_portable_invocation.py reports/portable-skill-170-2026-10-23.zip --require-promotion
```

Separate historical reports remain available:

- [Skill 1.3.1 / engine 0.12.1](docs/BENCHMARKS.md): complete-caller observations and original/reviewed grading. Recompute with `python3 tools/check_benchmark.py`.
- [Standalone engine 0.16.0](docs/ENGINE-PROMOTION.md): a narrower controller profile. Recompute with `python3 tools/audit_promoted_release.py`.

These profiles have different measurement boundaries. Do not substitute standalone results for complete-skill results or convert provider tokens directly to subscription-quota percentages.
