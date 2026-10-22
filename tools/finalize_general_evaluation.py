"""Build final measured documentation; never executes a model."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.general.report import write


def main():
    output=ROOT/'reports/general-live-001'
    report=write(output);manifest=json.loads((output/'manifest.json').read_text())
    report['source_snapshot_integrity']=all(hashlib.sha256((output/'source_snapshot'/name).read_bytes()).hexdigest()==sha for name,sha in manifest['source_fingerprint'].items())
    report['preregistration_integrity']=manifest==json.loads((output/'preregistered-protocol.json').read_text())
    report['local_tests']=json.loads((ROOT/'reports/tests.json').read_text())
    report['recorded_at']=datetime.now(timezone.utc).isoformat()
    report['announced_deliveries_rejected_by_external_judge']={
        mode:sum(r['status'] in ('delivered','scope_passed','completed') and not r['artifact_success']
                 for r in report['records'] if r['mode']==mode) for mode in ('direct','goalpilot')}
    report['quality_by_suite']={}
    for mode in ('direct','goalpilot'):
        report['quality_by_suite'][mode]={}
        for group in ('delivery','errors_integrity','blocker','restart_newdata'):
            checks=[check for r in report['records'] if r['mode']==mode for check in r['checks'] if check['id']==group]
            report['quality_by_suite'][mode][group]={'passed':sum(x['passed'] for x in checks),'total':len(checks)}
    pairs={}
    for row in report['records']:pairs.setdefault((row['case'],row['repeat']),{})[row['mode']]=row
    comparisons=[]
    for (case,repetition),pair in pairs.items():
        if set(pair)!= {'direct','goalpilot'} or any(x['infrastructure_interrupted'] for x in pair.values()):continue
        direct,pilot=pair['direct'],pair['goalpilot']
        dc=direct['usage']['total_tokens']-direct['usage']['cached_input_tokens']
        pc=pilot['usage']['total_tokens']-pilot['usage']['cached_input_tokens']
        comparisons.append({'case':case,'repeat':repetition,
            'time_reduction_percent':100*(1-pilot['seconds']/direct['seconds']) if direct['seconds'] else None,
            'non_cached_token_reduction_percent':100*(1-pc/dc) if dc and direct['usage']['usage_complete'] and pilot['usage']['usage_complete'] else None})
    report['paired_resource_comparisons']=comparisons
    report['consistency']={}
    for key in ('time_reduction_percent','non_cached_token_reduction_percent'):
        values=[x[key] for x in comparisons if x[key] is not None]
        report['consistency'][key]={'wins':sum(x>0 for x in values),'pairs':len(values),'median':statistics.median(values) if values else None,'range':[min(values),max(values)] if values else None}
    (ROOT/'reports/general-evaluation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    if not report['finished']:raise ValueError('Campaign incomplete; preserve partial data without a final efficacy claim')
    a,b=report['groups']['direct'],report['groups']['goalpilot']
    def n(x,d=2):return 'indisponible' if x is None else f'{x:,.{d}f}'.replace(',',' ')
    table='\n'.join(f"| {r['case']} | {r['repeat']} | {r['mode']} | {'oui' if r['autonomous_success'] else 'non'} | {n(r['seconds'],3)} | {r['usage']['total_tokens']} | {r['new_agent_turns']} | {sum(x['passed'] for x in r['checks'])}/{len(r['checks'])} |" for r in report['records'])
    conclusion='Critère préétabli atteint sur ce corpus.' if report['primary_threshold_met'] else 'Avantage général non démontré sur ce corpus.'
    text=f"""# Évaluation autonome générale de GoalPilot

[Rapport interactif](reports/general-live-001/report.html) · [JSON](reports/general-evaluation.json) · [CSV](reports/general-live-001/trials.csv) · [Protocole initial](reports/general-live-001/preregistered-protocol.json)

## Résultat mesuré

**{conclusion}** Trois applications avec plusieurs composants, deux répétitions, 12 essais prévus. Objectifs livrés correctement sans aide humaine : **GoalPilot {b['autonomous_successes']}/{b['eligible_trials']} ; Codex direct {a['autonomous_successes']}/{a['eligible_trials']}**. Interruptions d'infrastructure : {a['infrastructure_interruptions']+b['infrastructure_interruptions']}, conservées séparément sans remplacement.

La réussite est évaluée par les critères externes prédéfinis. Le gain observé de consommation ne doit pas être présenté comme davantage de goals aboutis : le nombre de gains appariés de réussite est {report['quality_wins']}, et celui des régressions {report['quality_losses']}. Les temps et tokens sont affichés séparément ; ils ne sont pas une conversion en quota d'abonnement.

| Mesure, tous les essais comptés | Codex direct | GoalPilot |
|---|---:|---:|
| Objectifs livrés sans aide | {a['autonomous_successes']}/{a['eligible_trials']} | {b['autonomous_successes']}/{b['eligible_trials']} |
| Artefacts corrects, indépendamment de la livraison | {a['artifact_successes']} | {b['artifact_successes']} |
| Défauts de départ résolus | {a['blockers_resolved']}/{a['eligible_trials']} | {b['blockers_resolved']}/{b['eligible_trials']} |
| Résultats stables sur nouvelles entrées | {a['stable_on_new_inputs']}/{a['eligible_trials']} | {b['stable_on_new_inputs']}/{b['eligible_trials']} |
| Temps complet du produit, secondes | {n(a['seconds'],3)} | {n(b['seconds'],3)} |
| Tokens rapportés | {n(a['reported_tokens'],0)} | {n(b['reported_tokens'],0)} |
| Entrée hors cache + sortie | {n(a['non_cached_input_plus_output'],0)} | {n(b['non_cached_input_plus_output'],0)} |
| Tokens rapportés par succès, échecs compris | {n(a['reported_tokens_per_success'],0)} | {n(b['reported_tokens_per_success'],0)} |
| Hors cache + sortie par succès | {n(a['non_cached_tokens_per_success'],0)} | {n(b['non_cached_tokens_per_success'],0)} |
| Tours agent démarrés | {a['agent_turns']} | {b['agent_turns']} |
| Inputs humains après lancement | {a['human_inputs_after_start']} | {b['human_inputs_after_start']} |
| Répétitions identiques de commandes en échec | {a['repeated_identical_failed_commands']} | {b['repeated_identical_failed_commands']} |

Réduction de temps : {n(report['time_reduction_percent'])} %. Réduction de tokens rapportés : {n(report['reported_token_reduction_percent'])} %. Réduction hors cache + sortie : {n(report['non_cached_token_reduction_percent'])} %. Un nombre négatif indique une hausse. Comparaison complète de consommation disponible : {report['cost_comparison_available']}.

Gains appariés de réussite : {report['quality_wins']}. Régressions appariées : {report['quality_losses']}. Modèle observé : {', '.join(report['observed_models'])}. Les essais sont autonomes après le prompt initial ; les interventions automatiques de GoalPilot restent comprises dans son coût.

Livraisons annoncées mais rejetées par les contrôles externes : direct {report['announced_deliveries_rejected_by_external_judge']['direct']}, GoalPilot {report['announced_deliveries_rejected_by_external_judge']['goalpilot']}. Les taux par dimension de qualité sont conservés dans le JSON.

Régularité descriptive : GoalPilot est plus rapide dans {report['consistency']['time_reduction_percent']['wins']}/{report['consistency']['time_reduction_percent']['pairs']} paires et utilise moins de tokens hors cache + sortie dans {report['consistency']['non_cached_token_reduction_percent']['wins']}/{report['consistency']['non_cached_token_reduction_percent']['pairs']} paires. Médianes et étendues des écarts appariés figurent dans le JSON ; ces paires ne représentent que trois projets indépendants.

## Tous les essais

| Projet | Répétition | Condition | Goal livré | Temps, s | Tokens | Tours | Suites externes |
|---|---:|---|---|---:|---:|---:|---:|
{table}

Les erreurs détaillées sont dans les fichiers trials/*/judge-*.json et record.json. Aucun essai raté n'est remplacé. Une interruption pendant l'exécution garde les compteurs observés, marqués partiels. Une interruption du seul juge peut être réparée sans réappeler le modèle.

## Ce qui est éprouvé

- **Desk** : HTTP/SQLite, commentaires, filtres, rapports, export atomique, migration d'anciennes données et créations concurrentes. Le prototype ne démarre pas à cause d'un import indisponible.
- **Queue** : migration SQLite, idempotence, transitions, baux expirés, reprise après worker absent, tentatives limitées, concurrence, statistiques et export.
- **Vault** : migration d'historique, déduplication SHA256, détection honnête d'objets endommagés, restauration sans écrasement, chemins dangereux, rétention et fichiers étrangers préservés.

Le juge externe comporte quatre groupes par projet sur deux graines figées avant les appels : livraison, erreurs/intégrité, défaut initial et redémarrage/nouvelles données. Les tests ne sont pas transmis aux agents et ne servent pas aux réparations. Les tests proposés par GoalPilot sont distincts et ne suffisent jamais à réussir l'évaluation.

Avant les appels, les trois prototypes échouent aux quatre groupes. Trois références indépendantes les réussissent ; le juge rejette aussi des mutations sémantiques (priorité booléenne, absence de contrôle du propriétaire de bail et fausse restauration de contenu corrompu). [Prévalidation](reports/general-live-001/preflight.json).

## Protocole et seuil

Le même code et les mêmes données initiales sont matérialisés pour les deux conditions. Le délai total est {manifest['seconds_per_trial']} secondes ; direct a une session autonome continue, GoalPilot le parcours go complet avec au plus trois tours dans ce même délai. Préparation, rapports, vérifications locales, réparations et fermeture sont compris dans le temps du produit. Le juge externe est chronométré séparément et exclu des deux côtés.

L'ordre est alterné entre projets et inversé à la seconde répétition. Le protocole, les sources, budgets et graines ont été figés avant les appels. Intégrité du protocole : {report['preregistration_integrity']}. Intégrité des sources archivées : {report['source_snapshot_integrity']}.

Le premier appel direct a été exécuté sous le protocole pilote archivé, puis repris sans nouvel appel après une correction du collecteur (sortie de commande null et conservation des jugements déjà terminés). Les traitements, prompts, budgets, tâches, graines et le juge sont inchangés. Les jugements originaux, y compris un éventuel échec, sont conservés verbatim. [Provenance et différence de source](reports/general-live-001/first-trial-provenance.json) ; le protocole pilote et ses sources restent dans general-pilot-001.

Critère préétabli : campagne entière comparable, même modèle, aucune régression appariée, puis au moins deux objectifs livrés supplémentaires ; ou réussite complète égale avec au moins 15 % de gain de temps total ou d'entrée hors cache + sortie. Les comparaisons de coût exigent une consommation complète. Le seuil ne remplace pas une preuve statistique sur une population de projets.

## Limites à conserver

Trois projets synthétiques en Python avec interfaces documentées. Les prompts généraux sont vagues, mais les contrats publics bornent l'ambition. Deux répétitions ne font pas six projets indépendants. Le budget de dix minutes est un plafond : les durées réellement observées figurent dans la table, et aucun gain sur des sessions de plusieurs heures n'est établi.

Le taux de livraison repose sur des critères exécutables indépendants, sans mesure de satisfaction personnelle. Les défauts sont contrôlés ; ils ne représentent pas la fréquence naturelle des blocages. Les nouvelles entrées et redémarrages mesurent la robustesse, pas plusieurs jours d'utilisation réelle.

Entrée hors cache + sortie = entrée + sortie − entrée en cache. Le seuil de tokens est souple, contrôlé entre tours et peut être dépassé dans un tour. Une consommation manquante n'est jamais zéro. **Aucun pourcentage exact de quota d'abonnement ni tarif n'est déduit des tokens.**

Les intervalles de Wilson du JSON décrivent les comptes d'essais ; ils ignorent la corrélation des répétitions d'un même projet et ne sont pas des intervalles de confiance d'efficacité générale.

## Coût de cette campagne et tests locaux

{a['agent_turns']+b['agent_turns']} tours réels démarrés, {n(a['reported_tokens']+b['reported_tokens'],0)} tokens rapportés ; usage complet : {a['usage_complete'] and b['usage_complete']}. Les campagnes précédentes sont séparées de ce total.

{report['local_tests']['passed']}/{report['local_tests']['tests_run']} tests locaux passent en {n(report['local_tests']['duration_seconds'],3)} secondes, sans appel de modèle. Ils vérifient les mécanismes, le juge, ses mutations, les coûts incluant les échecs, les interruptions et l'absence de relance d'un essai déjà enregistré.

## Reproduire

~~~bash
python3 validate.py
python3 -m evaluation.general create --output /tmp/goalpilot-general --seconds 600 --repeats 2
python3 tools/run_general_campaign.py --live --output /tmp/goalpilot-general
python3 -m evaluation.general report --output /tmp/goalpilot-general
~~~

La commande --live consomme le compte connecté. La reproduction sur ce corpus publié ne constitue pas une nouvelle validation sur des tâches inédites.

[Anciennes mesures sur les reprises](MEASUREMENTS-resumes.md) · [Rapport des reprises](reports/utility.html) · [Mesures V1](MEASUREMENTS-v1.md). Les anciens résultats, simulations et interruptions ne sont pas effacés ni mélangés à cette campagne.
"""
    (ROOT/'MEASUREMENTS.md').write_text(text)
    print(json.dumps({key:report[key] for key in ('finished','groups','primary_threshold_met','time_reduction_percent','non_cached_token_reduction_percent','quality_wins','quality_losses')},indent=2))


if __name__=='__main__':main()
