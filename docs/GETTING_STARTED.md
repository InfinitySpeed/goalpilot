# Getting started

The simplest route is to ask your coding agent to install GoalPilot from the GitHub URL. Copy the [installation and task prompts](../README.md#how-to-use-it). The agent follows [INSTALL.md](../INSTALL.md), handles dependencies and verifies the installed local command.

## Requirements

Your agent must be able to read skill instructions, write user-local files and run commands under its normal permissions. The bootstraps can prepare Python and download source without Git; missing dependencies need network access. No separate model account, GoalPilot service or API key is needed.

The local verifier supports bounded compatible Python unittest projects with initial tests on Linux, macOS and Windows. The optional `service_race` helper requires POSIX fork. Native registration depends on the host; a generic bundle can be read explicitly where automatic skill discovery is unavailable.

## Installation and diagnosis

Use [INSTALL.md](../INSTALL.md) for shell and PowerShell bootstraps, or run `python install.py` from an existing checkout/Python environment. Selection defaults to the active or uniquely discovered host. Ambiguous cases return a generic skill path rather than modifying every tool.

Use `--doctor` to validate installed files and the recorded runtime, and `--dry-run` to preview paths. Use `--host` to select a known tool or `--target` for a documented custom location. [Host details and examples](HOSTS.md).

## Using the skill

In Codex use `$goalpilot <complete goal>`, in Claude Code `/goalpilot <complete goal>`, and in Antigravity/Hermes ask the agent to load and use GoalPilot for the goal. T3 Code uses its underlying provider's integration. For another tool, have the agent read the installed `SKILL.md` from the returned path.

Include the desired outcome, constraints and behavior/data to preserve. The skill saves the complete request, captures original tests and records deadlines and verification limits. Work happens in the calling agent session. The agent calls local verification before concluding; configured Codex Stop hooks can do this automatically on POSIX.

A success requires `scope_passed` and `closed:true`. Failures, unsupported checks, infrastructure restrictions and exhausted budgets stay open. Repair retains the same run, acceptance, tests and budget; do not reset evidence to claim completion.

## Optional Codex Stop hooks

On a compatible POSIX Codex installation:

```bash
python3 ~/.agents/skills/goalpilot/scripts/goalpilot.py hook-config install
```

This verifies trust in exact local hook commands and preserves unrelated handlers. It is optional and is not used by the other hosts or the Windows portable path. Tests execute commands with the caller's permissions; review commands in untrusted projects.

Legacy `go`/`continue` controller commands can launch additional model sessions when explicitly used. They are not the default in-session skill path. Historical performance figures apply only to the recorded Codex automatic-hook benchmark, not every installation mode or current host.
