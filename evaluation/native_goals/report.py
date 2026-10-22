"""Real native-goal lifecycle compared with product closure, hidden correctness required."""
import csv,html,json
from pathlib import Path
from goalpilot.engine import atomic_json


def calculate(rows,m):
    groups={}
    for mode in('native_goal','goalpilot'):
        xs=[r for r in rows if r['mode']==mode];n=sum(r['success']for r in xs);complete=bool(xs)and all(r['usage']['usage_complete']for r in xs)
        groups[mode]={'runs':len(xs),'completed_goals':n,'artifact_successes':sum(r['artifact_success']for r in xs),'false_completion':sum(r['normal_exit']and not r['artifact_success']for r in xs),
        'groups_passed':sum(j['passed']for r in xs for j in r['judgments']),'groups_total':sum(len(r['judgments'])for r in xs),'seconds':sum(r['seconds']for r in xs),'reported_tokens':sum(r['usage']['total_tokens']for r in xs),'uncached_input_plus_output':sum(r['usage']['total_tokens']-r['usage']['cached_input_tokens']for r in xs),'usage_complete':complete,
        'model_turns':sum(r['model_turns']for r in xs)}
        g=groups[mode];g['seconds_per_delivered_goal']=g['seconds']/n if n else None;g['tokens_per_delivered_goal']=g['reported_tokens']/n if n and complete else None
    pairs=[]
    for name in m['cases']:
        xs={r['mode']:r for r in rows if r['case']==name}
        if len(xs)==2:pairs.append({'case':name,'native_success':xs['native_goal']['success'],'goalpilot_success':xs['goalpilot']['success']})
    wins=sum(p['goalpilot_success']and not p['native_success']for p in pairs);losses=sum(p['native_success']and not p['goalpilot_success']for p in pairs)
    full=len(rows)==len(m['order']);models=sorted({v for r in rows for v in r['models']})
    eligible=full and models==[m['model']]and not any(r['fatal']or r['infrastructure_interruption']for r in rows)
    return {'complete':full,'eligible':eligible,'primary_completion_advantage_observed':eligible and wins>=1 and losses==0,'groups':groups,'pairs':pairs,'quality_wins':wins,'quality_losses':losses,'models':models,'protocol':m}


def report(output):
    output=Path(output);m=json.loads((output/'protocol.json').read_text());rows=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()];data=calculate(rows,m);atomic_json(output/'report.json',data)
    fields=['id','case','mode','status','success','artifact_success','seconds','model_turns','reported_tokens','uncached_input_plus_output','usage_complete','failed_groups']
    with(output/'trials.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:r[k]for k in('id','case','mode','status','success','artifact_success','seconds','model_turns')}|{'reported_tokens':r['usage']['total_tokens'],'uncached_input_plus_output':r['usage']['total_tokens']-r['usage']['cached_input_tokens'],'usage_complete':r['usage']['usage_complete'],'failed_groups':','.join(sorted({j['id']for j in r['judgments']if not j['passed']}))})
    esc=html.escape
    table=''.join(f"<tr><td>{esc(r['id'])}</td><td>{esc(r['status'])}</td><td>{r['success']}</td><td>{sum(j['passed']for j in r['judgments'])}/{len(r['judgments'])}</td><td>{r['seconds']:.3f}</td><td>{r['model_turns']}</td><td>{r['usage']['total_tokens']:,}</td></tr>"for r in rows)
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vrais /goal — GoalPilot</title><style>body{{max-width:1100px;margin:auto;padding:36px 20px;background:#101b29;color:#edf2fa;font:16px/1.65 system-ui}}td,th{{padding:12px 8px;border-bottom:1px solid #3a4f64;text-align:left}}table{{border-collapse:collapse;width:100%}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c3046;padding:20px;border-radius:12px}}a{{color:#96dfc9}}.scroll{{overflow:auto}}</style><h1>Vrai /goal natif et GoalPilot</h1><p>Cette comparaison attend l’état natif du goal, pas uniquement le premier message final. Les continuations automatiques et leurs compteurs sont conservés. Le succès exige aussi tous les parcours cachés corrects.</p><div class="scroll"><table><tr><th>Essai</th><th>Statut</th><th>Livré</th><th>Groupes</th><th>Secondes</th><th>Tours modèle</th><th>Tokens connus</th></tr>{table}</table></div><pre>{esc(json.dumps({k:v for k,v in data.items()if k!='protocol'},ensure_ascii=False,indent=2))}</pre><p>Deux objectifs liés sur un moteur de workflows : le noyau persistant et une extension avec véritables workers exécutant des tâches. Ce ne sont pas deux projets indépendants. Le noyau n’avait fait l’objet d’aucune exécution modèle réelle avant cette campagne ; l’extension est nouvelle. Contrats publics détaillés, même modèle et plafond de quinze minutes. Un supplément de conclusion sans régression constitue le critère descriptif, pas une preuve statistique générale.</p><p>Le contrôleur utilise le même modèle dans un autre contexte. Une restriction de socket du sandbox peut affecter le goal natif ; les probes du produit s’exécutent sur l’hôte. Le code correct mais un goal bloqué est distingué d’un code incorrect. Les mesures partielles ne permettent pas de calculer une économie totale de tokens.</p><p><a href="protocol.json">Protocole figé</a> · <a href="report.json">JSON</a> · <a href="trials.csv">CSV</a></p></html>'''
    (output/'report.html').write_text(page);return data
