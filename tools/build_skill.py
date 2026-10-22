"""Build the portable skill with its pinned, tested embedded engine."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def engine_version(source):
    tree=ast.parse((Path(source)/'__init__.py').read_text())
    for node in tree.body:
        if isinstance(node,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='__version__'for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f'No literal __version__ in {source}')


def build(root=ROOT):
    root=Path(root);skill=root/'skills/goalpilot';runtime=skill/'runtime/goalpilot'
    previous_manifest=skill/'MANIFEST.json'
    skill_version=json.loads(previous_manifest.read_text()).get('skill_version','1.6.0') if previous_manifest.is_file() else '1.6.0'
    # The caller-facing Skill uses the last fully successful, externally judged engine.
    # The standalone controller under goalpilot/ can evolve independently.
    source=root/'benchmarks/codex-1.3.1/goalpilot'
    version=engine_version(source)
    source_files={p.name:sha(p)for p in sorted(source.glob('*.py'))}
    if not source_files:raise ValueError('No engine source')
    runtime.mkdir(parents=True,exist_ok=True)
    for p in runtime.glob('*.py'):
        if p.name not in source_files:p.unlink()
    for name in source_files:shutil.copy2(source/name,runtime/name)
    measurement_path=root/'reports/skill-131-summary/measurement.json'
    measurement=None
    applies=False
    if measurement_path.is_file():
        measurement=json.loads(measurement_path.read_text())
        applies=bool(measurement.get('complete')and measurement.get('target_achieved')and
                     measurement.get('audit_successful')and
                     measurement.get('engine_files')==source_files and
                     measurement.get('skill_sha256')==sha(skill/'SKILL.md'))
        measurement={**measurement,'applies_to_current_bundle':applies}
        (skill/'references/measurements.json').write_text(json.dumps(measurement,ensure_ascii=False,indent=2)+'\n')
    baseline={
        'engine_version':version,'cold_measured_version':'0.9.0','cold_current_version_benchmarked':False,
        'cold':json.loads((root/'reports/quota-native-live-007/analysis.json').read_text()),
        'reuse_engine_091':json.loads((root/'reports/reuse-current-001/analysis.json').read_text()),
        'source_note':'Historical engine evidence, not new cold skill measurements. The caller conversation is not included in backend usage.',
        'accepted_future_targets':{'anti_loop':True,'time_saving_percent':25,'uncached_input_saving_percent':45,'output_saving_percent':45,'achieved':applies,
            'user_amended_from':{'time_saving_percent':30,'uncached_input_saving_percent':50,'output_saving_percent':50},
            'note':'Explicit user tolerance of five percentage points. Historical engine evidence is distinct; current whole-caller evidence only applies when the exact engine and skill hashes match references/measurements.json.'},
        'current_skill_measurement':'measurements.json'if measurement else None,
        'current_measurement_applies':applies}
    (skill/'references/baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n')
    files={str(p.relative_to(skill)):sha(p)for p in sorted(skill.rglob('*'))
           if p.is_file()and '__pycache__'not in p.parts and p.suffix!='.pyc'and p.name!='MANIFEST.json'}
    manifest={'package':'goalpilot-codex-skill','skill_version':skill_version,
              'engine':{'version':version,'files':source_files,'unchanged_source':True},'files':files,
              'meter_scope':('Default session: zero nested engine model calls. Entire caller usage/time measured on20 selected synthetic Python service missions; see references/measurements.json and its scope/review/continuation disclosures. General caller usage remains UNKNOWN without external metering; no subscription-quota conversion.'if applies else
              'Default session: zero nested engine model calls; caller usage UNKNOWN, measured externally. Current source/skill savings not established by retained historical measurements. Legacy controller meters backend calls only.'),
              'measured_runtime_and_skill_parity':applies,
              'post_measurement_metadata_only':measurement.get('metadata_added_after_measurement',[])if applies else[]}
    (skill/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=root/'dist/goalpilot-skill.zip'
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p in sorted(skill.rglob('*')):
            if p.is_file()and '__pycache__'not in p.parts and p.suffix!='.pyc':z.write(p,'goalpilot/'+str(p.relative_to(skill)))
    with zipfile.ZipFile(archive)as z:
        assert z.testzip()is None
        for rel,digest in files.items():assert hashlib.sha256(z.read('goalpilot/'+rel)).hexdigest()==digest
    receipt={'path':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),
             'engine_version':version,'engine_modules':len(source_files),'all_hashes_verified':True}
    (archive.parent/'goalpilot-skill-release.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(build(),indent=2))
