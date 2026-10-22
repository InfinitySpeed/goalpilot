# Agent installation instructions

If your user shared this repository **to install or use GoalPilot**, handle the setup yourself. Do not make the user clone a repository, install Python, choose internal paths or copy commands between tools. Use normal host permissions; do not bypass approval policies.

## 1. Identify the current agent

Use the identity of the tool you are running in, rather than assuming the user wants every installed tool configured:

| Context | Installer selection |
| :--- | :--- |
| Codex | `--host codex` |
| Claude Code | `--host claude-code` |
| Antigravity | `--host antigravity` |
| Hermes Agent | `--host hermes`; preserve `HERMES_HOME`, or provide the actual profile's skills directory with `--target`. |
| T3 Code | `--host t3-code --provider <underlying-agent>`; T3 uses its provider's skills, not an invented T3 directory. |
| Another agent | Confirm its supported skill format and native directory, then use `--host generic --target <native-directory>/goalpilot`. |

If the tool identity is unavailable, `--host auto` checks session hints and existing tool locations. When discovery is ambiguous it installs a generic entry and reports the explicit `SKILL.md` path. Do not claim native automatic discovery for an unknown host. Read that file in the current session if the host permits, or explain the actual loading limitation.

## 2. Prepare and install without user-managed dependencies

Download and read the appropriate bootstrap from this repository, then execute it with the selected host. It reuses a suitable Python or provisions a user-local managed Python through uv. No administrator access, Codex account for other hosts, API key or Git executable is required. Network access is needed for missing dependencies and source download.

For Linux/macOS shells:

```bash
curl -fsSL https://raw.githubusercontent.com/InfinitySpeed/goalpilot/main/bootstrap.sh -o /tmp/goalpilot-bootstrap.sh
# Inspect the downloaded script, then run for the current host:
bash /tmp/goalpilot-bootstrap.sh --host claude-code
```

For Windows PowerShell:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/InfinitySpeed/goalpilot/main/bootstrap.ps1 -OutFile "$env:TEMP\goalpilot-bootstrap.ps1"
# Inspect the downloaded script, then run under the normal execution policy:
& "$env:TEMP\goalpilot-bootstrap.ps1" -HostName claude-code
```

Substitute the current host. PowerShell exposes `-Provider`, `-Target`, `-Doctor` and `-DryRun`; shell arguments use `--provider`, `--target`, `--doctor` and `--dry-run`. If execution policy or network rules block setup, report the precise restriction; do not bypass it.

If this repository is already available locally, pass `--source /path/to/checkout` to the shell bootstrap or `-Source C:\path\to\checkout` to PowerShell. With Python3.11+ already available, `python install.py --host <host>` works directly.

## 3. Confirm readiness

Installation automatically validates the manifest and runs the installed local command's help through its recorded interpreter. Require `verification.ready: true`. The output gives `skill_file`; the installed `RUNTIME.json` gives the exact interpreter and command entry point.

Run the same bootstrap with `--doctor` / `-Doctor` for diagnosis. Reload the host's skills, or read the installed `SKILL.md` for immediate use in this session. Do not claim a local doctor check proves a paid end-to-end agent benchmark.

## 4. Respond briefly, then use it

Tell the user which host is ready and how to invoke GoalPilot. If an objective was supplied, start that objective with GoalPilot in the current session. Preserve its complete original wording; run verification before claiming completion. Do not launch another coding model or a benchmark for onboarding.

Support is a local Python unittest verifier. Other languages may load the skill, but supported verified closure is not yet claimed for their test frameworks. The optional `service_race` helper requires POSIX fork; basic Windows installation and local verification do not depend on that helper.
