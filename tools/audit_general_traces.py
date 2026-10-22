"""Check frozen evidence and counters; does not make model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.general.campaign import fingerprint,read_records,events,telemetry
from goalpilot.engine import atomic_json


def run(output):
    output=Path(output).resolve();manifest=json.loads((output/'manifest.json').read_text())
    rows=read_records(output,manifest)
    results=[];suspects=[]
    for row in rows:
        trial=output/'trials'/row['id'];observed=telemetry(trial)['usage_lower_bound']
        usage_matches=all(observed[k]==row['usage'][k] for k in ('input_tokens','output_tokens','cached_input_tokens')) if row['usage']['usage_complete'] else None
        results.append({'trial':row['id'],'usage_complete':row['usage']['usage_complete'],'counters_match_raw_notifications':usage_matches})
        for packet in events(trial):
            if packet.get('method')!='item/completed':continue
            item=packet.get('params',{}).get('item',{})
            if item.get('type')!='commandExecution':continue
            command=item.get('command') or ''
            if any(marker in command for marker in ('evaluation/general','oracle_desk','oracle_queue','oracle_vault','/source_snapshot/')):
                suspects.append({'trial':row['id'],'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'reason':'potential benchmark-source reference; requires review'})
    source_ok=fingerprint()==manifest['source_fingerprint']
    snapshot_ok=all(hashlib.sha256((output/'source_snapshot'/name).read_bytes()).hexdigest()==sha for name,sha in manifest['source_fingerprint'].items())
    first='desk-r1-direct';pilot=output.parent/'general-pilot-001'
    original_preserved=all((pilot/'trials'/first/f'judge-{i}.json').read_bytes()==(output/'trials'/first/f'judge-{i}.json').read_bytes() for i in (1,2))
    result={'kind':'raw_evidence_audit','model_calls':0,'source_unchanged':source_ok,
        'snapshot_integrity':snapshot_ok,'preregistered_protocol_unchanged':manifest==json.loads((output/'preregistered-protocol.json').read_text()),
        'imported_first_judgments_preserved_verbatim':original_preserved,'trials':results,
        'potential_benchmark_source_references':suspects,
        'limits':'Command-text audit only; does not prove absence of every possible read outside the repository.'}
    atomic_json(output/'trace-audit.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=run(a.output);print(json.dumps(r,indent=2))
