"""Recompute the portable skill's complete-caller comparison from frozen evidence."""
import argparse
import importlib.util
import tempfile
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def hashes(root):return {p.relative_to(root).as_posix():sha(p)for p in sorted(root.rglob('*'))if p.is_file()and'__pycache__'not in p.parts and p.suffix!='.pyc'}
def require(value,message):
    if not value:raise ValueError(message)


def totals(rows,historical=False):
    return {'executed':len(rows),'correct':sum(r.get('success',r.get('correct',False))for r in rows),
            'verified_goals':sum((r.get('normal_closure',r.get('success',r.get('correct',False)))and r.get('reviewed_correct',r.get('success',r.get('correct',False))))for r in rows),
            'seconds':sum(r['seconds']for r in rows),
            'raw':sum(r['usage']['raw'if historical else'total_tokens']for r in rows),
            'uncached_plus_output':sum(r['usage']['uncached_plus_output'if historical else'uncached_tokens']for r in rows),
            'uncached_input':sum(r['usage']['uncached_input']if historical else r['usage']['input_tokens']-r['usage']['cached_input_tokens']for r in rows),
            'output':sum(r['usage']['output_tokens']for r in rows)}


def saving(candidate,control):
    return {k:100*(1-candidate[k]/control[k])for k in ('seconds','raw','uncached_plus_output','uncached_input','output')}


def analyze(folder):
    folder=Path(folder);protocol=json.loads((folder/'protocol.json').read_text())
    if (folder/'budget-amendment.json').exists():
        amendment=json.loads((folder/'budget-amendment.json').read_text());original=json.loads((folder/'protocol.original.json').read_text())
        require(sha(folder/'protocol.original.json')==amendment['original_protocol_sha256']and sha(folder/'protocol.json')==amendment['amended_protocol_sha256'],'Research budget amendment hashes differ')
        fields=('campaign_raw_cap','campaign_uncached_plus_output_cap')
        require({k:v for k,v in original.items()if k not in fields}=={k:v for k,v in protocol.items()if k not in fields},'Budget amendment changed efficacy protocol')
    require(hashes(folder/'source')==protocol['source_hashes'],'Frozen source differs')
    require(hashes(folder/'harness')==protocol['harness_hashes'],'Frozen graders differ')
    for file,field in [('historical-controls.json','historical_controls_sha256'),('standalone-control.json','standalone_control_sha256'),('ci.json','ci_sha256'),('worker.py','worker_sha256'),('driver.py','driver_sha256')]:
        require(sha(folder/file)==protocol[field],file+' hash differs')
    ci=json.loads((folder/'ci.json').read_text());require(ci['successful']and not ci['failures']and not ci['errors']and not ci['skipped'],'Frozen CI did not pass')
    spec=importlib.util.spec_from_file_location('frozen_portable_grader_templates',folder/'harness/cases.py')
    grader=importlib.util.module_from_spec(spec);spec.loader.exec_module(grader)
    race_spec=importlib.util.spec_from_file_location('frozen_portable_races',folder/'harness/races.py')
    races=importlib.util.module_from_spec(race_spec);race_spec.loader.exec_module(races)
    promoted=json.loads((folder/'standalone-control.json').read_text())
    require(promoted['engine_version']=='0.16.0','Unexpected frozen engine version')
    candidate=folder/'source/skills/goalpilot-016/runtime/goalpilot'
    require({p.name:sha(p)for p in candidate.glob('*.py')}=={Path(k).name:v for k,v in promoted['source_hashes'].items()},'Skill engine differs from frozen 0.16.0')
    rows=[];seen=set();installed_verified=0
    for file in sorted((folder/'trials').glob('*/result.json')):
        row=json.loads(file.read_text());ident=(row['case'],row['arm']);require(ident not in seen and row['case']in protocol['cases']and row['arm']in ('old','new'),'Duplicate/unplanned outcome');seen.add(ident)
        trial=file.parent;caller=json.loads((trial/'caller-result.json').read_text());meters=[]
        for line in (trial/'caller/events.jsonl').read_text().splitlines():
            packet=json.loads(line)['packet']
            if packet.get('method')=='thread/tokenUsage/updated':meters.append(packet['params']['tokenUsage']['total'])
        require(bool(meters),'Missing provider meter')
        for i,m in enumerate(meters):
            require(all(type(m.get(k))is int and m[k]>=0 for k in ('inputTokens','outputTokens','cachedInputTokens')),'Invalid provider counter')
            require(m['cachedInputTokens']<=m['inputTokens'],'Cache exceeds input')
            if i:require(all(m[k]>=meters[i-1][k]for k in ('inputTokens','outputTokens','cachedInputTokens')),'Provider counter decreased')
        meter=meters[-1];usage=row['usage'];require(usage['usage_complete']and caller.get('usage_complete')is not False,'Incomplete meter')
        require(usage['input_tokens']==meter['inputTokens']and usage['output_tokens']==meter['outputTokens']and usage['cached_input_tokens']==meter['cachedInputTokens'],'Reported usage differs from wire counters')
        require(usage['total_tokens']==meter['inputTokens']+meter['outputTokens'],'Raw tokens do not reconcile')
        require(usage['uncached_tokens']==usage['total_tokens']-meter['cachedInputTokens'],'Uncached tokens do not reconcile')
        require(caller['usage']=={k:usage[k]for k in ('input_tokens','output_tokens','cached_input_tokens')},'Caller result differs from provider meter')
        require(abs(row['seconds']-row['caller_seconds']-row['judge_seconds'])<1e-8,'Wall-time arithmetic differs')
        setup=row['hooks_setup'];require(setup['effective_configuration_verified']and setup['model_calls']==0 and not setup['global_settings_changed']and setup['unrelated_hooks_preserved'],'Hook setup not verified')
        require(len(setup['owned_hook_keys'])==3 and len(set(setup['owned_hook_keys']))==3,'Expected one active hook set')
        require(row['engine_model_calls']==0 and row['calls']==1,'Nested/caller count differs')
        require(row['source_unchanged'],'Source changed during outcome')
        model=row['model'];require(model['model']==protocol['model']and model['reasoningEffort']==protocol['effort'],'Actual model/effort differs')
        strict=row['strict_judge'];review=row['reviewed_judge']
        with patch.dict(sys.modules,{'races':races}):program=grader.judge_program(row['case'])
        require(sha(trial/'strict-judge/judge.py')==hashlib.sha256(program.encode()).hexdigest(),'Strict grader differs from frozen template')
        if row['case']in ('subscriptions','annotations'):
            note=json.loads((folder/'harness'/('grading-amendment-subscriptions.json'if row['case']=='subscriptions'else'grading-interpretation-annotations.json')).read_text())
            require(hashlib.sha256(program.encode()).hexdigest()==note['original_program_sha256'],'Original grading amendment identity differs')
            program=program.replace(note['original_condition'],note['corrected_condition'if row['case']=='subscriptions'else'sensitivity_condition'])
            require(sha(trial/'reviewed-judge/judge.py')==hashlib.sha256(program.encode()).hexdigest()==note['corrected_program_sha256'if row['case']=='subscriptions'else'interpretation_program_sha256'],'Reviewed grader differs from preregistered amendment')
        for judged,subdir in ((strict,'strict-judge'),(review,'reviewed-judge'if row['case']in ('subscriptions','annotations')else'strict-judge')):
            groups=[x[5:]for x in (trial/subdir/'judge.log').read_text().splitlines()if x.startswith('PASS ')]
            require(groups==judged['groups_passed'],'Judge groups differ')
            require(judged['correct']==(judged['returncode']==0 and len(groups)==10),'Judge correctness differs')
        session=trial/'session';statefile=session/'session-state.json'
        if statefile.exists():
            for filename in ('session-state.json','session.json','acceptance.json'):
                path=session/filename
                if path.exists():require(sha(path)==json.loads((session/(filename+'.sha256')).read_text())['sha256'],'Sealed session artifact differs')
            state=json.loads(statefile.read_text());goal=json.loads((trial/'started.json').read_text())['goal']
            preserved=(session/'goal.bin').read_bytes()==goal.encode('utf8');require(preserved==row['goal_verbatim_preserved'],'Goal preservation differs')
            closed=bool(caller['returncode']==0 and state.get('closed')and state.get('status')=='scope_passed'and (row['arm']=='old'or state.get('goal_assessment',{}).get('goal_complete')))
            # Current session status stores assessment at top level in some clients;
            # the frozen receipt also retains the last verification assessment.
            if row['arm']=='new'and not closed:
                assessment=(state.get('verifications')or[{}])[-1].get('goal_assessment',{})
                closed=bool(caller['returncode']==0 and state.get('closed')and state.get('status')=='scope_passed'and assessment.get('goal_complete'))
            require(closed==row['normal_closure'],'Closure differs from sealed receipt')
            require(row['success']==bool(closed and review['correct']and preserved),'Completion differs')
            delivered=hashes(trial/'delivered');verified=state.get('verified_source',{}).get('files',{})
            if closed:require({k:v['sha256']for k,v in verified.items()}==delivered,'Delivered code differs from verified source')
        source=folder/'source/skills'/('goalpilot-016'if row['arm']=='new'else'goalpilot')
        if row['arm']=='old':
            require(row['installed_files']==hashes(source),'Installed legacy bundle differs from frozen source');installed_verified+=1
        elif (trial/'installed/RUNTIME.json').exists():
            runtime=json.loads((trial/'installed/RUNTIME.json').read_text())
            require(runtime['host']=='codex'and runtime['engine_version']=='0.16.0','Unexpected installed profile')
            spec=importlib.util.spec_from_file_location('frozen_portable_installer',folder/'source/install.py')
            installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer);installer.SOURCE=source
            with tempfile.TemporaryDirectory()as temp:
                # Relocate only recorded interpreter/version metadata, not engine/skill behavior.
                with patch.object(installer.sys,'executable',runtime['python']),patch.object(installer.sys,'version',runtime['python_version']+' archived'),patch.object(installer,'os',SimpleNamespace(name='posix')):
                    expected=installer.prepare_bundle(Path(temp)/'expected','codex')
                require(hashes(expected)==row['installed_files'],'Installed new bundle differs from frozen installer output')
            installed_verified+=1
            for name in ('RUNTIME.json','SKILL.md','MANIFEST.json'):
                require(sha(trial/'installed'/name)==row['installed_files'][name],'Installed metadata differs')
        rows.append(row)
    cases={r['case']for r in rows};matched={c for c in cases if (c,'old')in seen and(c,'new')in seen}
    primary={arm:totals([r for r in rows if r['arm']==arm and r['case']in matched])for arm in ('old','new')}
    historical=json.loads((folder/'historical-controls.json').read_text());standalone=json.loads((folder/'standalone-control.json').read_text())
    controls={arm:totals([r for r in historical['rows']if r['arm']==arm and r['case']in matched],True)for arm in ('new','native')}
    standalone_rows=[r for r in standalone['per_case']if r['case']in matched]
    frozen_standalone=totals([{**r,'success':r['correct']}for r in standalone_rows])
    savings=({name:saving(primary['new'],control)for name,control in [('contemporary_old',primary['old']),('historical_old',controls['new']),('historical_native',controls['native']),('historical_standalone',frozen_standalone)]}if matched else{})
    complete=len(rows)==40 and len(matched)==20
    gates={'all_installed_profiles_verified':installed_verified==len(rows),'complete20_pairs':complete,'new20_correct':sum(r['success']for r in rows if r['arm']=='new')==20,'all_meters_complete':all(r['usage']['usage_complete']for r in rows),'all_new_exact_goals':all(r['goal_verbatim_preserved']for r in rows if r['arm']=='new')}
    if matched:
        gates.update(time_gain_vs_current_old_at_least10=savings['contemporary_old']['seconds']>=10,raw_gain_vs_current_old_at_least15=savings['contemporary_old']['raw']>=15,uncached_gain_vs_current_old_at_least15=savings['contemporary_old']['uncached_plus_output']>=15,time_gain_vs_historical_native_at_least25=savings['historical_native']['seconds']>=25)
        gates.update({k+'_gain_vs_historical_native_at_least45':savings['historical_native'][k]>=45 for k in ('raw','uncached_plus_output','uncached_input','output')})
    return {'planned_pairs':20,'recorded_calls':len(rows),'matched_pairs':len(matched),'primary':primary,'historical_controls':controls,'historical_standalone':frozen_standalone,'savings_percent':savings,'gates':gates,'promotable':bool(complete and all(gates.values())),'ci_passed':ci['passed'],'strict_correct':{arm:sum(r['strict_correct']for r in rows if r['arm']==arm)for arm in ('old','new')},'completion_definition':'verified_goals = normal closure plus all independent reviewed behavioral checks. strict_receipt_success additionally requires byte-identical original goal; a lone trailing newline is not presented as a business-goal failure.',
 'completion':{arm:{'executed':sum(r['arm']==arm for r in rows),'verified_goals':sum(r['normal_closure']and r['reviewed_correct']for r in rows if r['arm']==arm),'strict_receipt_success':sum(r['success']for r in rows if r['arm']==arm),'exact_goal_files':sum(r['goal_verbatim_preserved']for r in rows if r['arm']==arm),'not_run':20-sum(r['arm']==arm for r in rows)}for arm in ('old','new')},'scope':protocol['scope']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--output',type=Path);p.add_argument('--require-promotion',action='store_true');a=p.parse_args(argv)
    try:
        if a.folder.is_file():
            with tempfile.TemporaryDirectory()as temp,zipfile.ZipFile(a.folder)as archive:
                entries=archive.infolist()
                require(len(entries)<=10000 and sum(x.file_size for x in entries)<=128000000,'Evidence archive exceeds bounds')
                for item in entries:
                    path=Path(item.filename)
                    require(not path.is_absolute()and '..'not in path.parts and item.file_size<=8000000 and ((item.external_attr>>16)&0o170000)!=0o120000,'Unsafe evidence archive entry')
                archive.extractall(temp)
                result=analyze(Path(temp))
        else:result=analyze(a.folder)
        if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        if a.require_promotion:require(result['promotable'],'Promotion gates did not all pass')
    except (OSError,ValueError,KeyError,TypeError,AssertionError)as exc:print('FAIL: '+str(exc),file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
