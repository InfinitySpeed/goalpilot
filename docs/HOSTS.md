# Coding-agent compatibility

GoalPilot is a skill for coding agents, not a separate model. One local verifier is delivered through native skill folders where documented, with an explicit-load fallback elsewhere.

## Automatic installation

Send your agent the repository URL and the installation prompt in [the README](../README.md#how-to-use-it). [INSTALL.md](../INSTALL.md) tells the agent to select its host, prepare the runtime and confirm readiness. The user does not need to install Python or Git manually.

`install.py` defaults to `--host auto`. Explicit `GOALPILOT_HOST` and recognized session hints take precedence, then a single discovered host. Ambiguous discovery returns a generic installation and its explicit skill path; it does not configure every tool. An agent that knows its identity should choose it explicitly.

## Native paths and prompts

| Host | Default destination | Prompt after installation |
| :--- | :--- | :--- |
| Codex | `~/.agents/skills/goalpilot/` | `$goalpilot [goal]` |
| Claude Code | `~/.claude/skills/goalpilot/` | `/goalpilot [goal]` |
| Antigravity IDE / App | `~/.gemini/config/skills/goalpilot/` | `Use GoalPilot to achieve: [goal]` |
| Antigravity CLI | `~/.gemini/antigravity-cli/skills/goalpilot/` | `/goalpilot [goal]` |
| Hermes Agent | `$HERMES_HOME/skills/goalpilot/`, otherwise the default Hermes home | `Load GoalPilot and use it to achieve: [goal]` |
| T3 Code | The underlying provider's native skill folder | `Use GoalPilot with this session's agent to achieve: [goal]` |
| Other tools | Custom `--target`, or GoalPilot's own user-data skill directory | Read the returned `skill_file` and ask the agent to follow it. |

Antigravity installs its IDE/App and CLI locations. Hermes respects `HERMES_HOME`; its default is `~/.hermes` on POSIX and `%LOCALAPPDATA%/hermes` on Windows. For a different active Hermes profile, pass its actual skill directory with `--target` rather than guessing. T3 Code is a control surface; it does not require a separate fictional skills directory.

Generic installation defaults to `~/.local/share/goalpilot/skills/goalpilot` on POSIX (respecting `XDG_DATA_HOME`) and `%LOCALAPPDATA%/GoalPilot/skills/goalpilot` on Windows. This does not overwrite a native Codex installation or claim automatic discovery by every unknown host. Agents without file-reading and command-execution capabilities cannot run the local verifier.

## Direct commands

With an existing Python3.11+ and checkout:

```bash
python install.py                         # auto-select and verify
python install.py --host hermes
python install.py --host t3-code --provider claude-code
python install.py --host generic --target /path/to/native/skills/goalpilot
python install.py --host auto --dry-run
python install.py --host hermes --doctor
```

`--host all` is an explicit opt-in for all named native hosts. Existing unrelated skills and symlink destinations are refused. Each replacement is staged and hash-validated; goals and evidence outside the bundle are not reset. Installation does not modify host trust, permissions or settings.

## Runtime and Windows

The bootstraps reuse Python3.11+ or prepare a user-local Python through uv. The installed skill records the interpreter in `RUNTIME.json`, so the agent does not rely on a user-managed `python3` command or PATH edits. Missing dependency/source downloads need network access; existing-runtime installations work offline.

The default Skill1.7.0 embeds engine0.16.0 and maps frozen goal requirements to verified criteria, exact source quotes and executable checks. It uses the current calling session. Local Python unittest verification is available on Linux, macOS and Windows. Optional `service_race` still requires POSIX fork and is not a Windows feature. Restricted runners that cannot create the required process job fail verification rather than silently claiming success.

Codex on POSIX can use its optional native Stop hooks. Windows and portable adapters call verification explicitly in the current agent session. They do not install Codex hooks or launch a separate model. Other test frameworks and blanket compatibility with every agent remain outside the supported verified scope.

## Performance scope

The promoted default is Skill1.7.0 / engine0.16.0. Its [complete-caller comparison](PORTABLE-ENGINE.md#measured-results) benchmarks Codex POSIX with native Stop hooks. Other hosts and explicit fallback have offline installation/verification coverage, not model-performance evidence. Archived Skill1.3.1 source and figures remain separately reproducible. Do not transfer percentages across hosts, profiles or workloads.

## Sources

Host registration choices were checked against official sources on October22,2026:

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Antigravity skills](https://antigravity.google/docs/skills/)
- [Hermes skills implementation](https://github.com/NousResearch/hermes-agent/blob/main/tools/skills_tool.py) and [runtime home implementation](https://github.com/NousResearch/hermes-agent/blob/main/hermes_constants.py)
- [T3 Code provider model](https://github.com/pingdotgg/t3code#readme)
- [uv managed Python](https://docs.astral.sh/uv/guides/install-python/)
