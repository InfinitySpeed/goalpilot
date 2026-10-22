"""Live end-to-end comparison with automatic framing and an external judge.

This is one small open-ended notes goal with a documented interface, not a
representative sample of multi-hour ambitious goals. Evaluation checks stay out
of coding prompts; planning time and usage count toward the supervised budget.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from goalpilot.adapters import CodexAdapter
from goalpilot.benchmark import fixtures
from goalpilot.cli import initialize
from goalpilot.engine import atomic_json, run_mission, token_totals, verify
from goalpilot.model import ContractError, digest, validate
from .holdouts import holdouts


GOAL = "Termine ce projet pour en faire un outil de notes personnel fiable et utilisable au quotidien. Prends les décisions nécessaires, préserve mes données existantes, gère les cas qui risquent de me bloquer, vérifie le résultat et laisse des instructions d'utilisation claires."
README = """# Notes personnel — projet inachevé

L'interface prévue est `python3 notes.py --store CHEMIN COMMANDE`.
Commandes : `add TEXTE [--tag TAG]` (option répétable), `list`, `search REQUÊTE`,
`delete ID`, `export`. Les commandes list/search/export émettent du JSON.
Le stockage est un tableau JSON d'objets {id: entier, text: chaîne, tags: tableau}.
Les identifiants existants sont conservés ; les nouveaux sont max(id)+1, ou 1
dans un stockage vide. Recherche de sous-chaîne insensible à la casse.
Un texte vide/blanc doit être refusé avec le code 2. Supprimer un ID absent doit
retourner 1 sans modifier les données ; une suppression réussie retourne 0.
Préserver les notes Unicode et les fichiers déjà existants. Bibliothèque standard
Python uniquement. Aucun service, compte externe, publication ou déploiement.
"""


def run(args):
    if not args.live:
        raise ContractError("--live required; this evaluation consumes actual Codex usage")
    root = args.output.resolve()
    resuming = bool(getattr(args, "resume", False))
    if root.exists() and any(root.iterdir()) and not resuming:
        raise ContractError("Output must be new or empty")
    root.mkdir(parents=True, exist_ok=True)
    acceptance = fixtures()[0]["checks"] + holdouts()["notes"]
    budget = {"max_calls": 3, "wall_seconds": args.wall_seconds,
              "attempt_seconds": args.attempt_seconds, "max_tokens": 100000}
    public_files = {"notes.py": "import json\nprint(json.dumps([]))\n", "README.md": README}
    manifest = {"kind": "live_open_ended_goal_with_external_judge", "created_at": time.time(),
                "goal": GOAL, "public_files": public_files, "public_files_hash": digest(public_files),
                "frozen_evaluation_checks": acceptance, "acceptance_hash": digest(acceptance),
                "budget_per_condition": budget, "planning_seconds": args.planning_seconds,
                "order": ["supervised", "direct"],
                "method": "Identical goal, repository and interface documentation. Direct gets one continuous session. Supervised includes automatic read-only planning, inferred checks, verification and recovery. Frozen external checks run only after execution, without feeding failures back.",
                "limitations": ["One small notes task with an open-ended goal and documented interface", "Not a representative long ambitious goal", "Single trial per condition; order/cache effects uncontrolled", "Subscription quota and subjective satisfaction not observable", "Tokens only measured if Codex emits usage before ending; token ceiling soft"], "results": []}
    if resuming:
        previous = json.loads((root / "manifest.json").read_text())
        if previous["acceptance_hash"] != manifest["acceptance_hash"] or previous["public_files_hash"] != manifest["public_files_hash"] or previous["budget_per_condition"] != budget:
            raise ContractError("Cannot resume with changed tasks, acceptance or budgets")
        manifest = previous
        manifest["resumed_at"] = time.time()
        if manifest.get("stopped_early"):
            manifest["prior_stop"] = manifest.pop("stopped_early")
    atomic_json(root / "manifest.json", manifest)
    adapter = CodexAdapter(args.model)
    manifest["simulated"] = bool(getattr(adapter, "simulated", False))
    for mode in manifest["order"]:
        if any(record["mode"] == mode for record in manifest["results"]):
            continue
        repo = root / "repos" / mode
        repo.mkdir(parents=True, exist_ok=resuming)
        for name, content in public_files.items():
            (repo / name).write_text(content)
        judge = validate({"goal": GOAL, "repo": str(repo), "scope": "user_defined", "checks": acceptance, "budget": dict(budget)})
        print(f"LIVE OPEN-ENDED / {mode}", flush=True)
        start = time.monotonic()
        deadline = start + args.wall_seconds
        if mode == "supervised":
            options = argparse.Namespace(goal=GOAL, repo=repo, output=root / "contracts" / "supervised.json",
                checks=None, model=args.model, max_calls=3, wall_seconds=args.wall_seconds,
                attempt_seconds=args.attempt_seconds, max_tokens=100000, planning_seconds=args.planning_seconds)
            try:
                contract = initialize(options)
            except ContractError as exc:
                result_file = root / "contracts" / "supervised-planning" / "result.json"
                if not result_file.exists():
                    raise
                planning_result = json.loads(result_file.read_text())
                calls = [{"strategy": "planning", "result": planning_result}]
                internal_status = "agent_unavailable" if planning_result.get("fatal") else "planning_failed"
                atomic_json(root / "planning-failure.json", {"reason": str(exc), "result": planning_result})
            else:
                state = run_mission(contract, adapter, root / "runs" / mode, notify=lambda x: print(x, flush=True))
                calls = state["calls"]
                internal_status = state["status"]
        else:
            prompt = f"""Work autonomously in this repository to complete the following goal:
{GOAL}
Inspect project instructions and README, implement a complete usable result and test it.
Resolve reversible ambiguities yourself and record your choices. Preserve existing data.
Do not publish, deploy, obtain credentials or perform destructive external actions.
Finish with a concise handoff describing actual changes, checks and remaining limits.
"""
            result = adapter.execute(prompt, repo, max(1, deadline - time.monotonic() - 10), root / "calls" / mode)
            calls = [{"strategy": "direct", "result": result.to_dict()}]
            atomic_json(root / "direct-result.json", result.to_dict())
            internal_status = "agent_unavailable" if result.fatal else ("timed_out" if result.timed_out else "session_finished")
        # A fixed post-run assessment is outside the agent's work allowance, equal
        # for both conditions. Its time is reported separately.
        judge_start = time.monotonic()
        evidence = verify(judge, judge_start + 30, root / "external-evidence" / mode)
        assessment_seconds = time.monotonic() - judge_start
        execution_seconds = judge_start - start
        record = {"mode": mode, "internal_status": internal_status,
                  "simulated": bool(getattr(adapter, "simulated", False)),
                  "external_goal_success": all(x["passed"] for x in evidence),
                  "checks_passed": sum(x["passed"] for x in evidence), "checks_total": len(evidence),
                  "execution_seconds_including_planning": execution_seconds,
                  "assessment_seconds": assessment_seconds, "agent_calls": len(calls),
                  "usage": token_totals(calls), "checks": evidence}
        manifest["results"].append(record)
        atomic_json(root / "manifest.json", manifest)
        print(json.dumps({k:v for k,v in record.items() if k != "checks"}, ensure_ascii=False), flush=True)
        if internal_status in ("agent_unavailable", "verification_unavailable", "adapter_error"):
            manifest["stopped_early"] = internal_status
            atomic_json(root / "manifest.json", manifest)
            break
    by_mode = {x["mode"]: x for x in manifest["results"]}
    comparison = None
    if len(by_mode) == 2:
        direct, supervised = by_mode["direct"], by_mode["supervised"]
        complete = all(x["usage"]["usage_complete"] for x in (direct, supervised))
        comparison = {
            "success_difference": int(supervised["external_goal_success"]) - int(direct["external_goal_success"]),
            "token_difference": supervised["usage"]["total_tokens"] - direct["usage"]["total_tokens"] if complete else None,
            "token_change_percent": 100*(supervised["usage"]["total_tokens"]/direct["usage"]["total_tokens"]-1) if complete and direct["usage"]["total_tokens"] else None,
            "seconds_difference": supervised["execution_seconds_including_planning"] - direct["execution_seconds_including_planning"] if supervised["execution_seconds_including_planning"] is not None and direct["execution_seconds_including_planning"] is not None else None,
            "note": "Descriptive single-task comparison; not a causal benefit estimate."}
    report = {"kind": manifest["kind"], "results": manifest["results"], "comparison": comparison,
              "limitations": manifest["limitations"], "acceptance_hash": manifest["acceptance_hash"]}
    atomic_json(root / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--wall-seconds", type=float, default=180)
    parser.add_argument("--attempt-seconds", type=float, default=120)
    parser.add_argument("--planning-seconds", type=float, default=60)
    parser.add_argument("--resume", action="store_true", help="Keep recorded conditions; run only conditions not yet completed")
    args = parser.parse_args()
    run(args)
