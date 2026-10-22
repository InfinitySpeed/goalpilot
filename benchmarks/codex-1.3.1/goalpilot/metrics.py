"""Reproducible metrics. No synthetic quota percentages or invented prices."""

from __future__ import annotations

from collections import Counter
import html
import json
import math
from pathlib import Path

from .engine import progress, token_totals


def wilson(successes: int, trials: int) -> list[float] | None:
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0, center - radius), min(1, center + radius)]


def summarize(state: dict) -> dict:
    verifications = state["verifications"]
    final = verifications[-1]["checks"] if verifications else []
    initial = verifications[0]["checks"] if verifications else []
    usage = token_totals(state["calls"])
    gain = progress(final) - progress(initial)
    calls = [x for x in state["calls"] if x["strategy"] not in ("planning", "audit", "audit-recovery", "audit-repair", "audit-validation", "challenge")]
    recoveries = sum(1 for i, v in enumerate(verifications) if i > 0 and v.get("strategy") in ("diagnose", "alternative", "integrate", "restore") and progress(v["checks"]) > progress(verifications[i - 1]["checks"]))
    return {
        "id": state["id"], "goal": state["contract"]["goal"], "mode": state["mode"],
        "status": state["status"], "scope": state["contract"]["scope"],
        "unverified_requirements": state['contract'].get('unverified', []),
        "acceptance_origin": state['contract'].get('acceptance_origin', state['contract'].get('creation_mode', 'legacy')),
        "simulated": state["simulated"], "checks_total": len(final),
        "checks_initially_passed": progress(initial), "checks_finally_passed": progress(final),
        "check_gain": gain, "contract_passed": bool(final) and all(x["passed"] for x in final),
        "verified_success": state["status"] == "completed",
        "evaluable_for_task_utility": state["status"] not in ("agent_unavailable", "verification_unavailable", "adapter_error", "interrupted", "running"),
        "active_seconds": state["active_seconds"], "agent_calls": len(state["calls"]),
        "execution_calls": len(calls), "planning_calls": sum(x['strategy'] == 'planning' for x in state['calls']),
        "review_calls": sum(x['strategy'] in ('audit','audit-recovery', 'audit-repair','audit-validation','challenge') for x in state['calls']),
        "verification_commands": sum(x.get("returncode") is not None for v in verifications for x in v["checks"]),
        "strategy_changes": sum(a["strategy"] != b["strategy"] for a, b in zip(calls, calls[1:])),
        "recovery_steps_with_progress": recoveries,
        "new_checks_per_1000_tokens": gain * 1000 / usage["total_tokens"] if usage["usage_complete"] and usage["total_tokens"] else None,
        "usage": usage, "budget": state["contract"]["budget"],
        "stop_reason": state.get("stop_reason"),
        "reuse": state.get('reuse'),
    }


def aggregate(states: list[dict]) -> dict:
    runs = [summarize(s) for s in states]
    groups = {}
    for label in sorted({("simulated" if x["simulated"] else "real") + "/" + x["mode"] for x in runs}):
        members = [x for x in runs if ("simulated" if x["simulated"] else "real") + "/" + x["mode"] == label]
        declared = [x for x in members if x["scope"] == "user_defined"]
        eligible = [x for x in declared if x["evaluable_for_task_utility"]]
        n = len(eligible)
        successes = sum(x["verified_success"] for x in eligible)
        total_tokens = sum(x["usage"]["total_tokens"] for x in members)
        usage_complete = all(x["usage"]["usage_complete"] for x in members)
        groups[label] = {
            "runs": len(members), "declared_user_defined_runs": len(declared),
            "user_defined_runs": n, "infrastructure_or_interruption_exclusions": len(declared) - n,
            "verified_successes": successes,
            "success_rate": successes / n if n else None,
            "success_rate_wilson_95": wilson(successes, n) if label.startswith("real/") else None,
            "statuses": dict(Counter(x["status"] for x in members)),
            "active_seconds": sum(x["active_seconds"] for x in members),
            "agent_calls": sum(x["agent_calls"] for x in members),
            "reported_tokens": total_tokens, "usage_complete": usage_complete,
            "calls_without_usage": sum(x["usage"]["calls_without_usage"] for x in members),
            "tokens_per_verified_success": total_tokens / successes if successes and usage_complete and n == len(members) else None,
        }
    comparison = None
    direct, supervised = groups.get("real/direct"), groups.get("real/supervised")
    if direct and supervised and direct["success_rate"] is not None and supervised["success_rate"] is not None:
        complete_usage = direct["usage_complete"] and supervised["usage_complete"]
        comparison = {
            "success_rate_difference_percentage_points": 100 * (supervised["success_rate"] - direct["success_rate"]),
            "reported_token_difference": supervised["reported_tokens"] - direct["reported_tokens"] if complete_usage else None,
            "token_comparison_available": complete_usage,
            "reported_token_change_percent": 100 * (supervised["reported_tokens"] / direct["reported_tokens"] - 1) if direct["reported_tokens"] and direct["usage_complete"] and supervised["usage_complete"] else None,
            "active_seconds_difference": supervised["active_seconds"] - direct["active_seconds"],
            "warning": "Descriptive only. Check matching tasks and budgets. Small samples do not establish a causal benefit.",
        }
    return {"runs": runs, "groups": groups, "comparison": comparison, "definitions": {
        "verified_success": "Final frozen checks pass and scope=user_defined. Measures the declared contract, not subjective satisfaction.",
        "tokens": "Sum of emitted input_tokens + output_tokens; cached tokens are a subset of input, never added twice. Unknown usage is missing, not zero.",
        "wall_time": "Measured active supervision time including checks and planning; excludes downtime between resumes.",
        "token_budget": "Soft threshold observed between calls. A single call can overshoot; incomplete usage prevents full accounting.",
        "quota": "No access to subscription quota or monetary pricing. Tokens are not an exact subscription quota conversion.",
        "utility_denominator": "Authentication/provider failures, adapter errors, interruptions and running missions are excluded from task-utility rates and reported separately.",
        "recovery": "A changed strategy followed by an increase in passing acceptance checks; does not prove why progress occurred.",
    }}


def html_report(report: dict) -> str:
    esc = lambda x: html.escape(str(x), quote=True)
    cards = []
    for run in report["runs"]:
        total = run["checks_total"]
        pct = 100 * run["checks_finally_passed"] / total if total else 0
        usage = run["usage"]
        label = "SIMULATION" if run["simulated"] else "EXÉCUTION RÉELLE"
        token_label = f"{usage['total_tokens']:,} tokens rapportés" if usage["usage_complete"] else f"Consommation incomplète : {usage['total_tokens']:,} tokens rapportés, {usage['calls_without_usage']} appels sans mesure"
        cards.append(f'''<article><div class="eyebrow">{label} · {esc(run['mode'])} · {esc(run['id'])}</div>
<h2>{esc(run['goal'])}</h2><p><strong>{esc(run['status'])}</strong> · périmètre {esc(run['scope'])}</p>
<div class="bar" role="meter" aria-label="Critères réussis" aria-valuemin="0" aria-valuemax="{total}" aria-valuenow="{run['checks_finally_passed']}"><span style="width:{pct:.2f}%"></span></div>
<p>{run['checks_initially_passed']} → <b>{run['checks_finally_passed']}/{total}</b> critères · {run['active_seconds']:.3f} s · {run['agent_calls']} appels</p>
<p>{token_label} · {usage['cached_input_tokens']:,} en cache (inclus)</p>
<p>{run['strategy_changes']} changements de stratégie · {run['recovery_steps_with_progress']} reprises avec progrès</p></article>''')
    groups = []
    for name, group in report["groups"].items():
        interval = group["success_rate_wilson_95"]
        ci = f"[{100*interval[0]:.1f} % ; {100*interval[1]:.1f} %]" if interval else "indisponible"
        groups.append(f"<li><b>{esc(name)}</b> : {group['verified_successes']}/{group['user_defined_runs']} contrats évaluables réussis ; {group['infrastructure_or_interruption_exclusions']} exécutions exclues (infrastructure/interruption) ; IC Wilson 95 % {ci}</li>")
    comparison = esc(json.dumps(report["comparison"], ensure_ascii=False, indent=2))
    notice = f"<p><strong>Benchmark arrêté : {esc(report['benchmark_status'])}. L'utilité réelle n'a pas pu être évaluée.</strong></p>" if report.get("benchmark_status") else ""
    controlled = f"<h2>Simulation contrôlée</h2><pre>{esc(json.dumps(report['controlled_result'], ensure_ascii=False, indent=2))}</pre>" if report.get("controlled_result") else ""
    validation = report.get("validation")
    test_note = f"<p><strong>{esc(validation['passed'])}/{esc(validation['tests_run'])} tests locaux réussis</strong> en {validation['duration_seconds']:.3f} secondes · aucun appel d'API pendant les tests.</p>" if validation else ""
    return f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GoalPilot — preuves d'exécution</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#0c1321;color:#e5eaf4;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:48px 24px}}h1{{font-size:40px;line-height:1.15}}h2{{font-size:20px}}article{{padding:24px;background:#151f31;border:1px solid #2d3c55;border-radius:16px;margin:20px 0}}.eyebrow{{font-size:12px;letter-spacing:.08em;color:#9cb7dc}}.bar{{height:10px;background:#314058;border-radius:8px;overflow:hidden}}.bar span{{display:block;height:100%;background:#60d7b1}}p{{color:#bcc9dd}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#151f31;padding:20px;border-radius:12px}}small{{color:#a9b8cf}}
</style><main><div class="eyebrow">GOALPILOT / OBSERVATOIRE LOCAL</div><h1>Des résultats vérifiés.<br>Des coûts observés.</h1>
<p>Les simulations et les appels réels sont séparés. La réussite porte sur les critères déclarés ; la satisfaction de l'utilisateur n'est pas mesurée ici.</p>{notice}
{test_note}<ul>{''.join(groups)}</ul>{controlled}{''.join(cards)}<h2>Comparaison descriptive</h2><pre>{comparison}</pre>
<h2>Définitions et limites</h2><pre>{esc(json.dumps(report['definitions'], ensure_ascii=False, indent=2))}</pre>
<small>Rapport autonome, sans connexion ni télémétrie externe. Les données brutes restent dans les dossiers d'exécution.</small></main></html>'''
