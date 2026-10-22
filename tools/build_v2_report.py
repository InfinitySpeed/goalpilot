"""Recalculate the frozen live study. No model calls and no source edits."""
from __future__ import annotations

import csv
import hashlib
from html import escape
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.dossier_study import summarize


def number(value,digits=1):
    return 'indisponible' if value is None else f'{value:,.{digits}f}'.replace(',',' ')


def build(study):
    study=Path(study).resolve()
    manifest=json.loads((study/'protocol.json').read_text())
    report=summarize(manifest)
    report['stopped_early']=manifest.get('stopped_early')
    first=[x for x in report['results'] if x.get('repeat',1)==1]
    if len(first)==2*len(manifest['cases']):
        seconds={mode:sum(x['seconds'] for x in first if x['mode']==mode) for mode in ('direct','goalpilot')}
        report['complete_first_repeat']={'seconds':seconds,
            'time_increase_percent':100*(seconds['goalpilot']/seconds['direct']-1),
            'successes':{mode:sum(x['external_success'] for x in first if x['mode']==mode) for mode in ('direct','goalpilot')}}
    snapshot=study/'source_snapshot'
    report['snapshot_integrity']=all(hashlib.sha256((snapshot/name).read_bytes()).hexdigest()==sha
                                    for name,sha in manifest['code_fingerprint'].items())
    report['preregistration_unchanged']=all(
        json.loads((study/'preregistered-protocol.json').read_text())[key]==manifest[key]
        for key in manifest if key not in ('results','stopped_early','interrupted_trials'))
    report['study_directory']=str(study.relative_to(ROOT))
    pairs={}
    for x in report['results']:pairs.setdefault((x['case'],x.get('repeat',1)),{})[x['mode']]=x
    changes=[100*(1-x['goalpilot']['seconds']/x['direct']['seconds'])
             for x in pairs.values() if len(x)==2 and x['direct']['seconds']]
    report['paired_time_reductions_percent']=changes
    report['median_paired_time_reduction_percent']=statistics.median(changes) if changes else None
    report['tests']=json.loads((ROOT/'reports/tests.json').read_text())
    report['raw_protocol']='protocol.json'
    report['per_project']=[]
    for case in manifest['cases']:
        row={'project':case['name']}
        for mode in ('direct','goalpilot'):
            runs=[x for x in report['results'] if x['case']==case['name'] and x['mode']==mode]
            row[mode]={'runs':len(runs),'successes':sum(x['external_success'] for x in runs),
                'seconds':sum(x['seconds'] for x in runs),
                'reported_tokens':sum((x['usage'] or {}).get('total_tokens',0) for x in runs),
                'non_cached_input_plus_output':sum((x['usage'] or {}).get('total_tokens',0)-(x['usage'] or {}).get('cached_input_tokens',0) for x in runs)}
        report['per_project'].append(row)
    dev=json.loads((ROOT/'reports/v2-dev-001/report.json').read_text())
    smoke=json.loads((ROOT/'reports/v2-go-dev-001/report.json').read_text())
    report['development_usage']={
        'agent_turns':sum(x['runs'] for x in dev['groups'].values())+smoke['calls'],
        'reported_tokens':sum(x['reported_tokens'] for x in dev['groups'].values())+smoke['usage']['total_tokens'],
        'usage_complete':all(x['usage_complete'] for x in dev['groups'].values()) and smoke['usage']['usage_complete']}
    extra_dev=ROOT/'reports/v21-dev-001/report.json'
    if extra_dev.exists():
        extra=json.loads(extra_dev.read_text())
        report['development_usage']['agent_turns']+=sum(x['runs'] for x in extra['groups'].values())
        report['development_usage']['reported_tokens']+=sum(x['reported_tokens'] for x in extra['groups'].values())
        report['development_usage']['usage_complete'] &= all(x['usage_complete'] for x in extra['groups'].values())
    prior=ROOT/'reports/v2-validation-001/protocol.json'
    prior_report={'agent_turns':0,'reported_tokens_lower_bound':0,'usage_complete':True}
    if prior.exists() and prior.parent!=study:
        failed=json.loads(prior.read_text())
        interrupted=failed.get('interrupted_trials',[])
        prior_report={'agent_turns':sum(x['agent_turns'] for x in failed['results'])+len(interrupted),
            'reported_tokens_lower_bound':sum((x['usage'] or {}).get('total_tokens',0) for x in failed['results'])+sum(x['reported_usage_lower_bound']['totalTokens'] for x in interrupted),
            'usage_complete':not interrupted and all(x['usage_complete'] for x in failed['results']),
            'reason':failed.get('stopped_early'),'finished_pairs':len(failed['results'])//2}
    report['prior_interrupted_validation']=prior_report
    report['v2_campaign_usage']={
        'agent_turns':report['development_usage']['agent_turns']+sum(x['agent_turns'] for x in report['results'])+prior_report['agent_turns'],
        'reported_tokens_lower_bound':report['development_usage']['reported_tokens']+sum((x['usage'] or {}).get('total_tokens',0) for x in report['results'])+prior_report['reported_tokens_lower_bound'],
        'usage_complete':report['development_usage']['usage_complete'] and all(x['usage_complete'] for x in report['results']) and prior_report['usage_complete']}
    out=ROOT/'reports/v2-evaluation.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    with (ROOT/'reports/v2-trials.csv').open('w') as stream:
        fields=['trial_id','case','repeat','mode','seconds','external_success','checks_passed','checks_total',
                'agent_turns','command_count','usage_complete','input_tokens','output_tokens','cached_input_tokens','non_cached_input_plus_output']
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for item in report['results']:
            row={k:item.get(k) for k in fields if k not in ('input_tokens','output_tokens','cached_input_tokens','non_cached_input_plus_output')}
            row.update({k:(item['usage'] or {}).get(k) for k in ('input_tokens','output_tokens','cached_input_tokens')})
            row['non_cached_input_plus_output']=(item['usage'] or {}).get('total_tokens',0)-(item['usage'] or {}).get('cached_input_tokens',0)
            writer.writerow(row)
    a,b=report['groups']['direct'],report['groups']['goalpilot']
    conclusion=('Critère préétabli atteint sur ce corpus.' if report['primary_threshold_met']
                else 'Campagne interrompue : aucun avantage global validé.' if report['stopped_early']
                else 'Critère préétabli non atteint.' if report['finished'] else 'Campagne en cours : aucune conclusion.')
    rows=''.join(f"<tr><td>{escape(x['case'])} · {x.get('repeat',1)}</td><td>{escape(x['mode'])}</td><td>{'oui' if x['external_success'] else 'NON'} ({x['checks_passed']}/{x['checks_total']})</td><td>{number(x['seconds'])}</td><td>{number((x['usage'] or {}).get('total_tokens'),0)}</td><td>{number((x['usage'] or {}).get('total_tokens',0)-(x['usage'] or {}).get('cached_input_tokens',0),0)}</td><td>{x['agent_turns']}</td></tr>" for x in report['results'])
    pairs={}
    for x in report['results']:pairs.setdefault((x['case'],x.get('repeat',1)),{})[x['mode']]=x
    cards=''.join(f"<article><b>{label}</b><strong>{number(report[key])} %</strong><small>réduction observée ; négatif = hausse</small></article>"
        for label,key in [('Temps total','time_reduction_percent'),('Tokens rapportés','reported_token_reduction_percent'),('Hors cache + sortie','non_cached_token_reduction_percent')])
    chart_payload=json.dumps(report['results'],ensure_ascii=True).replace('<',chr(92)+'u003c')
    html=f"""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GoalPilot — mesures réelles V2</title>
<style>body{{font:16px system-ui;background:#10151e;color:#e9eef5;max-width:1120px;margin:40px auto;padding:0 20px;line-height:1.5}}a{{color:#90c4ff}}h1{{font-size:38px}}small{{display:block;color:#aebbc9}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}article{{background:#1a2432;border:1px solid #32435b;padding:20px;border-radius:12px;flex:1;min-width:180px}}strong{{display:block;font-size:32px}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #344050}}.scroll{{overflow-x:auto}}select{{padding:8px;background:#233148;color:inherit;border:1px solid #58749b;border-radius:6px}}.bar{{height:22px;margin:4px 0;background:#7195ed;min-width:1px;border-radius:3px}}.goalpilot{{background:#57c4ab}}.chartrow{{margin:18px 0}}code{{color:#bce5d5}}</style>
<h1>GoalPilot : essais réels</h1><p><b>{conclusion}</b> {report['unique_projects']} projets distincts, {manifest.get('repeats',1)} répétitions, {len(report['results'])} essais enregistrés.</p>
<div class="cards">{cards}</div>
<p>Réussites externes : Codex direct <b>{a['external_successes']}/{a['runs']}</b> ; GoalPilot <b>{b['external_successes']}/{b['runs']}</b>. Usage complet : {a['usage_complete'] and b['usage_complete']}. Modèle observé : {escape(', '.join(report['observed_models']))}.</p>
<h2>Comparer les essais appariés</h2><select id="metric"><option value="seconds">Temps total (secondes)</option><option value="total_tokens">Tokens entrée + sortie</option><option value="uncached">Entrée hors cache + sortie</option><option value="command_count">Commandes agent</option></select>
<p><span style="color:#7195ed">■ Codex direct</span> · <span style="color:#57c4ab">■ GoalPilot</span></p><div id="chart"></div>
<h2>Tous les résultats</h2><div class="scroll"><table><thead><tr><th>Projet · répétition</th><th>Condition</th><th>Tests externes</th><th>Secondes</th><th>Tokens</th><th>Hors cache + sortie</th><th>Tours</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Ce qui est mesuré</h2><p>Le temps inclut préparation, implémentation, contrôles internes et fermeture du client. Les contrôles cachés d'évaluation, identiques pour les deux conditions, sont exclus du temps produit. GoalPilot utilise le parcours <code>go</code> complet, sans session de planification séparée. Direct utilise une session autonome avec le même délai total de {manifest['seconds_per_trial']} secondes. GoalPilot peut réparer dans ce même délai, avec au plus deux tours.</p>
<p>Les tests cachés sont figés avant les appels et ne servent jamais aux réparations. L'ordre est inversé à la seconde répétition. Les {report['expected_pairs']} paires ne représentent que {report['unique_projects']} projets indépendants. Les fichiers sources et le protocole initiaux sont conservés : intégrité {report['snapshot_integrity'] and report['preregistration_unchanged']}.</p>
<p>Critère fixé avant la campagne : réussir tous les tests externes dans les deux conditions, disposer d'un usage complet et du même modèle, puis gagner au moins 15 % sur le temps total OU l'entrée hors cache + sortie. Les tokens rapportés sont une mesure secondaire.</p>
<h2>Limites</h2><p>Petits projets synthétiques avec interfaces documentées. Aucun test sur tes anciens goals de plusieurs heures ni mesure de ta satisfaction. Les répétitions partagent un environnement et des caches. Aucun intervalle de confiance généralisable n'est déduit de trois projets. Les tokens en cache sont inclus dans l'entrée ; leur poids réel dans le quota d'abonnement est inconnu. <b>Ces pourcentages ne sont pas des économies de quota.</b></p>
<p>Tests locaux : {report['tests']['passed']}/{report['tests']['tests_run']} en {number(report['tests']['duration_seconds'],3)} secondes, sans appels de modèle. Ces tests vérifient les mécanismes, pas l'utilité d'un LLM.</p>
<p><a href="v2-evaluation.json">Données et calculs JSON</a> · <a href="v2-trials.csv">Essais CSV</a> · <a href="{escape(report['study_directory'].split('/')[-1])}/preregistered-protocol.json">Protocole initial</a> · <a href="real-evaluation.html">Échecs V1 conservés</a></p>
<script>const rows={chart_payload};function value(r,m){{if(m==='uncached')return (r.usage?.total_tokens||0)-(r.usage?.cached_input_tokens||0);return r[m]??r.usage?.[m]??0}}function draw(){{const m=document.querySelector('#metric').value,max=Math.max(1,...rows.map(r=>value(r,m))),chart=document.querySelector('#chart');chart.replaceChildren();const groups=new Map();for(const r of rows){{const k=r.case+' · '+r.repeat;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)}}for(const [k,rs]of groups){{const div=document.createElement('div');div.className='chartrow';const title=document.createElement('b');title.textContent=k;div.append(title);for(const r of rs.sort((a,b)=>a.mode.localeCompare(b.mode))){{const label=document.createElement('small');label.textContent=r.mode+': '+value(r,m).toLocaleString('fr-FR',{{maximumFractionDigits:1}});const bar=document.createElement('div');bar.className='bar '+r.mode;bar.style.width=(100*value(r,m)/max)+'%';div.append(label,bar)}}chart.append(div)}}}}document.querySelector('#metric').addEventListener('change',draw);draw();</script></html>"""
    (ROOT/'reports/v2-evaluation.html').write_text(html)
    if report['finished']:
        table='\n'.join(
            f"| {x['case']} | {x.get('repeat',1)} | {x['mode']} | {x['checks_passed']}/{x['checks_total']} | {number(x['seconds'],3)} | {number((x['usage'] or {}).get('total_tokens'),0)} | {number((x['usage'] or {}).get('total_tokens',0)-(x['usage'] or {}).get('cached_input_tokens',0),0)} |"
            for x in report['results'])
        text=f"""# Mesures réelles de GoalPilot 0.2.1

[Rapport interactif](reports/v2-evaluation.html) · [JSON recalculé](reports/v2-evaluation.json) · [CSV des essais](reports/v2-trials.csv) · [Protocole initial]({report['study_directory']}/preregistered-protocol.json)

## Résultat

**{conclusion}** Sur {report['unique_projects']} petits projets inédits au moment de la validation, répétés deux fois, Codex direct réussit **{a['external_successes']}/{a['runs']}** et GoalPilot **{b['external_successes']}/{b['runs']}**. Chaque réussite exige tous les contrôles externes, sans utiliser leurs échecs pour réparer le projet.

| Mesure cumulée | Codex direct | GoalPilot | Réduction observée |
|---|---:|---:|---:|
| Temps complet du parcours | {number(a['seconds'],3)} s | {number(b['seconds'],3)} s | {number(report['time_reduction_percent'],2)} % |
| Tokens entrée + sortie | {number(a['reported_tokens'],0)} | {number(b['reported_tokens'],0)} | {number(report['reported_token_reduction_percent'],2)} % |
| Entrée hors cache + sortie | {number(a['non_cached_input_plus_output'],0)} | {number(b['non_cached_input_plus_output'],0)} | {number(report['non_cached_token_reduction_percent'],2)} % |
| Entrée en cache, déjà incluse | {number(a['cached_input_tokens'],0)} | {number(b['cached_input_tokens'],0)} | — |
| Commandes exécutées par l'agent | {a['commands']} | {b['commands']} | — |
| Tours agent | {a['agent_turns']} | {b['agent_turns']} | — |

Une réduction négative signifie une hausse. Les compteurs sont complets dans tous les essais : **{a['usage_complete'] and b['usage_complete']}**. Modèle réellement observé : **{', '.join(report['observed_models'])}**. GoalPilot est plus rapide dans {report['time_wins']}/{report['paired_cases']} paires. Les répétitions ne constituent pas de nouveaux projets indépendants.

## Tous les essais, sans sélection

| Projet | Répétition | Condition | Contrôles externes | Temps, s | Tokens totaux | Hors cache + sortie |
|---|---:|---|---:|---:|---:|---:|
{table}

## Protocole et sens des chiffres

- Le traitement est le parcours **go complet** : contexte local, implémentation directe, proposition de contrôles, exécution de ces contrôles, réparations éventuelles et fermeture du client. Le temps de préparation et de vérification interne est inclus. Les contrôles cachés d'évaluation sont exclus du temps produit dans les deux conditions.
- Même modèle et serveur Codex, mêmes fichiers publics, même objectif et même délai total de {manifest['seconds_per_trial']} secondes. Direct dispose d'une session autonome continue ; GoalPilot peut utiliser au plus deux tours dans ce même délai. Ordre alterné entre projets et inversé à la deuxième répétition.
- Les interfaces publiques sont documentées dans les README. Les {sum(len(x['checks']) for x in manifest['cases'])} contrôles externes composés couvrent les parcours utilisateur, erreurs, conservation des données, Unicode, dépendances et archives dangereuses. Ils sont conservés hors des dépôts de travail et ne sont pas transmis dans les prompts. Avant les appels, ils ont rejeté les squelettes inachevés et accepté trois implémentations de référence indépendantes.
- Le protocole et les empreintes ont été enregistrés **avant** les appels. Tous les essais et répétitions prévus sont conservés. Sources inchangées pendant la campagne ; intégrité du snapshot et du protocole : **{report['snapshot_integrity'] and report['preregistration_unchanged']}**.
- Critère préétabli : tous les contrôles externes réussis dans les deux conditions, compteurs complets et modèle identique, puis au moins 15 % de gain sur le temps total **ou** l'entrée hors cache + sortie. Le total de tokens est secondaire. Aucun remplacement d'un échec par une nouvelle tentative sélectionnée.
- Entrée hors cache + sortie = input_tokens + output_tokens − cached_input_tokens. Les notifications cumulées sont différenciées entre tours pour éviter les doubles comptes. Une interruption garde les compteurs partiels mais interdit de conclure à une économie complète.

## Limites

**Ces résultats ne démontrent pas une économie précise de quota d'abonnement.** Le poids du cache et de la sortie dans ce quota n'est pas fourni. Les compteurs ne sont ni un prix ni un pourcentage de quota.

Trois petits projets synthétiques, deux répétitions par condition, environnement et caches partagés. Les effets d'ordre sont réduits, pas éliminés. Aucun intervalle de confiance généralisable ne peut être tiré de ce corpus. Ce n'est pas une mesure sur des objectifs ambitieux de plusieurs heures, sur tes anciens goals ou sur ta satisfaction personnelle. Réussir des contrôles proposés par l'agent reste scope_passed ; seuls les contrôles externes de cette campagne définissent la réussite évaluée.

## Coût de cette évaluation et historique

La validation finale comprend {a['agent_turns']+b['agent_turns']} tours agent réels et {number(a['reported_tokens']+b['reported_tokens'],0)} tokens rapportés. Les {report['development_usage']['agent_turns']} appels de développement, conservés séparément, ajoutent {number(report['development_usage']['reported_tokens'],0)} tokens.

Une première campagne V2.0 s'est interrompue après trois paires complètes et pendant un septième appel : coupure du transport exec-server, puis disparition des processus. Ces trois paires réussissaient dans les deux conditions mais ne suffisaient pas au critère préétabli ; leur gain cumulé de temps était de 13,84 %, avec davantage de tokens hors cache. L'appel interrompu conserve 15 538 tokens observés, consommation partielle. [Incident et traces](reports/v2-validation-001/interruption.json). Ces essais ne sont pas intégrés à l'efficacité de la variante finale.

Total de l'itération, essais abandonnés compris : **{report['v2_campaign_usage']['agent_turns']} tours**, **au moins {number(report['v2_campaign_usage']['reported_tokens_lower_bound'],0)} tokens rapportés**. Le total est incomplet à cause de l'interruption ; il ne faut pas le présenter comme le coût intégral de l'évaluation.

Le développement initial comparait seulement la préparation de contexte sur notes : 16,46 % de temps et 29,37 % de tokens rapportés en moins. Ce cas connu n'entre pas dans les chiffres de validation. Un essai du parcours go avait aussi révélé davantage de tokens hors cache malgré un total moindre : il est conservé, sans le transformer en économie de quota.

La V1 avait obtenu direct 2/2 et supervisé 1/2 sur deux microtâches, avec des consommations incomplètes et des interruptions trop courtes. Ces résultats négatifs ne sont pas effacés : [mesures V1](MEASUREMENTS-v1.md), [rapport réel V1](reports/real-evaluation.html). Les simulations scriptées restent séparées de toutes les mesures réelles.

## Vérifications et reproduction

**{report['tests']['passed']}/{report['tests']['tests_run']} tests locaux passent en {number(report['tests']['duration_seconds'],3)} secondes**, sans appel de modèle. Ils couvrent budgets, reprises, stagnation, échecs, notifications d'usage, contexte borné, tours réutilisés et calculs du protocole. Ils vérifient le logiciel, pas l'efficacité générale d'un LLM.

~~~bash
python3 validate.py
python3 -m evaluation.reference_oracles_v21
python3 tools/build_v2_report.py {report['study_directory']}
~~~

Pour une nouvelle campagne réelle, consommant l'usage du compte :

~~~bash
python3 -m evaluation.dossier_study --live --stage validation --suite v21 --treatment autopilot \\
  --repeats 2 --seconds 300 --model gpt-6.1-sol --output /tmp/goalpilot-etude-nouvelle
~~~

Les projets déjà publiés servent alors à la reproduction, pas à une nouvelle validation sur des projets inédits.
"""
        (ROOT/'MEASUREMENTS.md').write_text(text)
    return report


if __name__=='__main__':
    report=build(sys.argv[1] if len(sys.argv)>1 else ROOT/'reports/v21-validation-001')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','per_project')},indent=2,ensure_ascii=False))
