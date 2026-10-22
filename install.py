#!/usr/bin/env python3
"""Install GoalPilot for coding hosts, offline and without changing host settings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'skills/goalpilot'
ADAPTERS = ROOT / 'integrations/portable'
HOSTS = ('codex', 'claude-code', 'antigravity')


def base_installer():
    spec = importlib.util.spec_from_file_location('goalpilot_bundle_installer', SOURCE / 'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def destinations(host, target=None):
    if target is not None:
        if host == 'all':
            raise ValueError('--target requires a single --host')
        return [(host, target.expanduser().absolute())]
    hosts = HOSTS if host == 'all' else (host,)
    folders = {'codex': ('.agents/skills',), 'claude-code': ('.claude/skills',),
               'antigravity': ('.gemini/config/skills', '.gemini/antigravity-cli/skills')}
    return [(name, Path.home() / folder / 'goalpilot') for name in hosts for folder in folders[name]]


def preflight(target):
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlink: ' + str(target))
    if target.exists():
        previous = json.loads((target / 'MANIFEST.json').read_text())
        if not isinstance(previous, dict) or previous.get('package') != 'goalpilot-codex-skill':
            raise ValueError('Destination belongs to another skill: ' + str(target))


def portable_bundle(destination, host):
    shutil.copytree(SOURCE, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ADAPTERS / 'SKILL.md', destination / 'SKILL.md')
    shutil.copy2(ADAPTERS / 'host.py', destination / 'scripts/host.py')
    manifest = json.loads((destination / 'MANIFEST.json').read_text())
    manifest.update(host_profile=host, adapter_version='1.0.0',
                    completion_mode='explicit-session-finish', entry_point='scripts/host.py',
                    measured_runtime_and_skill_parity=False,
                    post_measurement_metadata_only=[],
                    adapter_files=['SKILL.md', 'scripts/host.py', 'references/measurements.json', 'references/baseline.json'],
                    meter_scope='This host adapter has not been benchmarked. Retained performance evidence concerns the historical Codex integration only. Local verification launches no models; calling-agent usage remains unknown without external metering.')
    measurement = destination / 'references/measurements.json'
    if measurement.exists():
        data = json.loads(measurement.read_text())
        data.update(applies_to_current_bundle=False, host_profile=host,
                    host_adapter_benchmarked=False, reference_host='codex',
                    current_runtime_matches_reference=True,
                    current_skill_instructions_match_reference=False)
        measurement.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    baseline = destination / 'references/baseline.json'
    if baseline.exists():
        data = json.loads(baseline.read_text())
        data['current_measurement_applies'] = False
        data['source_note'] = 'Historical Codex evidence only. This host adapter has no measured performance claim.'
        data.get('accepted_future_targets', {})['achieved'] = False
        baseline.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    manifest['files'] = {
        str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(destination.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
        and p != destination / 'MANIFEST.json'
    }
    (destination / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description='Install GoalPilot for Codex, Claude Code and Antigravity; no network or model calls.')
    parser.add_argument('--host', choices=(*HOSTS, 'all'), default='all', help='Host to install for (default: all).')
    parser.add_argument('--target', type=Path, help='Custom skill directory for a single selected host.')
    parser.add_argument('--dry-run', action='store_true', help='Validate and print the installation plan without writing files.')
    args = parser.parse_args()
    try:
        installer = base_installer()
        installer.validate(SOURCE)
        plan = destinations(args.host, args.target)
        for host, target in plan:
            if host != 'codex' and target.resolve() == SOURCE.resolve():
                raise ValueError('A portable adapter cannot replace the source Codex bundle')
            preflight(target)
        if args.dry_run:
            result = {'dry_run': True, 'model_calls': 0,
                      'destinations': [{'host': host, 'path': str(target)} for host, target in plan]}
        else:
            installed = []
            with tempfile.TemporaryDirectory(prefix='goalpilot-host-install-') as tmp:
                bundles = {'codex': SOURCE}
                for host, target in plan:
                    if host not in bundles:
                        bundles[host] = portable_bundle(Path(tmp) / host, host)
                    result = installer.install(bundles[host], target)
                    installed.append({'host': host, **result,
                                      'invocation': '$goalpilot' if host == 'codex' else '/goalpilot' if host == 'claude-code' else 'Ask the IDE to use GoalPilot; /goalpilot in the CLI',
                                      'verification': 'Codex Stop hooks when configured; explicit finish otherwise' if host == 'codex' else 'Explicit local verification in the calling session'})
            result = {'installed': installed, 'model_calls': 0,
                      'host_settings_changed': False,
                      'note': 'Reload skill discovery or restart the host. Codex automatic Stop hooks are optional and configured separately. All hosts retain the Python/POSIX verification requirements.'}
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'Installation refused: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
