# GoalPilot 1.1.0 : bilan mesuré

Le Codex appelant réalise le goal. Un contrôleur Python local conserve l'objectif, les tests initiaux, les critères figés et les preuves. Le défaut ne lance plus un second Codex. La consommation de la conversation appelante est incluse, jamais considérée comme gratuite.

## Résultat principal : six nouveaux projets

Catalogue, comptabilité, workflow de dépendances, configuration JSON, ETL CSV et archives ZIP. Même gpt-6.1-sol, effort LOW configuré, mêmes fichiers initiaux et mêmes accès hôte. Aucun juge ne demande réseau, sockets ou credentials. Les six goals de ce premier groupe sont fournis en fichiers déjà préparés ; le coût de cette préparation n'est pas un appel modèle du banc.

| Mesure sur 6 essais | Ancien skill 1.0.0 | Nouveau skill 1.1.0 | Codex natif /goal |
|---|---:|---:|---:|
| Goals clos ET corrects selon juge externe | 5/6 | 6/6 | 6/6 |
| Groupes de comportement réussis | 29/30 | 30/30 | 30/30 |
| Temps des essais, secondes | 732,05 | 507,56 | 536,21 |
| Entrée hors cache, tokens | ≥ 134 382 | 67 254 | 75 076 |
| Sortie, tokens | ≥ 30 188 | 26 146 | 29 417 |
| Entrée hors cache + sortie | ≥ 164 570 | 93 400 | 104 493 |

Face à l'ancien skill : **−30,67 % de temps d'essai et au moins 43,2 % de baisse d'entrée hors cache+sortie**. Son workflow a dépassé le temps et livré une CLI incorrecte : c'est un goal incomplet, pas un refus d'accès. Ses compteurs sont partiels, d'où les bornes basses. Ce temps n'est pas un temps de réussite sur 6 goals, puisque l'ancien n'en conclut que 5.

Face au natif : **−5,34 % de temps et −10,62 % d'entrée hors cache+sortie**, 6/6 corrects et clos dans les deux branches. Entrée hors cache −10,42 %, sortie −11,12 %, entrée en cache −6,53 % : la baisse ne repose pas sur les seuls tokens bruts.

Résultats détaillés par projet (données dans goalpilot.zip : reports/skill-efficiency-live-003/report.md) · Protocole et sources (données dans goalpilot.zip : reports/skill-efficiency-live-003/protocol.json) · Audit 166/166 (données dans goalpilot.zip : reports/skill-efficiency-live-003/audit.json)

## Complément : une demande vague normale

« Termine ce projet de bout en bout pour que je puisse gérer mes réservations sereinement au quotidien. Prends les décisions réversibles nécessaires, couvre tous les parcours du README, ajoute les tests et la documentation, puis vérifie que tout fonctionne. »

Cette fois le goal apparaît une seule fois dans chaque requête ; aucun fichier de goal n'est fourni au modèle. Sa transcription par le skill est donc incluse dans ses tokens et son temps. Le README décrit les interfaces, conflits d'intervalles, récurrences atomiques, annulations, persistance, export CSV et CLI. Le juge externe, figé avant l'essai, vérifie 5 groupes indépendants.

| Mesure | Nouveau skill | Codex natif /goal |
|---|---:|---:|
| Clôture correcte | 1/1 | 1/1 |
| Temps, secondes | 89,32 | 114,04 |
| Entrée hors cache + sortie | 22 071 | 24 188 |

**−21,68 % de temps et −8,75 % d'entrée hors cache+sortie** sur cette seule demande. Ce n'est pas une estimation pour toute la population de goals vagues. L'ancien contrôle a été perdu lors du redémarrage de l'environnement : traces et compteurs partiels sont conservés, mais cet incident est exclu des comparaisons de qualité et de temps. Il n'a jamais été relancé.

Complément audité 39/39 (données dans goalpilot.zip : reports/skill-efficiency-live-004/audit.json) · Données complètes (données dans goalpilot.zip : reports/skill-efficiency-live-004/analysis.json)

## Ensemble descriptif des sept projets, nouveau contre natif

7/7 goals clos et corrects dans chaque branche,35/35 groupes indépendants pour chacune. **−8,21 % de temps total et −10,27 % d'entrée hors cache+sortie**. Entrée hors cache −9,17 %, sortie −13,07 %, entrée en cache −12,75 %. Les compteurs des deux branches sont complets. Cet agrégat associe les 6 entrées en fichiers et 1 demande libre ; les deux groupes restent publiés séparément. Il est descriptif, pas une campagne unique ininterrompue préenregistrée de 7 goals.

## Portée et limites

219/219 tests locaux passent, zéro ignoré, en 68,122272104 s. Les adaptateurs simulés des tests techniques n'entrent jamais dans les mesures d'utilité. Le juge de recherche est externe au dépôt, figé avant les résultats et ne fournit pas de retours de réparation aux réalisateurs. Ses contrôles restent finis : ce n'est pas la preuve de toute intention subjective. Sur 6 succès/6, l'intervalle Wilson descriptif 95 % est [60,97 %;100 %] ; cet échantillon choisi ne justifie pas de taux de succès universel.

Le nouveau protocole requiert actuellement des projets Python unittest compatibles et bornés, avec des tests initiaux. Autres frameworks, projets sans tests, gros worktrees et usages personnels ne sont pas validés par ce pilote. Les budgets tokens de la conversation appelante requièrent une application externe. Le contrôleur historique reste accessible sur demande explicite. Le palier accepté −30 % temps/−50 % entrée hors cache/−50 % sortie sur 20 longs goals reste à démontrer. La version est un progrès mesuré, pas un résultat « game changer » établi.

La campagne 001 a été arrêtée avant codage sur un démarrage de sous-Codex empêché par le bac du caller. Elle n'est pas un avantage produit. La campagne 002 s'est arrêtée à 8/18 sur compteur partiel. La continuation 003 a exécuté seulement les 10 bras non encore exécutés, sans changer le code ni les juges et sans refaire un échec. Les huit résultats copiés sont identiques et ne sont jamais refacturés dans les coûts. Un proxy expérimental uniformise uniquement les permissions thread/start de tous les modèles en accès hôte ; son action est enregistrée. Le complément 004 a subi un redémarrage : l'ancien essai est conservé comme interrompu, seuls les deux bras non exécutés ont ensuite été réalisés.

## Coût de recherche et quota

Développement et essais de cette amélioration : **au moins 4 815 352 tokens bruts et 521 464 tokens d'entrée hors cache+sortie**. La conversation principale n'est pas mesurée et des appels interrompus ont un compteur inconnu : ces totaux sont des bornes basses. Aucun amortissement net de quota n'est revendiqué. Historique connu cumulé : au moins 16 311 833 tokens bruts.

La phase de développement via l'ancien GoalPilot a livré le code mais s'est arrêtée avant audit à 93 026 tokens hors cache+sortie, dépassant son plafond souple 90 000 pendant l'unique appel. Elle reste incomplete, jamais comptée comme un goal clos. Les mesures connues des essais font 3 611 030 tokens bruts, sous leur seuil commun connu de 4 millions, observé entre essais entiers.

Le compteur hebdomadaire du compte a affiché 68 % puis 71 % pendant les essais, même fenêtre. C'est une observation globale arrondie avec un délai inconnu et une possible activité concurrente ; elle ne mesure pas une différence exacte de quota entre branches. Les économies de tokens ci-dessus ne sont donc pas présentées comme des pourcentages exacts d'abonnement.

[Données consolidées et coûts](session-study.json) · Observation de quota (données dans goalpilot.zip : reports/skill-efficiency-live-004/quota-observation.json)
