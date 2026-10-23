"""Recompute the prospective extension study; never hide individual regressions."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

ARMS = ('native', 'previous', 'current')


def summarize(rows):
    if len(rows) != 12 or len({(r['case'], r['arm']) for r in rows}) != 12:
        raise ValueError('Expected twelve unique case/arm outcomes, with no substitutions')
    cases = sorted({r['case'] for r in rows})
    if len(cases) != 4 or {(r['case'], r['arm']) for r in rows} != {(c, a) for c in cases for a in ARMS}:
        raise ValueError('Expected the same four cases for all three arms')
    totals = {}
    for arm in ARMS:
        chosen = [r for r in rows if r['arm'] == arm]
        for row in chosen:
            if type(row['correct']) is not bool or not isinstance(row['seconds'], (int, float)) or not math.isfinite(row['seconds']) or row['seconds'] <= 0:
                raise ValueError('Invalid outcome or duration')
            u = row['usage']
            fields = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'total_tokens', 'uncached_tokens')
            if any(type(u[x]) is not int or u[x] < 0 for x in fields) or u['cached_input_tokens'] > u['input_tokens'] or not u.get('usage_complete'):
                raise ValueError('Incomplete or invalid provider usage')
            if u['total_tokens'] != u['input_tokens'] + u['output_tokens'] or u['uncached_tokens'] != u['total_tokens'] - u['cached_input_tokens']:
                raise ValueError('Usage arithmetic mismatch')
        totals[arm] = {
            'business_passed': sum(r['correct'] for r in chosen),
            'certified': None if arm == 'native' else sum(r['certified'] is True for r in chosen),
            'raw_tokens': sum(r['usage']['total_tokens'] for r in chosen),
            'uncached_tokens': sum(r['usage']['uncached_tokens'] for r in chosen),
            'seconds': sum(r['seconds'] for r in chosen),
        }
    comparisons = {}
    for control in ('native', 'previous'):
        current = totals['current']; baseline = totals[control]
        comparisons[control] = {key + '_saving_pct': 100 * (1 - current[key] / baseline[key]) for key in ('raw_tokens', 'uncached_tokens', 'seconds')}
    regressions = []
    for case in cases:
        current = next(r for r in rows if r['case'] == case and r['arm'] == 'current')
        for control in ('native', 'previous'):
            baseline = next(r for r in rows if r['case'] == case and r['arm'] == control)
            losses = []
            if baseline['correct'] and not current['correct']:
                losses.append('business_completion')
            for key in ('total_tokens', 'uncached_tokens'):
                if current['usage'][key] > baseline['usage'][key]:
                    losses.append(key)
            if current['seconds'] > 1.03 * baseline['seconds']:
                losses.append('seconds_gt_3pct')
            if losses:
                regressions.append({'case': case, 'control': control, 'metrics': losses})
    gates = {
        'current_business_4_of_4': totals['current']['business_passed'] == 4,
        'current_certified_4_of_4': totals['current']['certified'] == 4,
        'goals_preserved': all(r['goal_preserved'] is True for r in rows if r['arm'] == 'current'),
        'aggregate_tokens_no_regression': all(totals['current'][k] <= totals[a][k] for a in ('native', 'previous') for k in ('raw_tokens', 'uncached_tokens')),
        'aggregate_time_within_3pct': all(totals['current']['seconds'] <= 1.03 * totals[a]['seconds'] for a in ('native', 'previous')),
        'uniform_per_case_no_regression': not regressions,
        'universal_claim_established': False,
    }
    return {'totals': totals, 'comparisons': comparisons, 'per_case_regressions': regressions, 'gates': gates}


def audit(report, evidence=None):
    if report.get('schema_version') != 1:
        raise ValueError('Unknown report schema')
    result = summarize(report['rows'])
    if report['summary'] != result:
        raise ValueError('Published summary does not match the outcomes')
    if evidence:
        if hashlib.sha256(evidence.read_bytes()).hexdigest() != report['evidence']['sha256']:
            raise ValueError('Evidence archive digest mismatch')
        with zipfile.ZipFile(evidence) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise ValueError('Duplicate archive members')
            if set(archive.namelist()) != set(report['evidence']['files']):
                raise ValueError('Evidence inventory mismatch')
            for name, sha in report['evidence']['files'].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != sha:
                    raise ValueError('Evidence file digest mismatch: ' + name)
            protocol = json.loads(archive.read('study/protocol.json'))
            if protocol != report['protocol'] or set(protocol['cases']) != {r['case'] for r in report['rows']}:
                raise ValueError('Frozen protocol mismatch')
            policy = json.loads(archive.read('inputs/current/PORTABLE_SKILL.json'))
            if policy['native_workflow']['version'] != report['skill_version']:
                raise ValueError('Measured skill version mismatch')
            for prefix, measured in (('inputs/current/', policy['native_workflow']['source_files']), ('inputs/previous/', policy['measured_files'])):
                for name, sha in measured.items():
                    if hashlib.sha256(archive.read(prefix + name)).hexdigest() != sha:
                        raise ValueError('Frozen measured source changed: ' + name)
            for path, sha in protocol['source_sha256'].items():
                filename = PurePosixPath(path).name
                name = 'study/' + filename if filename in ('cases.py', 'worker.py') else 'inputs/current/integrations/native/' + filename
                if hashlib.sha256(archive.read(name)).hexdigest() != sha:
                    raise ValueError('Preregistered source changed: ' + path)
            for name, field in (('judge-positive-controls.json', 'reference_accepted'), ('judge-negative-controls.json', 'unimplemented_rejected')):
                controls = json.loads(archive.read('study/' + name))
                if set(controls) != set(protocol['cases']) or not all(r[field] is True for r in controls.values()):
                    raise ValueError('Judge controls failed')
            for row in report['rows']:
                prefix = 'trials/' + row['case'] + '-' + row['arm'] + '/'
                if json.loads(archive.read(prefix + 'result.json')) != row:
                    raise ValueError('Outcome receipt mismatch')
                integrity = json.loads(archive.read(prefix + 'post-run-integrity.json'))
                if integrity['changed_original_tests_or_headers'] or integrity['changed_installed_skill_files']:
                    raise ValueError('Original tests, ABI or installed skill changed')
                updates = [json.loads(line) for line in archive.read(prefix + 'usage.jsonl').decode().splitlines()]
                if not updates:
                    raise ValueError('Provider usage notifications missing')
                final = updates[-1]['params']['tokenUsage']['total']
                for public, provider in (('input_tokens', 'inputTokens'), ('output_tokens', 'outputTokens'), ('cached_input_tokens', 'cachedInputTokens')):
                    if row['usage'][public] != final[provider]:
                        raise ValueError('Provider usage mismatch')
    return result


def replay(report, evidence):
    """Explicitly execute the archived delivered programs and frozen judges."""
    audit(report, evidence)
    results = []
    with zipfile.ZipFile(evidence) as archive:
        for row in report['rows']:
            prefix = 'trials/' + row['case'] + '-' + row['arm'] + '/repo/'
            with tempfile.TemporaryDirectory(prefix='goalpilot-extension-replay-') as tmp:
                work = Path(tmp)
                for name in report['evidence']['files']:
                    if not name.startswith(prefix):
                        continue
                    relative = PurePosixPath(name[len(prefix):])
                    if relative.is_absolute() or '..' in relative.parts or not relative.parts or '\\' in str(relative):
                        raise ValueError('Unsafe delivered file path')
                    path = work / str(relative)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(name))
                spec = json.loads(archive.read('judges/' + row['case'] + '.json'))
                filename = spec['filename']
                if PurePosixPath(filename).name != filename or '\\' in filename:
                    raise ValueError('Unsafe judge file path')
                (work / filename).write_text(spec['source'], encoding='utf-8')
                run = subprocess.run(spec['argv'], cwd=work, capture_output=True, text=True, timeout=45)
                correct = run.returncode == 0
                result = {'case': row['case'], 'arm': row['arm'], 'correct': correct, 'matches_recorded_outcome': correct == row['correct']}
                if not result['matches_recorded_outcome']:
                    result['log'] = run.stdout + run.stderr
                results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--replay', action='store_true', help='Execute trusted archived delivered code and judges locally; no model calls')
    parser.add_argument('--require-improvement', action='store_true')
    parser.add_argument('--require-per-case', action='store_true')
    args = parser.parse_args()
    try:
        result = audit(json.loads(args.report.read_text(encoding='utf-8')), args.evidence)
        if args.replay:
            if not args.evidence:
                raise ValueError('--replay requires --evidence')
            result['replay'] = replay(json.loads(args.report.read_text(encoding='utf-8')), args.evidence)
        print(json.dumps(result, indent=2))
        gates = result['gates']
        required = ('current_business_4_of_4', 'current_certified_4_of_4', 'goals_preserved', 'aggregate_tokens_no_regression', 'aggregate_time_within_3pct')
        return int(bool(args.require_improvement and not all(gates[k] for k in required) or args.require_per_case and not gates['uniform_per_case_no_regression'] or args.replay and not all(r['matches_recorded_outcome'] for r in result['replay'])))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
