"""Publish measured results without losing the preceding evidence or failures."""
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    study=ROOT/'reports/efficiency-live-002';r=json.loads((study/'analysis.json').read_text());ci=json.loads((ROOT/'reports/tests.json').read_text())
    for path,dest in [('README.md','docs/README-v0.5.2.md'),('MEASUREMENTS.md','MEASUREMENTS-v5.md'),('docs/FINISH.md','docs/FINISH-v0.5.2.md')]:
        if not(ROOT/dest).exists():shutil.copy2(ROOT/path,ROOT/dest)
    b,c=r['totals']['baseline'],r['totals']['candidate'];s=r['savings_percent']
    def pct(k):
        if k=='seconds'and r.get('time_savings_percent_exact')is not None:return f"{r['time_savings_percent_exact']:.2f} %"
        if s[k]is not None:return f'{s[k]:.2f} %'
        value=r.get('supplementary_savings_lower_bound_percent',{}).get(k)
        return f'≥ {value:.2f} %'if value is not None else 'non établie'
    old=json.loads((ROOT/'reports/efficiency-live-001/analysis.json').read_text())
    cost=old['new_known_raw_tokens']+r['new_known_raw_tokens']
    primary_passed=r['joint_primary_target_met']
    passed=primary_passed or r.get('supplementary_twenty_percent_target_met',False)
    baseline_prefix=''if all(a['complete']for a in r['call_audit']if a['id'].endswith('-baseline'))else'≥ '
    headline=('Clôture conservée et les trois cibles de gain atteintes sur ces deux cas.'if passed else 'La cible conjointe clôture/temps/tokens n’est pas entièrement établie sur ces essais.')
    table=f'''| Mesure totale | GoalPilot 0.5.2 | GoalPilot 0.6.1 | Économie |
|---|---:|---:|---:|
| Goals corrects et conclus | {b['fully_delivered']}/2 | {c['fully_delivered']}/2 | — |
| Livrables corrects | {b['correct_artifacts']}/2 | {c['correct_artifacts']}/2 | — |
| Temps complet | {b['seconds']:.6f} s | {c['seconds']:.6f} s | {pct('seconds')} |
| Entrée + sortie brutes | {baseline_prefix}{b['raw_tokens']:,} | {c['raw_tokens']:,} | {pct('raw_tokens')} |
| Entrée hors cache + sortie | {baseline_prefix}{b['uncached_tokens']:,} | {c['uncached_tokens']:,} | {pct('uncached_tokens')} |
| Appels modèle | {b['model_turns']} | {c['model_turns']} | — |
| Groupes indépendants réussis | {b['groups_passed']}/52 | {c['groups_passed']}/52 | — |
'''
    readme=f'''# GoalPilot 0.6.1

Un superviseur local pour terminer des objectifs Codex ambitieux avec des contrôles exécutés, des corrections et une reprise dans un budget persistant.

**{headline}** [Mesures et limites](MEASUREMENTS.md) · [Rapport](reports/efficiency-live-002/report.html).

{table}
Ces chiffres comparent deux versions de GoalPilot sur deux plateformes synthétiques déjà connues, avec une nouvelle exécution par version et par domaine. Ils ne constituent pas une preuve statistique ni une mesure de tes goals personnels. Le témoin est GoalPilot 0.5.2, pas le `/goal` natif. Les tokens bruts et hors cache sont séparés ; aucun quota exact d’abonnement n’est déduit. Si le témoin a des compteurs partiels, ses coûts et les économies marquées ≥ sont des bornes inférieures ; tous les compteurs du candidat sont exigés complets pour cette analyse conservatrice.

## Utiliser

Python 3.11+, Linux/macOS ou WSL, aucune dépendance Python. Codex CLI installé et connecté. Le produit pilote la CLI ; il ne modifie pas le `/goal` de l’application.

```bash
codex login status
python3 -m goalpilot go "Termine ce projet pour en faire un outil fiable et utilisable" \\
  --repo /chemin/projet --run-dir /chemin/hors-projet/mission-001 \\
  --wall-seconds 900 --max-calls 6 --max-tokens 1000000
python3 -m goalpilot status /chemin/hors-projet/mission-001
python3 -m goalpilot continue /chemin/hors-projet/mission-001
python3 -m goalpilot report /chemin/hors-projet/mission-001 --output /chemin/hors-projet/rapport.html
```

Le dossier de preuves reste hors du dépôt. Codex modifie le projet ; une branche ou copie permet de l’essayer. Installation optionnelle : `python3 -m pip install -e .`.

## Ce qui économise du travail

Pour un objectif avec plusieurs chantiers explicites, un contexte séparé prépare d’abord deux programmes d’acceptation compacts à partir du besoin et des interfaces d’origine. Avant leur gel, un contrôle local recherche certaines erreurs de plomberie des scripts. Une réparation bornée peut corriger ces erreurs en conservant exigences, provenance et assertions. Les versions avant/après restent disponibles. Ce contrôle n’est pas une preuve complète de validité des tests.

Les scripts sont ensuite gelés hors du dépôt. Le codeur reçoit leur contenu et réutilise l’infrastructure existante ; il évite de recréer une grande suite d’acceptation parallèle. L’hôte exécute ces contrôles et les tests d’origine conservés. Seuls des contrôles exécutés avec succès permettent `scope_passed`. Une altération des preuves ou un blocage essentiel empêche la clôture. L’hôte peut vérifier localhost HTTP quand le sandbox du codeur ne le permet pas.

Les petits objectifs gardent le parcours adaptatif. `--thorough` garde une revue complète après réalisation ; `--fast` conserve l’ancienne boucle. Les runs existants conservent leur répartition lors de `continue`. [Détails](docs/FINISH.md).

## Budgets et preuves

Toutes les préparations, revues, réparations, attentes de modèle et vérifications partagent le même budget persistant. Les réservations sont enregistrées avant appel. Une reprise n’efface ni les appels ni leur coût ; une mission terminée est d’abord revérifiée localement. Les erreurs de connexion/quota arrêtent le travail sans boucle automatique.

Le plafond de tokens est souple, observé entre les tours ; un tour peut le dépasser. Cache inclus dans l’entrée. Une mesure manquante ou partielle ne vaut jamais zéro et interdit une économie complète. Aucun calcul exact de quota ou d’argent.

Les preuves incluent `finish-run.json`, `original-tree/`, les tests unittest d’origine et fixtures lorsqu’ils sont détectés, `audit.json`, `acceptance/`, `mission.json`, `state.json` et `calls/*/events.jsonl`. Les tests d’origine sont vérifiés sur une copie temporaire du code. La détection automatique reste conservatrice et ne protège pas une suite pytest/mixte de la même façon. Les scripts tournent avec tes droits : le gel n’est pas une isolation de sécurité.

Un contexte distinct du même modèle n’assure pas son indépendance statistique. Le codeur voit les exemples d’acceptation et peut les suradapter ; le juge de comparaison reste séparé et inaccessible. `scope_passed` porte sur les scénarios déduits, pas sur une satisfaction subjective prouvée. Après arrêt, la reprise reconstruit un contexte local depuis le contrat, le dépôt et le dernier compte rendu ; elle ne restaure pas l’historique distant complet.

## Critères déjà définis

```bash
python3 -m goalpilot go "Ton objectif" --repo /chemin/projet \\
  --run-dir /chemin/hors-projet/mission-002 --checks /chemin/acceptance.json
```

`--checks` attend une liste JSON de contrôles, chaque élément avec `id`, `description`, `command` (tableau argv, sans shell implicite) et éventuellement `timeout_seconds`. Ces critères sont `user_defined` ; leur réussite donne `completed`.

## Tests et résultats conservés

`python3 validate.py` : **{ci['passed']}/{ci['tests_run']} tests locaux réussis**, sans API. La comparaison0.6.1 est enregistrée avant ses appels, avec les sources exactes, critères, compteurs bruts et jugements. [CSV](reports/efficiency-live-002/trials.csv) · [Protocole](reports/efficiency-live-002/protocol.json) · [Audit](reports/efficiency-live-002/analysis.json).

La tentative0.6.0 reste conservée comme échec/incomplète : revue interrompue sans métrique complète et erreurs du vérificateur ; arrêt anticipé non prévu au protocole, sans gain revendiqué. Coût nouveau connu de cette mise au point et des comparaisons0.6 : **au moins {cost:,} tokens bruts**, avec consommation partielle dans la tentative échouée. Les économies d’exécution ne remboursent pas automatiquement ce coût de recherche.

Le gain de clôture historique0.5.2 face au vrai `/goal` natif demeure une observation distincte, limitée au blocage HTTP du sandbox : [mesures0.5](MEASUREMENTS-v5.md). Les études antérieures et l’erratum du graphe vide restent inchangés. Rejouer ces domaines est une régression sur des tâches déjà exposées.
'''
    (ROOT/'README.md').write_text(readme)
    details=['# GoalPilot 0.6.1 — clôture, vitesse et tokens','',f'**{headline}**','',table,'[Rapport](reports/efficiency-live-002/report.html) · [Protocole figé](reports/efficiency-live-002/protocol.json) · [Données et audit](reports/efficiency-live-002/analysis.json) · [CSV](reports/efficiency-live-002/trials.csv)','',
    f"Exécutions réalisées : {r['completed_trials']}/4. Clôture conservée : {r['closure_maintained_on_both_cases']}. Critère primaire avec compteurs intégraux : {primary_passed}. Analyse complémentaire conservatrice (au moins20 % sur chaque coût) : {r.get('supplementary_twenty_percent_target_met',False)}. Intégrité : {r['integrity_verified']}. Compteurs complets : {r['usage_complete']}.",
    '', '## Interprétation', '', 'Deux domaines : support multi-équipe et gestion des stocks/commandes, avec respectivement14 et18 opérations, rôles ou allocations, idempotence, concurrence, reprise, sauvegarde, préservation des données, CLI et HTTP. Même gpt-6.1-sol, mêmes fichiers initiaux et budgets900s/6appels/1,5M tokens souples par essai. Ordre alterné ; aucun feedback du juge caché ni intervention humaine dans les essais de confirmation. Temps complet de supervision inclus ; temps du juge de recherche exclu également. Les coûts des échecs font partie des totaux.', '',
    'Les deux domaines avaient déjà été utilisés au développement ; ces nouvelles exécutions ne sont pas des projets inédits. Une exécution par version/domaine, pas de preuve statistique ou de garantie sur tes goals vagues de plusieurs heures. Le seuil20 % est une cible pratique déclarée avant les appels, pas un test de significativité. Les différents produits et versions ne sont pas mélangés pour convertir un critère raté en réussite.', '',
    '## Échec0.6.0 conservé', '', 'La première tentative prévoyait4 exécutions, mais s’est arrêtée après le témoin support et son candidat. Le témoin était correct et conclu. Le candidat a dépassé une limite interne120s pendant la génération des critères, laissant un compteur inconnu. Ses scripts contenaient ensuite un doublon de keyword et un nom masquant le module HTTP. Les tentatives de correction du code ne pouvaient pas réparer ces critères gelés. Le candidat avait malgré tout un livrable correct26/26 au juge externe, mais aucun succès de clôture n’est revendiqué.', '',
    'L’orchestrateur a été suspendu, puis le worker interrompu pour éviter d’autres appels inutiles. Cet arrêt anticipé et cette interruption de recherche n’étaient pas prévus au protocole : campagne incomplète, pas une preuve comparative positive ni un échec normal attribuable au code. Tous les journaux, le dénominateur prévu4 et les coûts connus restent conservés. [Résultats](reports/efficiency-live-001/report.html) · [Arrêt et déviation](reports/efficiency-live-001/boundary-stop-request.json).', '',
    'La version0.6.1 regroupe les contrôles, leur donne un délai moins serré, expose les programmes au codeur et contrôle leur plomberie avant gel. Une réparation conserve les exigences/provenances et la structure AST des assertions ; elle ne prouve pas une équivalence sémantique complète. Aucun test échoué gelé n’est modifié pour rendre le code conforme. Le juge de recherche n’a pas changé. [Rejeu statique des erreurs](reports/probe-plumbing-replay-001/result.json).', '',
    '## Coûts et historique', '',f'Coût nouveau connu0.6 : **au moins {cost:,} tokens bruts**, dont {old["new_known_raw_tokens"]:,} connus pour la tentative incomplète et {r["new_known_raw_tokens"]:,} pour la nouvelle comparaison. Les compteurs partiels sont des bornes inférieures. Cette dépense de mise au point est distincte de l’économie par mission ; elle n’est pas effacée.', '',
    'Le rejeu sans API des10 anciens contrôles Runforge/Automation passe encore. C’est une régression technique, pas une nouvelle mesure de taux de clôture. Le résultat historique natif2/2 contre1/2 reste limité à un cas de vérification HTTP bloquée dans le sandbox ; il ne prouve pas un meilleur code. [Historique0.5](MEASUREMENTS-v5.md) · [Historique0.4](MEASUREMENTS-v4.md).', '',
    f'Tests actuels : {ci["passed"]}/{ci["tests_run"]}, {ci["duration_seconds"]:.6f}s, zéro API. Ils vérifient les mécanismes et ne sont pas une mesure d’utilité à eux seuls.']
    details+=['','## Compteurs partiels du témoin et borne conservatrice','','Le protocole primaire exigeait tous les compteurs complets ; il reste non validé si un tour du témoin est partiel. Une analyse complémentaire a été définie et horodatée avant tout essai0.6.1. Elle ne remplace pas le primaire : elle exige des coûts complets pour le candidat, des coûts connus audités pour le témoin et tous les critères de correction/clôture. Si B est le coût connu du témoin et C le coût complet du candidat, le vrai coût témoin T vérifie T≥B ; donc 1−C/T≥1−C/B. Les économies de tokens affichées ≥ sont ainsi des minimums calculés, pas des pourcentages exacts. Le temps complet de workflow est mesuré indépendamment et reste exact. Aucun coût inconnu n’est remplacé par zéro.','', '[Règle complémentaire définie avant les candidats](reports/efficiency-live-002/supplementary-bounds-preregistered.json) · [Exécution complémentaire séparée](reports/efficiency-live-002/supplement-execution.json). Le protocole primaire arrêté et ses raisons sont conservés.','', 'Le témoin support de la nouvelle comparaison a un code correct mais reste bloqué par ses scripts : doublon de keyword et compteur15 au lieu14. Le diagnostic isolé sur une référence complète, sans modifier les scripts gelés ni les modèles, est [conservé](reports/efficiency-live-002/fairness/frozen-event-count-diagnostic.json). Ces défauts expliquent une partie du coût et de la non-clôture ; cela ne signifie pas que le nouveau produit écrit un meilleur code.']
    (ROOT/'MEASUREMENTS.md').write_text('\n'.join(details)+'\n')
    finish='''# Contrôle des missions0.6.1

Les objectifs avec de nombreux chantiers déclenchent une acceptation indépendante **avant** réalisation. Elle vient du besoin et des interfaces d’origine, sans inspection du code à venir. Le contrôleur utilise le même modèle dans un contexte distinct, pas une source de vérité indépendante.

La revue demande au plus deux programmes compacts couvrant les workflows et entrypoints explicites, avec des assertions réelles et des données temporaires. Elle dispose d’au plus240s et30 % du temps restant. Un contrôle local cherche certaines erreurs des scripts, notamment les collisions d’imports et les doublons de keywords. Si nécessaire, un appel `audit-repair` borné à120s et20 % du temps restant répare seulement ces programmes avant leur gel. Exigences, provenance et structure des assertions sont conservées ; avant/après sont archivés. Ce garde-fou n’est pas une preuve d’équivalence sémantique ou d’absence d’autres erreurs.

Une fois valides structurellement, les programmes sont gelés hors du dépôt avec leurs SHA-256. Leur contenu est fourni au codeur. La réalisation reçoit au plus80 % du temps restant ; l’hôte exécute ensuite les probes et les tests unittest d’origine conservés dans une copie temporaire du code. Les erreurs métier déclenchent une correction dans le budget. Altération des scripts, infrastructure indisponible ou blocage essentiel empêchent une clôture complète.

Les petits objectifs gardent la route adaptative. `--thorough` conserve la revue après réalisation, jusqu’à huit programmes, avec au plus55 % du temps restant pour la première réalisation et45 % de ce qui reste pour la revue. Une revue interrompue peut récupérer seulement les programmes complets, puis demander les manquants, dans les mêmes budgets. Aucune assertion gelée n’est supprimée pour obtenir un statut vert.

Tous les appels sont persistés avant exécution et comptabilisés, y compris les réparations du vérificateur. `continue` conserve les paramètres de la mission, les preuves et les coûts ; il ne réinitialise pas les limites. Les missions pré0.6 gardent leur timing après réalisation. Les compteurs incomplets ne valent jamais zéro. Les plafonds de tokens restent souples entre les tours.

`scope_passed` signifie que les scénarios déduits ont effectivement réussi. Le codeur peut voir et suradapter les scénarios ; des omissions communes restent possibles. Le juge de comparaison vérifie donc séparément le code, sans aider les corrections. Les scripts tournent avec les droits de l’utilisateur et ne sont pas une isolation de sécurité.

La première tentative0.6.0, ses erreurs de vérificateur et son arrêt non prévu sont conservés dans les mesures. Les comparaisons ne doivent pas mélanger les versions ni présenter des projets déjà utilisés comme des tâches inédites. Voir [mesures](../MEASUREMENTS.md), [algorithme](ACCEPTANCE_FIRST.md) et [ancienne spécification](FINISH-v0.5.2.md).
'''
    (ROOT/'docs/FINISH.md').write_text(finish)
    print(json.dumps({'joint_target':passed,'research_tokens_known_lower_bound':cost,'tests':ci['tests_run']}))


if __name__=='__main__':main()
