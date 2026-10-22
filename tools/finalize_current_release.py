"""Current reuse release; cold claims remain attached to the measured0.9.0 source."""
import html,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def prose(text):
    for old,new in [('GoalPilot0.','GoalPilot 0.'),('La0.','La 0.'),('la0.','la 0.'),('version0.','version 0.'),('noyau0.','noyau 0.'),('réutilisation0.','réutilisation 0.')]:text=text.replace(old,new)
    text=re.sub(r'(\d)(réutilisations|contrôles|tokens|groupes|résultats|répétitions|goals|nouveaux|appels|appel|point|ne\b|à)',r'\1 \2',text)
    text=re.sub(r'(?<=à)(?=\d)',' ',text)
    text=re.sub(r'(\d)(s\b|API\b)',r'\1 \2',text)
    return re.sub(r',(?=[A-Za-zÀ-ÿ])',', ',text)


def main():
    from goalpilot import __version__
    cold=ROOT/'reports/quota-native-live-007';hot=ROOT/'reports/reuse-current-001'
    a=json.loads((cold/'analysis.json').read_text());w=json.loads((hot/'analysis.json').read_text());ci=json.loads((ROOT/'reports/tests.json').read_text());components=json.loads((cold/'token-components.json').read_text())
    assert __version__=='0.9.1'and w['version']==__version__ and ci['successful']
    assert w['complete']and w['executed']==8 and w['correct_closed']==8 and w['raw_tokens']==0 and w['model_attempts']==0
    docs=ROOT/'docs'
    for name,target in [('README.md','README-v0.9.0.md'),('MEASUREMENTS.md','MEASUREMENTS-v9.md'),('reports/release-decision.json','release-decision-v0.9.0.json')]:
        if not(docs/target).exists():(docs/target).write_bytes((ROOT/name).read_bytes())
    n=a['totals']['native_goal'];g=a['totals']['goalpilot'];s=a['savings_percent']
    initial=w['modes']['initial'];delivered=w['modes']['delivered']
    measured=f'''# GoalPilot0.9.1 : temps,tokens et quota

**Quota d'inférence nul établi sur les réutilisations exactes vérifiées. Économie exacte de quota non établie sur un nouveau goal.**

## Version actuelle : réutilisation sans modèle

La0.9.1 reconnaît le même goal sur les mêmes fichiers initiaux ET le même goal renvoyé sur un projet
déjà livré dont les fichiers et données n'ont pas changé. Elle revalide les contrôles figés dans une
copie temporaire. Sur les fichiers initiaux,elle applique ensuite le patch appris ; sur un projet
déjà livré,elle ne réécrit pas son code. Le coût initial d'apprentissage reste séparé et non nul.

| Parcours mesuré0.9.1 | Livraisons correctes et closes | Temps moyen | Appels modèle |
|---|---:|---:|---:|
| Mêmes fichiers initiaux | {initial['correct_closed']}/2 | {initial['mean_seconds']:.3f}s | 0 |
| Goal renvoyé sur projet déjà livré | {delivered['correct_closed']}/6 | {delivered['mean_seconds']:.3f}s | 0 |

**8/8résultats clos et corrects ;208/208groupes indépendants réussis ;0token modèle.**
Il s'agit de vrais fichiers,processus et tests HTTP locaux,pas d'une simulation de consommation.
Les points d'entrée d'inférence et de démarrage app-server sont bloqués pendant les essais et aucun
n'est tenté. L'exécution des tests utilise toujours du temps et du CPU local.

Ces deux parcours sont différents. Le temps du parcours « déjà livré » n'est pas comparé au temps
natif d'un premier passage sur un prototype : leurs fichiers initiaux diffèrent. Aucun nouveau
contrôle natif « déjà livré » n'a été exécuté. Les zéros d'inférence du produit sont constatés
directement ; ils ne sont pas déduits d'un pourcentage arrondi du compte.

Les artefacts appris proviennent des DEUX réalisations0.9.0 de l'étude007 connues avant ces tests.
Les454622tokens bruts de cet apprentissage ne sont pas gratuits et ne sont pas facturés deux fois
dans le coût de recherche. Une modification du goal,d'un fichier,de ses permissions ou des données
empêche le hit. Les instructions parentes et le runtime sont aussi vérifiés ; les contrôles sont
relancés pour tester l'environnement courant. Une revue indépendante demandée explicitement
ignore le cache. Les limites de la nouvelle mission sont conservées pour ses futures reprises.

[Protocole0.9.1](reports/reuse-current-001/preregistered-protocol.json) ·
[Résultats et provenance](reports/reuse-current-001/analysis.json)

## Dernière comparaison à froid : version0.9.0

La0.9.1 n'a pas fait l'objet d'un nouveau benchmark froid. Les chiffres ci-dessous appartiennent
au noyau0.9.0 figé dans l'étude007 ; ils ne sont pas réattribués à un nouveau run0.9.1.
Le changement0.9.1 ajoute la reconnaissance du projet déjà livré,renforce la politique de revue
et les budgets,et évite les utilitaires Python sur les projets sans gate unittest compatible.

| Deux goals complets | Codex `/goal` historique | GoalPilot0.9.0 neuf | Économie |
|---|---:|---:|---:|
| Clos et corrects | {n['closed_correct']}/2 | {g['closed_correct']}/2 | — |
| Groupes de correction du code | {n['groups_passed']}/52 | {g['groups_passed']}/52 | — |
| Temps complet | {n['seconds']:.3f}s | {g['seconds']:.3f}s | {s['seconds']:.2f}% |
| Tokens entrée+sortie,bruts | {n['raw_tokens']} | {g['raw_tokens']} | {s['raw_tokens']:.2f}% |
| Entrée hors cache+sortie,proxy | {n['uncached_tokens']} | {g['uncached_tokens']} | {s['uncached_tokens']:.2f}% |
| Sortie totale,raisonnement inclus | {n['output_tokens']} | {g['output_tokens']} | {s['output_tokens']:.2f}% |
| Entrée hors cache | {n['uncached_input_tokens']} | {g['uncached_input_tokens']} | {s['uncached_input_tokens']:.2f}% |
| Entrée en cache | {n['cached_input_tokens']} | {g['cached_input_tokens']} | {s['cached_input_tokens']:.2f}% |

Le raisonnement est une sous-partie de la sortie : il passe de3618à4560tokens,soit **+26.04%**,
pendant que la sortie visible passe de25079à23647. Ces sous-totaux ne s'ajoutent pas une seconde
fois à la sortie totale. Les règles de pondération du quota d'abonnement sont inconnues : même
cette baisse des trois grands postes ne prouve pas une économie exacte de quota.
La cible préenregistrée de20% sur temps,brut,proxy ET sortie **n'est pas atteinte**.
La baisse de temps14.58% et de proxy26.48% reste un constat sur ces deux essais.

Méthode : mêmes fichiers originaux,même gpt-6.1-sol,900s par mission,6appels maximum pour GoalPilot.
Les DEUX contrôles natifs viennent de l'étude001,avec résultats connus avant la conception du
candidat ; leurs sessions persistantes et continuations automatiques réelles sont auditées.
Deux candidats sont exécutés à neuf avec caches isolés vides. GoalPilot demande LOW au premier
codage puis MEDIUM seulement après échec hôte ; les contrôles natifs sont à effort configuré/par
défaut. Il ne s'agit donc pas d'une comparaison du wrapper seul à effort forcé égal.
Les critères d'origine et le correcteur indépendant26groupes par artefact sont inchangés.
Le correcteur ne fournit aucun retour au modèle. Aucun échec n'est rejoué ou supprimé.

Les deux natifs ont un code correct mais un goal bloqué sur la vérification HTTP en sandbox.
GoalPilot peut tester HTTP depuis l'hôte : c'est un avantage de clôture dans cet environnement,
pas une amélioration démontrée de la qualité du code. Deux domaines synthétiques connus ne
prouvent pas l'utilité sur tous les projets ni sur des goals personnels réellement vagues.
Les proportions affichées de quota sont+1point pour chaque bras,à des moments différents ;
ce sont des pourcentages entiers du compte avec arrondi,délai et activité concurrente possibles.
Aucun pourcentage exact attribuable d'économie de quota froid n'est calculable ici.

[Mesures froides](reports/quota-native-live-007/analysis.json) ·
[Composants des tokens](reports/quota-native-live-007/token-components.json) ·
[Audit des compteurs et du lifecycle natif](reports/quota-native-live-007/audit.json) ·
[Protocole froid scellé](reports/quota-native-live-007/preregistered-protocol.json)

## Utilité réelle et coûts

Le taux de réutilisation dans vos sessions personnelles n'est pas encore mesuré. Les cas de hit
sont construits volontairement ici pour tester le mécanisme ;8/8ne prédit pas leur fréquence
naturelle chez vous. Si aucun goal ne se répète à fichiers inchangés,ce levier ne rapporte rien.
Les commandes `status` et `report` exposent les hits,leurs coûts d'apprentissage et les appels
réels enregistrés pour observer cet usage sans nouvelle inférence.

L'étude froide007 coûte454622nouveaux tokens bruts CLI ; les deux contrôles archivés ne sont pas
refacturés dans ce coût. Les tests de réutilisation0.9.0 et0.9.1 n'ajoutent aucune inférence.
Cumul CLI de recherche connu : **au moins11424441tokens bruts**,interruptions conservées comme
bornes inférieures. La session de développement n'est pas instrumentée. Aucun bénéfice net global
de quota ou retour financier de l'ensemble du développement n'est établi.

Tests locaux actuels : **{ci['passed']}/{ci['tests_run']}**,{ci['duration_seconds']:.3f}s,zéro API.
Les vérifications couvrent les changements de goal et de données,la corruption du cache et des
critères,l'échec du staging,les budgets de reprise et le respect d'une revue indépendante demandée.
Toutes les études001–007,versions rejetées et interruptions restent dans le dossier de preuves.
'''
    measured=prose(measured)
    (ROOT/'MEASUREMENTS.md').write_text(measured)
    local=measured.replace('(reports/reuse-current-001/','(').replace('(reports/quota-native-live-007/','(../quota-native-live-007/')
    (hot/'RESULTS.md').write_text(local)
    (hot/'report.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>GoalPilot0.9.1 — preuves</title><style>body{max-width:1100px;margin:3rem auto;padding:1rem;background:#10151e;color:#edf2f7;font:16px/1.5 system-ui}pre{white-space:pre-wrap}a{color:#83dcd0}</style><h1>GoalPilot0.9.1 : preuves et limites</h1><p><a href="RESULTS.md">Rapport</a> · <a href="analysis.json">Mesures</a></p><pre>'+html.escape(measured)+'</pre></html>')
    readme=f'''# GoalPilot0.9.1

Des goals de code suivis de tests hôte,de reprises et de preuves persistantes.
La réutilisation vérifiée évite de redemander au modèle un résultat déjà appris ou déjà livré.

**Version actuelle :8/8réutilisations correctes et closes,208/208contrôles,zéro appel modèle,
environ{delivered['mean_seconds']:.1f}s pour revalider un projet déjà livré.** Cela économise le quota
d'inférence de cette répétition. Le coût du premier apprentissage reste à payer.

Dernier benchmark froid,version0.9.0 :2/2goals clos et corrects,52/52contrôles ;
**−14.6% de temps,−26.5% d'entrée hors cache+sortie,−1.7% de sortie totale**,face à deux
contrôles Codex `/goal` historiques connus. La0.9.1 n'a pas été rebenchmarkée à froid.
L'économie exacte de quota sur un nouveau goal et le taux de hit dans votre usage restent inconnus.

[Mesures,méthode,coûts et limites](MEASUREMENTS.md) · [Rapport HTML](reports/reuse-current-001/report.html)

Python3.11+,Linux/macOS,Codex CLI authentifié ;stdlib uniquement.

```bash
python -m goalpilot go "Terminer le projet de bout en bout" --repo /chemin/projet --run-dir /chemin/preuves/initial
# Même goal,projet déjà livré et fichiers inchangés : nouvelle vérification sans génération.
python -m goalpilot go "Terminer le projet de bout en bout" --repo /chemin/projet --run-dir /chemin/preuves/reverification
python -m goalpilot continue /chemin/preuves/initial
python -m goalpilot status /chemin/preuves/reverification
python -m goalpilot report /chemin/preuves --output rapport.html
python validate.py
```

`--cache-dir` choisit le cache local,par défaut `~/.goalpilot/reuse`. Conservez les preuves du premier
run : le cache dépend de ses contrôles figés. Si les entrées ou les preuves changent,la réutilisation
est refusée et le chemin habituel peut consommer du modèle. Les inventaires sont bornés ;les gros
projets,symlinks et fichiers sensibles peuvent désactiver la réutilisation.

`--no-reuse` force une nouvelle réalisation ; `--thorough` exige une revue indépendante et ignore
le cache. `--checks` utilise vos contrôles explicites ; `--fast` conserve l'ancienne boucle directe.
`--max-uncached-tokens` est un plafond souple entre appels,un appel peut le dépasser.
Les projets unittest compatibles conservent leurs tests originaux puis figent ceux de livraison
avant les réparations. Les contrôles proposés par le réalisateur ne prouvent pas toute une intention
personnelle. Sans gate compatible,la contre-vérification existante reste nécessaire.

Les réutilisations identiques sont une optimisation conditionnelle ;elles ne couvrent pas toute
requête nouvelle. [Décision de version](reports/release-decision.json).
'''
    readme=prose(readme)
    (ROOT/'README.md').write_text(readme)
    (docs/'FINISH.md').write_text(readme+'\n\n'+measured)
    decision={'selected_version':__version__,'status':'conditional_quota_saver_for_verified_exact_reuse',
              'cold_measured_version':'0.9.0','current_version_cold_benchmarked':False,'cold_study':'quota-native-live-007','warm_study':'reuse-current-001',
              'cold_subscription_quota_saving_proven':False,'warm_zero_model_quota_proven':w['complete']and w['model_attempts']==0,
              'all_arbitrary_goals_efficiency_proven':False,'all_user_general_efficiency_objectives_met':False,'natural_user_hit_rate_known':False,
              'cold_metrics':a,'warm_metrics':w,'token_components':components,'offline_tests':ci,
              'new_research_raw_tokens':454622,'lifetime_known_cli_raw_lower_bound':11424441,'development_tokens_unmetered':True}
    (ROOT/'reports/release-decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    print(json.dumps({k:v for k,v in decision.items()if k not in ('cold_metrics','warm_metrics','token_components','offline_tests')},indent=2))


if __name__=='__main__':main()
