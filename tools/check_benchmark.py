"""Recompute published aggregates from retained rows; no network or model calls.

This checks arithmetic and source identity, not the unpublished raw provider logs.
"""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports/skill-131-summary'
TOKEN_KEYS = ('input_tokens', 'cached_input_tokens', 'uncached_input',
              'output_tokens', 'raw', 'uncached_plus_output')
ANCHORS = {'rental', 'invoices', 'documents', 'manufacturing'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label):
    require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-7), label)


def aggregate(rows):
    return {
        'executed': len(rows),
        'successful': sum(row['success'] for row in rows),
        'seconds': math.fsum(row['seconds'] for row in rows),
        'usage': {key: sum(row['usage'][key] for row in rows) for key in TOKEN_KEYS},
    }


def savings(candidate, control):
    return {
        key: 100 * (1 - (candidate['seconds'] if key == 'seconds' else candidate['usage'][key]) /
                     (control['seconds'] if key == 'seconds' else control['usage'][key]))
        for key in ('seconds', *TOKEN_KEYS)
    }


def verify_dataset(filename):
    data = json.loads((EVIDENCE / filename).read_text())
    rows = data['rows']
    require(data['complete'] and len(rows) == 44, 'Expected complete 44-row study')
    require(len({row['id'] for row in rows}) == 44, 'Duplicate row')
    for row in rows:
        usage = row['usage']
        require(row['meter_complete'] and not row['lower_bound'], row['id'] + ': incomplete meter')
        require(all(type(usage[key]) is int and usage[key] >= 0 for key in TOKEN_KEYS), 'Invalid counters')
        require(usage['cached_input_tokens'] <= usage['input_tokens'], 'Cache exceeds input')
        require(usage['uncached_input'] == usage['input_tokens'] - usage['cached_input_tokens'], 'Uncached arithmetic')
        require(usage['raw'] == usage['input_tokens'] + usage['output_tokens'], 'Raw arithmetic')
        require(usage['uncached_plus_output'] == usage['uncached_input'] + usage['output_tokens'], 'Combined arithmetic')
        require(row['success'] == bool(row['normal_closure'] and row['correct_artifact']), 'Success lifecycle')
        require(row['backend_model_calls'] == 0, 'Nested inference')
        close(row['seconds'], row['caller_seconds'] + row['judge_seconds'], 'Whole time accounting')
    totals = {}
    for arm, expected_count in [('new', 20), ('native', 20), ('old', 4)]:
        arm_rows = [row for row in rows if row['arm'] == arm]
        total = aggregate(arm_rows)
        require(total['executed'] == expected_count, arm + ': unexpected count')
        recorded = data['arms'][arm]
        require(total['successful'] == recorded['successful'], arm + ': completion aggregate')
        require(total['usage'] == recorded['known_usage'], arm + ': token aggregate')
        close(total['seconds'], recorded['seconds'], arm + ': time aggregate')
        totals[arm] = total
    new_cases = {row['case'] for row in rows if row['arm'] == 'new'}
    native_cases = {row['case'] for row in rows if row['arm'] == 'native'}
    require(new_cases == native_cases and len(new_cases) == 20, 'Twenty matched cases required')
    reduction = savings(totals['new'], totals['native'])
    for key, value in data['primary_matched']['saving_percent'].items():
        close(reduction[key], value, 'Published saving ' + key)
    require(totals['new']['successful'] >= max(18, totals['native']['successful']), 'Correct closure target')
    for key, minimum in [('seconds', 25), ('uncached_input', 45), ('output_tokens', 45)]:
        require(reduction[key] >= minimum, 'Accepted target ' + key)
    old_cases = {row['case'] for row in rows if row['arm'] == 'old'}
    require(old_cases == ANCHORS, 'Predefined old-skill anchors')
    new_anchor = aggregate([row for row in rows if row['arm'] == 'new' and row['case'] in ANCHORS])
    require(new_anchor['successful'] == totals['old']['successful'] == 4, 'Anchor closure preservation')
    anchor_reduction = savings(new_anchor, totals['old'])
    require(anchor_reduction['seconds'] >= 0 and anchor_reduction['uncached_plus_output'] >= 0, 'Anchor cost preservation')
    require(data['target_achieved'], 'Published target marker disagrees')
    return {'totals': totals, 'saving_percent': reduction, 'anchor_saving_percent': anchor_reduction}


def load_and_verify():
    original = verify_dataset('analysis.json')
    reviewed = verify_dataset('analysis-reviewed.json')
    old_data = json.loads((EVIDENCE / 'analysis.json').read_text())
    new_data = json.loads((EVIDENCE / 'analysis-reviewed.json').read_text())
    require(hashlib.sha256((EVIDENCE / 'analysis.json').read_bytes()).hexdigest() ==
            new_data['source_original_analysis_sha256'], 'Original analysis identity')
    old_rows = {row['id']: row for row in old_data['rows']}
    for row in new_data['rows']:
        old = old_rows[row['id']]
        require(row['usage'] == old['usage'] and row['caller_seconds'] == old['caller_seconds'], 'Review changed caller cost')
        require(row['normal_closure'] == old['normal_closure'], 'Review changed lifecycle')
        require(row['judge_seconds'] >= old['judge_seconds'], 'Review removed judging cost')
    measurement = json.loads((EVIDENCE / 'measurement.json').read_text())
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'goalpilot').glob('*.py')}
    current_matches = (actual == measurement['engine_files'] and
        hashlib.sha256((ROOT / 'skills/goalpilot/SKILL.md').read_bytes()).hexdigest() == measurement['skill_sha256'])
    reference = ROOT / 'benchmarks/codex-1.3.1'
    reference_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (reference/'goalpilot').glob('*.py')}
    require(reference_files == measurement['engine_files'], 'Archived measured engine differs')
    require(hashlib.sha256((reference/'SKILL.md').read_bytes()).hexdigest() == measurement['skill_sha256'], 'Archived measured instructions differ')
    bundle = ROOT / 'skills/goalpilot'
    bundled_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (bundle/'runtime/goalpilot').glob('*.py')}
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    bundle_matches = (bundled_files == measurement['engine_files'] and
        hashlib.sha256((bundle/'SKILL.md').read_bytes()).hexdigest() == measurement['skill_sha256'] and
        manifest['engine']['version'] == measurement['engine_version'] and
        manifest['skill_version'] == measurement['skill_version'] and
        manifest['measured_runtime_and_skill_parity'] is True)
    require(bundle_matches,
            'Archived Skill baseline differs from the measured treatment; never overwrite historical evidence')
    promoted = ROOT / 'PORTABLE_SKILL.json'
    current_is_new = promoted.is_file() and json.loads(promoted.read_text()).get('status') == 'promoted'
    return {'original': original, 'reviewed': reviewed, 'source_matches_measured': current_matches,
            'archived_skill_bundle_matches_measured': bundle_matches,
            'shipped_skill_matches_measured': bundle_matches and not current_is_new,
            'archived_measured_reference_verified': True}


if __name__ == '__main__':
    result = load_and_verify()
    print(json.dumps(result, indent=2))
    print('PASS: scoring definitions, aggregates, targets and archived measured-source identity. No model calls.')
