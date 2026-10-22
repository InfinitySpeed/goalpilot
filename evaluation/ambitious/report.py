"""Completion is primary; cost and partial coverage never substitute for it."""
import csv,html,json,math
from pathlib import Path
from goalpilot.engine import atomic_json


def calculate(records,m):
    groups={}
    for mode in('direct','goalpilot'):
        xs=[r for r in records if r['mode']==mode];n=sum(r['success']for r in xs)
        seconds=sum(r['seconds']for r in xs);tokens=sum(r['usage']['total_tokens']for r in xs);uncached=sum(r['usage']['total_tokens']-r['usage']['cached_input_tokens']for r in xs);complete=bool(xs)and all(r['usage']['usage_complete']for r in xs)
        passed=sum(sum(j['passed']for j in r['judgments'])for r in xs);total=sum(len(r['judgments'])for r in xs)
        groups[mode]={'runs':len(xs),'completed_goals':n,'artifact_successes':sum(r['artifact_success']for r in xs),'false_completion':sum(r['normal_exit']and not r['artifact_success']for r in xs),
        'groups_passed':passed,'groups_total':total,'workflow_group_fraction':passed/total if total else None,
        'seconds':seconds,'reported_tokens':tokens,'uncached_input_plus_output':uncached,'usage_complete':complete,'agent_turns':sum(len(r['calls'])for r in xs),
        'seconds_per_completed_goal':seconds/n if n else None,'tokens_per_completed_goal':tokens/n if n and complete else None,'uncached_per_completed_goal':uncached/n if n and complete else None}
    pairs=[]
    for name in m['cases']:
        for repeat in range(m['repeats']):
            pair={r['mode']:r for r in records if r['case']==name and r['repeat']==repeat}
            if len(pair)==2:pairs.append({'case':name,'repeat':repeat,'direct_success':pair['direct']['success'],'goalpilot_success':pair['goalpilot']['success']})
    wins=sum(p['goalpilot_success']and not p['direct_success']for p in pairs);losses=sum(p['direct_success']and not p['goalpilot_success']for p in pairs)
    discordant=wins+losses;p=sum(math.comb(discordant,k)for k in range(wins,discordant+1))/2**discordant if discordant else None
    models=sorted({v for r in records for v in r['models']});full=len(records)==len(m['order'])
    all_models=all(c.get('result',{}).get('telemetry',{}).get('model',{}).get('model')==m['model']for r in records for c in r['calls'])
    eligible=full and len(pairs)==len(m['order'])//2 and models==[m['model']]and all_models and not any(r.get('fatal')or r.get('infrastructure_interruption')for r in records)
    d,g=groups['direct'],groups['goalpilot']
    saving={key:100*(1-g[key]/d[key])if d[key]and g[key]is not None and ('token'not in key and 'uncached'not in key or d['usage_complete']and g['usage_complete'])else None for key in('seconds','reported_tokens','uncached_input_plus_output','seconds_per_completed_goal','tokens_per_completed_goal','uncached_per_completed_goal')}
    per_project=[{'case':name,'direct_successes':sum(r['success']for r in records if r['case']==name and r['mode']=='direct'),'goalpilot_successes':sum(r['success']for r in records if r['case']==name and r['mode']=='goalpilot')}for name in m['cases']]
    return {'complete':full,'eligible_for_quality_comparison':eligible,'primary_completion_advantage_observed':eligible and g['completed_goals']-d['completed_goals']>=2 and losses==0,
       'groups':groups,'pairs':pairs,'quality_wins':wins,'quality_losses':losses,'per_project':per_project,'models':models,'savings_percent':saving,
       'paired_one_sided_p_if_independent':p,'statistical_limit':'Repeated projects are correlated. The independent-pair exact sign probability is descriptive and cannot establish population significance for three projects.','protocol':m}


def report(output):
    output=Path(output);m=json.loads((output/'protocol.json').read_text());rows=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()];data=calculate(rows,m);atomic_json(output/'report.json',data)
    fields=['id','case','repeat','mode','success','status','seconds','reported_tokens','uncached_input_plus_output','usage_complete','groups_passed','groups_total','failed_groups']
    with(output/'trials.csv').open('w',newline='')as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:writer.writerow({k:r[k]for k in('id','case','repeat','mode','success','status','seconds')}|{'reported_tokens':r['usage']['total_tokens'],'uncached_input_plus_output':r['usage']['total_tokens']-r['usage']['cached_input_tokens'],'usage_complete':r['usage']['usage_complete'],'groups_passed':sum(j['passed']for j in r['judgments']),'groups_total':len(r['judgments']),'failed_groups':','.join(sorted({j['id']for j in r['judgments']if not j['passed']}))})
    esc=html.escape
    table=''.join(f"<tr><td>{esc(r['id'])}</td><td>{r['success']}</td><td>{sum(j['passed']for j in r['judgments'])}/{len(r['judgments'])}</td><td>{r['seconds']:.2f}</td><td>{r['usage']['total_tokens']:,}</td><td>{esc(', '.join(sorted({j['id']for j in r['judgments']if not j['passed']})))}</td></tr>"for r in rows)
    title='Avantage de conclusion observé sur cette campagne.'if data['primary_completion_advantage_observed']else'Avantage de conclusion non établi.'
    if not data['complete']:title='Évaluation des goals ambitieux en cours.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — objectifs ambitieux</title><style>body{{max-width:1150px;margin:auto;padding:36px 20px;background:#101b29;color:#edf3fb;font:16px/1.65 system-ui}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:12px 8px;text-align:left;border-bottom:1px solid #3a4e66}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1d3046;padding:20px;border-radius:12px}}a{{color:#91dfc7}}.scroll{{overflow:auto}}</style><h1>{title}</h1>
<p>Trois plateformes nouvelles : support multi-équipe, stocks et commandes, workflows durables. Les composants métier sont à construire et à intégrer à une infrastructure SQLite/JSONL/HTTP fournie. Le critère principal exige deux objectifs entièrement livrés supplémentaires et aucune régression appariée. Une économie de temps seule ne compte pas.</p>
<div class="scroll"><table><tr><th>Essai</th><th>Goal livré</th><th>Groupes cachés</th><th>Secondes</th><th>Tokens rapportés</th><th>Groupes en échec</th></tr>{table}</table></div>
<h2>Bilan calculé</h2><pre>{esc(json.dumps({k:v for k,v in data.items()if k!='protocol'},ensure_ascii=False,indent=2))}</pre>
<h2>Protocole</h2><p>Mêmes fichiers initiaux, gpt-6.1-sol et 900 secondes par essai. Deux répétitions avec ordre inversé. Aucun arrêt/incident de session provoqué, aucun feedback du juge caché au produit, aucune relance d’un essai raté. Les vérifications incluent CLI/HTTP et des processus concurrents réels. Les graines varient certains scénarios, pas chaque groupe ; les répétitions et scénarios partagent les projets.</p>
<h2>Limites</h2><p>Trois projets synthétiques et des contrats publics détaillés, malgré un goal initial bref. Cela ne mesure pas directement des goals personnels de plusieurs heures ou la satisfaction subjective. Les répétitions sont corrélées. Les coûts partiels restent des bornes inférieures. Le quota d’abonnement n’est pas déduit des tokens.</p><p><a href="protocol.json">Critères figés avant les appels</a> · <a href="report.json">Données JSON</a> · <a href="trials.csv">Résultats CSV</a></p></html>'''
    (output/'report.html').write_text(page);return data
