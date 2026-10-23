"""Codex JSONL adapter; usage comes from emitted events, never estimates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .process import run_process


@dataclass
class AgentResult:
    returncode: int
    message: str
    duration_seconds: float
    usage: dict | None
    timed_out: bool = False
    fatal: bool = False
    simulated: bool = False
    usage_complete: bool | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    telemetry: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_events(path: Path) -> tuple[str, dict | None, bool]:
    usage = None
    messages = []
    fatal = False
    if not path.exists():
        return "", None, False
    with path.open(errors="replace") as stream:
        for line in stream:
            # Guard against non-JSON startup messages and pathological lines.
            if len(line) > 2_000_000:
                continue
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                current = event["usage"]
                if all(type(current.get(k)) is int and current[k] >= 0 for k in ("input_tokens", "output_tokens")):
                    usage = usage or {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}
                    for key in usage:
                        usage[key] += max(0, current.get(key, 0)) if type(current.get(key, 0)) is int else 0
            item = event.get("item", {})
            if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
                messages.append(str(item.get("text", "")))
            if event.get("type") in ("error", "turn.failed"):
                error = str(event.get("message", event.get("error", "")))
                messages.append(error)
                if any(word in error.lower() for word in ("unauthorized", "authentication", "rate limit", "quota", "401", "403", "429", "usage limit", "access token", "sign in again", "not logged in", "refresh token", "credentials")):
                    fatal = True
    return "\n".join(messages)[-10000:], usage, fatal


class CodexAdapter:
    simulated = False

    def __init__(self, model: str | None = None, executable: str = "codex"):
        self.model = model
        self.executable = executable

    def execute(self, prompt: str, repo: Path, timeout: float, log_dir: Path, *, planning: bool = False, schema: Path | None = None) -> AgentResult:
        log_dir.mkdir(parents=True, exist_ok=True)
        final = log_dir / "last-message.txt"
        events = log_dir / "events.jsonl"
        command = [self.executable, "-a", "never", "exec", "--json", "--color", "never", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only" if planning else "workspace-write", "-C", str(repo), "-o", str(final)]
        if self.model:
            command += ["--model", self.model]
        if schema:
            command += ["--output-schema", str(schema)]
        command += ["-"]
        process = run_process(command, repo, timeout, stdin=prompt, log_path=events)
        message, usage, fatal = parse_events(events)
        if final.exists():
            message = final.read_text(errors="replace") if planning else final.read_text(errors="replace")[-16000:]
        if not message:
            message = process.output[-4000:]
        return AgentResult(process.returncode, message, process.duration_seconds, usage, process.timed_out, fatal or process.returncode == 127)
