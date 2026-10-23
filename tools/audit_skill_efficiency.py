"""Recompute the skill instruction-efficiency promotion from frozen evidence."""
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


# These are the only archived Python modules imported during this audit. Pin them
# independently of the archive's self-reported hashes before executing any code.
APPROVED_IMPORTS={
    'source/install.py':'3e875f7936a14aafdad8ee363530bf822e52fbe89db521bcc6465835baecc407',
    'harness/cases.py':'e8f68b7f5b1e276f6e19b15363af30ce0d07cb5444c0304704250aedfce280bd',
    'harness/races.py':'d5633a37595ec97f5cf9eb93d8ecb8292232615d42da42be7b6ebf75c22c696c',
}


def analyze(folder):
    folder=Path(folder);protocol=json.loads((folder/'protocol.json').read_text())
    require(all(sha(folder/name)==digest for name,digest in APPROVED_IMPORTS.items()),'Unapproved archived executable source')
    if (folder/'budget-amendment.json').exists():
        amendment=json.loads((folder/'budget-amendment.json').read_text())
        original=json.loads((folder/'protocol.original.json').read_text())
        require(sha(folder/'protocol.original.json')==amendment['original_protocol_sha256']and sha(folder/'protocol.json')==amendment['amended_protocol_sha256'],'Budget amendment identity differs')
        resource_fields={'campaign_raw_cap','campaign_uncached_plus_output_cap'}
        require({k:v for k,v in original.items()if k not in resource_fields}=={k:v for k,v in protocol.items()if k not in resource_fields},'Budget amendment changed efficacy or frozen experiment')
    require(hashes(folder/'source')==protocol['source_hashes'],'Frozen source differs')
    require(hashes(folder/'harness')==protocol['harness_hashes'],'Frozen graders differ')
    require(sha(folder/'worker.py')==protocol['worker_sha256'],'Frozen worker differs')
    require(sha(folder/'candidate-SKILL.md')==protocol['candidate_sha256'],'Frozen candidate differs')
    require(len(protocol['cases'])==20 and len(set(protocol['cases']))==20,'Expected20 distinct cases')
    spec=importlib.util.spec_from_file_location('frozen_efficiency_grader',folder/'harness/cases.py');grader=importlib.util.module_from_spec(spec);spec.loader.exec_module(grader)
    spec=importlib.util.spec_from_file_location('frozen_efficiency_races',folder/'harness/races.py');races=importlib.util.module_from_spec(spec);spec.loader.exec_module(races)
    source=folder/'source/skills/goalpilot-016';manifest=json.loads((source/'MANIFEST.json').read_text())
    require({p.name:sha(p)for p in(source/'runtime/goalpilot').glob('*.py')}==manifest['engine']['files'],'Frozen engine manifest differs')
    require(manifest['engine']['version']=='0.16.0','Unexpected engine version')
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
            closed=bool(caller['returncode']==0 and state.get('closed')and state.get('status')=='scope_passed'and state.get('goal_assessment',{}).get('goal_complete'))
            # Current session status stores assessment at top level in some clients;
            # the frozen receipt also retains the last verification assessment.
            if not closed:
                assessment=(state.get('verifications')or[{}])[-1].get('goal_assessment',{})
                closed=bool(caller['returncode']==0 and state.get('closed')and state.get('status')=='scope_passed'and assessment.get('goal_complete'))
            require(closed==row['normal_closure'],'Closure differs from sealed receipt')
            require(row['success']==bool(closed and review['correct']and preserved),'Completion differs')
            delivered=hashes(trial/'delivered');verified=state.get('verified_source',{}).get('files',{})
            if closed:require({k:v['sha256']for k,v in verified.items()}==delivered,'Delivered code differs from verified source')
        source=folder/'source/skills/goalpilot-016'
        require((trial/'installed/RUNTIME.json').exists(),'Missing installed profile evidence')
        runtime=json.loads((trial/'installed/RUNTIME.json').read_text())
        require(runtime['host']=='codex'and runtime['engine_version']=='0.16.0','Unexpected installed profile')
        spec=importlib.util.spec_from_file_location('frozen_efficiency_installer',folder/'source/install.py')
        installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer);installer.SOURCE=source
        with tempfile.TemporaryDirectory()as temp:
            with patch.object(installer.sys,'executable',runtime['python']),patch.object(installer.sys,'version',runtime['python_version']+' archived'),patch.object(installer,'os',SimpleNamespace(name='posix')):
                expected=installer.prepare_bundle(Path(temp)/'expected','codex')
            if row['arm']=='new':
                original=(expected/'SKILL.md').read_text();start=original.index('## Installed runtime');end=original.index('GP =',start)
                candidate=(folder/'candidate-SKILL.md').read_text().replace('# GoalPilot\n','# GoalPilot\n\n'+original[start:end],1)
                (expected/'SKILL.md').write_text(candidate)
                manifest=json.loads((expected/'MANIFEST.json').read_text());manifest['files']['SKILL.md']=sha(expected/'SKILL.md')
                (expected/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            require(hashes(expected)==row['installed_files'],'Installed profile differs from frozen installer and candidate instructions')
        installed_verified+=1
        for name in ('RUNTIME.json','SKILL.md','MANIFEST.json'):
            require(sha(trial/'installed'/name)==row['installed_files'][name],'Installed metadata differs')
        row['provider_meter_updates']=len(meters)
        rows.append(row)
    expected_order=[(item['case'],arm)for item in protocol['order']for arm in item['arms']]
    actual_order=sorted(rows,key=lambda row:json.loads((folder/'trials'/(row['case']+'-'+row['arm'])/'started.json').read_text())['at'])
    require([(r['case'],r['arm'])for r in actual_order]==expected_order[:len(rows)],'Registered interleaved order differs')
    require(all(json.loads((folder/'trials'/(r['case']+'-'+r['arm'])/'started.json').read_text())['at']>=protocol['registered_at']for r in rows),'Outcome started before registration')
    independent_replay=None
    if (folder/'independent-replay/result.json').exists():
        replay=json.loads((folder/'independent-replay/result.json').read_text())
        require(replay['model_calls']==0 and replay['recorded_replays']==40 and replay['all_consistent'],'Independent replay incomplete')
        require({(r['case'],r['arm'])for r in replay['results']}==seen and len(replay['results'])==40,'Independent replay cases differ')
        for outcome in replay['results']:
            trial=folder/'trials'/(outcome['case']+'-'+outcome['arm'])
            log=folder/'independent-replay'/trial.name/'judge.log'
            program=trial/('reviewed-judge'if outcome['case']in('annotations','subscriptions')else'strict-judge')/'judge.py'
            require(sha(program)==outcome['program_sha256']and sha(log)==outcome['log_sha256'],'Independent replay artifact differs')
            groups=[line[5:]for line in log.read_text().splitlines()if line.startswith('PASS ')]
            require(groups==outcome['groups']and outcome['correct']==(outcome['returncode']==0 and len(groups)==10),'Independent replay score differs')
            recorded=next(r for r in rows if r['case']==outcome['case']and r['arm']==outcome['arm'])
            require(outcome['correct']==recorded['reviewed_correct'],'Independent replay does not confirm the original artifact')
        independent_replay={k:v for k,v in replay.items()if k!='results'}
    matched={c for c in protocol['cases']if(c,'old')in seen and(c,'new')in seen}
    primary={arm:totals([r for r in rows if r['arm']==arm and r['case']in matched])for arm in('old','new')}
    for arm,value in primary.items():
        value['independent_business_correct']=sum(r['reviewed_correct']for r in rows if r['arm']==arm and r['case']in matched)
        count=value['verified_goals']
        value['cost_per_verified_goal']={k:value[k]/count if count else None for k in('raw','uncached_plus_output','seconds')}
    historical=json.loads((folder/'historical-controls.json').read_text())
    controls={name:totals([r for r in historical['rows']if r['arm']==arm and r['case']in matched],True)for name,arm in [('legacy_1_3_1','new'),('native','native')]}
    previous=json.loads((folder/'previous-promotion.json').read_text())
    # Historical Skill1.7 per-case values live in its source archive; its complete aggregate is displayed separately.
    savings={name:saving(primary['new'],control)for name,control in [('fresh_current',primary['old']),('historical_legacy',controls['legacy_1_3_1']),('historical_native',controls['native'])]}if matched else{}
    pg=protocol['primary_gates'];hg=protocol['historical_gates']
    require(hg=={'native_raw_and_uncached_plus_output_saving_at_least_percent':45,'native_time_saving_at_least_percent':25},'Unexpected historical promotion thresholds')
    require(pg=={'candidate_correct':20,'all_meters':True,'min_raw_saving_percent':10,'min_uncached_plus_output_saving_percent':10,'max_time_regression_percent':3,'no_completion_regression':True},'Unexpected promotion thresholds')
    gates={'complete20pairs':len(rows)==40 and len(matched)==20,'candidate20correct':sum(r['success']for r in rows if r['arm']=='new')==20,'all_meters_complete':all(r['usage']['usage_complete']for r in rows),'all_installed_profiles_verified':installed_verified==len(rows),'no_completion_regression':primary['new']['correct']>=primary['old']['correct']}
    if matched:
        g=savings['fresh_current'];n=savings['historical_native'];gates.update(raw_saving_at_least10=g['raw']>=10,uncached_plus_output_saving_at_least10=g['uncached_plus_output']>=10,time_regression_at_most3=g['seconds']>=-3,native_raw_saving_at_least45=n['raw']>=hg['native_raw_and_uncached_plus_output_saving_at_least_percent'],native_uncached_saving_at_least45=n['uncached_plus_output']>=hg['native_raw_and_uncached_plus_output_saving_at_least_percent'],native_time_saving_at_least25=n['seconds']>=hg['native_time_saving_at_least_percent'])
    return {'recorded_calls':len(rows),'matched_pairs':len(matched),'primary':primary,'historical_same_cases':controls,'historical_current_20':previous['primary']['new'],'savings_percent':savings,'gates':gates,'promotable':all(gates.values()),'strict_correct':{a:sum(r['strict_correct']for r in rows if r['arm']==a)for a in('old','new')},'provider_meter_updates':{a:sum(r['provider_meter_updates']for r in rows if r['arm']==a)for a in('old','new')},'per_case':[{'case':r['case'],'arm':r['arm'],'success':r['success'],'raw':r['usage']['total_tokens'],'uncached_plus_output':r['usage']['uncached_tokens'],'seconds':r['seconds'],'provider_meter_updates':r['provider_meter_updates']}for r in rows],'independent_replay':independent_replay,'completion_definition':'Certified closure requires normal caller exit, frozen GoalPilot checks and goal_complete true, exact original goal bytes and all independent reviewed business groups. Business correctness is reported separately; a frozen authored-test defect can block certification of an otherwise correct artifact.','limitations':protocol['limitations']}


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
