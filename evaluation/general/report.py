"""Metrics distinguish objective delivery, incomplete usage and infrastructure."""
from collections import defaultdict
import csv
from html import escape
import json
import math
from pathlib import Path
import statistics
from .campaign import read_records


def wilson(successes,total):
    if not total:return None
    z=1.96;p=successes/total;den=1+z*z/total
    center=(p+z*z/(2*total))/den
    margin=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0,center-margin),min(1,center+margin)]


def summarize(manifest,records):
    groups={}
    for mode in ('direct','goalpilot'):
        members=[x for x in records if x['mode']==mode];eligible=[x for x in members if not x['infrastructure_interrupted']]
        successes=sum(x['autonomous_success'] for x in eligible);tokens=sum(x['usage']['total_tokens'] for x in members)
        uncached=sum(x['usage']['total_tokens']-x['usage']['cached_input_tokens'] for x in members)
        complete=bool(members) and all(x['usage']['usage_complete'] for x in members)
        groups[mode]={'recorded_trials':len(members),'eligible_trials':len(eligible),'infrastructure_interruptions':len(members)-len(eligible),
            'autonomous_successes':successes,'success_rate':successes/len(eligible) if eligible else None,
            'descriptive_wilson_interval':wilson(successes,len(eligible)),'artifact_successes':sum(x['artifact_success'] for x in eligible),
            'blockers_resolved':sum(x['blocker_resolved'] for x in eligible),
            'stable_on_new_inputs':sum(x['stable_on_new_inputs'] for x in eligible),
            'seconds':sum(x['seconds'] for x in eligible),'usage_complete':complete,'reported_tokens':tokens,
            'non_cached_input_plus_output':uncached,'cached_input_tokens':sum(x['usage']['cached_input_tokens'] for x in members),
            'reported_tokens_per_success':tokens/successes if complete and successes else None,
            'non_cached_tokens_per_success':uncached/successes if complete and successes else None,
            'agent_turns':sum(x['new_agent_turns'] for x in members),'human_inputs_after_start':sum(x['human_inputs_after_start'] for x in members),
            'repeated_identical_failed_commands':sum(x['telemetry']['repeated_identical_failed_commands'] for x in members)}
    pairs=defaultdict(dict)
    for row in records:pairs[(row['case'],row['repeat'])][row['mode']]=row
    paired=[x for x in pairs.values() if len(x)==2 and not any(y['infrastructure_interrupted'] for y in x.values())]
    models={model for r in records for model in r['telemetry']['observed_models']}
    same_model=models=={manifest['model']} and all(r['telemetry']['observed_models'] for r in records if not r['infrastructure_interrupted'])
    planned=len(manifest['order']);finished=len(records)==planned
    a,b=groups['direct'],groups['goalpilot'];comparable=finished and len(paired)*2==planned and same_model
    quality_wins=sum(x['goalpilot']['autonomous_success'] and not x['direct']['autonomous_success'] for x in paired)
    quality_losses=sum(x['direct']['autonomous_success'] and not x['goalpilot']['autonomous_success'] for x in paired)
    all_pass=comparable and a['autonomous_successes']==b['autonomous_successes']==planned//2
    cost_available=comparable and a['usage_complete'] and b['usage_complete']
    def reduction(field,available=True):return 100*(1-b[field]/a[field]) if available and comparable and a[field] else None
    speed=reduction('seconds');tokens=reduction('reported_tokens',cost_available);uncached=reduction('non_cached_input_plus_output',cost_available)
    primary=bool(comparable and not any(x.get('simulated') for x in records) and quality_losses==0 and (quality_wins>=2 or (all_pass and ((speed or 0)>=15 or (uncached or 0)>=15))))
    return {'kind':manifest['kind'],'finished':finished,'planned_trials':planned,'recorded_trials':len(records),
        'unique_projects':len(manifest['cases']),'repetitions':manifest['repeats'],'groups':groups,
        'complete_eligible_pairs':len(paired),'quality_wins':quality_wins,'quality_losses':quality_losses,
        'observed_models':sorted(models),'same_observed_model':same_model,'cost_comparison_available':cost_available,
        'time_reduction_percent':speed,'reported_token_reduction_percent':tokens,'non_cached_token_reduction_percent':uncached,
        'primary_threshold_met':primary,'decision_rule':manifest['decision_rule'],'scope':manifest['scope'],
        'limitations':['Three projects; repetitions and suites are not independent projects.',
            'Wilson intervals describe trial counts only and ignore within-project correlation; not a confidence claim for general efficacy.',
            'A ten-minute budget does not mean a session actually lasted ten minutes. No multi-hour efficacy or personal satisfaction measured.',
            'Restart/new-input checks measure robustness, not days of real-world usage.',
            'Soft token threshold is observed between turns and can be exceeded; tokens do not convert exactly to subscription quota.',
            'Blockers are controlled starting faults, not the observed distribution of natural blockers.',
            'Repeated failing-command count is a conservative trace indicator, not a measure of wasted tokens.'],
        'records':records}


def write(output):
    output=Path(output).resolve();manifest=json.loads((output/'manifest.json').read_text());records=read_records(output,manifest);report=summarize(manifest,records)
    (output/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    fields=['id','case','repeat','mode','status','seconds','autonomous_success','artifact_success','blocker_resolved','stable_on_new_inputs','new_agent_turns','infrastructure_interrupted']
    with (output/'trials.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields+['reported_tokens','cached_input_tokens','usage_complete'])
        writer.writeheader()
        for r in records:writer.writerow({**{k:r[k] for k in fields},'reported_tokens':r['usage']['total_tokens'],'cached_input_tokens':r['usage']['cached_input_tokens'],'usage_complete':r['usage']['usage_complete']})
    def num(x):return 'indisponible' if x is None else f'{x:,.2f}'.replace(',',' ')
    a,b=report['groups']['direct'],report['groups']['goalpilot']
    rows=''.join(f"<tr><td>{escape(r['case'])} · {r['repeat']}</td><td>{r['mode']}</td><td>{r['status']}</td><td>{'oui' if r['autonomous_success'] else 'non'}</td><td>{num(r['seconds'])}</td><td>{r['usage']['total_tokens']}</td><td>{r['new_agent_turns']}</td><td>{sum(x['passed'] for x in r['checks'])}/{len(r['checks'])}</td></tr>" for r in records)
    title='Critère préétabli atteint' if report['primary_threshold_met'] else 'Campagne terminée : avantage non démontré' if report['finished'] else 'Campagne en cours'
    payload=json.dumps(report,ensure_ascii=True).replace('<',chr(92)+'u003c')
    html=f"""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — évaluation autonome générale</title><style>body{{font:16px system-ui;background:#111923;color:#eaf1fa;max-width:1150px;margin:40px auto;padding:0 20px;line-height:1.6}}a{{color:#8ecbff}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}article{{padding:18px;background:#203044;border-radius:10px;flex:1;min-width:190px}}b.big{{display:block;font-size:28px}}table{{border-collapse:collapse;font-size:14px;width:100%}}td,th{{text-align:left;padding:8px;border-bottom:1px solid #364a62}}.scroll{{overflow:auto}}select{{padding:8px;background:#263c57;color:white}}.bar{{height:22px;background:#739dee;margin:4px 0}}.goalpilot{{background:#62d0b1}}.note{{padding:15px;border-left:4px solid #e5ad68;background:#2c2820}}</style>
<h1>Évaluation autonome : missions complètes</h1><p><b>{title}.</b> {len(records)}/{report['planned_trials']} essais enregistrés, trois applications, {manifest['repeats']} répétitions, délai de {manifest['seconds_per_trial']} secondes par essai.</p>
<div class="cards"><article>Objectifs livrés sans aide<b class="big">{b['autonomous_successes']}/{b['eligible_trials']} contre {a['autonomous_successes']}/{a['eligible_trials']}</b>GoalPilot puis Codex direct</article><article>Temps total<b class="big">{num(report['time_reduction_percent'])} %</b>réduction ; négatif = hausse</article><article>Hors cache + sortie<b class="big">{num(report['non_cached_token_reduction_percent'])} %</b>réduction observée, pas quota</article></div>
<div class="note">Objectifs synthétiques avec interfaces publiques documentées. Ils nécessitent plusieurs composants et comportent des défauts de départ. Le temps réel est dans la table : un budget de dix minutes ne prouve pas une efficacité sur plusieurs heures. Aucune satisfaction personnelle mesurée.</div>
<h2>Explorer les résultats</h2><select id="metric"><option value="seconds">Temps complet du produit</option><option value="tokens">Tokens rapportés</option><option value="uncached">Entrée hors cache + sortie</option></select><div id="chart"></div>
<h2>Tous les essais</h2><div class="scroll"><table><thead><tr><th>Projet · répétition</th><th>Condition</th><th>État</th><th>Objectif réussi</th><th>Secondes</th><th>Tokens</th><th>Tours</th><th>Suites externes</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Autonomie, qualité et blocages</h2><p>Inputs humains après lancement : {a['human_inputs_after_start']+b['human_inputs_after_start']}. Blocages initiaux résolus : GoalPilot {b['blockers_resolved']}/{b['eligible_trials']}, direct {a['blockers_resolved']}/{a['eligible_trials']}. Résultats stables avec les nouvelles entrées : {b['stable_on_new_inputs']}/{b['eligible_trials']} contre {a['stable_on_new_inputs']}/{a['eligible_trials']}. Répétitions identiques de commandes en échec : {b['repeated_identical_failed_commands']} contre {a['repeated_identical_failed_commands']}.</p>
<p>Chaque résultat doit passer les suites indépendantes livraison, erreurs/conservation, blocage initial et redémarrage/nouvelles données, sur deux graines fixées avant les appels. Ces suites ne servent pas aux réparations. Les checks proposés par GoalPilot sont distincts ; leur réussite seule ne suffit pas à réussir l'objectif évalué. Interventions du superviseur automatiques incluses dans son coût.</p>
<h2>Coût par résultat obtenu</h2><p>Tokens rapportés par succès, tous les échecs comptés : GoalPilot {num(b['reported_tokens_per_success'])}, direct {num(a['reported_tokens_per_success'])}. Hors cache + sortie par succès : {num(b['non_cached_tokens_per_success'])} contre {num(a['non_cached_tokens_per_success'])}. Usage complet : {b['usage_complete'] and a['usage_complete']}. Interruptions d'infrastructure : {b['infrastructure_interruptions']+a['infrastructure_interruptions']}, conservées séparément et jamais remplacées.</p>
<h2>Règle fixée avant les essais</h2><p>Campagne complète, même modèle, aucune régression appariée, puis au moins deux objectifs réussis supplémentaires ; ou réussite complète égale avec au moins 15 % de gain de temps ou de tokens hors cache + sortie. Les comparaisons de coût exigent des mesures complètes. Modèles observés : {escape(', '.join(report['observed_models']))}.</p>
<p>Échantillon de trois projets, répétitions corrélées, pas de conclusion statistique générale. Aucun test longitudinal sur plusieurs jours ; le redémarrage et les nouvelles données vérifient seulement la robustesse. Aucun taux naturel de blocage ni conversion des tokens en quota d'abonnement.</p>
<p><a href="report.json">Données JSON</a> · <a href="trials.csv">CSV</a> · <a href="preregistered-protocol.json">Protocole initial</a></p>
<script>const d={payload};function draw(){{const metric=document.querySelector('#metric').value,c=document.querySelector('#chart');c.replaceChildren();function v(r){{return metric==='seconds'?(r.seconds||0):metric==='tokens'?r.usage.total_tokens:r.usage.total_tokens-r.usage.cached_input_tokens}}const max=Math.max(1,...d.records.map(v));for(const r of d.records){{const text=document.createElement('div');text.textContent=r.id+': '+v(r).toLocaleString('fr-FR',{{maximumFractionDigits:2}});const bar=document.createElement('div');bar.className='bar '+r.mode;bar.style.width=(100*v(r)/max)+'%';c.append(text,bar)}}}}document.querySelector('#metric').addEventListener('change',draw);draw();</script></html>"""
    (output/'report.html').write_text(html)
    return report
