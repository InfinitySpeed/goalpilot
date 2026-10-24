# GoalPilot

**A skill that helps coding agents finish ambitious goals with explicit, auditable verification.**

GoalPilot preserves the original request, maps it to executable checks, and keeps a clear record when acceptance criteria need refinement after implementation uncovers a missing check. It runs in the current coding-agent session and does not start a second coding model. The default is **Skill 1.14.0 with the frozen service engine 0.16.0**.

[![Offline checks](https://github.com/InfinitySpeed/goalpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/InfinitySpeed/goalpilot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](pyproject.toml)
[![Skill 1.14.0](https://img.shields.io/badge/Skill-1.14.0-0F766E)](https://github.com/InfinitySpeed/goalpilot/releases/latest)
[![Service engine 0.16.0](https://img.shields.io/badge/Engine-0.16.0-334155)](PORTABLE_SKILL.json)

[Install and use](#how-to-use-it) · [How it works](#how-it-works) · [Native comparison and evidence](docs/PROMOTION-1.14.md) · [Supported hosts](docs/HOSTS.md) · [Contributing](CONTRIBUTING.md)

## Measured results

![GoalPilot 1.14 compared with matched Codex native runs for uncached tokens, time, and held-out test pass rate.](docs/assets/native-only-release-1.14.svg)

The benchmark runs the same three upstream coding tasks with Codex native `/goal` and GoalPilot, using the same model, prompts, base commits, and environment. Across eight paired runs, held-out tests passed **21/21 with GoalPilot and 14/21 with Codex native**. GoalPilot certified **7/8** goals while Codex native certified **8/8**.

| Equal-weight mean across three task families | Codex native | GoalPilot 1.14 | Change |
| :--- | ---: | ---: | ---: |
| Held-out tests passed | 14/21 | **21/21** | +7 tests |
| Certified goals | **8/8** | 7/8 | −1 certificate |
| Uncached tokens per task | **33,716** | 35,828 | +6.3% |
| Elapsed seconds per task | **70.9 s** | 165.0 s | +132.7% |

This is a **scoped reliability and auditability promotion**, not an efficiency win: it used more uncached tokens, took longer, and certified fewer goals in this sample. The feature lets an agent amend acceptance checks after a failed verification without losing the original goal, passing evidence, or prior failures; amendment history is SHA-256-checked. The small held-out sample is not a general completion-rate estimate. Provider caching could not be disabled, so raw token totals are descriptive and do not establish subscription-quota savings. See the [full report](docs/PROMOTION-1.14.md), [machine-readable run data](reports/native-only-benchmark-2026-10-24.json), and [complete evidence archive](reports/native-only-evidence-2026-10-24.zip).

## How to use it

These instructions install **Skill 1.14.0 with the frozen engine 0.16.0** in your current coding-agent session.

### 1. Send this to your coding agent

```text
Install GoalPilot from https://github.com/InfinitySpeed/goalpilot for the agent
I am using. Follow INSTALL.md, handle the runtime and skill registration yourself,
and confirm the local doctor check passes. Do not run benchmarks or start another
coding agent. Then tell me how to invoke GoalPilot here.
```

Or install and start your first task in one prompt:

```text
Install GoalPilot from https://github.com/InfinitySpeed/goalpilot if needed,
then use it to achieve this goal: [YOUR COMPLETE GOAL].
Work in this session, preserve existing tests and data, and verify the result
before reporting completion.
```

The agent handles source download, Python runtime setup, host selection and installation. It needs terminal access and normal permission to install user-local files. **Agents installing this repository: read [INSTALL.md](INSTALL.md) and complete the requested setup.** No manual Git or Python management is needed through the bootstrap.

### 2. Give it an objective

| Tool | Ready-to-copy prompt after installation |
| :--- | :--- |
| Codex | `$goalpilot [YOUR COMPLETE GOAL]. Preserve existing behavior and verify before concluding.` |
| Claude Code | `/goalpilot [YOUR COMPLETE GOAL]. Preserve existing behavior and verify before concluding.` |
| Antigravity | `Use the GoalPilot skill to achieve: [YOUR COMPLETE GOAL]. Verify before concluding.` |
| Hermes Agent | `Load the GoalPilot skill and use it to achieve: [YOUR COMPLETE GOAL]. Verify before concluding.` |
| T3 Code | `Use GoalPilot with this session's underlying coding agent to achieve: [YOUR COMPLETE GOAL].` |
| Other coding agents | `Read the installed GoalPilot SKILL.md and follow it for: [YOUR COMPLETE GOAL].` |

Use the full objective, constraints and important workflows. Codex can use optional automatic Stop hooks on POSIX; other adapters use explicit local verification before concluding. T3 Code uses its provider's skill support. For an unknown host, the installer returns an explicit skill path; native automatic discovery is only claimed where documented.

### Optional: install directly

Already have Python 3.11+ and the repository? Run `python install.py`. It defaults to **auto**, chooses the current/discovered host, and verifies the installed command. It does not configure every tool. Use `--host hermes`, `--host claude-code`, etc. to select explicitly, or `--host generic --target <native-skill-directory>/goalpilot` for another tool.

For automatic runtime setup, the shell and PowerShell bootstraps prepare a user-local Python when needed, download source without Git and run the same installer. See [INSTALL.md](INSTALL.md) and [host adapters](docs/HOSTS.md). `--doctor` checks readiness without model calls; `--dry-run` previews destination paths.

Native verification uses the project's own test commands. Five stacks were measured on Codex; other hosts have local installation checks. Compatible Python scaffolds retain the optimized helpers. The optional service_race helper requires POSIX fork. [Scope and limits](docs/GENERALIZATION.md#scope-and-reproduction).


## How it works

```mermaid
flowchart LR
    A[Original goal and initial tests] --> B[Inventory quoted requirements and preserve goal, tests, budgets]
    B --> C[Your coding agent implements and links checks in this session]
    C --> D[Map every requirement to criteria and executable checks]
    D -->|All checks, requirements and criteria pass| E[goal_complete true]
    D -->|Missing or blocked requirement| C
    D -->|Check fails, budget remains| C
    D -->|Unsupported or budget exhausted| F[Goal remains open]
```

- **Trace the goal.** The final receipt reports requirement-to-criterion coverage and per-criterion check evidence. Missing mappings or blocked criteria keep `goal_complete` false.
- **Preserve acceptance.** Initial tests are retained. Original tests and each executed snapshot stay immutable. Explicit pre-green builder revisions retain every failure; accepted tests then freeze.
- **Reduce repeated work.** Compact context, exact-hash helper reuse and optional storage/transport/test helpers avoid repeatedly generating the same infrastructure.
- **Diagnose loops locally.** Hooks observe supported commands and report repeated failures; they do not launch another model or silently retry the task.
- **Verify completion.** Successful verification requires applicable frozen original assertions, the accepted builder suite and mapped checks. Unsupported verification remains open.

Passing tests establishes evidence for listed criteria. The calling agent still has to capture intent in a vague request; quotes and mappings improve the audit trail but cannot prove no requirement was omitted. Read the [architecture and boundaries](docs/ARCHITECTURE.md).

## Compatibility

| Host or project | Current status |
| :--- | :--- |
| Codex CLI | Native skill and optional Stop hooks; recorded Codex benchmark available. |
| Claude Code | Native skill directory; explicit local verification. |
| Antigravity IDE, App and CLI | Installable skill adapter using explicit local verification; no host performance benchmark. |
| Native test commands | Language-independent argv checks; five stacks measured |
| Hermes Agent | Profile-aware native skill directory; explicit local verification. |
| T3 Code | Uses the selected underlying provider; no fictional T3 skill directory. |
| Other coding agents | Generic bundle and custom native directory or explicit-load fallback; discovery depends on the host. |
| Oversized snapshots, missing tools, unsupported environments | Supported closure is not claimed |

The standalone helper-assisted controller has a separate [historical 20-goal study](docs/ENGINE-PROMOTION.md). Its figures exclude any outer agent and must not be used as full-skill figures. The new Codex comparison uses explicit verification; other hosts have no model-performance benchmark.

Optional helpers suit their documented interfaces. `ReplayService` is intended for new pure applications with a compatible storage format; existing formats and external side effects require a different strategy. See [architecture](docs/ARCHITECTURE.md).

## Development

The engine uses the Python standard library. The repository has **388 offline tests** (362 engine tests); all 388 passed on the verified Linux run, with no skips. See [criteria evaluation and regression measurements](docs/CRITERIA_EVALUATION.md).

```bash
python3 validate.py
python3 tools/check_benchmark.py
python3 tools/build_skill.py
```

`dist/goalpilot-skill.zip` contains the current self-contained Codex bundle. The repository's `install.py` derives the other host bundles locally. These commands run local verification and packaging; they do not launch model benchmarks. See [CONTRIBUTING.md](CONTRIBUTING.md) for chart generation and measurement rules.

## License

Free for individuals acting on their own behalf; business use requires a separate paid commercial license. GoalPilot is source-available under the [GoalPilot Personal and Commercial License 1.0](LICENSE). [Examples and commercial licensing](docs/LICENSING.md).
