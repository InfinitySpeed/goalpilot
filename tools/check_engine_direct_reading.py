"""Audit the frozen 0.15.0 direct-first diagnostic and its raw trial records."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/engine-direct-reading-2026-10-22.json'


def load(report, name):
    return json.loads((ROOT / report['evidence_paths'][name]).read_text())


def main():
    report = json.loads(REPORT.read_text())
    source_hash = hashlib.sha256((ROOT / 'goalpilot/autopilot.py').read_bytes()).hexdigest()
    assert source_hash == report['candidate_source_sha256'], 'Candidate prompt source changed'
    arms = {'candidate': [], 'old_goalpilot': [], 'native_codex': []}
    for case in ('flowdesk', 'stockroom'):
        for arm in arms:
            record = load(report, f'{case}_{arm}')
            usage = record['usage']
            assert usage['usage_complete'] and usage['calls_without_usage'] == 0
            if arm == 'candidate':
                assert record['status'] == 'scope_passed' and record['success']
                assert record['groups_passed'] == record['groups_total'] == 26
                assert all(item['passed'] for item in record['judgments'])
            else:
                assert record['artifact_success'] and len(record['judgments']) == 26
                assert all(item['passed'] for item in record['judgments'])
            arms[arm].append({
                'raw_tokens': usage['total_tokens'],
                'uncached_plus_output_tokens': usage['uncached_tokens'],
                'seconds': record['seconds'],
                'judge_groups_passed': record['groups_passed'] if arm == 'candidate'
                    else sum(item['passed'] for item in record['judgments']),
                'judge_groups_total': record['groups_total'] if arm == 'candidate'
                    else len(record['judgments']),
                'normal_closure': record.get('normal_exit', record['status'] == 'scope_passed'),
                'artifact_success': record.get('artifact_success', all(x['passed'] for x in record['judgments'])),
            })
    totals = {}
    for arm, rows in arms.items():
        totals[arm] = {
            key: sum(row[key] for row in rows)
            for key in ('raw_tokens', 'uncached_plus_output_tokens', 'seconds',
                        'judge_groups_passed', 'judge_groups_total')
        }
        totals[arm]['normal_closures'] = sum(row['normal_closure'] for row in rows)
        totals[arm]['artifact_successes'] = sum(row['artifact_success'] for row in rows)
    assert totals == report['totals'], 'Aggregate report does not match raw trial records'
    for base, result in report['savings_percent'].items():
        arm = base.removeprefix('candidate_vs_')
        for key in ('raw_tokens', 'uncached_plus_output_tokens', 'seconds'):
            expected = round(100 * (1 - totals['candidate'][key] / totals[arm][key]), 2)
            assert result[key] == expected, f'{base} {key} does not reconcile'
    assert totals['candidate']['normal_closures'] == totals['old_goalpilot']['normal_closures'] == 2
    assert totals['candidate']['artifact_successes'] == totals['old_goalpilot']['artifact_successes'] == 2
    assert totals['native_codex']['normal_closures'] == 0
    assert totals['native_codex']['artifact_successes'] == 2
    print('PASS: two candidate tasks, six raw records, source hash, closure and aggregates reconcile.')


if __name__ == '__main__':
    main()
