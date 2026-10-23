#!/usr/bin/env python3
"""Validate the recorded direct-first 20-goal benchmark summary."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/engine-direct-20-2026-10-22.json'
CONTROL = Path('/workspace/goalpilot-research/thin-skill-002/analysis-reviewed.json')


def main():
    report = json.loads(REPORT.read_text(encoding='utf-8'))
    control = json.loads(CONTROL.read_text(encoding='utf-8'))
    assert hashlib.sha256(CONTROL.read_bytes()).hexdigest() == report['frozen_control_sha256']
    candidate = report['candidate']
    rows = report['per_case']
    assert len(rows) == candidate['cases'] == 20
    assert [row['case'] for row in rows] == report['cases_in_historical_order']
    assert len(set(report['cases_in_historical_order'])) == 20
    assert all(row['tokens']['meter_complete'] for row in rows)
    assert all(row['engine_normal_closure'] for row in rows)
    for key in ('input', 'cached_input', 'uncached_input', 'output',
                'raw_input_plus_output', 'uncached_input_plus_output'):
        assert sum(row['tokens'][key] for row in rows) == candidate[key], key
    assert candidate['independent_correct'] == sum(row['independent_judge_passed'] for row in rows) == 18
    assert candidate['normal_closures'] == 20 and candidate['meter_complete']
    assert abs(sum(row['elapsed_seconds_including_judge'] for row in rows) - candidate['elapsed_seconds_including_judge']) < 1e-6
    for arm in ('new', 'native'):
        frozen = control['arms'][arm]
        assert frozen['successful'] == report['frozen_controls'][arm]['independent_correct']
        assert frozen['known_usage']['raw'] == report['frozen_controls'][arm]['tokens']['raw_input_plus_output']
        assert frozen['known_usage']['uncached_plus_output'] == report['frozen_controls'][arm]['tokens']['uncached_input_plus_output']
        assert frozen['seconds'] == report['frozen_controls'][arm]['elapsed_seconds_including_judge']
    assert report['candidate_vs_codex_native']['time_saving_percent'] < 25
    assert report['candidate_vs_codex_native']['uncached_input_plus_output_saving_percent'] < 45
    assert report['target_result']['overall'] == 'NOT MET'
    print('PASS: 20 cases, independent judgments, complete meters, totals, frozen anchors, and thresholds reconcile.')


if __name__ == '__main__':
    main()
