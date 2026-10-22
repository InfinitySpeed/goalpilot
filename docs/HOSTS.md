# Host adapters

One Python engine, the shared `SKILL.md` format, and a local installer for **Codex, Claude Code and Antigravity**. Installation copies a self-contained bundle; it makes no network requests, starts no models and changes no agent settings.

## Install

From the cloned repository:

```bash
# All supported hosts, user-wide:
python3 install.py --host all

# Or choose one:
python3 install.py --host codex
python3 install.py --host claude-code
python3 install.py --host antigravity
```

Default installation targets:

| Host | User-wide skill directory | How to invoke |
| :--- | :--- | :--- |
| Codex | `~/.agents/skills/goalpilot/` | `$goalpilot <goal>` |
| Claude Code | `~/.claude/skills/goalpilot/` | `/goalpilot <goal>` |
| Antigravity IDE / App | `~/.gemini/config/skills/goalpilot/` | Ask the agent to use GoalPilot; inspect the IDE's Customizations/skills menu. |
| Antigravity CLI | `~/.gemini/antigravity-cli/skills/goalpilot/` | `/goalpilot <goal>` |

`--host antigravity` installs both the IDE/App and CLI locations. Reload skill discovery or restart the selected tool if needed. Terminal execution permissions remain under the host's normal control; the installer does not change trust or approval settings.

## Custom locations

```bash
python3 install.py --host claude-code \
  --target /absolute/path/to/project/.claude/skills/goalpilot
```

Use `--target` for an explicit host-compatible location. For simultaneous use across all three tools, the default user-wide installation keeps host-specific entries separate and avoids duplicate workspace skill names. Host project-skill discovery and precedence rules vary; do not install conflicting entries with the same name in multiple discovery directories.

To preview destinations without writing files:

```bash
python3 install.py --host all --dry-run
```

For an older Antigravity IDE using its legacy global directory, or another custom installation location:

```bash
python3 install.py --host antigravity \
  --target ~/.gemini/antigravity/skills/goalpilot
```

`--target` requires a single host and specifies the complete skill directory, including `goalpilot`. Existing unrelated skills and symlink destinations are refused. Each bundle replacement is staged, hash-validated and installed atomically; existing local GoalPilot runs outside the bundle are not reset.

## Completion behavior

**Codex:** its existing instructions and engine are preserved. By default the skill calls `session finish` explicitly. Optional native Stop hooks can take ownership of final verification:

```bash
python3 ~/.agents/skills/goalpilot/scripts/goalpilot.py hook-config install
```

**Claude Code and Antigravity:** the portable adapter tells the calling agent to run `session finish` before concluding, inspect the result, repair failures in the same session and retain the same goal, tests, deadline and remaining budget. No host-specific Stop hook is assumed or installed. This works through the tool's terminal execution capability and requires no Codex executable, Codex login or GoalPilot service.

The portable launcher clears an inherited Codex thread identifier in its own process so that another host cannot accidentally bind to a parent Codex session. It exposes only local `session` commands and uses the same bundled engine. The adapters do not intercept a host that ignores the skill or stops before executing its instructions. Closure requires `scope_passed` and `closed:true` from the verifier.

## Requirements and measured scope

Agent portability does not change the engine's project/OS scope: Python 3.11+, POSIX, bounded compatible Python `unittest` projects and initial tests. Native Windows support and arbitrary test-framework support are separate work.

The portable adapter version is **1.0.0**. The base Codex skill remains **1.3.1** and the engine remains **0.12.1**. Local installation and verifier-command checks were performed; no end-to-end agent runs or model benchmarks were run for these new adapters. Published time/token/completion figures describe the recorded Codex automatic-hook integration only. Portable bundle metadata explicitly marks its host performance as unmeasured.

## Host documentation

Installation formats and paths were checked against the official documentation on October 22, 2026:

- [Claude Code skills](https://code.claude.com/docs/en/skills): personal and project skill directories, slash-command invocation and bundled scripts.
- [Antigravity skills](https://antigravity.google/docs/skills/): IDE/App/CLI locations, `SKILL.md`, CLI slash-command conversion and legacy `.agent/skills` compatibility.
- [Codex skills](https://developers.openai.com/codex/skills/): skill format and discovery. The existing Codex bundle and integration are retained.
