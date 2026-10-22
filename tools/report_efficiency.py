"""Audit and report the incremental version comparison, including every cost."""
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import atomic_json,token_totals
from goalpilot.rpc import normalize_usage


def fingerprint(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*'))if p.is_file()and '__pycache__'not in p.parts}


def report(output):
    m=json.loads((output/'protocol.json').read_text())
    assert m==json.loads((output/'preregistered-protocol.json').read_text())
    rows=[];audit=[];flags=[];pairs=[]
    frozen={mode:fingerprint(output/'source_snapshot'/mode)==sha for mode,sha in m['source_fingerprints'].items()}
    current=all(hashlib.sha256((ROOT/'goalpilot'/p.relative_to(output/'source_snapshot/candidate/goalpilot')).read_bytes()).hexdigest()==hashlib.sha256(p.read_bytes()).hexdigest()for p in (output/'source_snapshot/candidate/goalpilot').glob('*.py'))
    for item in m['order']:
        trial=output/'trials'/item['id'];record=trial/'record.json'
        if not record.exists():continue
        r=json.loads(record.read_text());assert r['judgments']==json.loads((trial/'judgments.json').read_text())
        assert r['usage']==token_totals(r['calls'])
        assert r['artifact_success']==(len(r['judgments'])==26 and all(x['passed']for x in r['judgments']))
        assert r['success']==(r['normal_exit']and r['artifact_success'])
        assert r['human_inputs']==0
        counters={}
        for number,c in enumerate(r['calls'],1):
            result=c.get('result',{});events=trial/'run/calls'/str(number)/'events.jsonl'
            values=[];started=[];finished=[]
            if events.exists():
                for line in events.read_text().splitlines():
                    e=json.loads(line);p=e['packet'];params=p.get('params',{});method=p.get('method')
                    if method=='thread/tokenUsage/updated':values.append((params['threadId'],normalize_usage(params['tokenUsage']['total'])))
                    if method=='turn/started':started.append(params['turn']['id'])
                    if method=='turn/completed':finished.append(params['turn']['status'])
                    if method=='item/completed':
                        obj=params['item'];kind=obj.get('type','')
                        if any(s in kind.lower()for s in ('collab','subagent')):flags.append({'trial':r['id'],'reason':'Possible delegated usage','type':kind})
                        if kind=='commandExecution':
                            command=obj.get('command','')
                            if re.search(r'\b(codex|claude|gemini|aider)\s+(exec|app-server|run|code)\b',command):flags.append({'trial':r['id'],'reason':'Possible nested model','command':command[:1000]})
                            if any(s in command for s in ('evaluation/ambitious','reference_flowdesk','reference_stockroom','source_snapshot','preregistered-protocol')):flags.append({'trial':r['id'],'reason':'Possible benchmark read','command':command[:1000]})
            actual=None
            if values:
                thread,total=values[-1];before=counters.get(thread,dict.fromkeys(total,0));actual={k:total[k]-before[k]for k in total};counters[thread]=total
            audit.append({'id':r['id'],'call':number,'strategy':c['strategy'],'raw_counters_match':result.get('usage')==actual if actual is not None else False,'complete':result.get('usage_complete')is True,'model':(result.get('telemetry',{}).get('model')or{}).get('model'),'simulated':result.get('simulated',False),'started_turns':len(started),'finished_statuses':finished})
        u=r['usage'];r['uncached_tokens']=u['input_tokens']-u['cached_input_tokens']+u['output_tokens'];rows.append(r)
    for case in m['cases']:
        ps=[output/'trials'/(case+'-'+mode)/'started.json'for mode in ('baseline','candidate')]
        if all(p.exists()for p in ps):pairs.append({'case':case,'byte_identical':json.loads(ps[0].read_text())['initial_repo_fingerprint']==json.loads(ps[1].read_text())['initial_repo_fingerprint']})
    complete=len(rows)==len(m['order']);full_usage=bool(audit)and all(a['complete']and a['raw_counters_match']for a in audit)
    integrity=complete and all(frozen.values())and current and len(pairs)==2 and all(p['byte_identical']for p in pairs)and not flags and all(a['model']==m['model']and not a['simulated']and a['started_turns']==1 for a in audit)
    totals={}
    for mode in ('baseline','candidate'):
        arm=[r for r in rows if r['mode']==mode]
        totals[mode]={'trials':len(arm),'fully_delivered':sum(r['success']for r in arm),'correct_artifacts':sum(r['artifact_success']for r in arm),'normal_exits':sum(r['normal_exit']for r in arm),'seconds':sum(r['seconds']for r in arm),'raw_tokens':sum(r['usage']['total_tokens']for r in arm),'uncached_tokens':sum(r['uncached_tokens']for r in arm),'model_turns':sum(len(r['calls'])for r in arm),'groups_passed':sum(c['passed']for r in arm for c in r['judgments'])}
    phase_totals={}
    for mode in ('baseline','candidate'):
        phase_totals[mode]={}
        for row in rows:
            if row['mode']!=mode:continue
            for call in row['calls']:
                phase=call['strategy'];d=call.get('result',{});u=d.get('usage')or{}
                v=phase_totals[mode].setdefault(phase,{'calls':0,'model_seconds':0,'raw_tokens':0,'uncached_tokens':0})
                v['calls']+=1;v['model_seconds']+=d.get('provider_duration_seconds',d.get('duration_seconds',0))or 0
                v['raw_tokens']+=u.get('input_tokens',0)+u.get('output_tokens',0)
                v['uncached_tokens']+=u.get('input_tokens',0)-u.get('cached_input_tokens',0)+u.get('output_tokens',0)
        assert sum(v['raw_tokens']for v in phase_totals[mode].values())==totals[mode]['raw_tokens']
    losses=[]
    for case in m['cases']:
        pair={r['mode']:r for r in rows if r['case']==case}
        if len(pair)==2 and (pair['baseline']['success']and not pair['candidate']['success']or pair['baseline']['artifact_success']and not pair['candidate']['artifact_success']):losses.append(case)
    savings={k:100*(1-totals['candidate'][k]/totals['baseline'][k])if complete and full_usage and totals['baseline'][k]else None for k in ('seconds','raw_tokens','uncached_tokens')}
    maintained=bool(integrity and not losses and totals['candidate']['fully_delivered']==2)
    hit={k:v is not None and v>=20 for k,v in savings.items()}
    supplement_path=output/'supplementary-bounds-preregistered.json'
    supplement=json.loads(supplement_path.read_text())if supplement_path.exists()else None
    candidate_calls=[a for a in audit if a['id'].endswith('-candidate')]
    candidate_usage_complete=bool(candidate_calls)and all(a['complete']and a['raw_counters_match']for a in candidate_calls)
    bound_registration=supplement['registered_at']if supplement else m['registered_at']if m.get('primary_allows_baseline_bounds')else None
    registered_before_candidates=bound_registration is not None and all(bound_registration<json.loads((output/'trials'/r['id']/'started.json').read_text())['at']for r in rows if r['mode']=='candidate')
    known_baseline_valid=all(a['raw_counters_match']for a in audit if a['id'].endswith('-baseline'))and all(0<=u.get('cached_input_tokens',0)<=u['input_tokens'] and u['output_tokens']>=0 for row in rows if row['mode']=='baseline'for call in row['calls']if(u:=call.get('result',{}).get('usage'))is not None)
    bound_savings={k:100*(1-totals['candidate'][k]/totals['baseline'][k])if complete and candidate_usage_complete and known_baseline_valid and totals['baseline'][k]else None for k in ('seconds','raw_tokens','uncached_tokens')}
    bound_target=bool(maintained and integrity and registered_before_candidates and all(v is not None and v>=20 for v in bound_savings.values()))
    result={'complete':complete,'planned_trials':4,'completed_trials':len(rows),'totals':totals,'phase_totals':phase_totals,'savings_percent':savings,'supplementary_savings_lower_bound_percent':bound_savings,'supplementary_twenty_percent_target_met':bound_target,'supplement_registered_before_candidates':registered_before_candidates,'candidate_usage_complete':candidate_usage_complete,'time_savings_percent_exact':100*(1-totals['candidate']['seconds']/totals['baseline']['seconds'])if complete and totals['baseline']['seconds']else None,'baseline_known_usage_valid':known_baseline_valid,'original_exact_meter_study_stopped':(output/'stopped.json').exists(),'twenty_percent_thresholds':hit,'closure_maintained_on_both_cases':maintained,'joint_primary_target_met':bool(maintained and full_usage and all(hit.values())or m.get('primary_allows_baseline_bounds')and bound_target),'exact_meter_target_met':bool(maintained and full_usage and all(hit.values())),'paired_regressions':losses,'integrity_verified':bool(integrity),'usage_complete':full_usage,'frozen_sources':frozen,'current_candidate_matches':current,'initial_pairs':pairs,'call_audit':audit,'possible_violations':flags,'comparison_known_raw_tokens':sum(t['raw_tokens']for t in totals.values()),'new_known_raw_tokens':sum(row['usage']['total_tokens']for row in rows if row['id']not in m.get('archived_cells',[])),'planned_fresh_trials':len(m['order'])-len(m.get('archived_cells',[])),'completed_fresh_trials':sum(row['id']not in m.get('archived_cells',[])for row in rows),'archived_cells':m.get('archived_cells',[]),'limitation':'Two familiar synthetic domains, one comparison observation per version/domain, same gpt-6.1-sol. Any historical control reuse is explicit in protocol and archived_cells; it is not a fresh execution. Descriptive effect sizes, not statistical proof or a personal-goal guarantee. Baseline is GoalPilot0.5.2, not native Codex. Raw tokens are not exact quota; cache is reported separately. No training, nested model or human steering in trials. Code correctness is judged independently of product closure.'}
    atomic_json(output/'analysis.json',result)
    flat=[]
    for r in rows:flat.append({k:r[k]for k in ('id','case','mode','seconds','status','normal_exit','artifact_success','success','uncached_tokens')}|{'raw_tokens':r['usage']['total_tokens'],'model_turns':len(r['calls']),'groups_passed':sum(c['passed']for c in r['judgments']),'usage_complete':r['usage']['usage_complete'],'token_value_kind':'complete'if r['usage']['usage_complete']else'known_lower_bound'})
    if flat:
        stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=flat[0]);w.writeheader();w.writerows(flat);(output/'trials.csv').write_text(stream.getvalue())
    baseline_label=html.escape(m['versions']['baseline']);candidate_label=html.escape(m['versions']['candidate'])
    body=['<!doctype html><html lang="fr"><meta charset="utf-8"><title>GoalPilot — efficacité mesurée</title><style>body{font:17px system-ui;max-width:1150px;margin:40px auto;padding:20px;color:#17243b;background:#f5f7fa}table{border-collapse:collapse;width:100%;background:white}td,th{padding:14px;border:1px solid #dce1e9;text-align:left}code{overflow-wrap:anywhere}a{color:#1462ba}</style>', '<h1>GoalPilot — clôture et efficacité</h1>',f'<p>{len(rows)}/4 cellules de comparaison ; {result["completed_fresh_trials"]}/{result["planned_fresh_trials"]} nouvelles exécutions, {len(m.get("archived_cells",[]))} témoin historique réutilisé. Cible conjointe atteinte : <b>{result["joint_primary_target_met"]}</b>. Clôture conservée : <b>{maintained}</b>.</p>',f'<table><tr><th>Mesure totale</th><th>{baseline_label}</th><th>{candidate_label}</th><th>Économie</th></tr>']
    for key,label in [('fully_delivered','Goals corrects et conclus'),('correct_artifacts','Livrables corrects'),('seconds','Temps complet (s)'),('raw_tokens','Tokens bruts'),('uncached_tokens','Entrées hors cache + sorties'),('model_turns','Appels modèle'),('groups_passed','Groupes indépendants réussis')]:
        values=[str(totals[mode][key])if key not in('raw_tokens','uncached_tokens')or all(r['usage']['usage_complete']for r in rows if r['mode']==mode)else '≥ '+str(totals[mode][key])for mode in ('baseline','candidate')];v=result['time_savings_percent_exact']if key=='seconds'else savings.get(key);bound=bound_savings.get(key);economy=f'{v:.2f} %'if v is not None else (f'≥ {bound:.2f} %'if bound is not None else '—');body.append(f'<tr><td>{label}</td><td>{values[0]}</td><td>{values[1]}</td><td>{economy}</td></tr>')
    if full_usage:
        meter_note='Tous les compteurs sont complets. Les économies affichées sont calculées sur les coûts totaux de tous les essais, préparation et corrections incluses.'
    else:
        meter_note='Compteurs incomplets : aucun gain exact de tokens. Une économie minimale marquée ≥ exige tous les coûts du candidat et des coûts connus du témoin audités. La règle et ses limites sont dans le protocole.'
    if complete and maintained and not result['joint_primary_target_met']:
        missed=[key for key,value in savings.items()if value is not None and value<20]
        meter_note+=' Les coûts baissent, mais la cible interne de20 % sur CHAQUE ressource reste manquée pour : '+', '.join(missed)+'.'
    body+=['</table><p>'+meter_note+'</p><h2>Détail des cellules de comparaison</h2><table><tr><th>Cas / version</th><th>Conclu et correct</th><th>Temps</th><th>Bruts</th><th>Hors cache + sorties</th></tr>']
    for r in rows:body.append(f'<tr><td>{html.escape(r["id"])}</td><td>{r["success"]}</td><td>{r["seconds"]:.3f} s</td><td>{r["usage"]["total_tokens"]}</td><td>{r["uncached_tokens"]}</td></tr>')
    body+=[f'</table><p>Le protocole précise les éventuels témoins historiques réutilisés ; ils ne sont pas de nouvelles exécutions. Les deux domaines avaient déjà servi au développement : ces essais ne sont pas inédits. Un essai par version et par domaine ; effets descriptifs, pas de preuve statistique. Le témoin est GoalPilot {baseline_label}, pas Codex natif. Le temps inclut toute la supervision ; aucune économie exacte de tokens n’est calculée avec des compteurs incomplets. Les bornes conservatrices sont expliquées ci-dessus.</p>',f'<p>Audit : intégrité={bool(integrity)}, compteurs complets={full_usage}, alertes={len(flags)}.</p>','<p><a href="protocol.json">Protocole figé</a> · <a href="analysis.json">Chiffres et audit</a> · <a href="trials.csv">CSV</a></p>']
    (output/'report.html').write_text('\n'.join(body));return result


if __name__=='__main__':
    r=report(Path(sys.argv[1]).resolve());print(json.dumps({k:r[k]for k in ('completed_trials','totals','savings_percent','closure_maintained_on_both_cases','joint_primary_target_met','possible_violations')},indent=2))
