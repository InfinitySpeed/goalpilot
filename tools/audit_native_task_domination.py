"""Recompute gates for the scoped 1.12.5 native task promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def audit(root: Path) -> dict:
    root = Path(root)
    policy = json.loads((root / "PORTABLE_SKILL.json").read_text())
    active = policy["active_native_workflow"]
    report_path = root / active["benchmark"]
    report = json.loads(report_path.read_text())
    source = root / "integrations/native/routed-SKILL.md"
    means = report["equal_task_weight_metrics"]
    native = means["Codex native"]
    candidate = means["GoalPilot 1.12.5"]
    checks = {
        "promoted_version": active["status"] == "promoted" and active["version"] == "1.12.5",
        "report_version": report["version"] == "1.12.5" and report["status"] == "promoted-scoped",
        "report_hash": hashlib.sha256(report_path.read_bytes()).hexdigest() == active["benchmark_sha256"],
        "skill_hash": hashlib.sha256(source.read_bytes()).hexdigest() == active["source_files"]["integrations/native/routed-SKILL.md"],
        "complete_meters": all(x["raw_tokens"] > 0 and x["uncached_tokens"] > 0 for x in report["per_run"]),
        "candidate_all_hidden_pass": candidate["hidden_passes"] == candidate["runs"] == 4,
        "native_completion_not_lower": native["hidden_passes"] == 2 and native["runs"] == 4,
        "uncached_gain": means["uncached_reduction_percent"] >= 25,
        "elapsed_gain": means["wall_time_reduction_percent"] > 0,
        "native_only_comparator": "No prior GoalPilot version is used as a control." in report["scope"],
    }
    return {"promotable": all(checks.values()), "checks": checks, "report": active["benchmark"]}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=Path(__file__).resolve().parents[1], type=Path)
    print(json.dumps(audit(parser.parse_args().root), indent=2))
