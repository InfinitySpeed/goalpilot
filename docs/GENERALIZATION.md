Historical **Skill 1.8** evidence. The current default is [Skill 1.9](PROMOTION-1.9.md); the figures below do not describe the changed release.

# GoalPilot 1.8: native project verification

The default preserves the project's language, interfaces and test framework. One begin command selects unchanged engine 0.16.0/helpers for compatible unimplemented Python JSONL/HTTP scaffolds; other projects use native adapter 0.1.0. Neither route starts a second coding model.

## Whole-caller results

Eight known synthetic development goals across Node.js, Python/pytest, Bash, SQLite and C: ledger, configuration CLI, backup tool, migration, ring buffer, template engine, accounting and ETL.

| Eight attempts per arm | Native Codex | GoalPilot r2 | GoalPilot 1.8 |
| :--- | ---: | ---: | ---: |
| Independent business checks | 8/8 | 8/8 | **8/8** |
| Certified GoalPilot closure | N/A | 2/8 | **8/8** |
| Raw tokens, including cached input | 965,638 | 761,197 | **472,982** |
| Uncached input + output | 141,318 | 100,205 | **87,958** |
| Total caller time, minutes | 14.94 | 11.50 | **8.23** |

**51.02% fewer raw tokens, 37.76% fewer uncached-input + output tokens and 44.92% less caller time versus native Codex**, preserving 8/8 independent business checks.

r2 produced business-correct code on all eight. Its verifier could only certify the two supported services: the six unsupported closures are not business failures. Native has no GoalPilot certification, so independent business checks provide the comparable completion measure.

Matched gpt-6.1-sol/LOW callers use the same permissions and 240-second host deadline. Six native/r2 controls are reused sequentially from the first campaign; two service triples are new. Caller time excludes installation and posthoc judging. All 45callers, including rejected candidates, are retained; all 45independent business replays matched without model calls.

These are development cases, one observation per arm/case, not blind or production proof. Gains are aggregate: the CLI, ledger and template used more uncached+output than native. Across the two services, tokens improved versus r2 but time was 8.6%higher; this small subgroup does not establish a stable speed change. Original r2 remains available. Raw includes cached input; uncached+output is a distinct counter, not an exact subscription-quota or invoice conversion.

## Verification policy

The exact UTF-8 goal, original source/tests, criteria, argv commands and budgets are preserved. Commands run against disposable worktrees using installed project tools. Changed originals receive a separate frozen overlay; unchanged originals plus added tests run once as a union.

Every executed test snapshot is immutable. Before first green, an invalid authored test can receive a specification-based revision with finish --test-revision REASON. Earlier drafts, failures and rationale remain; previous test files cannot be deleted. Original tests, criteria, commands, deadline and verification budget stay fixed. Accepted builder tests freeze after first green; edits/stale source invalidate closure. This revision policy applies to native sessions; the specialized engine keeps its original frozen policy.

A recorded incorrect builder fixture was replayed with identical business code: old policy remained incomplete; new policy closed after one justified revision. Both failed first and retained that snapshot. This local replay used zero models and does not inflate caller savings.

Only goal_complete:true establishes checked completion. Authored tests cannot independently prove every interpretation of a vague request.

## Scope and reproduction

Project test commands are explicit argv lists. Required tools must be installed. Snapshots are bounded to 32 MB / 3000 files / 4 MB per file; dotenv files, auth.json, credentials.json, private-key extensions, caches and dependencies are excluded. Unsupported symlinks/limits fail explicitly. Test/spec/fixture directories and standard test/spec filenames are captured; inline or unconventional tests need separate acceptance. External dependencies, services and environment are not frozen. Unverifiable human-quality claims remain blocked. Host readiness is not a cross-host inference benchmark.

[Per-case counters](../reports/native-generalization-2026-10-23.json) and [complete evidence](https://github.com/InfinitySpeed/goalpilot/releases/download/skill-v1.8.0/goalpilot-generalization-evidence.tar.xz).

```bash
python tools/audit_generalization.py reports/native-generalization-2026-10-23.json --require-promotion
# Download the evidence asset; verify its source, outcomes and provider counters:
python tools/audit_generalization.py reports/native-generalization-2026-10-23.json --evidence goalpilot-generalization-evidence.tar.xz --require-promotion
# Extract it, then run: python replay.py --all
```

Evidence SHA-256: 4fc93681a846f1415b8caf765afe8a8fdff16beb74aec147128a7836d13eb44a

Retained research: 45 caller invocations, 3,759,365 raw and 574,725 uncached+output tokens. Parent research usage is UNKNOWN. The final comparison selects 24 of these callers; every rejected outcome remains archived.

[Historical 20-goal service results](SKILL-EFFICIENCY.md) do not measure this changed skill. Install the exact r2 control with --profile candidate; --profile legacy retains Skill 1.3.1. Normal installation selects 1.8 automatically.
