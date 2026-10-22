"""Publish the bounded evidence in repository docs after the model campaign ends."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    proof=json.loads((ROOT/'reports/native-goals-proof.json').read_text());data=proof['measurement'];m=data['protocol'];d,g=(data['groups'][k]for k in('native_goal','goalpilot'));ci=json.loads((ROOT/'reports/tests.json').read_text());qualified=proof['qualified_completion_advantage_observed']
    for source,dest in [('README.md','docs/README-v0.4.1.md'),('MEASUREMENTS.md','MEASUREMENTS-v4.md'),('docs/FINISH.md','docs/FINISH-v0.4.1.md')]:
        if not(ROOT/dest).exists():shutil.copy2(ROOT/source,ROOT/dest)
    title='Un avantage de conclusion a été observé sur le second objectif.'if qualified else'Aucun avantage de conclusion qualifié n’est établi.'
    if not data['complete']:title='La comparaison est incomplète ; aucun gain de conclusion qualifié.'
    rows=proof['corrected_analysis']['corrected_rows']if proof['corrected_analysis']else[]
    table='\n'.join(f"| {r['case']} | {'/goal natif'if r['mode']=='native_goal'else'GoalPilot'} | {r['status']} | {'oui'if r['success']else'non'} | {sum(j['passed']for j in r['judgments'])}/{len(r['judgments'])} | {r['seconds']:.6f} |"for r in rows)
    delta=proof['total_resource_changes_percent']
    resource_note=f"**Bilan total : {delta['seconds']:+.2f} % de temps, {delta['reported_tokens']:+.2f} % de tokens rapportés, {delta['uncached_input_plus_output']:+.2f} % de tokens hors cache + sortie.** Les trois économies globales ne sont pas établies ensemble."if all(v is not None for v in delta.values())else'La comparaison complète des ressources reste indisponible.'
    text=f'''# GoalPilot {m['product_version']} — objectifs plus ambitieux et vrai /goal

**{title}** Les chiffres ci-dessous utilisent l’analyse corrigée, avec les scores originaux conservés séparément. Ils concernent {len(rows)} exécutions sur quatre prévues, sur deux périmètres liés d’un même moteur de workflows.

[Rapport lisible](reports/native-goals-proof.html) · [Données et audits](reports/native-goals-proof.json) · [CSV corrigé](reports/native-goals-live-001/corrected-trials.csv) · [Scores bruts](reports/native-goals-live-001/trials.csv) · [Protocole original](reports/native-goals-live-001/protocol.json) · [Erratum fixé avant le second objectif](reports/native-goals-live-001/fairness/oracle-erratum.json)

| Objectif | Mode | Clôture | Livré et validé | Groupes corrigés | Secondes actives |
|---|---|---|---:|---:|---:|
{table}

| Mesure | /goal natif | GoalPilot |
|---|---:|---:|
| Goals livrés, analyse corrigée | {d['completed_goals']}/{d['runs']} | {g['completed_goals']}/{g['runs']} |
| Livrables corrects sans condition de clôture | {d['artifact_successes']} | {g['artifact_successes']} |
| Clôtures normales avec défauts cachés | {d['false_completion']} | {g['false_completion']} |
| Secondes actives totales | {d['seconds']:.6f} | {g['seconds']:.6f} |
| Tokens rapportés connus | {d['reported_tokens']:,} | {g['reported_tokens']:,} |
| Entrée hors cache + sortie connues | {d['uncached_input_plus_output']:,} | {g['uncached_input_plus_output']:,} |
| Consommation complète | {d['usage_complete']} | {g['usage_complete']} |

{resource_note}

Paires gagnées dans l’analyse corrigée : {data['quality_wins']}, perdues : {data['quality_losses']}. Avantage prospectif sur le second objectif après audit : **{qualified}**. Le premier périmètre corrigé est rétrospectif ; il ne sert pas seul à confirmer un avantage nouveau.

## Ce qui a changé dans l’évaluation

Le comparateur est enfin le **vrai /goal natif**, via une session persistante et l’API native. Le pilote attend l’état `complete` ET la fin du dernier tour, et laisse fonctionner les continuations automatiques. Un simple message final ne suffit pas. Les API de goal ne fonctionnent pas dans les anciennes sessions éphémères.

Les objectifs portent sur un moteur complet (16 opérations : graphes/révisions, claims, expiration, retries, annulation, artifacts, rétention, schedules, sauvegarde/restauration, CLI/HTTP), puis sur une extension avec workers exécutant de vraies tâches emit/sum/join/collect/artifact/fail. Le second périmètre ajoute six groupes de parcours réels et concurrents aux 26 vérifications du noyau. Les deux périmètres partagent du code et ne sont pas deux projets indépendants. Le socle transactionnel SQLite et le transport sont fournis ; le domaine commence vide.

Même modèle gpt-6.1-sol, mêmes fichiers initiaux et plafond de 900 secondes par essai. Les tokens sont plafonnés de façon souple entre les tours, à 1,5 million par essai et trois millions observés entre essais pour la comparaison. Les tours du produit, y compris revues et reprises, restent inclus. Les coûts des échecs sont conservés. Aucun feedback caché n’est transmis aux modèles, et aucun essai raté n’est remplacé.

## Erreur du juge : aucune fausse preuve

Le juge initial refusait un graphe vide alors que le contrat exigeait seulement des IDs non vides et ne rendait pas la liste non vide obligatoire. Le natif respectait les cas explicitement invalides mais acceptait ce choix non spécifié. Nous ne comptons pas cet écart comme un défaut ni comme un avantage du produit.

Les jugements bruts et le protocole initial restent inchangés. Une analyse séparée retire **uniquement** cet input non spécifié, sans toucher aux cycles, dépendances, types, propriétés de graphes ni aux autres groupes. Le code de cette correction et sa règle ont été figés par SHA-256 avant le démarrage des deux essais du second objectif. La correction du premier est rétrospective. Le critère brut original n’est pas utilisé comme preuve ; le gain qualifié doit être observé sur le second objectif et sans perte appariée corrigée.

## Les échecs des versions précédentes restent conservés

La première campagne 0.5.0 prévoyait douze exécutions. Elle s’est arrêtée après trois, quand la première paire rendait son critère sans régression impossible. Cet arrêt anticipé n’était pas prévu au protocole ; cette étude est conservée comme incomplète et en échec. Codex direct et GoalPilot avaient tous deux un support correct (26/26 groupes), mais GoalPilot arrêtait sa revue à 677,366978 s alors qu’il restait environ 223 s. Stockroom avec GoalPilot passe ensuite en 405,705855 s ; son comparateur n’a pas été lancé et n’est jamais inventé. [Résultats](reports/ambitious-proof.html).

La reprise 0.5.1 a récupéré sept programmes complets dans la réponse tronquée et obtenu le dernier. Un vérificateur externe ne trouvait ensuite pas le module du projet ; trois tours de code inutiles n’ont pas réparé ce problème d’hôte. Le livrable restait correct, mais la mission finissait au budget. Coût nouveau de cet essai de développement : quatre tours, **334 225 tokens connus, consommation partielle**. Les deux anciens appels copiés ne sont jamais facturés à nouveau dans les coûts. [Échec conservé](reports/audit-rescue-001/result.json).

La version 0.5.2 fournit le contexte d’import du dépôt aux probes Python déduits et gelés, sans changer leurs assertions ni les critères utilisateur. Sur un **rejeu sans API du code original inchangé**, les neuf mêmes vérifications passent. Ce rejeu n’est pas une nouvelle réussite réelle ni une mesure d’économie future. [Rejeu 9/9](reports/probe-context-replay-001/report.json).

## Coût de toute cette itération et limites

Coût connu : **au moins {proof['development_costs']['iteration_known_token_lower_bound']:,} tokens rapportés**, comprenant l’étude 0.5.0 incomplète, les deux essais techniques de l’API, les nouveaux appels de reprise et la comparaison actuelle. Les métriques historiques copiées ne sont pas ajoutées deux fois. Des compteurs sont partiels ; le coût exact intégral est inconnu.

Les tokens rapportés sont entrée + sortie ; le cache fait déjà partie de l’entrée. L’entrée hors cache + sortie est calculée séparément. Une mesure partielle interdit une économie complète. Aucune conversion exacte en quota d’abonnement, argent ou heures personnelles.

Le premier test technique natif a révélé une erreur d’écoute avant la fin du tour ; son garde-fou de compteurs a empêché le lancement de l’étude. Le second valide une vraie fin de goal avec consommation complète. Les deux traces sont conservées.

Les deux conditions utilisent le même sandbox Codex. Une restriction de socket locale peut empêcher le modèle de tester HTTP alors que le vérificateur hôte fonctionne. Cette différence fait partie du workflow du produit et limite la généralisation. Le contrôleur utilise le même modèle dans un autre contexte ; ses erreurs restent possibles. Les contrats sont détaillés malgré un objectif initial bref : ces résultats ne mesurent pas directement tes intentions vagues personnelles ou des goals de plusieurs heures. L’audit des commandes n’est pas une observation exhaustive des accès aux fichiers.

**{ci['passed']}/{ci['tests_run']} tests locaux passent en {ci['duration_seconds']:.6f} s**, sans API, sur les sources de cette comparaison. Les références complètes et les mutants de validation ont été vérifiés avant les appels. Ces tests de mécanismes ne constituent pas à eux seuls une mesure d’utilité.

[Sources exactes et reproduction](reports/native-goals-live-001/source_snapshot/README.txt). Les rejouer sera une régression sur des tâches déjà exposées, pas une nouvelle validation inédite. Les études 0.4 et leurs résultats sont conservés dans [MEASUREMENTS-v4.md](MEASUREMENTS-v4.md).
'''
    (ROOT/'MEASUREMENTS.md').write_text(text)
    readme=(ROOT/'docs/README-v0.4.1.md').read_text().replace('# GoalPilot 0.4.1','# GoalPilot '+m['product_version'])
    start=readme.index('**L’avantage mesuré est partiel.**');end=readme.index('\n\nPython',start)
    readme=readme[:start]+f'**{title}** Analyse corrigée : {g["completed_goals"]}/{g["runs"]} goals avec GoalPilot contre {d["completed_goals"]}/{d["runs"]} avec le vrai `/goal` natif. [Chiffres, erratum et limites](MEASUREMENTS.md).'+readme[end:]
    readme=readme.replace('--wall-seconds 900 --max-calls 5','--wall-seconds 900 --max-calls 6')
    readme=readme.replace('## Fonctionnement','''## Objectifs avec plusieurs chantiers

Le mode normal détecte localement un contrat volumineux avec de nombreuses sections de travail et réserve une revue indépendante de complétude, même après une livraison normale. La décision et ses motifs sont conservés. Les petits objectifs gardent la route adaptative ; `--thorough` force la revue complète.

Une revue interrompue conserve les programmes entièrement reçus, puis demande seulement les éléments manquants dans le budget restant. Un programme tronqué n’est jamais exécuté. Les probes déduits et gelés disposent du contexte d’import du dépôt ; leurs assertions ne sont pas modifiées. La limite de tokens et les appels ne repartent pas de zéro.

## Fonctionnement''')
    readme=readme.replace('Ré​aliser avec au plus 80 %','Réaliser avec au plus 80 %')
    readme=readme.replace('avec au plus 80 % du temps restant en mode adaptatif','avec au plus 80 % du temps restant sur un petit objectif, ou 55 % quand la revue de complétude est activée')
    start=readme.index('Les tests locaux n’utilisent aucune API.')
    readme=readme[:start]+f'''Les tests locaux n’utilisent aucune API : **{ci['passed']}/{ci['tests_run']} réussis**. La version {m['product_version']} est celle de la comparaison réelle. [Rapport](reports/native-goals-proof.html) · [Mesures et limites](MEASUREMENTS.md).

Reproduction depuis `reports/native-goals-live-001/source_snapshot/` :

```bash
python3 validate.py
python3 -m evaluation.native_goals create --output /tmp/nouvelle-etude-native
python3 -m evaluation.native_goals run --live --output /tmp/nouvelle-etude-native
```

`run --live` consomme l’usage Codex. Les critères et sources sont figés avant les appels. Les erreurs restent conservées ; le juge caché n’aide jamais les corrections. Les chiffres corrigés sont présentés avec l’erratum et les scores bruts. Rejouer ces projets constitue une régression, pas une validation sur des tâches nouvelles.

Les résultats précédents restent [conservés](MEASUREMENTS-v4.md), avec les [instructions 0.4.1](docs/README-v0.4.1.md). Les versions et études ne sont pas fusionnées pour transformer un critère raté en réussite. Codes de sortie : 0 contrôles réussis ou lecture ; 1 erreur initiale ; 2 résultat incomplet, partiel ou budget épuisé.
'''
    (ROOT/'README.md').write_text(readme)
    finish=(ROOT/'docs/FINISH-v0.4.1.md').read_text().replace('Contrôle des missions 0.4.1','Contrôle des missions '+m['product_version'])
    finish+='''\n## Revue de complétude et livraison interrompue\n\nDepuis 0.5, un contrat volumineux avec de nombreuses sections déclenche automatiquement la revue réservée, même si le codeur rend un compte rendu normal. La revue automatique regroupe les parcours en au plus quatre probes compacts ; le mode explicite complet conserve jusqu’à huit. La réalisation reçoit alors au plus 55 % du temps restant.\n\nLa reprise extrait seulement les valeurs JSON et programmes entièrement reçus. Les programmes incomplets ne sont pas exécutés ; les blocages et limites sont conservés. Un tour borné d’audit-recovery peut compléter la revue, avec au plus 90 secondes et dans les mêmes budgets. Les erreurs de fournisseur arrêtent le travail sans boucle de reprise.\n\nLes probes Python déduits, gelés hors du dépôt, peuvent importer les modules publics du projet depuis son contexte. Leurs assertions et empreintes restent inchangées ; les commandes définies par l’utilisateur conservent leur environnement. Une vérification fausse ou incomplète reste possible ; les tests de comparaison cachés la jugent séparément.\n'''
    (ROOT/'docs/FINISH.md').write_text(finish)
    print(json.dumps({'documented_version':m['product_version'],'qualified':qualified,'complete':data['complete'],'native':d['completed_goals'],'goalpilot':g['completed_goals'],'ci':ci['passed']}))


if __name__=='__main__':main()
