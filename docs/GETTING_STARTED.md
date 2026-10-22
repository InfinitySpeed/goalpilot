# Getting started

## Requirements

- Python 3.11 or later and a POSIX host. Linux/Python 3.12.14 was used in the benchmark; native Windows is not a supported target.
- Codex CLI installed and authenticated. The tested CLI version is 0.163.0.
- A bounded Python project with discoverable, compatible `unittest` tests for supported closure.

The engine has no third-party runtime dependencies. Codex supplies the calling model; GoalPilot does not require a separate hosted backend.

## Install the skill and hooks

```bash
git clone https://github.com/InfinitySpeed/goalpilot.git
cd goalpilot
python3 skills/goalpilot/scripts/install.py
python3 ~/.agents/skills/goalpilot/scripts/goalpilot.py hook-config install
```

The first command installs the self-contained bundle into `~/.agents/skills/goalpilot`. The installer validates the manifest and refuses to replace an unrelated skill.

The second command installs the three local Codex hooks and verifies trust for their exact command definitions. It preserves unrelated handlers rather than broadly trusting hooks. Configuration uses no inference. Hooks and tests execute local commands with the calling process's permissions: review commands from untrusted projects before running them.

Restart Codex if the skill is not immediately listed. In Codex, use:

```text
$goalpilot Implement the complete goal below, preserve the existing API and data,
and verify all important workflows before closing it: ...
```

Include the desired user outcome, existing behavior to preserve, constraints and important edge cases. A vague goal still needs concrete acceptance decisions; the verifier cannot discover every implicit expectation.

## What happens during a goal

The skill saves the full original request, captures the original tests and records the deadline and verification limits. Coding happens in the current Codex session. When the session stops, supported hooks run local acceptance checks. On failure, repair continues in that same session with the same acceptance and remaining budget.

`scope_passed` together with `closed: true` means supported frozen checks passed. An unsupported environment, infrastructure error or exhausted budget leaves the goal open. It is not counted as successful completion.

## Manual local protocol

For a compatible project when automatic hooks are unavailable, run the following from the cloned GoalPilot directory. Create the goal file first. The run directory must be new and outside the target repository.

```bash
python3 -m goalpilot session start \
  --goal-file /tmp/my-goal.txt \
  --repo /absolute/path/to/project \
  --run-dir /tmp/goalpilot-my-goal-001 \
  --helpers --context

# Implement the complete goal and meaningful tests in the calling session.

python3 -m goalpilot session finish /tmp/goalpilot-my-goal-001
python3 -m goalpilot session status /tmp/goalpilot-my-goal-001
```

If a helper filename collides with existing source, repeat the same start without `--helpers`; the existing file must not be overwritten. On verification failure, repair the implementation, preserve the run and frozen acceptance, then run `finish` again. Do not reset the goal to refresh its budget. If `completion_owner=codex_stop_hook` is reported, let the hook own final verification instead of duplicating it manually.

Manual operation has not been assigned the measured automatic-hook performance figures. See the bundled [protocol reference](../skills/goalpilot/references/session.md) for explicit handoff checks, deadlines and repair semantics.

## Troubleshooting

| Symptom | Action |
| :--- | :--- |
| Skill missing in Codex | Confirm installation, then restart or reload skill discovery. |
| Hook setup fails | Check CLI compatibility and the exact configuration error. Do not enable a blanket trust bypass. Use the manual protocol where supported. |
| Verification says unsupported | Inspect test discovery, capture limits and excluded inputs. Successful shell execution alone does not establish closure. |
| Tests fail | Repair the implementation within the existing run and frozen acceptance. |
| Budget exhausted | Keep the original run as open/exhausted evidence; a new task is a separate attempt, not a free reset. |

The historical `go` and `continue` controller commands can launch additional coding/review model sessions when explicitly used. They are distinct from the default in-session skill and its zero-model passive monitor.
