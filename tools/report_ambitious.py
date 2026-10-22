"""Finalize ambitious-goal evidence without changing original judgments or criteria."""
import html,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from evaluation.ambitious.report import report
from tools.audit_ambitious import audit
ROOT=Path(__file__).resolve().parents[1]


def build(output):
    output=Path(output).resolve();data=report(output);checks=audit(output);m=data['protocol']
    qualified=data['primary_completion_advantage_observed']and checks['quality_integrity_verified']
    summary={'qualified_completion_advantage_observed':qualified,'measurements':data,'audit':checks,
    'meaning':'The primary criterion measures additional completely correct goals with normal delivery, not time savings or partial coverage. This is descriptive evidence on three synthetic platforms and correlated repeats; not population proof or personal satisfaction.',
    'environment':json.loads((output/'environment-observation.json').read_text())if(output/'environment-observation.json').exists()else None}
    atomic_json(ROOT/'reports/ambitious-proof.json',summary)
    d,g=(data['groups'][name]for name in('direct','goalpilot'));esc=html.escape
    title='Davantage de goals entièrement livrés observé.'if qualified else'Le supplément de goals livrés reste non démontré.'
    if not data['complete']:title='Campagne d’objectifs ambitieux incomplète.'
    per=''.join(f"<tr><td>{esc(p['case'])}</td><td>{p['direct_successes']}/{m['repeats']}</td><td>{p['goalpilot_successes']}/{m['repeats']}</td></tr>"for p in data['per_project'])
    def fmt(v):return 'indisponible'if v is None else f'{v:,.2f}'
    resource=''.join(f'<tr><td>{label}</td><td>{fmt(d[key])}</td><td>{fmt(g[key])}</td></tr>'for key,label in [('seconds','Temps actif total (secondes)'),('reported_tokens','Tokens rapportés'),('uncached_input_plus_output','Entrée hors cache + sortie'),('seconds_per_completed_goal','Secondes par goal livré, tous coûts inclus')])
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — conclusion des goals ambitieux</title><style>body{{max-width:1050px;margin:auto;padding:36px 20px;background:#101b2a;color:#edf4fa;font:17px/1.65 system-ui}}h1{{line-height:1.2}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #3c5066;padding:12px 10px;text-align:left}}a{{color:#92dec6}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1d3048;padding:20px;border-radius:12px}}.lead{{font-size:23px}}.box{{background:#1d3048;padding:22px;border-radius:12px;margin:24px 0}}small{{color:#bdd0e0}}</style>
<p><small>GOALPILOT {esc(m['product_version'])} · OBJECTIFS AMBITIEUX · CRITÈRES FIGÉS AVANT LES APPELS</small></p><h1>{title}</h1><p class="lead">Goals livrés : <strong>{d['completed_goals']}/{d['runs']} en direct → {g['completed_goals']}/{g['runs']} avec GoalPilot</strong>.</p>
<div class="box">Un succès exige une mission terminée normalement et les 13 groupes cachés réussis sur deux graines. Le critère principal exige au moins deux goals supplémentaires sans régression appariée. Temps et tokens ne remplacent pas ce critère.</div>
<table><tr><th>Plateforme</th><th>Codex direct</th><th>GoalPilot</th></tr>{per}</table>
<p>Paires gagnées : {data['quality_wins']}. Paires perdues : {data['quality_losses']}. Fausses clôtures : {d['false_completion']} en direct, {g['false_completion']} avec GoalPilot. Code correct, indépendamment de la clôture : {d['artifact_successes']} contre {g['artifact_successes']}.</p>
<h2>Un périmètre métier plus large</h2><p>Support multi-équipe : droits, notes privées, révisions, CSV, audit et livraison d’événements. Stock et commandes : achats, allocation multi-entrepôts, expéditions partielles, annulations, retours, transferts et inventaires. Workflows : graphes, workers, expiration de claims, retries, annulation, stockage d’artifacts et schedules. Respectivement 14, 18 et 16 opérations métier, plus sauvegarde/restauration et CLI/HTTP.</p>
<h2>Coûts de tous les essais</h2><table><tr><th>Mesure</th><th>Direct</th><th>GoalPilot</th></tr>{resource}</table><p>Consommation complète : direct {d['usage_complete']}, GoalPilot {g['usage_complete']}. Si des compteurs sont partiels, les totaux connus restent des bornes inférieures et aucune économie complète de tokens n’est calculée.</p>
<h2>Méthode et limites</h2><p>Trois plateformes synthétiques nouvelles, même gpt-6.1-sol, mêmes fichiers, 900 secondes par essai, deux répétitions et ordre inversé. Le transport et la base transactionnelle sont fournis ; le domaine est initialement à construire. Aucun résultat caché n’a servi aux corrections. Références complètes acceptées et 21 défauts isolés rejetés avant les appels réels.</p>
<p>Le contrôle automatique du produit est un autre contexte du même modèle. Les erreurs peuvent être communes. Les contrats publics sont détaillés : ces observations ne prouvent pas une meilleure compréhension des intentions vagues personnelles. Les répétitions sont corrélées ; la probabilité appariée calculée sous indépendance ne constitue pas une preuve statistique générale.</p>
<p>La session Codex a signalé une interdiction de socket locale ; le juge hôte réussit les tests HTTP. Les deux conditions ont le même sandbox. GoalPilot peut faire vérifier ses probes sur l’hôte. Une livraison directe correcte n’est pas pénalisée pour avoir signalé cette limite.</p>
<p>Les audits vérifient les sources figées, les fichiers initiaux, les identités des groupes et les compteurs bruts. La recherche de marqueurs de commandes ne prouve pas exhaustivement l’absence de lecture des fichiers du benchmark.</p>
<p><a href="ambitious-live-001/report.html">Chaque essai et ses échecs</a> · <a href="ambitious-live-001/protocol.json">Protocole original</a> · <a href="ambitious-live-001/trials.csv">CSV</a> · <a href="ambitious-proof.json">Bilan et audits JSON</a> · <a href="proof.html">Étude précédente, conservée</a></p></html>'''
    (ROOT/'reports/ambitious-proof.html').write_text(page)
    if data['complete']:
        for source,dest in [('README.md','docs/README-v0.4.1.md'),('MEASUREMENTS.md','MEASUREMENTS-v4.md')]:
            if not(ROOT/dest).exists():shutil.copy2(ROOT/source,ROOT/dest)
        ci=json.loads((ROOT/'reports/tests.json').read_text())
        table='\n'.join(f"| {p['case']} | {p['direct_successes']}/{m['repeats']} | {p['goalpilot_successes']}/{m['repeats']} |"for p in data['per_project'])
        text=f'''# Objectifs ambitieux — GoalPilot {m['product_version']}

**{title}** Douze exécutions réelles planifiées et conservées ; même modèle, mêmes départs et quinze minutes par essai.

[Rapport lisible](reports/ambitious-proof.html) · [Données et audit](reports/ambitious-proof.json) · [CSV](reports/ambitious-live-001/trials.csv) · [Protocole](reports/ambitious-live-001/protocol.json)

| Plateforme | Codex CLI direct | GoalPilot |
|---|---:|---:|
{table}
| **Goals entièrement livrés** | **{d['completed_goals']}/{d['runs']}** | **{g['completed_goals']}/{g['runs']}** |
| Livrables corrects, sans condition de clôture | {d['artifact_successes']} | {g['artifact_successes']} |
| Clôtures normales avec défauts cachés | {d['false_completion']} | {g['false_completion']} |
| Groupes de vérification réussis | {d['groups_passed']}/{d['groups_total']} | {g['groups_passed']}/{g['groups_total']} |
| Temps total, secondes | {d['seconds']:.6f} | {g['seconds']:.6f} |
| Tokens rapportés | {d['reported_tokens']:,} | {g['reported_tokens']:,} |
| Entrée hors cache + sortie | {d['uncached_input_plus_output']:,} | {g['uncached_input_plus_output']:,} |
| Tours modèle | {d['agent_turns']} | {g['agent_turns']} |
| Consommation complète | {d['usage_complete']} | {g['usage_complete']} |

## Ce qui compte comme conclusion

Les 13 groupes doivent tous passer sur les deux graines et la mission doit se terminer normalement. Les groupes testent les comportements publics et parcours intégrés, pas la présence de fichiers ou les affirmations du modèle. Un gain de couverture partielle n’est pas un goal livré.

Le critère primaire préenregistré exige au moins deux goals livrés supplémentaires et aucune perte appariée. Résultat qualifié après audit : **{qualified}**. Paires gagnées : {data['quality_wins']}, perdues : {data['quality_losses']}. Les essais ratés sont conservés et leur coût reste inclus. Aucun feedback caché n’est transmis au produit et aucun essai n’est remplacé.

## Ambition et différences du produit

Trois nouveaux projets : support multi-équipe (14 opérations), stock/commandes (18), workflows durables (16). Le transport JSONL/HTTP et le socle SQLite transactionnel sont fournis aux deux conditions ; toute la logique métier est initialement absente. Les contrats publics détaillent les interactions, droits, invariants, erreurs, concurrence et restauration. Les objectifs initiaux restent brefs et ambitieux.

GoalPilot 0.5.0 détecte localement un grand nombre de sections de travail et réserve alors une revue indépendante de complétude, même après une livraison normale. Le réalisateur reçoit au plus 55 % du temps restant ; la revue reçoit au plus 45 % du temps ensuite disponible et le reste sert aux corrections. Les petits objectifs conservent la route adaptative 0.4. Les tests d’origine sont conservés, les probes du contrôleur sont gelés et tous les coûts restent dans le budget. La règle de routage est un heuristique observable, pas un modèle d’évaluation entraîné sur les résultats.

## Fiabilité du juge et traces

Avant les appels : références complètes acceptées sur 78 groupes au total, prototypes incomplets rejetés, 21 défauts isolés détectés. Certaines validations/paginations/graphes varient selon deux graines ; les autres scénarios fixes sont répétés. Ces groupes ne sont pas indépendants. Le juge final s’exécute hors du contexte des modèles.

Sources et critères figés : {checks['source_snapshot_intact']}. Sources courantes encore identiques : {checks['current_registered_sources_intact']}. Départs appariés identiques : {checks['all_paired_initial_files_identical']}. Audit des résultats et de leur règle de réussite : {checks['quality_integrity_verified']}. Appels entièrement mesurés dans les événements bruts : {checks['all_calls_fully_metered_from_raw']}. Les scripts de reproduction et les dépendances de test sont conservés sous `source_snapshot/`.

## Coût et limites

Coût connu des appels réels de cette campagne : **{checks['known_token_lower_bound']:,} tokens rapportés**, sur {checks['model_calls']} tours. Ce total est le coût de l’évaluation, pas une économie. Tout compteur incomplet reste signalé ; les économies de tokens correspondantes sont indisponibles. Le cache est inclus dans l’entrée et n’est pas ajouté deux fois. Aucune conversion exacte en quota d’abonnement.

Les deux conditions utilisent le même sandbox Codex. Une session a signalé l’impossibilité d’ouvrir une socket locale, alors que les tests HTTP du juge hôte fonctionnent. GoalPilot peut exécuter ses probes sur l’hôte ; cela fait partie de la différence de workflow mesurée. Le comparateur n’est pas pénalisé pour signaler une limite de vérification si le code livré passe le juge. [Observation conservée](reports/ambitious-live-001/environment-observation.json).

Trois plateformes synthétiques avec des contrats détaillés et deux répétitions corrélées ne prouvent pas une amélioration générale sur les objectifs personnels vagues de plusieurs heures. La probabilité appariée unilatérale sous hypothèse d’indépendance est {data['paired_one_sided_p_if_independent']} ; les répétitions rendent cette hypothèse inadéquate pour une preuve statistique de population. Le contrôleur est le même modèle dans un autre contexte ; ses erreurs peuvent rester corrélées. L’audit de marqueurs de commandes ne constitue pas une observation exhaustive des accès aux fichiers.

**{ci['passed']}/{ci['tests_run']} tests locaux passent en {ci['duration_seconds']:.6f} s**, sans API, avant la campagne et sur les sources enregistrées. [Validation](reports/tests.json).

La campagne précédente reste inchangée : [MEASUREMENTS-v4.md](MEASUREMENTS-v4.md). Elle obtenait 7/7 goals dans les deux conditions et n’établissait aucun gain de conclusion. Les résultats des deux produits ne sont pas fusionnés pour sauver un critère raté.
'''
        (ROOT/'MEASUREMENTS.md').write_text(text)
        readme=(ROOT/'docs/README-v0.4.1.md').read_text().replace('# GoalPilot 0.4.1','# GoalPilot 0.5.0')
        start=readme.index('**L’avantage mesuré est partiel.**');end=readme.index('\n\nPython',start)
        readme=readme[:start]+f'**{title}** Nouvelle campagne : {g["completed_goals"]}/{g["runs"]} goals livrés avec GoalPilot contre {d["completed_goals"]}/{d["runs"]} en direct. Le critère porte sur des objectifs entièrement corrects et conclus, sans substituer les économies de temps à la réussite. [Résultats et limites](MEASUREMENTS.md).'+readme[end:]
        readme=readme.replace('## Fonctionnement','## Objectifs avec plusieurs chantiers\n\nLe mode normal détecte un contrat local volumineux avec de nombreuses sections de travail et active automatiquement la revue indépendante de complétude. Il réserve jusqu’à 55 % du temps restant à la réalisation, puis du temps à la revue et aux corrections. Le détail de cette décision est conservé dans `finish-run.json`. Les petits objectifs suivent la route adaptative décrite ci-dessous. `--thorough` permet de forcer cette revue. La règle repose sur le goal et les sections du contrat local ; elle ne mesure pas directement l’intention personnelle.\n\n## Fonctionnement')
        start=readme.index('Les tests locaux n’utilisent aucune API.');end=readme.index('\nInstallation optionnelle',start)if '\nInstallation optionnelle'in readme[start:]else len(readme)
        readme=readme[:start]+f'''Les tests locaux n’utilisent aucune API : **{ci['passed']}/{ci['tests_run']}** réussis. Les sources exactes 0.5.0 sont celles de la nouvelle campagne réelle. [Rapport](reports/ambitious-proof.html) · [Protocole](reports/ambitious-live-001/protocol.json) · [Résultats détaillés](MEASUREMENTS.md).

Reproduction depuis `reports/ambitious-live-001/source_snapshot/` :

```bash
python3 validate.py
python3 -m evaluation.ambitious create --output /tmp/nouvelle-etude-ambitieuse
python3 -m evaluation.ambitious run --live --output /tmp/nouvelle-etude-ambitieuse
```

`run --live` consomme l’usage Codex. Les sources, critères et budgets sont figés avant les appels, les essais ratés restent conservés et le juge caché n’aide jamais les corrections. Rejouer ces projets constitue une régression, pas une validation sur de nouveaux objectifs.

Les mesures 0.4.0 et leur résultat négatif restent [conservés](MEASUREMENTS-v4.md), avec les [anciennes instructions](docs/README-v0.4.1.md). Les résultats des versions ne sont pas fusionnés. Codes de sortie : 0 contrôles réussis ou lecture ; 1 erreur initiale ; 2 résultat incomplet, partiel ou budget épuisé.
'''
        (ROOT/'README.md').write_text(readme)
    print(json.dumps({'complete':data['complete'],'qualified_primary':qualified,'groups':data['groups'],'wins':data['quality_wins'],'losses':data['quality_losses']},indent=2));return summary


if __name__=='__main__':build(sys.argv[1])
