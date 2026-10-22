"""Keep successful and failed quota experiments separate; never convert tokens to quota."""
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/quota-native-live-003'


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
    new_raw=old1['new_known_raw_tokens']+old2['new_known_raw_tokens']+a['new_known_raw_tokens']
    cumulative=6991248+new_raw
    b,c=a['totals']['native_goal'],a['totals']['goalpilot']
    table='| Mesure sur deux goals | Codex natif archivé | GoalPilot 0.7.2 neuf | Écart de coût |\n|---|---:|---:|---:|\n'
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
    body=f'''# GoalPilot 0.7.2 — mesures d’efficacité

{table}

**Ce sont des économies de ressources mesurées sur deux cas ; l’économie exacte de quota d’abonnement n’est pas prouvée.** Les pourcentages de quota exposés par Codex sont entiers, communs au compte et peuvent être retardés. Une variation affichée de zéro ne signifie jamais une consommation nulle.

## Protocole et limites

Deux nouvelles exécutions GoalPilot0.7.2 et les deux contrôles natifs de la campagne001 réutilisés intégralement. Les résultats des contrôles étaient connus avant la conception du candidat. Ils sont historiques, sans randomisation contemporaine ; leurs SHA et origines sont vérifiés et leur coût n’est pas compté deux fois. Les cas Flowdesk et Stockroom sont familiers, déjà utilisés au développement, avec des contrats détaillés malgré les goals larges. Aucune généralisation aux goals personnels ou preuve statistique n’est revendiquée.

Même gpt-6.1-sol, mêmes fichiers initiaux et juge original,900s et plafond souple1,5M tokens bruts par essai. Codex natif reçoit le véritable `/goal` avec toutes ses continuations automatiques et l’effort de codage par défaut. GoalPilot garde cet effort pour le codeur et utilise un contexte séparé à effort faible pour définir ses critères. Tous les coûts de préparation, revue, formatage, code, réparation, tests et fermeture sont comptés. Le juge de recherche est exclu des deux temps et ne fournit aucun feedback aux agents. Aucun essai échoué n’est relancé.

Les critères et les tests d’origine restent gelés avant le code. Le contrôle arithmétique est désormais une auto-vérification dans le tour de génération : **aucun troisième contexte ou passage arithmétique indépendant n’est revendiqué**. La confiance sur les critères reste limitée. Le formatage local ne change aucun nombre ; il supprime au plus quatre guillemets parasites après un token numérique, uniquement avant gel et si le résultat entier compile. Les versions originales sont conservées ; toute autre erreur échoue sans démarrer le codeur.

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

0.7.2 / campagne003 : deux nouveaux candidats, coût nouveau {fmt(a['new_known_raw_tokens'])} tokens bruts. Le rejeu de compilation du programme exposé est un diagnostic local sans API, pas une nouvelle réussite de goal.

Total nouveau connu de cette itération : **{fmt(new_raw)} tokens bruts CLI**. Avec la mise au point et les comparaisons précédentes : **au moins {fmt(cumulative)} tokens bruts CLI**. Un appel d’accès refusé à l’authentification n’a fourni aucun compteur et reste inconnu, pas zéro ; il est conservé dans `quota-optimization-preflight`. La session de développement elle-même n’est pas instrumentée. Aucun amortissement de ces dépenses de recherche n’est prouvé.

Tests locaux de cette version : **{ci['passed']}/{ci['tests_run']}**, {fmt(ci['duration_seconds'],3)}s, zéro API. Les valeurs simulées des tests de mécanismes ne sont jamais ajoutées aux économies observées.

[Analyse complète](reports/quota-native-live-003/analysis.json) · [CSV](reports/quota-native-live-003/trials.csv) · [Protocole](reports/quota-native-live-003/protocol.json) · [Audit](reports/quota-native-live-003/audit.json) · [Campagne001](reports/quota-native-live-001/analysis.json) · [Échec002](reports/quota-native-live-002/analysis.json).
'''
    for src,dst in [('README.md','docs/README-v0.6.2.md'),('MEASUREMENTS.md','MEASUREMENTS-v6.md'),('docs/FINISH.md','docs/FINISH-v0.6.2.md'),('reports/release-decision.json','reports/releases/decision-v0.6.2.json')]:
        if not(ROOT/dst).exists():(ROOT/dst).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/src,ROOT/dst)
    (ROOT/'MEASUREMENTS.md').write_text(body)
    guide=f'''# GoalPilot 0.7.2

Superviseur local pour terminer des objectifs de développement Codex avec critères gelés, vérifications exécutées, corrections et budgets persistants.

{table}

**L’économie exacte de quota d’abonnement n’est pas prouvée.** Deux nouveaux candidats sur des cas connus, comparés à deux témoins natifs historiques dont les résultats étaient déjà connus. Les deux bras produisent du code correct ; le gain de clôture vient de la vérification HTTP depuis l’hôte. [Périmètre et limites](MEASUREMENTS.md) · [Rapport](reports/quota-native-live-003/report.html).

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

Pour un goal avec de nombreux workflows explicites, un contexte séparé prépare des programmes d’acceptation avant l’implémentation. Leurs calculs sont contrôlés dans ce même tour, sans second passage arithmétique indépendant. Les utilitaires stdlib de transport et de rejet sont réutilisés et gelés avec leurs SHA ; des contrôles locaux détectent certaines erreurs de scripts avant de dépenser des appels de code. Un formatage strictement borné peut supprimer un guillemet parasite après un nombre avant gel, en conservant la source brute. Les programmes valides sont inchangés.

Le codeur reçoit les programmes complets et le contrat d’origine, avec son effort par défaut. L’hôte exécute réellement les critères et les tests unittest d’origine conservés, puis transmet les échecs pour correction dans le budget partagé. Une assertion gelée n’est jamais modifiée pour faire passer une implémentation. Les scripts s’exécutent avec les droits de l’utilisateur ; le gel n’est pas une isolation de sécurité.

Les petits goals gardent le parcours adaptatif. `--thorough` garde une revue après réalisation ; `--fast` utilise les vérifications proposées par le codeur. `--checks fichier.json` fournit des critères utilisateur conservés tels quels. Les anciennes missions gardent leur configuration et leur coût lors de `continue`. L’API Python `run_finish` garde `review_context='fresh'` par compatibilité ; le parcours CLI mesuré utilise `review_context='single'`.

`scope_passed` signifie que les scénarios déduits ont réussi, sans garantir la satisfaction personnelle. Le même modèle peut inventer un mauvais critère ; les contrôles locaux ne prouvent pas sa justesse et le codeur peut suradapter les tests visibles. Les critères utilisateur explicites restent préférables lorsqu’ils existent.

## Vérification et historique

`python3 validate.py` : {ci['passed']}/{ci['tests_run']} tests sans API. Le benchmark conserve ses tentatives insuffisantes et échouées. Coût nouveau connu de l’itération : {fmt(new_raw)} tokens bruts CLI ; les économies de mission n’amortissent pas automatiquement la recherche. [Mesures actuelles](MEASUREMENTS.md) · [Historique0.6](MEASUREMENTS-v6.md) · [Historique0.5](MEASUREMENTS-v5.md).
'''
    (ROOT/'README.md').write_text(guide)
    (ROOT/'docs/FINISH.md').write_text(guide)
    (ROOT/'docs/ACCEPTANCE_FIRST.md').write_text(guide)
    (ROOT/'visuals/README.txt').write_text('Les infographies PNG de comparaison portent explicitement sur0.6.2. Elles restent historiques. Les mesures0.7.2 sont dans ../reports/quota-native-live-003/report.html.\n')
    (OUT/'RESULTS.md').write_text(body.replace('(reports/quota-native-live-003/','('))
    decision={'selected_version':'0.7.2','comparison':'reports/quota-native-live-003','closure':c['closed_correct'],'correctness':c['groups_passed'],
              'savings_percent':a['savings_percent'],'joint_target_met':a['joint_20_percent_target_met'],
              'quota_saving_proven':False,'new_known_cli_raw_tokens':new_raw,'known_cumulative_cli_raw_tokens_lower_bound':cumulative,
              'ci':ci,'limits':'Two familiar cases;2fresh candidates against2known historical native controls; no population or exact quota claim. All failed/insufficient studies retained.'}
    (ROOT/'reports/release-decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    page='<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GoalPilot0.7.2 : coût et clôture</title><style>body{font:17px system-ui;max-width:1120px;margin:40px auto;padding:0 20px;background:#f7f9fc;color:#17212c}table{border-collapse:collapse;width:100%;background:white;margin:24px 0}td,th{text-align:left;padding:11px;border-bottom:1px solid #dae0e8}a{color:#145ab1}pre{white-space:pre-wrap;line-height:1.6;font:16px system-ui}.caution{padding:20px;background:#fff0cd}</style><h1>GoalPilot0.7.2 face au /goal Codex natif</h1><p>Deux nouveaux candidats, deux contrôles historiques connus ; domaines familiers. Tous les coûts du superviseur sont comptés.</p>'
    page+='<table><tr><th>Mesure</th><th>Codex natif archivé</th><th>GoalPilot0.7.2 neuf</th></tr>'
    for label,bv,cv in [('Goals corrects et clôturés',str(b['closed_correct'])+'/2',str(c['closed_correct'])+'/2'),('Contrôles réussis',str(b['groups_passed'])+'/52',str(c['groups_passed'])+'/52'),('Secondes',fmt(b['seconds'],3),fmt(c['seconds'],3)),('Tokens bruts',fmt(b['raw_tokens']),fmt(c['raw_tokens'])),('Entrée hors cache + sortie',fmt(b['uncached_tokens']),fmt(c['uncached_tokens']))]:
        page+='<tr>'+''.join('<td>'+html.escape(v)+'</td>'for v in(label,bv,cv))+'</tr>'
    page+='</table><p class="caution"><strong>L’économie exacte de quota n’est pas prouvée.</strong> Compteurs du compte arrondis et potentiellement retardés. Zéro variation affichée ne signifie pas zéro consommation. Aucun avantage statistique général n’est établi.</p><h2>Mesures et limites complètes</h2><pre>'+html.escape(body)+'</pre><p><a href="analysis.json">Analyse exacte</a> · <a href="trials.csv">CSV</a> · <a href="protocol.json">Protocole figé</a> · <a href="audit.json">Audit</a></p></html>'
    (OUT/'report.html').write_text(page)
    print(json.dumps({'version':'0.7.2','savings':a['savings_percent'],'target_met':a['joint_20_percent_target_met'],'new_raw':new_raw,'cumulative_lower_bound':cumulative},indent=2))


if __name__=='__main__':main()
