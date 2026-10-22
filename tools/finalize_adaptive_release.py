"""Keep successful and failed quota experiments separate; never convert tokens to quota."""
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/quota-native-live-006'


def fmt(value,digits=0):
    return f'{value:,.{digits}f}'.replace(',',' ').replace('.',',')


def main():
    a=json.loads((OUT/'analysis.json').read_text())
    audit=json.loads((OUT/'audit.json').read_text())
    protocol=json.loads((OUT/'protocol.json').read_text())
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    assert a['complete']and a['integrity_verified']and a['usage_complete']
    assert a['totals']['goalpilot']['closed_correct']==2 and a['no_paired_regressions']
    assert ci['successful']and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ci['source_fingerprint'].items())
    for ident,origin in protocol['archived_controls'].items():
        assert hashlib.sha256((OUT/'trials'/ident/'record.json').read_bytes()).hexdigest()==origin['record_sha256']
        assert hashlib.sha256((Path(origin['source'])/'record.json').read_bytes()).hexdigest()==origin['record_sha256']
    old1=json.loads((ROOT/'reports/quota-native-live-001/analysis.json').read_text())
    old2=json.loads((ROOT/'reports/quota-native-live-002/analysis.json').read_text())
    old3=json.loads((ROOT/'reports/quota-native-live-003/analysis.json').read_text())
    old4=json.loads((ROOT/'reports/quota-native-live-004/analysis.json').read_text())
    old5=json.loads((ROOT/'reports/quota-native-live-005/analysis.json').read_text())
    new_raw=old1['new_known_raw_tokens']+old2['new_known_raw_tokens']+old3['new_known_raw_tokens']+old4['new_known_raw_tokens']+old5['new_known_raw_tokens']+a['new_known_raw_tokens']
    cumulative=6991248+new_raw
    b,c=a['totals']['native_goal'],a['totals']['goalpilot']
    table='| Mesure sur deux goals | Codex natif archivé | GoalPilot 0.8.1 neuf | Écart de coût |\n|---|---:|---:|---:|\n'
    table+=f"| Goals corrects et clôturés | {b['closed_correct']}/2 | {c['closed_correct']}/2 | — |\n| Contrôles indépendants | {b['groups_passed']}/52 | {c['groups_passed']}/52 | égalité |\n"
    for label,key,digits in [('Temps complet (s)','seconds',3),('Entrée + sortie brutes','raw_tokens',0),('Entrée hors cache + sortie','uncached_tokens',0)]:
        table+=f"| {label} | {fmt(b[key],digits)} | {fmt(c[key],digits)} | {fmt(-a['savings_percent'][key],2)} % |\n"
    target='réussie sur ces observations'if a['joint_20_percent_target_met']else'en échec : au moins un seuil de coût manque'
    rows=[json.loads((OUT/'trials'/item['id']/'record.json').read_text())for item in protocol['order']]
    detail='| Cas | Mode | État final | Contrôles | Secondes | Tokens bruts | Hors cache + sortie |\n|---|---|---|---:|---:|---:|---:|\n'
    quota='| Essai | Fenêtre du compte | Avant | Après | Variation affichée |\n|---|---|---:|---:|---:|\n'
    for r in rows:
        u=r['usage'];detail+=f"| {r['case']} | {r['mode']} | {r['status']} | {sum(j['passed']for j in r['judgments'])}/26 | {fmt(r['seconds'],3)} | {fmt(u['total_tokens'])} | {fmt(u['total_tokens']-u['cached_input_tokens'])} |\n"
        for w in r['quota_observation']['windows']:
            quota+=f"| {r['id']} | {w['bucket']}/{w['window']} | {w['before']['usedPercent']} % | {w['after']['usedPercent']} % | {w['reported_percentage_point_delta']} point(s) |\n"
    body=f'''# GoalPilot 0.8.1 — mesures d’efficacité

{table}

**Ces écarts de ressources portent sur deux cas ; l’économie de quota d’abonnement n’est pas démontrée.** Les pourcentages de quota exposés par Codex sont entiers, communs au compte et peuvent être retardés. Une variation affichée de zéro ne signifie jamais une consommation nulle.

## Protocole et limites

Deux nouvelles exécutions GoalPilot0.8.1 et les deux contrôles natifs de la campagne001 réutilisés intégralement. Les résultats des contrôles étaient connus avant la conception du candidat. Ils sont historiques, sans randomisation contemporaine ; leurs SHA et origines sont vérifiés et leur coût n’est pas compté deux fois. Les cas Flowdesk et Stockroom sont familiers, déjà utilisés au développement, avec des contrats détaillés malgré les goals larges. Aucune généralisation aux goals personnels ou preuve statistique n’est revendiquée.

Même gpt-6.1-sol, mêmes fichiers initiaux et juge original,900s et plafond souple1,5M tokens bruts par essai. Codex natif reçoit le véritable `/goal` avec toutes ses continuations automatiques et l’effort de codage par défaut. GoalPilot demande un effort faible pour le premier passage de code et moyen pour les réparations déclenchées par les contrôles de l’hôte. Cette différence d’effort est volontaire ; le modèle reste le même. Le produit commence par la vérification locale et engage une revue indépendante si la livraison ne peut pas être vérifiée par des suites renforcées gelées. Tous les coûts de préparation, revue, formatage, code, réparation, tests et fermeture sont comptés. Le juge de recherche est exclu des deux temps et ne fournit aucun feedback aux agents. Aucun essai échoué n’est relancé.

Les tests d’origine sont gelés avant le code. Le codeur renforce ensuite les tests du projet et propose des commandes. L’hôte conserve ces suites unittest APRÈS livraison, puis les gèle AVANT toute réparation. Pour un goal large, le parcours local exige une croissance des assertions et des suites reconnues ; sinon une revue indépendante intervient après réalisation. **Les nouveaux tests viennent du codeur et ne sont pas une acceptation indépendante.** Le gel empêche leur affaiblissement pendant les réparations, sans prouver leur couverture sémantique. La croissance des assertions est un indicateur de routage local, pas une preuve de complétude. Le juge externe original reste inchangé et ne fournit aucun feedback aux agents.

La cible pratique préenregistrée (deux goals corrects et conclus, aucune régression, au moins20% sur chacun des trois coûts) est **{target}**. Ce seuil ne constitue pas une significativité statistique. Sources figées et compteurs bruts vérifiés ; audit intègre : {a['integrity_verified']}. Tous les compteurs de cette comparaison sont complets.

## Résultats par cas

{detail}

Les deux bras produisent du code correct. Les deux goals natifs restent bloqués sur la vérification d’une vraie socket HTTP dans leur sandbox. GoalPilot vérifie HTTP depuis l’hôte et clôture. Ce gain de clôture mesure cette capacité dans cet environnement ; il ne prouve pas une meilleure qualité de code générale.

## Quota affiché

{quota}

Les relevés des contrôles viennent de leurs exécutions historiques ; les candidats sont mesurés plus tard. Arrondi inconnu, délai inconnu et activité concurrente possible empêchent une attribution exacte. On ne transforme ni les tokens ni ces deltas en pourcentage exact de quota économisé.

## Tentatives conservées et coût de recherche

0.7.0 / campagne001 : quatre essais neufs,2/2 goals GoalPilot conclus,52/52 contrôles dans les deux bras, seulement0,539% de tokens hors cache et1,695% de temps économisés. La cible échoue. Coût nouveau : {fmt(old1['new_known_raw_tokens'])} tokens bruts.

0.7.1 / campagne002 : premier candidat interrompu par un refus de syntaxe AVANT tout codeur,0/26 contrôles sur le prototype inchangé ; le second candidat prévu n’est pas lancé selon la règle d’arrêt. Ce n’est ni un succès de goal ni une économie revendiquée. Coût nouveau : {fmt(old2['new_known_raw_tokens'])} tokens bruts. Les contrôles natifs copiés ne sont pas refacturés dans ce coût.

0.7.2 / campagne003 : deux nouveaux candidats correctement conclus, mais seulement5,410% de tokens hors cache et9,800% de temps économisés ; cible en échec. Coût nouveau {fmt(old3['new_known_raw_tokens'])} tokens bruts. Le rejeu du programme syntaxiquement exposé est un diagnostic local sans API, pas une nouvelle réussite de goal.

0.8.0 / campagne004 : redémarrage externe de l’environnement pendant le premier tour de code. Le code partiel passe26/26 contrôles, mais aucun tour final ni compteur complet : aucune clôture normale ou économie revendiquée. Consommation connue **au moins {fmt(old4['new_known_raw_tokens'])} tokens bruts** ; le vrai total et le temps final sont inconnus. Le second candidat prévu n’a pas été lancé. Le résultat et le dénominateur prévus sont conservés.

0.8.0 / campagne005 : deux nouveaux candidats après l’interruption004, avec exactement les mêmes sources et le même juge. Les deux goals sont corrects et conclus, mais les coûts hors cache augmentent de3,697% et le temps ne baisse que de5,387% : la cible échoue. Coût nouveau {fmt(old5['new_known_raw_tokens'])} tokens bruts, sans refacturer les témoins natifs.

0.8.1 / campagne006 : deux nouveaux candidats à effort adaptatif, coût nouveau complet {fmt(a['new_known_raw_tokens'])} tokens bruts. Les témoins natifs gardent leur effort par défaut ; le candidat demande un effort faible initialement, moyen seulement si la vérification de l’hôte exige une réparation. L’effet de ce réglage est volontairement inclus dans le produit. Aucun contrôle Codex réglé manuellement au même faible effort n’a été exécuté : ce n’est pas une preuve que le superviseur seul bat ce contrôle alternatif.

Les campagnes001-003 ont consommé2 850 458 nouveaux tokens sous leur plafond observé3M. Les études0.8numérotées004-006partagent le plafond observé1M, en comptant le coût connu de004comme borne inférieure. Les inconnus ne sont pas zéro et le plafond observé ne garantit pas un maximum réel exact. Les protocoles antérieurs restent inchangés.

Total nouveau connu de cette itération : **au moins {fmt(new_raw)} tokens bruts CLI**. Avec la mise au point et les comparaisons précédentes : **au moins {fmt(cumulative)} tokens bruts CLI**. La fin de consommation du tour interrompu004reste inconnue. Un appel d’accès refusé à l’authentification n’a fourni aucun compteur et reste inconnu, pas zéro ; il est conservé dans `quota-optimization-preflight`. La session de développement elle-même n’est pas instrumentée. Aucun amortissement de ces dépenses de recherche n’est prouvé.

Tests locaux de cette version : **{ci['passed']}/{ci['tests_run']}**, {fmt(ci['duration_seconds'],3)}s, zéro API. Les valeurs simulées des tests de mécanismes ne sont jamais ajoutées aux économies observées.

[Analyse complète](reports/quota-native-live-006/analysis.json) · [CSV](reports/quota-native-live-006/trials.csv) · [Protocole](reports/quota-native-live-006/protocol.json) · [Audit](reports/quota-native-live-006/audit.json) · [Campagne001](reports/quota-native-live-001/analysis.json) · [Échec002](reports/quota-native-live-002/analysis.json).
'''
    for src,dst in [('README.md','docs/README-v0.7.2.md'),('MEASUREMENTS.md','MEASUREMENTS-v7.2.md'),('reports/release-decision.json','reports/releases/decision-v0.7.2.json'),('README.md','docs/README-v0.6.2.md'),('MEASUREMENTS.md','MEASUREMENTS-v6.md'),('docs/FINISH.md','docs/FINISH-v0.6.2.md'),('reports/release-decision.json','reports/releases/decision-v0.6.2.json')]:
        if not(ROOT/dst).exists():(ROOT/dst).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/src,ROOT/dst)
    (ROOT/'MEASUREMENTS.md').write_text(body)
    guide=f'''# GoalPilot 0.8.1

Superviseur local pour terminer des objectifs de développement Codex avec critères gelés, vérifications exécutées, corrections et budgets persistants.

{table}

**L’économie de quota d’abonnement n’est pas démontrée.** Deux nouveaux candidats sur des cas connus, comparés à deux témoins natifs historiques dont les résultats étaient déjà connus. Les deux bras produisent du code correct ; le gain de clôture vient de la vérification HTTP depuis l’hôte. [Périmètre et limites](MEASUREMENTS.md) · [Rapport](reports/quota-native-live-006/report.html).

## Utilisation

Python3.11+, Linux/macOS ou WSL, Codex CLI connecté ; aucune dépendance Python. Le produit pilote la CLI, sans s’insérer dans le `/goal` de l’application.

```bash
codex login status
python3 -m goalpilot quota
python3 -m goalpilot go "Termine ce projet et ses workflows documentés" \\
  --repo /chemin/projet --run-dir /chemin/hors-projet/mission-001 \\
  --wall-seconds 900 --max-calls 6 --max-tokens 1000000 \\
  --max-uncached-tokens 80000
python3 -m goalpilot status /chemin/hors-projet/mission-001
python3 -m goalpilot continue /chemin/hors-projet/mission-001
```

Le plafond hors cache est optionnel. Il compte entrée−cache+sortie et se conserve lors d’une reprise. Il empêche les appels suivants lorsque le coût observé atteint la limite ou qu’un compteur est inconnu. C’est un plafond **souple entre appels** : un appel peut le dépasser, et ce compteur n’est pas le quota exact de l’abonnement. Un budget trop petit peut laisser un goal inachevé.

## Fonctionnement

Le parcours CLI commence par la réalisation et les tests à effort de raisonnement faible, sans revue systématique. Si les contrôles de l’hôte échouent, les appels de réparation utilisent l’effort moyen. `--thorough` conserve l’effort configuré par défaut et une revue systématique. Les tests unittest d’origine sont conservés avant toute modification. Le codeur doit ajouter des tests comportementaux couvrant les workflows documentés, avec données temporaires et transport HTTP/CLI si pertinent. À la livraison, l’hôte copie et gèle ces tests renforcés avant toute réparation. Il exécute ces suites et les critères proposés contre le code, puis transmet les échecs pour correction dans le budget partagé.

Sur les goals larges, l’absence de renforcement des assertions ou de suites unittest reconnues déclenche une revue indépendante après réalisation. La croissance des assertions ne prouve pas la complétude ; les tests de livraison sont proposés par le codeur. Le gel empêche leur affaiblissement pendant les réparations, mais ne les rend pas indépendants. Les scripts s’exécutent avec les droits de l’utilisateur ; le gel n’est pas une isolation de sécurité.

Les petits goals gardent le parcours adaptatif. `--thorough` garde une revue après réalisation ; `--fast` utilise les vérifications proposées par le codeur. `--checks fichier.json` fournit des critères utilisateur conservés tels quels. Les anciennes missions gardent leur configuration et leur coût lors de `continue`. L’API Python `run_finish` garde `review_context='fresh'` par compatibilité ; le parcours CLI mesuré utilise `review_context='local', initial_effort='low'`, avec réparations à effort moyen.

`scope_passed` signifie que les scénarios déduits ont réussi, sans garantir la satisfaction personnelle. Le même modèle peut inventer un mauvais critère ; les contrôles locaux ne prouvent pas sa justesse et le codeur peut suradapter les tests visibles. Les critères utilisateur explicites restent préférables lorsqu’ils existent.

## Vérification et historique

`python3 validate.py` : {ci['passed']}/{ci['tests_run']} tests sans API. Le benchmark conserve ses tentatives insuffisantes et échouées. Coût nouveau connu de l’itération : {fmt(new_raw)} tokens bruts CLI ; les économies de mission n’amortissent pas automatiquement la recherche. [Mesures actuelles](MEASUREMENTS.md) · [Historique0.7](MEASUREMENTS-v7.2.md) · [Historique0.6](MEASUREMENTS-v6.md) · [Historique0.5](MEASUREMENTS-v5.md).
'''
    (ROOT/'README.md').write_text(guide)
    (ROOT/'docs/FINISH.md').write_text(guide)
    (ROOT/'docs/ACCEPTANCE_FIRST.md').write_text(guide)
    (ROOT/'visuals/README.txt').write_text('Les deux infographies PNG correspondent au parcours0.6.2 et restent historiques ; le défaut0.8 commence par coder puis gèle les tests renforcés. Les mesures0.8.1 sont dans ../reports/quota-native-live-006/report.html.\n')
    (OUT/'RESULTS.md').write_text(body.replace('(reports/quota-native-live-006/','('))
    decision={'selected_version':'0.8.1','comparison':'reports/quota-native-live-006','closure':c['closed_correct'],'correctness':c['groups_passed'],
              'savings_percent':a['savings_percent'],'joint_target_met':a['joint_20_percent_target_met'],
              'quota_saving_proven':False,'some_research_usage_unknown':True,'interrupted_study004_retained':True,'new_known_cli_raw_tokens':new_raw,'known_cumulative_cli_raw_tokens_lower_bound':cumulative,
              'ci':ci,'limits':'Two familiar cases;2fresh candidates against2known historical native controls; no population or exact quota claim. All failed/insufficient studies retained.'}
    (ROOT/'reports/release-decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    page='<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GoalPilot0.8.1 : coût et clôture</title><style>body{font:17px system-ui;max-width:1120px;margin:40px auto;padding:0 20px;background:#f7f9fc;color:#17212c}table{border-collapse:collapse;width:100%;background:white;margin:24px 0}td,th{text-align:left;padding:11px;border-bottom:1px solid #dae0e8}a{color:#145ab1}pre{white-space:pre-wrap;line-height:1.6;font:16px system-ui}.caution{padding:20px;background:#fff0cd}</style><h1>GoalPilot0.8.1 face au /goal Codex natif</h1><p>Deux nouveaux candidats, deux contrôles historiques connus ; domaines familiers. Tous les coûts du superviseur sont comptés.</p>'
    page+='<table><tr><th>Mesure</th><th>Codex natif archivé</th><th>GoalPilot0.8.1 neuf</th></tr>'
    for label,bv,cv in [('Goals corrects et clôturés',str(b['closed_correct'])+'/2',str(c['closed_correct'])+'/2'),('Contrôles réussis',str(b['groups_passed'])+'/52',str(c['groups_passed'])+'/52'),('Secondes',fmt(b['seconds'],3),fmt(c['seconds'],3)),('Tokens bruts',fmt(b['raw_tokens']),fmt(c['raw_tokens'])),('Entrée hors cache + sortie',fmt(b['uncached_tokens']),fmt(c['uncached_tokens']))]:
        page+='<tr>'+''.join('<td>'+html.escape(v)+'</td>'for v in(label,bv,cv))+'</tr>'
    page+='</table><p class="caution"><strong>L’économie de quota n’est pas démontrée.</strong> Compteurs du compte arrondis et potentiellement retardés. Zéro variation affichée ne signifie pas zéro consommation. Aucun avantage statistique général n’est établi.</p><h2>Mesures et limites complètes</h2><pre>'+html.escape(body)+'</pre><p><a href="analysis.json">Analyse exacte</a> · <a href="trials.csv">CSV</a> · <a href="protocol.json">Protocole figé</a> · <a href="audit.json">Audit</a></p></html>'
    (OUT/'report.html').write_text(page)
    print(json.dumps({'version':'0.8.1','savings':a['savings_percent'],'target_met':a['joint_20_percent_target_met'],'new_raw':new_raw,'cumulative_lower_bound':cumulative},indent=2))


if __name__=='__main__':main()
