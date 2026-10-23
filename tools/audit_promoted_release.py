#!/usr/bin/env python3
"""Audit the frozen release offline using its preregistered checker and evidence."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil,tempfile,zipfile


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path(__file__).resolve().parents[1]/'PROMOTED_ENGINE.json')
    args=parser.parse_args();root=args.manifest.resolve().parent
    release=json.loads(args.manifest.read_text());assert release['status']=='promoted'
    report_path=root/release['report'];assert sha(report_path)==release['report_sha256']
    report=json.loads(report_path.read_text());data=root/'reports/engine-promotion-2026-10-23'
    protocol=json.loads((data/'protocol.json').read_text());assert sha(data/'protocol.json')==release['protocol_sha256']
    assert sha(data/'controls.json')==protocol['controls_sha256']
    checker=data/'frozen-promotion-auditor.py';assert sha(checker)==protocol['promotion_auditor_sha256']
    spec=importlib.util.spec_from_file_location('frozen_gate',checker);gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    # Relocate only a historical file path. Keep the original sealed protocol,
    # checker, source, data, outcomes, thresholds and counters unchanged.
    with tempfile.TemporaryDirectory(prefix='goalpilot-release-audit-')as tmp:
        copied=Path(tmp)
        for name in ('source','harness','trials'):shutil.copytree(data/name,copied/name)
        local_protocol={**protocol,'controls_path':str((data/'controls.json').resolve())}
        (copied/'protocol.json').write_text(json.dumps(local_protocol))
        actual=gate.analyze(copied)
    for key in ('metrics','saving_percent','gates','source_hashes','promotable'):
        assert actual[key]==report[key],key
    assert actual['promotable'] and all(actual['gates'].values())
    for row in report['per_case']:
        trial=data/'trials'/row['case'];assert sha(trial/'result.json')==row['record_sha256']
        record=json.loads((trial/'result.json').read_text())
        log=trial/('reviewed-judge'if row['case']in ('annotations','subscriptions')else 'strict-judge')/'judge.log'
        groups=[s[5:]for s in log.read_text().splitlines()if s.startswith('PASS ')]
        assert groups==record['reviewed_judge']['groups_passed']
    artifact=root/release['archive'];assert sha(artifact)==release['archive_sha256']
    with zipfile.ZipFile(artifact)as archive:
        manifest=json.loads(archive.read('GOALPILOT-FROZEN.json'))
        contents={name:hashlib.sha256(archive.read(name)).hexdigest()for name in archive.namelist()if not name.endswith('/')and name!='GOALPILOT-FROZEN.json'}
    assert contents==protocol['source_hashes']==release['source_hashes']
    assert manifest['protocol_sha256']==release['protocol_sha256']and manifest['status']=='promoted'
    assert sha(root/release['launcher_snapshot'])==release['launcher_sha256']
    print('PASS: frozen ZIP, launcher, 20 complete provider meters, judgments and every promotion gate reconcile offline. Model calls: 0.')
    return 0
if __name__=='__main__':raise SystemExit(main())
