"""User-facing CLI. All remote work happens only on init/run/benchmark --live."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

from .adapters import CodexAdapter
from .engine import atomic_json, run_mission
from .metrics import aggregate, html_report, summarize
from .model import ContractError, PLAN_SCHEMA, load_contract, positive, validate


def initialize(args) -> dict:
    if not args.goal.strip():
        raise ContractError("Goal must not be empty")
    for field in ("max_calls", "wall_seconds", "attempt_seconds", "max_tokens"):
        positive(getattr(args, field), field)
    repo = args.repo.resolve()
    if not repo.is_dir():
        raise ContractError("Repository directory does not exist")
    destination = args.output.resolve()
    if destination.exists():
        raise ContractError("Output already exists; choose another mission path")
    contract = {"goal": args.goal, "repo": str(repo), "scope": "inferred", "model": args.model,
                "budget": {"max_calls": args.max_calls, "wall_seconds": args.wall_seconds,
                           "attempt_seconds": args.attempt_seconds, "max_tokens": args.max_tokens}}
    if args.checks:
        contract["checks"] = json.loads(args.checks.read_text())
        contract["scope"] = "user_defined"
        contract["assumptions"] = []
    else:
        log_dir = destination.parent / (destination.stem + "-planning")
        log_dir.mkdir(parents=True, exist_ok=True)
        schema = log_dir / "schema.json"
        atomic_json(schema, PLAN_SCHEMA)
        prompt = f"""Inspect this repository read-only and operationalize this ambitious goal:
{args.goal}
Choose reasonable reversible defaults autonomously. Preserve the original ambition; explicitly list
anything not covered by the proposed acceptance. Do not implement anything yet. Return the required JSON.
Create at most 6 milestones and 8 executable acceptance checks. Checks run with repository cwd after
implementation. Use argv arrays, no shell strings. Prefer substantive independent assertions in
python3 -c over checks for file existence, test counts, or self-reported success. Assertions must
actually exercise required user behavior. Checks must be bounded, local, non-destructive, use temporary
directories for data, require no credentials, no deployment and no network. Explicitly list subjective
or external requirements that cannot be proven. Never claim that inferred checks prove the whole goal.
"""
        result = CodexAdapter(args.model).execute(prompt, repo, min(args.planning_seconds, args.wall_seconds), log_dir, planning=True, schema=schema)
        atomic_json(log_dir / "result.json", result.to_dict())
        if result.returncode != 0:
            raise ContractError(f"Planning failed; raw evidence: {log_dir}\n{result.message[-1500:]}")
        try:
            plan = json.loads(result.message)
        except ValueError as exc:
            raise ContractError(f"Planner returned invalid JSON; see {log_dir}") from exc
        if not isinstance(plan, dict):
            raise ContractError("Planner returned a non-object")
        for key in ("checks", "assumptions", "milestones", "limitations"):
            if key not in plan:
                raise ContractError(f"Planner omitted {key}")
            contract[key] = plan[key]
        contract["planning"] = result.to_dict()
    validate(contract)
    atomic_json(destination, contract)
    return contract


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="GoalPilot — missions persistantes, reprises et preuves vérifiables")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser('session', help='Protocole local dans la conversation appelante, sans modèle imbriqué', add_help=False)
    init = sub.add_parser("init", help="Transformer un goal en contrat (Codex read-only, sauf --checks)")
    init.add_argument("goal")
    init.add_argument("--repo", type=Path, required=True)
    init.add_argument("--output", type=Path, default=Path("mission.json"))
    init.add_argument("--checks", type=Path, help="JSON array of user-defined trusted check commands; skips remote planning")
    init.add_argument("--model")
    init.add_argument("--max-calls", type=int, default=4)
    init.add_argument("--wall-seconds", type=float, default=600)
    init.add_argument("--attempt-seconds", type=float, default=180)
    init.add_argument("--max-tokens", type=int, default=100000)
    init.add_argument("--planning-seconds", type=float, default=90)
    for name in ("run", "resume"):
        run = sub.add_parser(name, help="Exécuter ou reprendre avec Codex")
        run.add_argument("mission", type=Path)
        run.add_argument("--run-dir", type=Path, required=name == "resume")
        run.add_argument("--model")
        run.add_argument("--mode", choices=["supervised", "direct"], default="supervised")
    status = sub.add_parser("status", help="Afficher l'état et les mesures sans appel distant")
    status.add_argument("run_dir", type=Path)
    sub.add_parser('quota',help='Lire les fenêtres de quota du compte sans appel modèle')
    cont = sub.add_parser('continue', help='Reprendre une mission finish, même interrompue avant les premiers tests')
    cont.add_argument('run_dir', type=Path)
    report = sub.add_parser("report", help="Calculer les mesures et générer un rapport HTML autonome")
    report.add_argument("paths", nargs="+", type=Path)
    report.add_argument("--output", type=Path, default=Path("report.html"))
    bench = sub.add_parser("benchmark", help="Comparer Codex direct et supervisé sur des projets isolés")
    bench.add_argument("--live", action="store_true", help="Required: actually uses authenticated Codex and consumes usage")
    bench.add_argument("--output", type=Path, required=True)
    bench.add_argument("--model")
    bench.add_argument("--wall-seconds", type=float, default=120)
    bench.add_argument("--attempt-seconds", type=float, default=45)
    bench.add_argument("--max-calls", type=int, default=3)
    bench.add_argument("--max-tokens", type=int, default=30000)
    lab = sub.add_parser("lab", help="Évaluation déterministe des mécanismes, sans API (simulation explicite)")
    lab.add_argument("--output", type=Path, required=True)
    go=sub.add_parser('go',help='Réaliser, contre-vérifier les parcours utilisateur et corriger automatiquement')
    go.add_argument('goal')
    go.add_argument('--repo',type=Path,required=True)
    go.add_argument('--run-dir',type=Path,required=True)
    go.add_argument('--checks',type=Path,help='Optional trusted acceptance JSON; otherwise checks are inferred after implementation')
    go.add_argument('--wall-seconds',type=float,default=900)
    go.add_argument('--max-calls',type=int,default=5)
    go.add_argument('--max-tokens',type=int,default=1000000)
    go.add_argument('--max-uncached-tokens',type=int,help='Plafond souple entrée hors cache + sortie, vérifié entre appels ; compteur inconnu bloque les appels suivants')
    policy=go.add_mutually_exclusive_group()
    policy.add_argument('--fast',action='store_true',help='Ancienne boucle : tests proposés par le réalisateur, sans contre-vérification')
    policy.add_argument('--thorough',action='store_true',help='Contre-vérifier systématiquement, même après une première livraison vérifiable')
    go.add_argument('--model')
    go.add_argument('--cache-dir',type=Path,default=Path.home()/'.goalpilot/reuse',help='Réutilisation vérifiée des demandes et fichiers initiaux strictement identiques')
    go.add_argument('--no-reuse',action='store_true',help='Forcer une nouvelle réalisation même si une livraison identique a été vérifiée')
    return root


def main(argv=None) -> int:
    # Route the deterministic protocol before constructing any controller adapter.
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'hook-config':
        from .hook_config import main as setup_main
        return setup_main(argv[1:])
    if argv and argv[0] == 'hook':
        from .hooks import main as hook_main
        return hook_main(argv[1:])
    if argv and argv[0] == 'session':
        from .session import main as session_main
        return session_main(argv[1:])
    args = parser().parse_args(argv)
    try:
        if args.command == 'quota':
            from .quota import snapshot
            print(json.dumps(snapshot(),ensure_ascii=False,indent=2))
        elif args.command == "init":
            contract = initialize(args)
            print(f"Contrat : {args.output.resolve()}\nPérimètre : {contract['scope']} · {len(contract['checks'])} critères")
            if contract["scope"] == "inferred":
                print("Critères déduits par l'agent : les relire avant de les déclarer user_defined. Leur réussite ne prouve pas toute votre intention.")
            print("Les commandes de vérification seront exécutées localement avec vos droits. Inspectez les contrats provenant d'un tiers.")
        elif args.command in ("run", "resume"):
            contract = load_contract(args.mission.resolve())
            run_dir = args.run_dir or Path.home() / ".goalpilot" / "runs" / uuid.uuid4().hex[:12]
            print(f"Preuves : {run_dir.resolve()}", flush=True)
            if contract.get('creation_mode')=='direct-first':
                from .rpc import AppServerAdapter
                with AppServerAdapter(args.model or contract.get('model'),prepared=True) as adapter:
                    state=run_mission(contract,adapter,run_dir,resume=args.command=='resume',mode=args.mode,notify=lambda x:print(x,flush=True))
            else:
                state = run_mission(contract, CodexAdapter(args.model or contract.get("model")), run_dir, resume=args.command == "resume", mode=args.mode, notify=lambda x: print(x, flush=True))
            print(json.dumps(summarize(state), ensure_ascii=False, indent=2))
            return 0 if state["status"] in ("completed", "scope_passed") else 2
        elif args.command == "status":
            from .view import status
            state = status(args.run_dir)
            print(json.dumps(state, ensure_ascii=False, indent=2))
        elif args.command == 'continue':
            if (args.run_dir/'finish-run.json').exists():
                from .finish import continue_finish
                state = continue_finish(args.run_dir, notify=lambda x: print(x, flush=True))
            else:
                from .rpc import AppServerAdapter
                contract=load_contract(args.run_dir/'mission.json')
                with AppServerAdapter(contract.get('model'),prepared=True)as adapter:
                    state=run_mission(contract,adapter,args.run_dir,resume=True,notify=lambda x: print(x,flush=True))
            print(json.dumps(summarize(state), ensure_ascii=False, indent=2))
            return 0 if state['status'] in ('completed', 'scope_passed') else 2
        elif args.command == "report":
            paths = set()
            for path in args.paths:
                if path.is_file():
                    paths.add(path.resolve())
                else:
                    paths.update(p.resolve() for p in path.rglob("state.json"))
            if not paths:
                raise ContractError("No run state.json files found")
            report = aggregate([json.loads(p.read_text()) for p in sorted(paths)])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(html_report(report))
            atomic_json(args.output.with_suffix(".json"), report)
            print(f"HTML : {args.output.resolve()}\nJSON : {args.output.with_suffix('.json').resolve()}")
        elif args.command == "benchmark":
            if not args.live:
                raise ContractError("Specify --live to authorize real Codex calls. Unit tests require no API.")
            from .benchmark import benchmark
            result = benchmark(args)
            return 2 if result.get("benchmark_status") in ("agent_unavailable", "verification_unavailable", "interrupted", "adapter_error") else 0
        elif args.command == "lab":
            from .lab import run_lab
            run_lab(args.output)
        elif args.command=='go':
            from .autopilot import run_autopilot
            checks=json.loads(args.checks.read_text()) if args.checks else None
            from .finish import run_finish
            runner = run_autopilot if args.fast or checks is not None else run_finish
            options = {'checks': checks} if runner is run_autopilot else {'audit_policy': 'always' if args.thorough else 'on-interruption', 'review_context': 'fresh' if args.thorough else 'local', 'initial_effort': None if args.thorough else 'low', 'compact_delivery': not args.thorough}
            if runner is run_finish and not args.thorough and not args.no_reuse:
                from .reuse import run_cached_finish
                runner=run_cached_finish
                options['cache']=args.cache_dir
            state=runner(args.goal,args.repo,args.run_dir,wall_seconds=args.wall_seconds,
                max_calls=args.max_calls,max_tokens=args.max_tokens,model=args.model,
                max_uncached_tokens=args.max_uncached_tokens,**options,
                notify=lambda x:print(x,flush=True))
            print(json.dumps(summarize(state),ensure_ascii=False,indent=2))
            return 0 if state['status'] in ('completed','scope_passed') else 2
        return 0
    except (ContractError, OSError, ValueError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
