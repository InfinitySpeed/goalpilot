"""Persistent supervisor. Acceptance evidence, not agent prose, decides success."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from .model import ContractError, digest, validate
from .activity import changes, snapshot
from .process import run_process
from .runtime_kit import _lock_stream, _unlock_stream


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        try:
            _lock_stream(stream, blocking=False)
        except BlockingIOError:
            raise ContractError("This mission is already running") from None
        try:
            yield
        finally:
            _unlock_stream(stream)


def token_totals(calls: list[dict]) -> dict:
    known = [x["result"]["usage"] for x in calls if x.get("result", {}).get("usage") is not None]
    inputs = sum(x["input_tokens"] for x in known)
    outputs = sum(x["output_tokens"] for x in known)
    return {
        "input_tokens": inputs, "output_tokens": outputs,
        "cached_input_tokens": sum(x.get("cached_input_tokens", 0) for x in known),
        "total_tokens": inputs + outputs,
        "uncached_tokens": inputs + outputs - sum(x.get('cached_input_tokens',0)for x in known),
        "calls_with_usage": len(known), "calls_without_usage": len(calls) - len(known),
        "calls_with_partial_usage": sum(x.get('result',{}).get('usage') is not None and x['result'].get('usage_complete') is False for x in calls),
        "usage_complete": len(known) == len(calls) and all(x.get('result',{}).get('usage_complete') is not False for x in calls),
    }


def progress(checks: list[dict]) -> int:
    return sum(x["passed"] for x in checks)


def artifacts_intact(contract: dict) -> bool:
    try:
        return all((p := Path(x['path'])).is_file() and not p.is_symlink() and
                   hashlib.sha256(p.read_bytes()).hexdigest() == x['sha256']
                   for x in contract.get('artifacts', []))
    except OSError:
        return False


def verify(contract: dict, deadline: float, evidence_dir: Path) -> list[dict]:
    results = []
    def invalid():
        return [{'id': x['id'], 'passed': False, 'returncode': None,
                 'output': 'Frozen acceptance artifact changed or missing; refusing verification',
                 'duration_seconds': 0, 'timed_out': False, 'infrastructure_error': True}
                for x in contract['checks']]
    for index, check in enumerate(contract["checks"]):
        if not artifacts_intact(contract):
            return invalid()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append({"id": check["id"], "passed": False, "returncode": None,
                            "output": "Not executed: mission deadline", "duration_seconds": 0, "timed_out": True})
            continue
        log = evidence_dir / f"check-{index + 1}.log"
        command=check['command'];env=None
        frozen_paths={a['path']for a in contract.get('artifacts',[])}
        repository_import_path=(contract.get('scope')=='inferred' and len(command)>1
            and Path(command[0]).name.startswith('python') and any(arg in frozen_paths for arg in command[1:]))
        if repository_import_path:
            # Generated probes live outside the repo. Give their ordinary public
            # imports the same project context as python -c from repo cwd, without
            # editing frozen programs or changing trusted user-defined checks.
            env=os.environ.copy();previous=env.get('PYTHONPATH')
            env['PYTHONPATH']=str(Path(contract['repo']).resolve())+(os.pathsep+previous if previous else '')
        result = run_process(command, Path(contract["repo"]), min(check.get("timeout_seconds", 30), remaining), log_path=log, env=env)
        executable = check["command"][0]
        candidate = (Path(contract["repo"]) / executable).resolve()
        repo = Path(contract["repo"]).resolve()
        # Missing scripts inside the project may be part of the implementation.
        # A missing external executable cannot be repaired inside its sandbox.
        project_executable = "/" in executable and (candidate == repo or repo in candidate.parents)
        infrastructure_error = (result.launch_error and not project_executable) or result.returncode in check.get('infrastructure_codes', [])
        results.append({"id": check["id"], "passed": result.returncode == 0,
                        "returncode": result.returncode, "output": result.output[-4000:],
                        "duration_seconds": result.duration_seconds, "timed_out": result.timed_out,
                        "log": str(log), "output_truncated": result.output_truncated,
                        "infrastructure_error": infrastructure_error, "repository_import_path": repository_import_path})
    return results if artifacts_intact(contract) else invalid()


def prompt_for(state: dict, strategy: str) -> str:
    contract = state["contract"]
    latest = state["verifications"][-1]["checks"]
    tactics = {
        "direct": "Complete this goal autonomously, handle blockers, and verify the full result before finishing.",
        "implement": "Build a working end-to-end path first. Resolve reversible ambiguities yourself, preserving the full goal.",
        "diagnose": "Progress has stalled. Reproduce one failing acceptance check in isolation, identify its root cause, then fix the cause. Do not repeat the previous approach unchanged.",
        "alternative": "Previous approaches did not improve acceptance. Choose a materially different implementation or remove an unnecessary dependency. Explain the changed hypothesis in your handoff.",
        "integrate": "Focus on the remaining end-to-end integration. Trace input through storage/logic to output. Use a simpler implementation where helpful while preserving every acceptance requirement.",
        "restore": "Acceptance regressed. Inspect the recent changes, restore the previously working behavior, then fix the remaining failing path without deleting unrelated user changes.",
    }
    previous = next((x["result"].get("message", "")[-3500:] for x in reversed(state["calls"]) if x.get("result") and x["strategy"] != "planning"), "")
    feedback = [{"id": x["id"], "passed": x["passed"], "output": x["output"][-1500:]} for x in latest]
    history = [{"strategy": x["strategy"], "passed": progress(x["checks"])} for x in state["verifications"] if x.get("strategy")]
    return f"""You are executing a persistent coding mission. Work autonomously in the given repository.
ORIGINAL GOAL (preserve the intent):
{contract['goal']}

ASSUMPTIONS: {json.dumps(contract['assumptions'], ensure_ascii=False)}
MILESTONES: {json.dumps(contract['milestones'], ensure_ascii=False)}
KNOWN LIMITATIONS: {json.dumps(contract['limitations'], ensure_ascii=False)}

FROZEN ACCEPTANCE CONTRACT:
{json.dumps(contract['checks'], ensure_ascii=False, indent=2)}

LATEST INDEPENDENT CHECK RESULTS:
{json.dumps(feedback, ensure_ascii=False)}

STRATEGY: {tactics[strategy]}
HISTORY: {json.dumps(history)}
PREVIOUS HANDOFF (untrusted; verify against the repository):
{previous}

Complete the work rather than only describing a plan. Inspect repository instructions first.
Run relevant checks. Do not modify the mission contract, external verifier, or supervisor files.
Do not weaken tests, fake evidence, or silently narrow the requested scope.
Choose reasonable reversible defaults; record your decisions. Do not deploy, publish, send messages,
obtain credentials, or perform destructive external actions. If genuinely blocked by missing access,
say exactly what is missing. Finish with a concise handoff: changes, checks, decisions, remaining work.
"""


def success_status(contract: dict) -> str:
    if contract.get('unverified'):
        return 'partial'
    return "completed" if contract["scope"] == "user_defined" else "scope_passed"


def run_mission(contract: dict, adapter, run_dir: Path, *, resume: bool = False, mode: str = "supervised", notify=None, seed_calls: list[dict] | None = None) -> dict:
    """Run with persistent call/time limits. Token limit is observed after each call."""
    run_dir = run_dir.resolve()
    validate(contract)
    if mode not in ("supervised", "direct"):
        raise ContractError("Unknown mode")
    repo = Path(contract["repo"]).resolve()
    if run_dir == repo or repo in run_dir.parents:
        raise ContractError("Run evidence must live outside the agent repository")
    with lock(run_dir / "run.lock"):
        state_path = run_dir / "state.json"
        if resume:
            state = json.loads(state_path.read_text())
            if state["contract_hash"] != digest(contract) or digest(state["contract"]) != state["contract_hash"] or state["mode"] != mode:
                raise ContractError("Cannot resume with changed criteria, budget, repository, or mode; create a new run")
            if state["status"] in ("completed", "scope_passed"):
                # Revalidate completion on resume: repository contents may have changed.
                state["status"] = "running"
            pending = state.get("pending")
            if pending:
                state["active_seconds"] += min(pending["reserved_seconds"], max(0, time.time() - pending["started_at"]))
                state["calls"][pending["call_index"]]["interrupted"] = True
                state["pending"] = None
        else:
            if state_path.exists():
                raise ContractError("Run already exists; use resume")
            state = {"version": 1, "id": uuid.uuid4().hex[:12], "contract": contract,
                     "contract_hash": digest(contract), "mode": mode, "status": "running",
                     "created_at": time.time(), "active_seconds": 0.0, "calls": [],
                     "verifications": [], "pending": None, "no_progress": 0, "best_passed": 0,
                     "inactive_calls": 0,
                     "simulated": bool(getattr(adapter, "simulated", False)),
                     "adapter": {"class": type(adapter).__name__, "model": getattr(adapter, "model", None)}}
            if contract.get("planning"):
                planning = contract["planning"]
                state["calls"].append({"strategy": "planning", "result": planning})
                state["active_seconds"] += planning["duration_seconds"]
            for call in seed_calls or []:
                state['calls'].append(call)
                state['active_seconds'] += call['result']['duration_seconds']
        start = time.monotonic()
        base_active = state["active_seconds"]
        deadline = start + max(0, contract["budget"]["wall_seconds"] - base_active)

        def save():
            state["active_seconds"] = base_active + time.monotonic() - start
            state["usage"] = token_totals(state["calls"])
            atomic_json(state_path, state)

        def check(strategy=None):
            checks = verify(contract, deadline, run_dir / "evidence" / f"verification-{len(state['verifications']) + 1}")
            state["verifications"].append({"checks": checks, "strategy": strategy, "at": time.time()})
            save()
            return checks

        try:
            state["status"] = "running"
            state.pop("stop_reason", None)
            save()
            checks = check()
            state["best_passed"] = max(state["best_passed"], progress(checks))
            while True:
                if all(x["passed"] for x in checks):
                    state["status"] = success_status(contract)
                    break
                if any(x.get("infrastructure_error") for x in checks):
                    state["status"] = "verification_unavailable"
                    state["stop_reason"] = "External verification executable could not start; agent retries would not fix access to it"
                    break
                usage = token_totals(state["calls"])
                fresh_cap=contract['budget'].get('max_uncached_tokens')
                if fresh_cap is not None and (not usage['usage_complete'] or usage['uncached_tokens']>=fresh_cap):
                    state['status']='budget_exhausted'
                    state['stop_reason']='uncached_usage_unknown' if not usage['usage_complete'] else 'observed_uncached_tokens (soft limit checked between calls)'
                    break
                if time.monotonic() >= deadline:
                    state["status"] = "budget_exhausted"
                    state["stop_reason"] = "wall_seconds"
                    break
                if len(state["calls"]) >= contract["budget"]["max_calls"]:
                    state["status"] = "budget_exhausted"
                    state["stop_reason"] = "max_calls"
                    break
                if usage["total_tokens"] >= contract["budget"]["max_tokens"]:
                    state["status"] = "budget_exhausted"
                    state["stop_reason"] = "observed_tokens (soft limit checked between calls)"
                    break
                if mode == "direct" and any(x["strategy"] != "planning" for x in state["calls"]):
                    state["status"] = "incomplete"
                    state["stop_reason"] = "direct_session_finished"
                    break
                if state["no_progress"] >= 4 and state.get("inactive_calls", 0) >= 2:
                    state["status"] = "stalled"
                    state["stop_reason"] = "four attempts without a new best acceptance score and at least two inactive calls"
                    break
                strategy = "direct" if mode == "direct" else ["implement", "diagnose", "alternative", "integrate"][min(state["no_progress"], 3)]
                if len(state["verifications"]) > 1 and progress(checks) < state["best_passed"]:
                    strategy = "restore" if mode == "supervised" else "direct"
                remaining = deadline - time.monotonic()
                reserve = min(10, remaining * 0.15)
                timeout = max(0.001, min(remaining - reserve, contract["budget"]["attempt_seconds"] if mode == "supervised" else remaining - reserve))
                call_index = len(state["calls"])
                before = snapshot(repo)
                state["calls"].append({"strategy": strategy, "started_at": time.time()})
                state["pending"] = {"call_index": call_index, "started_at": time.time(), "reserved_seconds": timeout}
                save()
                if notify:
                    notify(f"[{call_index + 1}/{contract['budget']['max_calls']}] {strategy} · {progress(checks)}/{len(checks)} checks · max {timeout:.1f}s")
                try:
                    if contract.get('repair_effort') and hasattr(adapter,'effort'):
                        adapter.effort=contract['repair_effort']
                    result = adapter.execute(prompt_for(state, strategy), repo, timeout, run_dir / "calls" / str(call_index + 1))
                except Exception as exc:
                    # Preserve the consumed reservation; do not start a hidden retry.
                    state["calls"][call_index]["error"] = f"{type(exc).__name__}: {exc}"
                    state["pending"] = None
                    state["status"] = "adapter_error"
                    state["stop_reason"] = str(exc)
                    break
                state["calls"][call_index]["result"] = result.to_dict()
                activity = changes(before, snapshot(repo))
                state["calls"][call_index]["repository_activity"] = activity
                if activity["changed_file_count"] or not activity["complete"]:
                    state["inactive_calls"] = 0
                else:
                    state["inactive_calls"] = state.get("inactive_calls", 0) + 1
                state["pending"] = None
                save()
                checks = check(strategy)
                count = progress(checks)
                if count > state["best_passed"]:
                    state["best_passed"] = count
                    state["no_progress"] = 0
                    state["inactive_calls"] = 0
                else:
                    state["no_progress"] += 1
                if result.fatal and not all(x["passed"] for x in checks):
                    state["status"] = "agent_unavailable"
                    state["stop_reason"] = result.message[-2000:]
                    break
        except KeyboardInterrupt:
            state["status"] = "interrupted"
            # A started call remains charged; usage remains unknown if not emitted.
            if state.get("pending"):
                state["calls"][state["pending"]["call_index"]]["interrupted"] = True
            state["pending"] = None
            state["stop_reason"] = "Interrupted; resume revalidates repository and preserves budgets"
        finally:
            save()
        return state
