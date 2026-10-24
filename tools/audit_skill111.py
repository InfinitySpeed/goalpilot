"""Source-bound audit for the active Skill 1.11 promotion."""
from __future__ import annotations
import hashlib
import json
import math
import zipfile
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
    archive_path = root / 'reports/skill-111-evidence.zip'
    if sha256(archive_path) != '080576079de83ad9e14007a72162b8fe0c51bf7cec9ecd2fc8c5d5198b30e73b':
        raise ValueError('historical 1.11 evidence archive hash mismatch')
    if active.get('version') == '1.11.0':
        if active.get('benchmark') != report_path.relative_to(root).as_posix() or active.get('benchmark_sha256') != sha256(report_path):
            raise ValueError('active 1.11 benchmark pointer mismatch')
        if active.get('evidence_sha256') != sha256(archive_path):
            raise ValueError('active 1.11 evidence hash mismatch')
    # Once superseded, validate historical source bytes from its immutable evidence archive.
    with zipfile.ZipFile(archive_path) as zf:
        archived = {n: hashlib.sha256(zf.read('promoted-source/' + n)).hexdigest()
                    for n in data['source_files'] if 'promoted-source/' + n in zf.namelist()}
    for name, expected in data['source_files'].items():
        live = sha256(root / name)
        if live != expected and archived.get(name) != expected:
            raise ValueError(f'historical promoted source mismatch: {name}')
        if active.get('version') == '1.11.0' and active['source_files'].get(name) != expected:
            raise ValueError(f'active promoted source mismatch: {name}')
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
    matched = data['native_matched_all_tasks']
    for case in ('java-vague', 'typescript-vague', 'flowdesk'):
        native = means[case]['native']
        if len(native['trials']) != 2 or not native['usage_complete']:
            raise ValueError(f'incomplete matched native runs: {case}')
        if native['correct'] != 2 or any(not r['independent_judge_passed'] or not r['usage_complete'] for r in native['trials']):
            raise ValueError(f'native judge or usage failure: {case}')
        if case == 'flowdesk' and native['judge_groups_passed'] != native['judge_groups_total']:
            raise ValueError('native Flowdesk behavior checks did not all pass')
    for arm in ('candidate', 'native'):
        values = [means[c][arm] for c in ('java-vague', 'typescript-vague', 'flowdesk')]
        aggregate = matched['arms'][arm]
        for field in ('uncached_input_plus_output_mean', 'seconds_mean'):
            key = 'uncached_input_plus_output_mean' if field == 'uncached_input_plus_output_mean' else 'seconds_mean'
            expected = sum(x[field] for x in values) / 3
            if not math.isclose(aggregate[key], expected, rel_tol=0, abs_tol=1e-8):
                raise ValueError(f'matched native aggregate mismatch: {arm}/{field}')
    expected_uncached = 100 * (1 - matched['arms']['candidate']['uncached_input_plus_output_mean'] / matched['arms']['native']['uncached_input_plus_output_mean'])
    expected_time = 100 * (1 - matched['arms']['candidate']['seconds_mean'] / matched['arms']['native']['seconds_mean'])
    if not math.isclose(matched['candidate_change_vs_native']['uncached_reduction_pct'], expected_uncached, abs_tol=1e-8):
        raise ValueError('native uncached-token comparison mismatch')
    if not math.isclose(matched['candidate_change_vs_native']['elapsed_time_reduction_pct'], expected_time, abs_tol=1e-8):
        raise ValueError('native elapsed-time comparison mismatch')
    if data['candidate_change_pct_vs_1_9']['seconds'] > 3 or data['candidate_change_pct_vs_1_10']['seconds'] > 3:
        raise ValueError('time regression exceeds the 3% gate')
    if data['quota_savings_claimed'] is not False or not data['gates']['raw_tokens_are_not_used_as_quota_evidence']:
        raise ValueError('raw-token quota claim is forbidden')
    return data


if __name__ == '__main__':
    data = audit()
    print(json.dumps({'promotable': data['promotable'], 'version': data['version'], 'candidate_source_sha256': data['candidate_source_sha256']}, indent=2))
