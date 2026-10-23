# Getting started

The default is **Skill 1.8: native verification plus service engine 0.16.0**, working inside your coding-agent session. [Whole-skill results and limitations](GENERALIZATION.md). The standalone controller remains an optional separate profile.

The simplest route is to ask your coding agent to install GoalPilot from the GitHub URL. Copy the [installation and task prompts](../README.md#how-to-use-it). The agent follows [INSTALL.md](../INSTALL.md), handles dependencies and verifies the installed local command.

## Requirements

Your agent must be able to read skill instructions, write user-local files and run commands under its normal permissions. The bootstraps can prepare Python and download source without Git; missing dependencies need network access. No separate model account, GoalPilot service or API key is needed.

The verifier uses project-native commands; five stacks were measured on Codex. See the study for snapshot/test-layout limits. The optional `service_race` helper requires POSIX fork. Native registration depends on the host; a generic bundle can be read explicitly where automatic skill discovery is unavailable.

## Installation and diagnosis

Use [INSTALL.md](../INSTALL.md) for shell and PowerShell bootstraps, or run `python install.py` from an existing checkout/Python environment. Selection defaults to the active or uniquely discovered host. Ambiguous cases return a generic skill path rather than modifying every tool.

Use `--doctor` to validate installed files and the recorded runtime, and `--dry-run` to preview paths. Use `--host` to select a known tool or `--target` for a documented custom location. [Host details and examples](HOSTS.md).

## Using the skill

In Codex use `$goalpilot <complete goal>`, in Claude Code `/goalpilot <complete goal>`, and in Antigravity/Hermes ask the agent to load and use GoalPilot for the goal. T3 Code uses its underlying provider's integration. For another tool, have the agent read the installed `SKILL.md` from the returned path.

Include the desired outcome, constraints and behavior/data to preserve. Before coding, GoalPilot's skill inventories each atomic requirement, including negative constraints, then maps every requirement to observable criteria. For vague quality words, it inspects the project for a defensible measurable proxy or leaves that requirement blocked. Quotes are checked against the original request; each criterion links to executable checks. The original request and tests remain frozen. Work happens in the calling agent session.

The agent submits this requirement-to-criterion-to-check map before finishing. A configured Codex Stop hook verifies it automatically on POSIX; other hosts use explicit local verification. A goal is complete only when `goal_complete:true`: every inventoried requirement, criterion and frozen test passed. New-format handoffs require mapped requirements and criteria; older handoffs get a labeled criterion-only compatibility projection. Missing behavior, blockers, unsupported checks and exhausted budgets stay open. Repair retains the same goal, criteria, commands, original tests and budget. Native authored drafts may receive explicit pre-green revisions; every version/failure remains and accepted tests then freeze. The map makes omissions easier to detect but cannot prove the agent's inventory captured all implicit intent.

## Optional Codex Stop hooks

For a new compatible POSIX Codex terminal session, use the installed `scripts/codex_launch.py` helper. Run it with `--audit-only` first to verify effective hook configuration without model calls; then launch with `-- --cd /path/to/project`. It isolates only exact trusted GoalPilot duplicates for that process, preserves unrelated policies and leaves global settings unchanged. See [completion modes and commands](PORTABLE-ENGINE.md#completion-modes).

An already running session with no matching hook beacon uses explicit local verification. Other hosts and Windows always use that fallback. Neither mode launches a second coding model. Performance figures apply only to their recorded profile; the new generalization study uses explicit verification.
