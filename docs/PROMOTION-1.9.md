# GoalPilot 1.9: broader native verification

Skill **1.9.0**, native adapter **0.2.0**, frozen service engine **0.16.0**.
This is a changed, measured skill with its own promotion, not a relabeling of 1.8.

## What changed

Checks can specify a relative working directory, so separate subprojects use their
own existing commands. Explicit `test_paths` freeze custom test files/directories
from the initial snapshot. Additional Java/.NET naming conventions are recognized.
Original tests remain immutable, and existing 1.8 sessions preserve their original
test-classification semantics when resumed.

Context headers and the file list are bounded; the complete original snapshot
remains available as evidence. An impossible criterion produces `stop_blocked`,
not success. Repeating unchanged successful checks for that blocked scope does
not spend another verification attempt. Failed tests still require repair;
source changes invalidate cached results.

Example criteria for a native monorepo:

```json
{"checks":[{"id":"web","argv":["npm","test"],"cwd":"packages/web"}],"test_paths":["quality"],"criteria":[{"quote":"EXACT PHRASE FROM THE ORIGINAL GOAL","checks":["web"]}]}
```

`cwd` and `test_paths` must stay relative to the repository; paths that escape,
missing working directories and unmatched test paths are rejected. Tests inline
with implementation, unconventional embedded assertions, external dependencies
and external services still require explicit evidence; automatic semantic test
discovery or arbitrary environment compatibility is not claimed.

## Local counterfactuals

The eight-method local suite passes **8/8** for 1.9 and **1/8** for 1.8: seven
new guard/compatibility methods, plus one old-session compatibility method that
both pass. Filename tests use executable sentinels to isolate snapshot behavior;
they are not separate live Java/.NET model benchmarks.

A synthetic tree with 2,500 long-path files returns **1,159,705 bytes** of begin
output under 1.8 and **24,226 bytes** under 1.9: **97.91% smaller output**, with all
2,500 original files captured in both. This is an exact payload-byte comparison,
not a provider-token or quota measurement; host output truncation can affect how
many of those bytes a model actually receives.

The new installed verifier passes **40/40 runtime/profile combinations** across
Python, JavaScript, TypeScript, Bash, SQLite, C, Java and Go on Linux. Five host
profiles do not mean five agent applications were launched. All **55 generated
files match byte-for-byte** between measured and deployed payloads on each profile.

## Whole-caller comparison

| Four goals per arm | Native Codex | GoalPilot 1.8 | GoalPilot 1.9 |
| :--- | ---: | ---: | ---: |
| Independent behavioral checks | 4/4 | 4/4 | 4/4 |
| Certified GoalPilot closure | N/A | 4/4 | 4/4 |
| Raw tokens, including cached input | 374,651 | 288,144 | 241,136 |
| Uncached input + output | 41,723 | 37,648 | 30,704 |
| Caller seconds | 244.50 | 228.03 | 210.78 |

| Savings versus | Raw tokens | Uncached input + output | Caller time |
| :--- | ---: | ---: | ---: |
| Native Codex | 35.64% | 26.41% | 13.79% |
| GoalPilot 1.8 | 16.31% | 18.44% | 7.57% |

Four known developer-authored synthetic tasks: Java interval arithmetic, Python
planner repair, concurrent Go quota limiting and transactional TypeScript storage.
All use Codex / gpt-6.1-sol / low reasoning effort. Java/Python native and 1.8
controls are reused from the frozen prior extension; Go/TypeScript controls and
all 1.9 callers are fresh. Each arm/case has one observation. Python/Java use
180-second caller budgets, Go/TypeScript 240 seconds; matched within each case.
No primary retry or outcome substitution occurred. All selected delivered artifacts
are independently replayed without model calls.

The registered gate requires 4/4 business success, certified closure and verbatim
goals; no aggregate raw/uncached/time regression above 3% versus 1.8; positive
raw and uncached savings versus native, with at most 3% time regression. The
expanded local capabilities must also pass. Every gate passes. Significant speed
gain was not mandatory. Cache states were not controlled; the raw-token and
uncached-token comparisons are reported separately.

These are aggregate results. For example, Python is slower than both controls,
and TypeScript is slightly slower than 1.8. The machine-readable report preserves
every per-task regression. No universal, blind, production, cross-agent, statistical
speed or exact subscription-quota claim is established. The full model caller is
metered, including skill context and verification; one-time installation and
post-caller judging are excluded. Older eight-/twenty-goal percentages do not
transfer to this changed skill.

## Research cost and rejected work

**9 fresh caller invocations: 683,303 raw tokens and 81,831 uncached-input + output
tokens**, including the retired first candidate. Four reused controls were not
charged again. Parent research-conversation usage is unknown. The first candidate
passed its Python business judge but was retired for old-session incompatibility;
its source, result and counters are retained. A TypeScript reference-control
implementation was corrected before any TypeScript caller; both initial failure
and passing reference/stub controls are retained, with judges unchanged.

## Reproduce and inspect

- [All outcomes, gates, source identities and research ledger](../reports/skill-190-2026-10-23.json)
- [Frozen protocols, sources, provider receipts, judges and delivered code](../reports/skill-190-evidence.zip)
- [New verifier matrix](../reports/verifier-portability-190.json)

```bash
python tools/audit_skill190.py reports/skill-190-2026-10-23.json --evidence reports/skill-190-evidence.zip --require-promotion
```

Add `--replay` to execute the trusted archived delivered programs against the
frozen judges. Required study runtimes must be installed. Neither auditing nor
replay launches a model. Hash receipts establish artifact consistency, not signed
provider attestation or tamper-proof evidence against the local owner.

## Versioned default and rollback

`PORTABLE_SKILL.json` schema2 uses **active_native_workflow** for the installed 1.9
default. The schema1 **native_workflow** alias remains the frozen 1.8 proof for
backward-compatible readers and historical audits. Current source checks bind to
the active record, not to old percentages. Installer selection/metadata plumbing
changed after measurement; the five-profile, 55-file parity proof establishes
that the calling agent receives the exact measured payload.

[Skill 1.8 source and assets](https://github.com/InfinitySpeed/goalpilot/releases/tag/skill-v1.8.0)
remain immutable for rollback. `--profile candidate` continues to select the exact
older r2 service control; it is not an alias for current 1.9. Legacy 1.3.1 and the
32 frozen service-engine modules are unchanged.
