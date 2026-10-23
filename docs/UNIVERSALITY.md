Historical **Skill 1.8** evidence. The current default is [Skill 1.11](PROMOTION-1.11.md); the figures below do not describe the changed release.

# Portability and the limits of performance claims

GoalPilot 1.8 uses project-native executable checks. The verification protocol is
independent of a particular programming language or model API. That makes it
portable; it does not establish identical efficiency in every coding agent.

Three different questions require different evidence:

| Question | Evidence needed | Current evidence |
| :--- | :--- | :--- |
| Can this agent load the skill? | Documented discovery path and actual agent invocation | Documented adapters; live model measurements on Codex only |
| Can the installed verifier run this project's checks correctly? | Execute passing and failing native programs; preserve failures and invalidate stale results | Reproducible runtime/profile matrix below |
| Does this agent finish more work with fewer tokens and less time? | Matched whole-caller trials and independent behavioral judging | [Eight-goal study](GENERALIZATION.md); additional trials must be reported separately |

Host-profile checks execute the generated installed verifier. They **do not launch
Claude Code, Antigravity or Hermes**, and do not prove automatic skill discovery in
those applications. T3 Code uses its underlying provider and is not a separate
model-performance category. An unknown tool can explicitly load the skill only
if it can read local files and execute the required commands.

## Reproduce verifier compatibility

```bash
python tools/check_portability.py --output portability.json
```

This performs no model calls. It installs into temporary isolated destinations,
then exercises Python, JavaScript, TypeScript, Bash, SQLite, C, Java and Go when their runtimes
are available, through five host profiles. Every supported combination must:

- Reject an incorrect program's behavior, rather than accepting compilation alone.
- Verify the correct repair while retaining the failed attempt and original test.
- Preserve the original Unicode goal byte for byte.
- Reuse unchanged successful verification without spending another attempt.
- Invalidate completion after the program changes.
- Report zero verifier model calls.

Missing or incompatible runtimes appear as `unsupported`, never as passes.
`--require-all` also fails when any requested combination is unsupported. For
example, an executable called `go` can be the Go board game rather than the Go
compiler; the tool checks the runtime before making a compatibility claim.
The [local report](../reports/verifier-portability-2026-10-23.json) records **40/40**
combinations passing on Linux: eight runtimes through five host profiles. The
[CI workflow](../.github/workflows/ci.yml) retains its own matrix report.

These are small compatibility probes, not ambitious coding tasks or evidence of
token savings. The original [runtime and host limitations](HOSTS.md) still apply,
including bounded repository snapshots, unsupported source symlinks and externally
managed project dependencies. The source and workflow of the promoted skill stay
unchanged while these additional checks are introduced.

## Why “equally performant everywhere” is not a supported claim

A finite benchmark cannot establish this for every request, repository, machine,
model, permission configuration and tool version. Small tasks can cost more when
verification overhead exceeds the work saved. External services or absent
credentials can prevent verification. A project command can itself have incomplete
tests. The skill's criteria do not prove a user's unstated intent.

An aggregate saving also does not imply savings on every individual task. The
eight-goal study already contains individual tasks with higher uncached-token
usage than native Codex. Those observations remain part of the evidence.

The actionable target is **measured portability across an explicit matrix, with
per-task regressions visible and no completion claim without evidence**. A new
study or adapter must identify its own scope; it cannot inherit percentages from
a different host or workload.

## Additional live comparison

This is a prospective extension of the **unchanged Skill 1.8.0**, not a new engine
promotion. Four new synthetic tasks cover Java interval arithmetic, a JavaScript
async worker pool, Python dependency-planner repair and a C byte-run codec.
Contracts and judges were frozen before the first caller invocation. Each arm ran
once per task, without retries or replacement of bad outcomes. The judges were
not supplied to the callers; positive-reference and negative-stub controls are
retained. This is developer-authored evidence, not an external blind evaluation.

All twelve calls use Codex, `gpt-6.1-sol`, low reasoning effort, the same permissions
and a 180-second caller deadline. Invocation order is recorded in the protocol.
The previous verifier cannot certify three tasks in this series; their independently
correct business code still counts as successful. Closure certification is separate.

| Four tasks per arm | Native Codex | Previous GoalPilot r2 | GoalPilot 1.8 |
| :--- | ---: | ---: | ---: |
| Independent behavioral checks | 4/4 | 4/4 | 4/4 |
| Certified GoalPilot closure | N/A | 1/4 | 4/4 |
| Raw tokens, including cached input | 329,116 | 383,212 | 233,073 |
| Uncached input + output | 43,420 | 37,996 | 36,465 |
| Caller seconds | 266.24 | 242.39 | 225.58 |

Skill 1.8 savings on this series:

| Compared with | Raw tokens | Uncached input + output | Caller time |
| :--- | ---: | ---: | ---: |
| Native Codex | 29.18% | 16.02% | 15.27% |
| Previous GoalPilot r2 | 39.18% | 4.03% | 6.94% |

These aggregate savings **do not hold on every task**. Negative values below mean
GoalPilot used more tokens or time than native Codex on that task:

| Task | Raw-token saving | Uncached-token saving | Time saving |
| :--- | ---: | ---: | ---: |
| java-ranges | +6.02% | -22.08% | +12.99% |
| node-pool | +38.65% | +44.27% | +30.37% |
| python-repair | +18.15% | -30.94% | -17.93% |
| c-codec | +48.03% | +40.21% | +16.88% |

The audit records regressions against previous GoalPilot as well. For example,
JavaScript uses slightly more uncached tokens than r2, and Java is 3.08% slower
than r2 in this one observation. All business outputs still pass. A favorable
aggregate must not conceal these differences.

**Limits:** one observation per arm and task, Linux, known developer-authored
contracts. Local offline probes and toolchain setup also ran during some early
Java trials, so time results are exploratory; no statistical speed claim is made.
One-time installation and post-caller judging are excluded. The entire model
caller is metered, including skill context and verification. Cached input is
included in raw tokens and is also separated out. Exact subscription-quota or
monetary savings are not established. These totals are separate from the earlier
eight-goal study and the historical twenty-service benchmark.

The campaign used **945,401 raw tokens / 117,881 uncached-input + output tokens**
across twelve measured invocations. Parent research-conversation usage is unknown.
No failed outcomes or discarded retries are omitted.

- [All outcomes, gates and source/evidence hashes](../reports/portability-extension-2026-10-23.json)
- [Frozen protocols, judges, provider usage receipts and delivered code](../reports/portability-extension-2026-10-23.zip)
- [Installed-verifier runtime report](../reports/verifier-portability-2026-10-23.json)

Recompute the report and verify provider counters without model calls:

```bash
python tools/audit_portability_extension.py reports/portability-extension-2026-10-23.json --evidence reports/portability-extension-2026-10-23.zip
```

Add `--replay` to execute the trusted archived delivered programs against the
frozen judges locally (requires the study's runtimes). `--require-improvement`
checks aggregate completion, token and time gates. `--require-per-case` additionally
requires no observed per-task regressions and **fails for this evidence**. No flag
can establish the unbounded claim of equal performance everywhere.
