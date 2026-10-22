"""Write release documentation from audited results, retaining failed development."""
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'reports/efficiency-live-003';r=json.loads((out/'analysis.json').read_text());m=json.loads((out/'protocol.json').read_text());ci=json.loads((ROOT/'reports/tests.json').read_text())
    for src,dest in [('README.md','docs/README-v0.5.2.md'),('MEASUREMENTS.md','MEASUREMENTS-v5.md'),('docs/FINISH.md','docs/FINISH-v0.5.2.md')]:
        if not(ROOT/dest).exists():shutil.copy2(ROOT/src,ROOT/dest)
    b,c=r['totals']['baseline'],r['totals']['candidate'];partial=not r['usage_complete'];bounds=r['supplementary_savings_lower_bound_percent'];exact=r['savings_percent']
    def economy(key):
        if key=='seconds'and r['time_savings_percent_exact']is not None:return f"{r['time_savings_percent_exact']:.2f} %"
        if exact[key]is not None:return f'{exact[key]:.2f} %'
        return f'≥ {bounds[key]:.2f} %'if bounds[key]is not None else 'non établie'
    bp='≥ 'if any(not a['complete']for a in r['call_audit']if a['id'].endswith('-baseline'))else''
    table=f'''| Mesure totale | 0.5.2 | 0.6.2 | Économie |
|---|---:|---:|---:|
| Goals corrects et conclus | {b['fully_delivered']}/2 | {c['fully_delivered']}/2 | — |
| Livrables corrects | {b['correct_artifacts']}/2 | {c['correct_artifacts']}/2 | — |
| Temps complet | {b['seconds']:.6f} s | {c['seconds']:.6f} s | {economy('seconds')} |
| Tokens bruts (entrée + sortie) | {bp}{b['raw_tokens']:,} | {c['raw_tokens']:,} | {economy('raw_tokens')} |
| Entrée hors cache + sortie | {bp}{b['uncached_tokens']:,} | {c['uncached_tokens']:,} | {economy('uncached_tokens')} |
| Appels modèle | {b['model_turns']} | {c['model_turns']} | — |
| Groupes indépendants réussis | {b['groups_passed']}/52 | {c['groups_passed']}/52 | — |
'''
    history=[]
    for name in ('efficiency-live-001','efficiency-live-002','efficiency-live-004'):
        a=json.loads((ROOT/'reports'/name/'analysis.json').read_text());history.append((name,a['new_known_raw_tokens']))
    smoke=json.loads((ROOT/'reports/arithmetic-review-smoke-001/result.json').read_text());su=smoke.get('usage')or{};smoke_tokens=su.get('input_tokens',0)+su.get('output_tokens',0)
    research=sum(v for _,v in history)+smoke_tokens+r['new_known_raw_tokens']
    headline=('Deux goals corrects et conclus ; gains de temps et de tokens mesurés sur ces deux cas.'if r['closure_maintained_on_both_cases']else'La clôture des deux goals n’est pas entièrement établie.')
    limits='Deux plateformes synthétiques déjà utilisées au développement, un résultat par version/domaine. Trois nouvelles exécutions et un témoin historique réussi réutilisé explicitement. Pas de preuve statistique ni de mesure de tes goals personnels. Le comparateur est GoalPilot0.5.2, pas Codex natif.'
    readme=f'''# GoalPilot 0.6.2

Un superviseur local pour terminer des objectifs Codex ambitieux avec des vérifications exécutées, des corrections et une reprise dans un budget persistant.

**{headline}** [Mesures détaillées](MEASUREMENTS.md) · [Rapport](reports/efficiency-live-003/report.html).

{table}
{limits}

Les tokens bruts et hors cache sont séparés. Un témoin partiellement mesuré donne seulement des bornes inférieures de coût ; les gains marqués ≥ sont des minimums calculés avec le coût complet du candidat. Aucun quota exact d’abonnement ou montant en argent n’est déduit.

## Lancer et reprendre

Python3.11+, Linux/macOS ou WSL, aucune dépendance Python. Codex CLI doit être installé et connecté. Le produit pilote la CLI ; il ne s’insère pas dans le `/goal` de l’application.

```bash
codex login status
python3 -m goalpilot go "Termine ce projet pour en faire un outil fiable et utilisable" \\
  --repo /chemin/projet --run-dir /chemin/hors-projet/mission-001 \\
  --wall-seconds 900 --max-calls 6 --max-tokens 1000000
python3 -m goalpilot status /chemin/hors-projet/mission-001
python3 -m goalpilot continue /chemin/hors-projet/mission-001
python3 -m goalpilot report /chemin/hors-projet/mission-001 --output /chemin/hors-projet/rapport.html
```

Le dossier de preuves reste hors du projet. Codex modifie le projet ; une branche ou copie permet de l’essayer. Installation optionnelle : `python3 -m pip install -e .`.

## Préparer les critères avant de coder

Pour les objectifs avec de nombreux chantiers explicites, un contexte séparé prépare deux programmes d’acceptation compacts à partir du besoin et des interfaces d’origine. Un contrôle local recherche certaines erreurs de plomberie des scripts ; une réparation bornée peut les corriger avant gel en conservant exigences, provenance et assertions.

Un autre contexte relit ensuite les calculs des valeurs attendues, sans voir l’implémentation à venir. Il peut corriger seulement des entiers attendus dans des assertions d’égalité, avec justification dans le contrat d’origine. Il ne peut pas supprimer une assertion, modifier un opérateur, changer les entrées ou le contrôle de flux. Les versions avant/après sont conservées. Cette relecture reste celle du même modèle et ne garantit pas l’absence d’erreur.

La variante ultérieure0.6.3 à auxiliaires partagés et contexte réduit a régressé sur sa première clôture et reste archivée ; la version retenue est exactement0.6.2.

Les scripts sont alors gelés hors du dépôt, avec leurs empreintes. Le codeur reçoit leur contenu et réutilise l’infrastructure existante, avec des tests de maintenance ciblés. L’hôte exécute ces programmes et les tests unittest d’origine conservés. Il peut vérifier localhost HTTP lorsque le sandbox du codeur l’interdit. Une assertion gelée échouée n’est jamais modifiée pour rendre le code conforme.

Les petits objectifs gardent le parcours adaptatif ; `--thorough` garde la revue après réalisation et `--fast` l’ancienne boucle. Les runs existants conservent leur répartition lors de `continue`. [Budgets et détails](docs/FINISH.md).

## Preuves et limites

Toutes les préparations, revues, réparations et vérifications partagent le même budget durable. Les réservations sont persistées avant appel. Une reprise ne remet pas les coûts à zéro ; une mission terminée est d’abord revérifiée localement. Les erreurs de connexion ou quota arrêtent la mission sans boucle automatique.

Le plafond de tokens est souple, observé entre les tours : un tour peut le dépasser. Le cache est déjà compris dans l’entrée. Un compteur manquant ou partiel ne vaut pas zéro. Les scripts tournent avec tes droits ; le gel ne constitue pas une isolation de sécurité.

Les fichiers de preuves comprennent `finish-run.json`, `original-tree/`, `audit.json`, `acceptance-validation.json`, `acceptance/`, `mission.json`, `state.json` et `calls/*/events.jsonl`. La capture initiale est bornée, avec exclusions et omissions indiquées. Les suites unittest reconnues sont conservées et vérifiées sur une copie temporaire du code ; les suites pytest ou mixtes ne bénéficient pas de cette protection automatique.

`scope_passed` signifie que les scénarios déduits ont effectivement réussi, pas que la satisfaction personnelle est prouvée. Le codeur voit ces scénarios et peut les suradapter ; le juge de comparaison reste séparé et inaccessible. Une altération des preuves ou un blocage essentiel empêche la clôture. Après arrêt, la reprise reconstruit un contexte depuis le contrat, le dépôt et le dernier compte rendu ; elle ne restaure pas tout l’historique distant.

## Critères déjà définis

```bash
python3 -m goalpilot go "Ton objectif" --repo /chemin/projet \\
  --run-dir /chemin/hors-projet/mission-002 --checks /chemin/acceptance.json
```

Le fichier est une liste JSON de contrôles avec `id`, `description`, `command` (tableau argv, sans shell implicite) et éventuellement `timeout_seconds`. Ces critères utilisateur restent inchangés ; leur réussite donne `completed`.

## Tests et historique

`python3 validate.py` : **{ci['passed']}/{ci['tests_run']} tests locaux réussis**, sans API. [CSV](reports/efficiency-live-003/trials.csv) · [Protocole et contrôle réutilisé](reports/efficiency-live-003/protocol.json) · [Audit des compteurs](reports/efficiency-live-003/analysis.json).

Les tentatives0.6.0 et0.6.1 ainsi que la variante0.6.3 sont conservées comme échecs/incomplètes, avec leurs causes d’arrêt et défauts de vérificateur. Les dépenses nouvelles connues de cette mise au point0.6 représentent **au moins {research:,} tokens CLI**, sans compter deux fois le témoin réutilisé. Les économies par mission ne remboursent pas automatiquement ce coût de recherche. La session de développement elle-même n’est pas instrumentée dans ces compteurs.

L’observation historique face au vrai `/goal` natif et son erratum restent séparés : [mesures0.5](MEASUREMENTS-v5.md). Rejouer ces domaines reste une régression sur des tâches déjà exposées.
'''
    (ROOT/'README.md').write_text(readme)
    rows=[]
    for item in m['order']:
        p=out/'trials'/item['id']/'record.json'
        if p.exists():
            v=json.loads(p.read_text());rows.append(f"| {v['case']} | {v['mode']} | {v['status']} | {v['success']} | {sum(x['passed']for x in v['judgments'])}/26 | {v['seconds']:.6f} |")
    measures=f'''# Mesures GoalPilot0.6.2

**{headline}**

{table}
[Rapport](reports/efficiency-live-003/report.html) · [Protocole figé](reports/efficiency-live-003/protocol.json) · [Analyse et audit](reports/efficiency-live-003/analysis.json) · [CSV](reports/efficiency-live-003/trials.csv).

| Cas | Mode | Statut | Correct et conclu | Groupes | Secondes |
|---|---|---|---|---:|---:|
{chr(10).join(rows)}

## Périmètre de la comparaison

{limits} Les deux domaines couvrent14 et18 opérations, concurrence, reprise, sauvegarde, préservation des données, CLI et HTTP. Le témoin support réussi de480,368157s est repris de la première étude : son résultat était connu avant la conception du candidat. Il constitue un contrôle historique favorable au témoin ; il ne s’agit pas d’une nouvelle observation indépendante. Ses octets produit0.5.2 sont identiques et les empreintes des fichiers initiaux sont comparées. Le témoin ultérieur bloqué900s reste archivé et ne remplace pas ce contrôle réussi pour gonfler le gain.

Même gpt-6.1-sol et mêmes interfaces, fichiers initiaux et juge par paire. Support :900s/6appels pour les deux versions. Stock :900s/4appels pour les deux versions afin de borner la dépense de recherche. Plafond souple1,5M tokens par essai ; plafond de campagne6M connus observé entre essais. Tous les appels de préparation, validation, réparation et code sont comptés. Le temps est celui du workflow complet, mise en route et vérifications incluses ; le juge externe de recherche est exclu également des deux bras. Aucun feedback du juge n’aide les agents.

Trois nouvelles exécutions prévues, quatre cellules de comparaison dont un témoin archivé. Nouvelles exécutées : {r['completed_fresh_trials']}/{r['planned_fresh_trials']}. Intégrité : {r['integrity_verified']}. Compteurs candidats complets : {r['candidate_usage_complete']}. Cible déclarée avant les nouveaux essais (au moins20 % sur chaque coût et deux goals corrects/conclus) : {r['joint_primary_target_met']}. La vitesse et les tokens bruts dépassent20 % ; le gain hors cache14,57 % manque ce seuil. Le critère conjoint est donc en échec, même si les trois coûts baissent et la clôture est conservée. Ce seuil est une cible pratique, pas une significativité statistique.

## Tokens exacts et bornes

Entrée+sortie brutes ; le cache est déjà inclus dans l’entrée. Entrée hors cache+sortie = entrée−cache+sortie. Les deux sont publiées. Les économies totales sont218,311486s,422230 tokens bruts et20822 entrées hors cache+sorties sur les deux objectifs. Ce sont des totaux de workflow, pas du temps humain personnel. Aucune conversion exacte en quota d’abonnement ou en argent.

Si tous les compteurs sont complets, le pourcentage est calculé exactement sur les coûts rapportés. Si seul le témoin est partiel, une borne est possible avec un candidat intégralement mesuré : pour coût connu B du témoin et coût complet C du candidat, le vrai témoin T≥B donne 1−C/T≥1−C/B. Les valeurs ≥ sont ces économies minimales ; aucun compteur inconnu n’est remplacé par zéro. Le temps reste mesuré intégralement. Toute consommation candidate partielle interdit cette borne et le succès du critère. Le protocole003 définit cette règle avant les appels0.6.2.

## Échecs de développement conservés

0.6.0 : revue limitée trop tôt120s, compteur incomplet, puis deux erreurs de scripts (keywords doublés et nom masquant `http.client`). Le code était correct26/26 mais ne pouvait satisfaire les contrôles gelés. Arrêt anticipé et interruption de recherche non prévus au protocole ; aucune preuve positive ni taux de clôture normal revendiqué. Coût nouveau connu de l’étude001 : {history[0][1]:,} tokens. [Données](reports/efficiency-live-001/analysis.json) · [Interruption et déviation](reports/efficiency-live-001/boundary-stop-request.json).

0.6.1 : le contrôle de plomberie fonctionne, mais une attente arithmétique18 au lieu16 bloque encore un code correct26/26. La tentative a été interrompue pour éviter d’autres corrections de code sans effet ; ce n’est pas un succès normal. Son témoin0.5.2 avait également un code correct mais restait bloqué900s sur des critères erronés15 au lieu14 et un keyword doublé. Le protocole exact a été arrêté comme prévu sur sa métrique partielle, puis l’analyse complémentaire également abandonnée sur le défaut arithmétique candidat. Coût nouveau connu de l’étude002 : {history[1][1]:,} tokens. [Données](reports/efficiency-live-002/analysis.json) · [Interruption complémentaire](reports/efficiency-live-002/supplement-interruption.json).

0.6.2 ajoute une vérification des calculs par un contexte frais avant tout codage et avant gel. Dans l’essai technique exposé, il a corrigé18 en16 en comptant7créations+6changements+2commentaires+1suppression, sans voir l’implémentation. Le script initial échoue sur une référence complète ; les deux scripts après correction passent. Ce contrôle technique est rétrospectif sur un programme déjà exposé, pas une nouvelle réussite de goal. Un premier rejeu avait omis le contexte d’import de l’hôte : ses quatre échecs d’import sont conservés, puis le même programme est rejoué avec le PYTHONPATH utilisé par le produit, sans changement d’assertion. [Relecture modèle](reports/arithmetic-review-smoke-001/review.json) · [Rejeu référence](reports/arithmetic-review-smoke-001/reference-replay-002.json).

0.6.3 : la variante à auxiliaires JSONL/HTTP partagés et à contexte réduit passe166 tests locaux mais manque sa première clôture (code correct26/26). Un constructeur de paquets réintroduit le doublon de keyword via un transfert indirect de kwargs ; le contrôle statique ne suit pas ce cas. Après6 appels, le goal reste bloqué sur ce critère gelé. Arrêt sur régression selon le protocole,1/2 nouvelles exécutions prévues ; le second candidat n’est jamais lancé. Aucun gain de cette variante n’est revendiqué. La livraison revient aux octets0.6.2 réellement mesurés et à leurs161 tests. Coût nouveau de l’essai004 : {history[2][1]:,} tokens, compteurs complets, sans recompter les deux contrôles0.6.2 réutilisés. [Échec conservé](reports/efficiency-live-004/analysis.json) · [Arrêt prévu](reports/efficiency-live-004/stopped.json).

## Dépense et limites

Coût nouveau connu de la mise au point0.6 : **au moins {research:,} tokens CLI** = {history[0][1]:,} (001) + {history[1][1]:,} (002) + {smoke_tokens:,} (contrôle technique arithmétique) + {r['new_known_raw_tokens']:,} (trois nouveaux essais003) + {history[2][1]:,} (variante004 rejetée). Le contrôle historique réutilisé n’est pas ajouté une seconde fois. Les compteurs partiels restent des bornes inférieures ; la session de développement elle-même n’est pas instrumentée. Ce coût n’est pas amorti automatiquement par les économies d’exécution.

Le même modèle dans plusieurs contextes peut répéter une erreur. La vérification arithmétique ne prouve pas la justesse complète des critères ; les attentes sont déduites du contrat et peuvent manquer des besoins personnels. Le codeur peut voir les scénarios et les suradapter ; le juge de recherche reste séparé. Les contrats sont détaillés malgré des goals initiaux brefs. Les budgets par projet, les domaines connus et le contrôle historique limitent la généralisation. Un avantage de clôture ne signifie pas automatiquement un meilleur code.

Tests locaux : {ci['passed']}/{ci['tests_run']} en{ci['duration_seconds']:.6f}s, zéro API. Le rejeu des10 anciens contrôles Runforge/Automation est une régression technique, pas une nouvelle mesure de taux de clôture. Les résultats face au vrai `/goal` natif, l’erratum et les échecs0.5 restent [conservés](MEASUREMENTS-v5.md), ainsi que l’[historique0.4](MEASUREMENTS-v4.md).
'''
    (ROOT/'MEASUREMENTS.md').write_text(measures)
    (ROOT/'docs/FINISH.md').write_text('''# Contrôle des missions0.6.2

Pour un objectif avec de nombreux chantiers explicites, le parcours normal prépare les critères avant la réalisation. Un contexte en lecture seule du même modèle produit deux programmes compacts depuis le besoin et les interfaces d’origine ; il n’inspecte pas l’implémentation à venir. Limite :240s et30 % du temps restant.

Avant gel, un contrôle local recherche certaines erreurs de plomberie. Une réparation bornée à120s et20 % du temps restant conserve exigences, provenance et assertions. Une autre conversation fraîche vérifie les calculs des attentes, sans voir le code. Elle dispose d’au plus90s et15 % du temps restant. Ses patches doivent être justifiés dans le contrat d’origine ; le garde-fou AST autorise seulement des entiers attendus dans des assertions d’égalité. Il interdit suppression d’assertion, modification d’opérateur, entrée, chaîne ou contrôle de flux. Les versions et justifications avant/après restent archivées. Cela ne prouve pas une équivalence sémantique ni une absence d’autres erreurs.

Les scripts sont ensuite gelés hors du dépôt avec leurs SHA-256, puis fournis au codeur. Celui-ci réutilise l’infrastructure existante et les contrôles, avec des tests de maintenance ciblés. Il reçoit au plus80 % du temps restant ; l’hôte vérifie et corrige dans le budget restant. Les tests unittest d’origine reconnus sont conservés et exercés sur une copie temporaire du code. Une suite pytest/mixte ne reçoit pas automatiquement cette protection.

Un test gelé échoué n’est jamais modifié pour obtenir le succès. Les blocs essentiels et les preuves altérées empêchent la clôture. Le codeur peut ne pas ouvrir de socket ; l’hôte peut néanmoins vérifier HTTP localhost. `scope_passed` porte sur les scénarios déduits, pas sur une satisfaction personnelle prouvée. Un juge distinct et inaccessible contrôle les résultats des comparaisons.

Les petits objectifs conservent la route adaptative. `--thorough` conserve la revue après réalisation, jusqu’à huit programmes,55 % du temps restant pour la première réalisation et45 % du reste pour sa revue. `--fast` conserve l’ancienne boucle. Les critères `--checks` fournis par l’utilisateur ne passent pas par la réécriture arithmétique.

Chaque appel est réservé et persisté avant exécution. Les appels de génération, réparation du vérificateur, validation et code partagent le même budget. `continue` conserve le contrat et les coûts ; les runs pré0.6 gardent leur répartition après réalisation. Les compteurs manquants ne valent jamais zéro et le plafond de tokens reste souple entre les tours.

Le codeur voit les critères et peut les suradapter. Plusieurs contextes du même modèle ne sont pas statistiquement indépendants. Les scripts s’exécutent avec les droits de l’utilisateur ; le gel n’est pas une isolation de sécurité. Voir les [mesures et échecs conservés](../MEASUREMENTS.md) et l’[ancienne spécification](FINISH-v0.5.2.md).
''')
    import re
    for name in ('README.md','MEASUREMENTS.md','docs/FINISH.md'):
        path=ROOT/name;parts=re.split(r'(```[\s\S]*?```|`[^`\n]*`|\]\([^)]+\))',path.read_text())
        for i,part in enumerate(parts):
            if part.startswith(('```','`','](')):continue
            part=re.sub(r'\b\d{1,3}(?:,\d{3})+\b',lambda m:m.group().replace(',',' '),part)
            part=re.sub(r'(?<=[^\W\d_])(?=\d)',' ',part)
            part=re.sub(r'(?<=\d)(?=[A-Za-zÀ-ÖØ-öø-ÿ])',' ',part)
            part=re.sub(r'(?<=[A-Za-zÀ-ÖØ-öø-ÿ]),(?=\d)',', ',part)
            parts[i]=part
        path.write_text(''.join(parts))
    print(json.dumps({'version':'0.6.2','joint_target':r['joint_primary_target_met'],'tests':ci['tests_run'],'research_raw_tokens_lower_bound':research}))


if __name__=='__main__':main()
