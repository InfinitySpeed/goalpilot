"""Generate a candid overview: first launches versus conditional resumes."""
import hashlib
from html import escape
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_v2_report import build,number
from tools.resume_study import summarize


def main():
    fresh=build(ROOT/'reports/v21-validation-001')
    directory=ROOT/'reports/resume-live-001'
    manifest=json.loads((directory/'protocol.json').read_text())
    resume=summarize(manifest)
    resume['snapshot_integrity']=all(hashlib.sha256((directory/'source_snapshot'/name).read_bytes()).hexdigest()==sha
        for name,sha in manifest['source_fingerprint'].items())
    resume['preregistration_unchanged']=all(json.loads((directory/'preregistered-protocol.json').read_text())[key]==value
        for key,value in manifest.items() if key!='results')
    if not resume['finished']:raise ValueError('Resume study incomplete; do not publish a positive conclusion')
    a,b=resume['groups']['direct'],resume['groups']['goalpilot']
    unchanged={}
    regressed={}
    for mode in ('direct','goalpilot'):
        normal=[x for x in resume['results'] if x['mode']==mode and x['condition']=='unchanged']
        broken=[x for x in resume['results'] if x['mode']==mode and x['condition']=='entrypoint-regression']
        unchanged[mode]=sum(x['seconds'] for x in normal)/len(normal)
        regressed[mode]=sum(x['seconds'] for x in broken)/len(broken)
    extra=regressed['goalpilot']-regressed['direct']
    saved=unchanged['direct']-unchanged['goalpilot']
    threshold=max(0,extra/(extra+saved)) if extra+saved>0 else None
    fresh_partial=json.loads((ROOT/'reports/v21-validation-001/protocol.json').read_text()).get('interrupted_trials',[])
    lower=sum((x.get('reported_usage_lower_bound') or {}).get('totalTokens',0) for x in fresh_partial)
    campaign={'agent_turns':fresh['v2_campaign_usage']['agent_turns']+len(fresh_partial)+a['agent_turns']+b['agent_turns'],
        'reported_tokens_lower_bound':fresh['v2_campaign_usage']['reported_tokens_lower_bound']+lower+a['reported_tokens']+b['reported_tokens'],
        'usage_complete':False,'reason':'Two infrastructure interruptions left partial usage.'}
    output={'fresh_goals':fresh,'resumes':resume,'conditional_time_model':{'unchanged_means':unchanged,
        'regressed_means':regressed,'break_even_unchanged_fraction':threshold,
        'interpretation':'Illustration from observed averages, not a forecast or a confidence interval. Only one injected regression.'},
        'iteration_usage':campaign}
    (ROOT/'reports/utility.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    rows=''.join(f"<tr><td>{escape(x['project'])}</td><td>{escape(x['condition'])}</td><td>{x['mode']}</td><td>{number(x['seconds'],3)}</td><td>{x['new_agent_turns']}</td><td>{number(x['usage']['total_tokens'],0)}</td><td>{x['checks_passed']}/{x['checks_total']}</td></tr>" for x in resume['results'])
    normal_direct=sum(x['new_agent_turns'] for x in resume['results'] if x['mode']=='direct' and x['condition']=='unchanged')
    normal_pilot=sum(x['new_agent_turns'] for x in resume['results'] if x['mode']=='goalpilot' and x['condition']=='unchanged')
    observed=[f"Premier lancement : direct {fresh['groups']['direct']['external_successes']}/{fresh['groups']['direct']['runs']}, GoalPilot {fresh['groups']['goalpilot']['external_successes']}/{fresh['groups']['goalpilot']['runs']}. Campagne incomplète après redémarrage, aucun gain global validé.",
              f"Reprises : direct {a['successes']}/{a['runs']}, GoalPilot {b['successes']}/{b['runs']}. {b['agent_turns']} appels supplémentaires contre {a['agent_turns']}. Aucun appel sur les trois reprises inchangées."]
    integrity=resume['snapshot_integrity'] and resume['preregistration_unchanged']
    payload=json.dumps({'normal':unchanged,'broken':regressed}).replace('<','\\u003c')
    title="Avantage vérifié sur les reprises" if resume['primary_threshold_met'] else "Avantage non démontré"
    html=f"""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — utilité mesurée</title>
<style>body{{font:16px system-ui;background:#111821;color:#ecf2fa;max-width:1060px;margin:44px auto;padding:0 20px;line-height:1.6}}a{{color:#8bc5ff}}h1{{font-size:36px}}.cards{{display:flex;gap:14px;flex-wrap:wrap}}article{{flex:1;min-width:200px;padding:18px;background:#1d2b3c;border-radius:10px}}strong{{display:block;font-size:30px;color:#8de0c8}}small{{color:#acbed1}}table{{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}}td,th{{padding:9px;text-align:left;border-bottom:1px solid #34485f}}.scroll{{overflow:auto}}.note{{border-left:4px solid #efa965;padding:10px 18px;background:#29251f}}input{{width:100%}}#estimate{{padding:20px;background:#1d2b3c;border-radius:10px}}</style>
<h1>{title}</h1><p>GoalPilot vérifie les critères persistés avant de rappeler Codex. Mesure réelle de quatre reprises sur trois projets déjà terminés : trois dépôts inchangés et une régression injectée.</p>
<div class="cards"><article>Tours Codex supplémentaires<strong>{b['agent_turns']} contre {a['agent_turns']}</strong><small>même résultat externe : {b['successes']}/{b['runs']} contre {a['successes']}/{a['runs']}</small></article><article>Temps total<strong>−{number(resume['time_reduction_percent'])} %</strong><small>{number(b['seconds'])} s contre {number(a['seconds'])} s</small></article><article>Tokens rapportés<strong>−{number(resume['reported_token_reduction_percent'])} %</strong><small>{number(b['reported_tokens'],0)} contre {number(a['reported_tokens'],0)}</small></article></div>
<p>Entrée hors cache + sortie : −{number(resume['non_cached_token_reduction_percent'])} %. Compteurs complets dans cette comparaison : {a['usage_complete'] and b['usage_complete']}. Modèle : {escape(', '.join(resume['observed_models']))}.</p>
<div class="note"><b>Ce gain concerne les reprises.</b> Le premier lancement n'a pas démontré de gain : sur la première série complète, GoalPilot était plus lent. Deux campagnes plus longues ont été interrompues par des redémarrages de l'environnement. Ces échecs restent visibles et leur usage est comptabilisé. Aucun résultat sur des goals personnels de plusieurs heures.</div>
<h2>Selon la fréquence de reprises inchangées</h2><p>Illustration à partir des temps observés, avec seulement une régression injectée. Déplacer le curseur change l'hypothèse d'usage ; ce n'est pas une nouvelle mesure.</p>
<label>Reprises sur un dépôt inchangé : <b id="share">75 %</b><input id="p" type="range" min="0" max="100" value="75"></label><div id="estimate"></div>
<h2>Toutes les reprises</h2><div class="scroll"><table><thead><tr><th>Projet</th><th>État</th><th>Condition</th><th>Secondes</th><th>Tours ajoutés</th><th>Tokens</th><th>Tests externes</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Conditions de comparaison</h2><p>Chaque condition reçoit une copie du même dépôt, le même goal, les mêmes critères gelés et le même compte rendu. Direct reçoit aussi les résultats initiaux des contrôles, puis lance une session Codex. GoalPilot utilise le vrai parcours de reprise, qui appelle Codex seulement si les contrôles échouent. Même temps restant et même modèle. Le coût déjà consommé par la mission précédente est exclu des deux conditions : c'est le coût supplémentaire d'une reprise.</p>
<p>Les sources viennent systématiquement de la première répétition GoalPilot, sans choisir le passage le plus rapide. L'ordre est alterné ; les contrôles externes restent hors des prompts et ne servent pas aux réparations. Les critères locaux sont inférés, pas une mesure de satisfaction. Les trois projets inchangés ne sont pas trois nouveaux objectifs. Le cas cassé est une injection contrôlée, pas un incident naturel. Intégrité du protocole et des sources : {integrity}.</p>
<p>Le critère fixé avant les appels exige quatre réussites dans les deux conditions, compteurs complets, même modèle et au moins 15 % de gain sur le temps ou l'entrée hors cache + sortie. Résultat : {resume['primary_threshold_met']}.</p>
<h2>Coût et limites</h2><p>L'ensemble de cette itération a démarré {campaign['agent_turns']} tours réels. Usage observé : au moins {number(campaign['reported_tokens_lower_bound'],0)} tokens, avec deux mesures partielles dues aux redémarrages. Les simulations ne sont pas incluses. <b>Les tokens ne se convertissent pas exactement en quota d'abonnement.</b></p>
<p>Tests locaux : {fresh['tests']['passed']}/{fresh['tests']['tests_run']}, sans appel de modèle. Aucun modèle alternatif ni satisfaction personnelle mesurés. Le produit est une CLI locale, sans intégration native au /goal de l'application.</p>
<p><a href="utility.json">Données complètes</a> · <a href="resume-live-001/preregistered-protocol.json">Protocole de reprise</a> · <a href="v2-evaluation.html">Tous les essais de premier lancement</a> · <a href="v21-validation-001/interruption.json">Deuxième interruption</a> · <a href="real-evaluation.html">Résultats V1</a></p>
<script>const d={payload};const slider=document.querySelector('#p');function draw(){{const p=slider.value/100;document.querySelector('#share').textContent=slider.value+' %';const direct=p*d.normal.direct+(1-p)*d.broken.direct;const pilot=p*d.normal.goalpilot+(1-p)*d.broken.goalpilot;const reduction=100*(1-pilot/direct);document.querySelector('#estimate').textContent='Temps moyen illustré : direct '+direct.toFixed(2)+' s · GoalPilot '+pilot.toFixed(2)+' s · '+reduction.toFixed(1)+' % de réduction.';}}slider.addEventListener('input',draw);draw();</script></html>"""
    (ROOT/'reports/utility.html').write_text(html)
    table='\n'.join(f"| {x['project']} | {x['condition']} | {x['mode']} | {number(x['seconds'],3)} | {x['new_agent_turns']} | {number(x['usage']['total_tokens'],0)} | {x['checks_passed']}/{x['checks_total']} |" for x in resume['results'])
    text=f"""# Utilité mesurée de GoalPilot 0.2.1

[Rapport interactif](reports/utility.html) · [Données complètes](reports/utility.json) · [Protocole initial](reports/resume-live-001/preregistered-protocol.json)

## Avantage effectivement observé : les reprises

Sur quatre scénarios de reprise, les deux conditions réussissent **4/4 scénarios**. GoalPilot ajoute **{b['agent_turns']} tour Codex contre {a['agent_turns']}**, prend **{number(b['seconds'],3)} s contre {number(a['seconds'],3)} s**, soit **{number(resume['time_reduction_percent'],2)} % de temps en moins**.

Tokens rapportés : **{number(b['reported_tokens'],0)} contre {number(a['reported_tokens'],0)}**, réduction **{number(resume['reported_token_reduction_percent'],2)} %**. Entrée hors cache + sortie : **{number(b['non_cached_input_plus_output'],0)} contre {number(a['non_cached_input_plus_output'],0)}**, réduction **{number(resume['non_cached_token_reduction_percent'],2)} %**. Usage complet dans cette comparaison, modèle observé {', '.join(resume['observed_models'])}.

Ce sont **trois dépôts déjà terminés, repris sans changement**, et **un cas supplémentaire de tâches avec programme principal volontairement cassé**. Les trois reprises inchangées consomment {normal_pilot} appel côté GoalPilot, contre {normal_direct} en direct. Le cas cassé exige une réparation réelle par Codex. Cette répartition ne prétend pas représenter la fréquence des blocages dans tes sessions.

| Projet | État | Condition | Secondes | Nouveaux tours | Tokens | Tests externes |
|---|---|---|---:|---:|---:|---:|
{table}

Le critère préétabli est atteint : **{resume['primary_threshold_met']}**. Il exige quatre réussites externes et locales dans chaque condition, usage complet, même modèle, puis au moins 15 % de gain sur le temps total ou l'entrée hors cache + sortie. Intégrité des sources et du protocole : **{integrity}**.

## Ce qui n'est pas démontré

**Aucun gain général au premier lancement d'un nouveau goal.** La première série V2.1 sur liens, archives et tâches réussit dans les deux conditions mais GoalPilot est plus lent. La campagne prévue de deux répétitions est interrompue au huitième appel par un redémarrage de l'environnement. Elle ne peut pas satisfaire son critère de validation. Sept essais complets et le huitième partiel sont conservés, sans remplacer un résultat par un autre.

Une campagne V2.0 précédente avait déjà été interrompue pendant son septième appel après trois paires complètes. Elle donnait 13,84 % de temps en moins mais davantage de tokens hors cache, sans atteindre son seuil. Les résultats négatifs V1 restent aussi disponibles.

[Tous les essais de premier lancement](reports/v2-evaluation.html) · [Campagne V2.1](reports/v21-validation-001/protocol.json) · [Interruption V2.1](reports/v21-validation-001/interruption.json) · [Interruption V2.0](reports/v2-validation-001/interruption.json) · [V1](MEASUREMENTS-v1.md)

## Sens et limites

- Le coût mesuré est **supplémentaire après une mission précédente**. Les deux conditions commencent avec le même travail déjà réalisé, le même goal, les mêmes vérifications gelées et le même compte rendu. Les appels déjà consommés sont des coûts communs, exclus des deux côtés.
- Direct reçoit aussi le résultat initial des vérifications, puis invoque Codex. GoalPilot vérifie les critères et peut conclure sans invoquer de modèle. Il ne s'agit pas d'une comparaison avec un autre outil qui aurait déjà le même mécanisme de vérification locale.
- L'implémentation de départ est toujours la première répétition GoalPilot, sans sélectionner la plus rapide. Les critères locaux restent inférés ; des tests externes distincts jugent le résultat. Ces derniers ne servent pas aux réparations.
- L'ordre est alterné entre scénarios, avec le même modèle et le même temps restant. La réparation utilise le parcours de reprise du produit, avec ses appels et son temps déjà consommés. Les sources et le protocole sont sauvegardés avant les appels.
- Trois projets synthétiques, un seul cas de régression injectée, aucun échantillon représentatif de goals personnels de plusieurs heures. Pas de mesure de satisfaction ou de fréquence naturelle des blocages, pas d'intervalle de confiance généralisable.
- Entrée hors cache + sortie = entrée + sortie − entrée en cache. Le cache est déjà inclus dans l'entrée. **Ces pourcentages ne sont pas des économies exactes de quota d'abonnement.**

Le curseur du rapport illustre comment le gain de temps changerait selon la part de reprises inchangées, à partir des moyennes de ces seuls essais. Il ne prédit pas ton usage. Seuil de rentabilité illustratif en temps : {number(threshold*100 if threshold is not None else None,2)} % de reprises inchangées.

## Coût total de l'itération

**{campaign['agent_turns']} tours réels démarrés**, **au moins {number(campaign['reported_tokens_lower_bound'],0)} tokens rapportés**, développement et campagnes interrompues compris. Deux consommations sont partielles ; ce total est une borne inférieure, pas une facture complète. Les anciennes dix sessions V1 ne sont pas ajoutées à ce total. Les acteurs scriptés ne figurent pas dans les mesures réelles.

## Vérifications et utilisation

**{fresh['tests']['passed']}/{fresh['tests']['tests_run']} tests locaux passent en {number(fresh['tests']['duration_seconds'],3)} secondes**, sans appel de modèle. Ils vérifient le logiciel et ses calculs, pas l'efficacité générale d'un LLM.

~~~bash
python3 -m goalpilot go "Ton objectif" --repo /chemin/projet --run-dir /chemin/hors-projet/mission
python3 -m goalpilot resume /chemin/hors-projet/mission/mission.json --run-dir /chemin/hors-projet/mission
~~~

Recalcul sans appel distant :

~~~bash
python3 validate.py
python3 tools/build_utility_report.py
~~~

Reproduire l'étude de reprise avec de vrais appels, donc en consommant le compte :

~~~bash
python3 tools/resume_study.py --live --source reports/v21-validation-001 --output /tmp/goalpilot-reprises-nouvelles
~~~
"""
    (ROOT/'MEASUREMENTS.md').write_text(text)
    print(json.dumps({'resume_groups':resume['groups'],'primary_threshold_met':resume['primary_threshold_met'],'iteration_usage':campaign},indent=2))


if __name__=='__main__':main()
