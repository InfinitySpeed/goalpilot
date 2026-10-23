"""Source-bound audit for the active Skill 1.11 promotion."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/skill-111-2026-10-23.json'
ARCHIVE = ROOT / 'reports/skill-111-evidence.zip'
POLICY = ROOT / 'PORTABLE_SKILL.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(report_path: Path = REPORT, root: Path = ROOT) -> dict:
    report_path = Path(report_path)
    root = Path(root)
    data = json.loads(report_path.read_text(encoding='utf-8'))
    policy = json.loads((root / 'PORTABLE_SKILL.json').read_text(encoding='utf-8'))
    active = policy['active_native_workflow']
    if data.get('version') != '1.11.0' or not data.get('promotable'):
        raise ValueError('not a promotable 1.11 report')
    if active.get('version') != '1.11.0':
        raise ValueError('active default is not 1.11.0')
    if active.get('benchmark') != report_path.relative_to(root).as_posix():
        raise ValueError('active benchmark path mismatch')
    if active.get('benchmark_sha256') != sha256(report_path):
        raise ValueError('active benchmark hash mismatch')
    if active.get('evidence_sha256') != sha256(root / 'reports/skill-111-evidence.zip'):
        raise ValueError('evidence archive hash mismatch')
    for name, expected in data['source_files'].items():
        if sha256(root / name) != expected or active['source_files'].get(name) != expected:
            raise ValueError(f'promoted source mismatch: {name}')
    means = data['per_case']
    for case in ('java-vague', 'typescript-vague', 'flowdesk'):
        for arm in ('candidate', 'current', 'previous'):
            item = means[case][arm]
            trials = item['trials']
            if len(trials) != 2 or not item['usage_complete']:
                raise ValueError(f'incomplete repeated measurements: {case}/{arm}')
            if any(not r['usage_complete'] for r in trials):
                raise ValueError(f'partial caller usage: {case}/{arm}')
            for key, field in (
                ('raw_tokens', 'raw_tokens_mean'),
                ('uncached_input_plus_output', 'uncached_input_plus_output_mean'),
                ('seconds', 'seconds_mean'),
            ):
                values = [r[key] if key in r else r['uncached_input_plus_output'] for r in trials]
                tolerance = 1e-3 if key == 'seconds' else 1e-8
                if not math.isclose(item[field], sum(values) / len(values), rel_tol=0, abs_tol=tolerance):
                    raise ValueError(f'trial mean mismatch: {case}/{arm}/{field}')
            if item['correct'] != sum(bool(r['independent_judge_passed']) for r in trials):
                raise ValueError(f'judge count mismatch: {case}/{arm}')
            if item['closed'] != sum(r['certified_closure'] is True for r in trials):
                raise ValueError(f'closure count mismatch: {case}/{arm}')
        for control in ('current', 'previous'):
            if means[case]['candidate']['uncached_input_plus_output_mean'] >= means[case][control]['uncached_input_plus_output_mean']:
                raise ValueError(f'uncached tokens did not improve: {case}/{control}')
    for arm in ('candidate', 'current', 'previous'):
        item = data['aggregate_equal_case_means'][arm]
        for field in ('raw_tokens_mean', 'uncached_input_plus_output_mean', 'seconds_mean'):
            expected = sum(means[c][arm][field] for c in ('java-vague', 'typescript-vague', 'flowdesk')) / 3
            if not math.isclose(item[field], expected, rel_tol=0, abs_tol=1e-8):
                raise ValueError(f'aggregate mismatch: {arm}/{field}')
    for arm in ('candidate', 'current', 'previous'):
        if data['aggregate_equal_case_means'][arm]['correct'] != 6 or data['aggregate_equal_case_means'][arm]['closed'] != 6 or data['aggregate_equal_case_means'][arm]['original_goal_preserved'] != 6:
            raise ValueError(f'completion or original-goal regression: {arm}')
    if data['candidate_change_pct_vs_1_9']['seconds'] > 3 or data['candidate_change_pct_vs_1_10']['seconds'] > 3:
        raise ValueError('time regression exceeds the 3% gate')
    if data['quota_savings_claimed'] is not False or not data['gates']['raw_tokens_are_not_used_as_quota_evidence']:
        raise ValueError('raw-token quota claim is forbidden')
    return data


if __name__ == '__main__':
    data = audit()
    print(json.dumps({'promotable': data['promotable'], 'version': data['version'], 'candidate_source_sha256': data['candidate_source_sha256']}, indent=2))
