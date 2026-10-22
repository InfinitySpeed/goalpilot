"""Behavioral checks withheld from coding sessions; deterministic and reproducible."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from goalpilot.benchmark import check
from goalpilot.engine import atomic_json
from goalpilot.model import digest
from goalpilot.process import run_process


def holdouts() -> dict[str, list[dict]]:
    notes = [check("notes-unseen-workflow", "Unseen Unicode notes, nonconsecutive IDs, repeated tags, search, delete and export", "notes.py", """
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/'store.json'
            seed=[{'id':3,'text':'Keep this original','tags':['old']},{'id':17,'text':'Another original','tags':[]}]
            store.write_text(json.dumps(seed))
            texts=['ÉTÉ à Lyon','café et thé','Semaine 42','旅の記録','Alpha beta','Ligne un\\nLigne deux','Oiseaux 🐦','Réunion']
            for text in texts:
                p=call('--store',store,'add',text,'--tag','perso','--tag','à revoir')
                assert p.returncode==0,p.stderr
            p=call('--store',store,'list')
            assert p.returncode==0,p.stderr
            records=json.loads(p.stdout)
            assert len(records)==10 and records[:2]==seed,records
            added=records[2:]
            assert [x['id'] for x in added]==list(range(18,26)),added
            assert [x['text'] for x in added]==texts,added
            assert all(x['tags']==['perso','à revoir'] for x in added),added
            p=call('--store',store,'search','été')
            assert p.returncode==0 and [x['text'] for x in json.loads(p.stdout)]==[texts[0]],p.stdout+p.stderr
            before=store.read_bytes()
            p=call('--store',store,'search','absent-needle-4539')
            assert p.returncode==0 and json.loads(p.stdout)==[],p.stdout+p.stderr
            assert store.read_bytes()==before
            p=call('--store',store,'delete','20')
            assert p.returncode==0,p.stderr
            p=call('--store',store,'export')
            remaining=json.loads(p.stdout)
            assert p.returncode==0 and len(remaining)==9 and all(x['id']!=20 for x in remaining),remaining
            assert remaining[:2]==seed
        """)]
    ledger = [
        check("ledger-unseen-data", "Seeded decimal totals across three currencies and shuffled headers", "ledger.py", """
        import random
        from decimal import Decimal
        rng=random.Random(20261021)
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'input.csv'
            totals={k:Decimal('0') for k in ['EUR','USD','JPY']}
            lines=['amount,currency,date']
            for i in range(60):
                currency=rng.choice(list(totals))
                value=Decimal(rng.randrange(-99999,99999))/100
                totals[currency]+=value
                lines.append(f'{value:.2f},{currency},2026-03-{1+i%28:02d}')
            source.write_text('\\n'.join(lines)+'\\n')
            p=call(source)
            expected={k:format(v,'.2f') for k,v in totals.items()}
            assert p.returncode==0 and json.loads(p.stdout)==expected,(p.returncode,p.stdout,p.stderr,expected)
        """),
        check("ledger-unseen-invalid", "Reject unseen malformed amounts, dates and currencies without partial output", "ledger.py", """
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'invalid.csv'
            for row in ['2026-01-01,EUR,1e2','2026-01-01,EUR,--2','2025-02-29,USD,3.00','2026-01-01,EUR,1.234','2026-01-01,€UR,3.00']:
                source.write_text('date,currency,amount\\n2026-01-01,EUR,1.00\\n'+row+'\\n')
                p=call(source)
                assert p.returncode==2 and not p.stdout.strip() and p.stderr.strip(),(row,p.returncode,p.stdout,p.stderr)
        """),
    ]
    return {"notes": notes, "ledger": ledger}


def freeze(destination: Path) -> dict:
    spec = {"created_at": time.time(), "seed": 20261021, "checks": holdouts(),
            "method": "Post-run behavioral checks, not included in agent prompts or recovery feedback. Task-level sample size is the number of projects, not the number of assertions."}
    spec["checks_hash"] = digest(spec["checks"])
    atomic_json(destination, spec)
    return spec


def evaluate_benchmark(root: Path, spec: dict) -> dict:
    if spec["checks_hash"] != digest(spec["checks"]):
        raise ValueError("Frozen holdout specification changed")
    manifest = json.loads((root / "manifest.json").read_text())
    results = []
    for record in manifest["runs"]:
        state = json.loads(Path(record["state"]).read_text())
        evidence = root / "holdout-evidence" / f"{record['task']}-{record['mode']}"
        evidence.mkdir(parents=True, exist_ok=True)
        checks = []
        for index, criterion in enumerate(spec["checks"][record["task"]]):
            result = run_process(criterion["command"], Path(state["contract"]["repo"]), criterion["timeout_seconds"], log_path=evidence / f"check-{index+1}.log")
            checks.append({"id": criterion["id"], "passed": result.returncode == 0,
                           "output": result.output[-2000:], "duration_seconds": result.duration_seconds})
        results.append({"task": record["task"], "mode": record["mode"], "status": state["status"],
                        "all_holdouts_passed": all(x["passed"] for x in checks), "checks": checks})
    report = {"kind": "live_solution_holdout_evaluation", "spec_hash": spec["checks_hash"], "results": results}
    atomic_json(root / "holdouts.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--spec", type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze(args.freeze)
        print(args.freeze)
    elif args.benchmark and args.spec:
        print(json.dumps(evaluate_benchmark(args.benchmark, json.loads(args.spec.read_text())), ensure_ascii=False, indent=2))
    else:
        parser.error("Use --freeze PATH or --benchmark PATH --spec PATH")
