"""Predefined resource-per-delivered-goal metrics, with absolute costs alongside."""
import html,json
from pathlib import Path
from goalpilot.engine import atomic_json


def calculate(records,protocol):
    groups={}
    for mode in ('direct','goalpilot'):
        xs=[r for r in records if r['mode']==mode];n=sum(r['success']for r in xs)
        secs=sum(r['seconds']for r in xs);raw=sum(r['usage']['total_tokens']for r in xs)
        uncached=sum(r['usage']['total_tokens']-r['usage']['cached_input_tokens']for r in xs)
        complete=all(r['usage']['usage_complete']for r in xs)
        groups[mode]={'runs':len(xs),'completed_goals':n,'seconds':secs,'reported_tokens':raw,
            'uncached_input_plus_output':uncached,'usage_complete':complete,
            'seconds_per_completed_goal':secs/n if n else None,
            'tokens_per_completed_goal':raw/n if n and complete else None,
            'uncached_per_completed_goal':uncached/n if n and complete else None,
            'agent_turns':sum(len(r['calls'])for r in xs),'false_completion':sum(r['normal_exit']and not r['artifact_success']for r in xs)}
    pairs=[]
    for name in protocol['cases']:
        for repeat in range(protocol['repeats']):
            a=next((r for r in records if r['case']==name and r['repeat']==repeat and r['mode']=='direct'),None)
            b=next((r for r in records if r['case']==name and r['repeat']==repeat and r['mode']=='goalpilot'),None)
            if a and b:pairs.append({'case':name,'repeat':repeat,'direct_success':a['success'],'goalpilot_success':b['success']})
    d,g=groups['direct'],groups['goalpilot']
    def reduction(key):return 100*(1-g[key]/d[key])if d[key]and g[key]is not None else None
    savings={k:reduction(k)for k in ('seconds','reported_tokens','uncached_input_plus_output','seconds_per_completed_goal','tokens_per_completed_goal','uncached_per_completed_goal')}
    full=len(records)==len(protocol['order']);models=sorted({m for r in records for m in r['models']if m})
    quality_wins=sum(p['goalpilot_success']and not p['direct_success']for p in pairs)
    quality_losses=sum(p['direct_success']and not p['goalpilot_success']for p in pairs)
    eligible=full and models==[protocol['model']]and d['usage_complete']and g['usage_complete']and not any(r.get('infrastructure_interruption')or r.get('fatal')for r in records)
    threshold=protocol['resource_threshold_percent']
    joint=eligible and quality_wins>=1 and quality_losses==0 and all(savings[k]is not None and savings[k]>=threshold for k in ('seconds_per_completed_goal','tokens_per_completed_goal','uncached_per_completed_goal'))
    return {'complete':full,'groups':groups,'pairs':pairs,'models':models,'eligible':eligible,'quality_wins':quality_wins,'quality_losses':quality_losses,
            'savings_percent':savings,'joint_preregistered_criterion_met':joint,'protocol':protocol,
            'interpretation':'Primary savings are all trial costs divided by the number of fully delivered goals, including costs of failures. Absolute costs are also shown. This is descriptive evidence on 3 synthetic projects and correlated repeats, not population proof, personal satisfaction or exact subscription quota.'}


def report(output):
    output=Path(output);m=json.loads((output/'protocol.json').read_text())
    records=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
    data=calculate(records,m);atomic_json(output/'report.json',data)
    esc=lambda x:html.escape(str(x))
    rows=''.join(f'<tr><td>{esc(r["id"])}</td><td>{esc(r["status"])}</td><td>{sum(c["passed"]for c in r["judgments"])}/{len(r["judgments"])}</td><td>{"oui"if r["success"]else"non"}</td><td>{r["seconds"]:.3f}</td><td>{r["usage"]["total_tokens"]:,}</td></tr>'for r in records)
    conclusion='Les trois critères conjoints sont atteints sur cette campagne.'if data['joint_preregistered_criterion_met']else'Les trois critères conjoints ne sont pas atteints.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — temps, conclusions, tokens</title>
<style>body{{max-width:1100px;margin:auto;padding:36px 20px;background:#0d1725;color:#e7eff8;font:16px/1.6 system-ui}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:10px;border-bottom:1px solid #33475b;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1b2a3e;padding:20px;border-radius:10px}}a{{color:#8edec3}}.scroll{{overflow:auto}}</style>
<h1>Temps, objectifs livrés, tokens</h1><p>{conclusion} Une campagne complète exige tous les essais prévus, le même modèle observé et les compteurs complets.</p>
<p>L’économie principale porte sur le coût par objectif complètement livré : coût de tous les essais, y compris les échecs, divisé par le nombre de réussites. Les coûts absolus restent affichés. Une économie par réussite n’est pas nécessairement une baisse du coût total.</p>
<div class="scroll"><table><tr><th>Essai</th><th>Statut</th><th>Groupes cachés</th><th>Livré</th><th>Secondes</th><th>Tokens rapportés</th></tr>{rows}</table></div>
<h2>Résultats calculés</h2><pre>{esc(json.dumps({k:data[k]for k in ('complete','eligible','groups','quality_wins','quality_losses','savings_percent','joint_preregistered_criterion_met')},ensure_ascii=False,indent=2))}</pre>
<h2>Protocole figé avant les appels</h2><pre>{esc(json.dumps(m,ensure_ascii=False,indent=2))}</pre>
<p>Trois projets synthétiques avec documentation publique détaillée, pas des goals personnels de plusieurs heures. Deux répétitions ne créent pas de nouveaux projets indépendants. Aucun retour du juge caché n’a servi aux corrections. Le contrôle du produit utilise le même modèle dans un autre contexte : erreurs corrélées possibles. Les tokens ne sont pas une conversion exacte du quota d’abonnement.</p><p><a href="report.json">Données JSON</a> · <a href="protocol.json">Protocole original</a></p></html>'''
    (output/'report.html').write_text(page)
    return data
