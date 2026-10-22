"""Small live integration benchmark, not evidence of general long-goal efficacy."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import textwrap
import time

from .adapters import CodexAdapter
from .engine import atomic_json, run_mission
from .metrics import aggregate, html_report
from .model import ContractError, digest


PREFIX = """import json, subprocess, sys, tempfile
from pathlib import Path
def call(*args):
    return subprocess.run([sys.executable, SCRIPT, *map(str,args)], capture_output=True, text=True, timeout=5)
"""


def check(ident: str, description: str, script: str, body: str) -> dict:
    return {"id": ident, "description": description,
            "command": [sys.executable, "-c", f"SCRIPT={script!r}\n" + PREFIX + textwrap.dedent(body)], "timeout_seconds": 15}


def fixtures() -> list[dict]:
    notes_checks = [
        check("persist", "Add and list preserve Unicode text, tags, and data across separate processes", "notes.py", """
        with tempfile.TemporaryDirectory() as d:
            store = Path(d)/'notes.json'
            p = call('--store', store, 'add', 'Réunion café', '--tag', 'travail')
            assert p.returncode == 0, p.stderr
            p = call('--store', store, 'list')
            assert p.returncode == 0, p.stderr
            notes = json.loads(p.stdout)
            assert len(notes)==1 and notes[0]['id']==1 and notes[0]['text']=='Réunion café' and notes[0]['tags']==['travail'], notes
        """),
        check("migration", "Preserve existing IDs and allocate max(id)+1; case-insensitive search", "notes.py", """
        with tempfile.TemporaryDirectory() as d:
            store = Path(d)/'notes.json'
            old = {'id':41,'text':'Ancienne NOTE','tags':['archive']}
            store.write_text(json.dumps([old]))
            p = call('--store', store, 'add', 'Nouvelle note')
            assert p.returncode==0, p.stderr
            p = call('--store', store, 'list')
            notes = json.loads(p.stdout)
            assert notes[0]==old and notes[1]['id']==42, notes
            p = call('--store', store, 'search', 'ancienne')
            assert p.returncode==0 and json.loads(p.stdout)==[old], p.stdout+p.stderr
        """),
        check("integrity", "Blank input and absent delete never corrupt data; export matches list", "notes.py", """
        with tempfile.TemporaryDirectory() as d:
            store = Path(d)/'notes.json'
            old = [{'id':8,'text':'keep','tags':[]}]
            store.write_text(json.dumps(old))
            p = call('--store', store, 'add', '   ')
            assert p.returncode==2, (p.returncode,p.stderr)
            assert json.loads(store.read_text())==old
            p = call('--store', store, 'delete', '999')
            assert p.returncode==1, p.returncode
            assert json.loads(store.read_text())==old
            p = call('--store', store, 'export')
            assert p.returncode==0 and json.loads(p.stdout)==old, p.stdout+p.stderr
            p = call('--store', store, 'delete', '8')
            assert p.returncode==0 and json.loads(store.read_text())==[], p.stderr
        """),
    ]
    ledger_checks = [
        check("precision", "Sum exact decimal cents including credits, emit fixed two-decimal strings", "ledger.py", """
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'data.csv'
            source.write_text('date,currency,amount\\n2026-01-01,EUR,0.10\\n2026-01-02,EUR,0.20\\n2026-01-03,EUR,-0.05\\n')
            p=call(source)
            assert p.returncode==0, p.stderr
            assert json.loads(p.stdout)=={'EUR':'0.25'}, p.stdout
        """),
        check("currencies", "Keep currencies separate; accept reordered headers and empty datasets", "ledger.py", """
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'data.csv'
            source.write_text('amount,date,currency\\n12.30,2026-01-01,EUR\\n8.00,2026-01-01,USD\\n-2.30,2026-01-02,EUR\\n')
            p=call(source)
            assert p.returncode==0 and json.loads(p.stdout)=={'EUR':'10.00','USD':'8.00'}, p.stdout+p.stderr
            source.write_text('date,currency,amount\\n')
            p=call(source)
            assert p.returncode==0 and json.loads(p.stdout)=={}, p.stdout+p.stderr
        """),
        check("validation", "Reject invalid rows atomically with exit 2, useful stderr, and no partial JSON", "ledger.py", """
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'data.csv'
            for row in ['2026-01-01,EUR,NaN', '2026-01-01,EUR,1.001', '2026-02-30,EUR,1.00', '2026-01-01,eu,1.00', '2026-01-01,USD,Infinity']:
                source.write_text('date,currency,amount\\n2026-01-01,EUR,3.00\\n'+row+'\\n')
                p=call(source)
                assert p.returncode==2 and not p.stdout.strip() and p.stderr.strip(), (row,p.returncode,p.stdout,p.stderr)
            source.write_text('currency,amount\\nEUR,1.00\\n')
            p=call(source)
            assert p.returncode==2 and not p.stdout.strip(), (p.returncode,p.stdout)
        """),
    ]
    return [
        {"name": "notes", "goal": "Finish this personal notes CLI so it is usable end-to-end. Use Python standard library. Commands: --store PATH add TEXT [--tag TAG repeatable], list, search QUERY, delete ID, export. Persist a JSON array of {id,text,tags}. Preserve existing records and allocate max ID + 1. Search text case-insensitively. List/search/export emit JSON to stdout. Blank text exits 2; nonexistent delete exits 1 without changing data; successful delete exits 0. Write concise usage documentation.",
         "files": {"notes.py": "import json\nprint(json.dumps([]))\n", "README.md": "# Notes\nUnfinished CLI. Preserve existing user notes.\n"}, "checks": notes_checks},
        {"name": "ledger", "goal": "Make this CSV expense summarizer reliable enough for personal bookkeeping, using Python standard library. Run python ledger.py PATH. Require date,currency,amount headers in any order; date must be real YYYY-MM-DD; currency must be three uppercase ASCII letters; amount must be a finite signed decimal with at most two fractional digits (no exponent notation). Sum independently per currency using exact decimals, include credits and output JSON mapping currency to fixed two-decimal strings. Empty input with valid headers gives {}. On any invalid input or unreadable file, exit 2, useful stderr, no partial stdout. Document usage.",
         "files": {"ledger.py": "import csv, json, sys\nrows=list(csv.DictReader(open(sys.argv[1])))\nprint(json.dumps({'TOTAL':sum(float(r['amount']) for r in rows)}))\n", "README.md": "# Ledger\nPrototype currently mixes currencies and uses floating point.\n"}, "checks": ledger_checks},
    ]


def benchmark(args) -> dict:
    root = args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError("Benchmark output must be a new or empty directory")
    root.mkdir(parents=True, exist_ok=True)
    budget = {"max_calls": args.max_calls, "wall_seconds": args.wall_seconds,
              "attempt_seconds": args.attempt_seconds, "max_tokens": args.max_tokens}
    manifest = {"started_at": time.time(), "kind": "live_microtask_integration", "budget_per_run": budget,
                "model_requested": args.model, "method": "Same initial files, goal, visible acceptance and wall/call/token ceilings. Direct gets one uninterrupted session using available wall time; supervised gets bounded attempts and check feedback. No planning phase in either condition.",
                "limitations": ["Two small standard-library tasks, not representative of long vague goals", "One trial per task and condition, no causal or general efficacy inference", "Token ceiling is soft and can be exceeded within one call", "No user satisfaction, historical failed goals, subscription quota or money measured"], "runs": []}
    atomic_json(root / "manifest.json", manifest)
    states = []
    adapter = CodexAdapter(args.model)
    for index, fixture in enumerate(fixtures()):
        # Counterbalance order to avoid always running the same condition first.
        modes = ("direct", "supervised") if index % 2 == 0 else ("supervised", "direct")
        for mode in modes:
            repo = root / "repos" / f"{fixture['name']}-{mode}"
            repo.mkdir(parents=True)
            for name, content in fixture["files"].items():
                (repo / name).write_text(content)
            contract = {"goal": fixture["goal"], "repo": str(repo), "scope": "user_defined", "checks": fixture["checks"], "budget": dict(budget)}
            contract_path = root / "contracts" / f"{fixture['name']}-{mode}.json"
            atomic_json(contract_path, contract)
            run_dir = root / "runs" / f"{fixture['name']}-{mode}"
            print(f"\nLIVE {fixture['name']} / {mode}", flush=True)
            state = run_mission(contract, adapter, run_dir, mode=mode, notify=lambda x: print(x, flush=True))
            states.append(state)
            manifest["runs"].append({"task": fixture["name"], "mode": mode, "state": str(run_dir / "state.json"), "acceptance_hash": digest(fixture["checks"]), "seed_hash": digest(fixture["files"]), "status": state["status"]})
            atomic_json(root / "manifest.json", manifest)
            report = aggregate(states)
            atomic_json(root / "report.json", report)
            (root / "report.html").write_text(html_report(report))
            print(f"Result: {state['status']} · {state['usage']['total_tokens']} reported tokens · {state['active_seconds']:.3f}s", flush=True)
            if state["status"] in ("agent_unavailable", "verification_unavailable", "interrupted", "adapter_error"):
                manifest["stopped_early"] = state["status"] + "; no blind retries or remaining runs"
                report["benchmark_status"] = state["status"]
                atomic_json(root / "manifest.json", manifest)
                atomic_json(root / "report.json", report)
                (root / "report.html").write_text(html_report(report))
                return report
    manifest["finished_at"] = time.time()
    atomic_json(root / "manifest.json", manifest)
    print(f"\nReport: {root / 'report.html'}", flush=True)
    return report
