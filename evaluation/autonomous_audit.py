"""Adversarial mechanism audit. Scripted actors; no LLM efficacy claims.

Run from the project root:
    python3 -m evaluation.autonomous_audit --output reports/autonomous-audit-001
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json
import sys
import time

from goalpilot.adapters import AgentResult
from goalpilot.engine import atomic_json, run_mission
from goalpilot.process import run_process


class Actor:
    simulated = True

    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = 0

    def execute(self, prompt, repo, timeout, log_dir):
        self.calls += 1
        self.behavior(repo, self.calls)
        return AgentResult(0, "Scripted actor; inspect independent evidence.", 0, None, simulated=True)


def mission(repo, description, command):
    return {"goal": description, "repo": str(repo), "scope": "user_defined",
            "checks": [{"id": "acceptance", "description": description, "command": command, "timeout_seconds": 2}],
            "budget": {"max_calls": 8, "wall_seconds": 20, "attempt_seconds": 2, "max_tokens": 10000}}


def audit(output: Path) -> dict:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    observations = []
    start = time.perf_counter()

    def setup(name):
        repo = output / "repos" / name
        repo.mkdir(parents=True)
        return repo, output / "runs" / name

    repo, run = setup("multi_step_progress")
    actor = Actor(lambda p, n: (p / f"stage-{n}").write_text(f"Completed prerequisite {n}"))
    contract = mission(repo, "Complete a five-stage pipeline. Each prerequisite needs one bounded execution; all five must exist.",
                       [sys.executable, "-c", "from pathlib import Path; assert all(Path(f'stage-{i}').exists() for i in range(1,6))"])
    state = run_mission(contract, actor, run)
    observations.append({"id": "multi_step_progress", "kind": "supervision_weakness", "expectation": "Do not declare a stall while distinct prerequisites are being completed within the eight-call budget.",
                         "status": state["status"], "calls": actor.calls, "completed_prerequisites": len(list(repo.glob("stage-*"))),
                         "required_prerequisites": 5, "available_call_budget": 8,
                         "expectation_met": state["status"] == "completed",
                         "finding": "Intermediate activity preserved: all five stages completed within the original budget." if state["status"] == "completed" else "Stall detection sees only whole acceptance checks; useful intermediate artifacts do not advance its score.", "state": str(run / "state.json")})

    repo, run = setup("verifier_unavailable")
    actor = Actor(lambda p, n: None)
    missing = output / "unavailable-external-verifier"
    state = run_mission(mission(repo, "Create a result; verify using an external executable that is missing from this environment.", [str(missing)]), actor, run)
    observations.append({"id": "verifier_unavailable", "kind": "supervision_weakness", "expectation": "Stop before consuming an agent call when an external verification executable cannot start.",
                         "status": state["status"], "calls": actor.calls,
                         "expectation_met": actor.calls == 0,
                         "finding": "External verifier failure detected before any agent call." if actor.calls == 0 else "A verifier launch failure is treated like an implementation failure and triggers useless retries.", "state": str(run / "state.json")})

    repo, run = setup("acceptance_generalization")
    actor = Actor(lambda p, n: (p / "transform.py").write_text("def transform(items):\n    return ['a', 'b'] if items else []\n"))
    contract = mission(repo, "Normalize arbitrary labels: strip whitespace, casefold Unicode, deduplicate and sort.",
                       [sys.executable, "-B", "-c", "from transform import transform; assert transform([' A ','b','a'])==['a','b']; assert transform([])==[]"])
    state = run_mission(contract, actor, run)
    held_out = run_process([sys.executable, "-B", "-c", "from transform import transform; assert transform(['C',' b '])==['b','c']; assert transform(['ÉTÉ','été'])==['été']"], repo, 2, log_path=output / "holdout.log")
    observations.append({"id": "acceptance_generalization", "kind": "acceptance_coverage_limitation", "expectation": "A completed visible contract should not be mistaken for proof of the broader natural-language goal.",
                         "status": state["status"], "calls": actor.calls,
                         "visible_contract_passed": state["status"] == "completed", "held_out_acceptance_passed": held_out.returncode == 0,
                         "expectation_met": held_out.returncode == 0,
                         "finding": "The provided examples can be hard-coded. Independent held-out behavioral checks are needed for an efficacy evaluation; the engine only guarantees its declared checks.",
                         "held_out_evidence": asdict(held_out), "state": str(run / "state.json")})

    repo, run = setup("already_complete")
    (repo / "answer").write_text("42")
    actor = Actor(lambda p, n: None)
    state = run_mission(mission(repo, "Read the correct existing result", [sys.executable, "-c", "from pathlib import Path; assert Path('answer').read_text()=='42'"]), actor, run)
    observations.append({"id": "already_complete", "kind": "control", "status": state["status"], "calls": actor.calls,
                         "expectation_met": state["status"] == "completed" and actor.calls == 0,
                         "finding": "The initial verification correctly avoids an unnecessary agent invocation.", "state": str(run / "state.json")})

    report = {"kind": "autonomous_adversarial_mechanism_audit", "simulated_actors": True, "live_model_calls": 0,
              "duration_seconds": time.perf_counter() - start, "observations": observations,
              "interpretation": "Diagnostic examples expose mechanism weaknesses and acceptance gaps. They are not a sample of LLM tasks, a goal-success rate, or a quota-saving measurement."}
    atomic_json(output / "audit.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.output)
