"""Controlled fault injection. Scripted behavior is NOT a language model."""

from __future__ import annotations

from pathlib import Path
import sys

from .adapters import AgentResult
from .engine import atomic_json, run_mission
from .metrics import aggregate, html_report
from .model import ContractError


class FaultAgent:
    simulated = True

    def __init__(self, scenario: str):
        self.scenario = scenario

    def execute(self, prompt, repo, timeout, log_dir):
        solve = self.scenario == "immediate" or (
            self.scenario == "diagnosis_required" and "STRATEGY: Progress has stalled" in prompt) or (
            self.scenario == "alternative_required" and "STRATEGY: Previous approaches" in prompt)
        if solve:
            (repo / "transform.py").write_text("def transform(items):\n    return sorted(set(x.strip().casefold() for x in items if x.strip()))\n")
        return AgentResult(0, "Scripted handoff: task is done (the verifier must check).", 0, None, simulated=True)


def run_lab(output: Path) -> dict:
    root = output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError("Lab output must be new or empty")
    root.mkdir(parents=True, exist_ok=True)
    scenarios = ("immediate", "diagnosis_required", "alternative_required", "irrecoverable")
    manifest = {
        "kind": "deterministic_fault_injection", "simulated": True,
        "description": "A scripted actor repairs a Python function only when a predefined strategy appears. Demonstrates control flow, NOT autonomous LLM skill or real quota savings.",
        "scenarios": list(scenarios), "runs": [],
    }
    states = []
    for scenario in scenarios:
        for mode in ("direct", "supervised"):
            repo = root / "repos" / f"{scenario}-{mode}"
            repo.mkdir(parents=True)
            (repo/"transform.py").write_text("def transform(items):\n    return items\n")
            contract = {
                "goal": "Normalize a list of labels: strip whitespace, remove blanks, casefold Unicode, deduplicate and sort.",
                "repo": str(repo), "scope": "user_defined",
                "checks": [{"id": "behavior", "description": "Normalization, Unicode, deduplication and empty input work", "command": [sys.executable, "-B", "-c", "from transform import transform; assert transform([' B ', 'a', 'A', ' ', 'ÉTÉ', 'été']) == ['a','b','été']; assert transform([])==[]"], "timeout_seconds": 2}],
                "budget": {"max_calls": 8, "wall_seconds": 20, "attempt_seconds": 2, "max_tokens": 1000},
            }
            state = run_mission(contract, FaultAgent(scenario), root / "runs" / f"{scenario}-{mode}", mode=mode)
            states.append(state)
            manifest["runs"].append({"scenario": scenario, "mode": mode, "id": state["id"], "status": state["status"]})
    report = aggregate(states)
    direct = report["groups"]["simulated/direct"]
    supervised = report["groups"]["simulated/supervised"]
    report["controlled_result"] = {
        "simulated": True, "direct_successes": direct["verified_successes"], "supervised_successes": supervised["verified_successes"],
        "scenarios_per_condition": len(scenarios), "direct_calls": direct["agent_calls"], "supervised_calls": supervised["agent_calls"],
        "success_rate_difference_percentage_points": 100 * (supervised["success_rate"] - direct["success_rate"]),
        "scripted_call_change_percent": 100 * (supervised["agent_calls"] / direct["agent_calls"] - 1),
        "interpretation": "Designed fault scenarios validate the recovery mechanism. These numbers are not measured LLM utility, token savings, or user-goal success rates.",
    }
    atomic_json(root / "manifest.json", manifest)
    atomic_json(root / "report.json", report)
    (root / "report.html").write_text(html_report(report))
    print(f"SIMULATION — {direct['verified_successes']}/4 direct, {supervised['verified_successes']}/4 supervised; {direct['agent_calls']} vs {supervised['agent_calls']} scripted calls")
    print(f"Report: {root / 'report.html'}")
    return report
