# Latest skill 1.1.0 session pilot

Seven different Python projects, same configured model/effort and host permissions. New skill and native Codex7/7 correct+closed,35/35 external behavior groups each. Six exact goal files plus one plain vague request, reported separately. New/native total time saving 8.21 %; uncached input+output saving 10.27 %. These are descriptive, not universal rates or exact subscription-quota savings.

Detailed evidence, limitations and research costs: [session-study](session-study.md), [structured summary](session-study.json). Default supports bounded existing unittest projects. No independent proof of20 longvaguegoals or personal usage distribution.

---

Historical standalone-engine evidence follows and does not describe the whole new skill invocation.

# Chiffres et périmètre

Les données ci-dessous concernent le skill historique 1.0.0 / moteur 0.9.1.
Le nouveau défaut 1.1.0 / 0.10.0 réalise dans la conversation appelante sans modèle
imbriqué ; ses gains globaux et taux de complétion sont en attente de mesure.
Voir session.md pour les limites du protocole et de son comptage UNKNOWN.

Mesures historiques du moteur :

- Réutilisation 0.9.1 : 8/8 livraisons correctes, 208/208 contrôles indépendants,
  zéro appel modèle ; environ 2,1 s pour revalider un projet déjà livré.
- Premier passage 0.9.0 : 2/2 goals clos et corrects, 52/52 contrôles ; −14,6 % de
  temps et −26,5 % d'entrée hors cache + sortie contre deux contrôles Codex `/goal`
  historiques connus. La sortie totale ne baisse que de 1,7 % et le raisonnement,
  qui en est une sous-partie, augmente de 26,0 %.
- Ces essais concernent deux domaines synthétiques connus. Les natifs avaient
  également un code correct, mais étaient bloqués sur des tests HTTP en sandbox.

Les pourcentages à froid restent attribués à la 0.9.0, pas à une nouvelle exécution
du skill. Les résultats sont conservés dans baseline.json avec leur provenance.
La vérification HTTP nécessite un terminal autorisant localhost. Une exécution depuis
un sandbox qui bloque les sockets ne conserve pas l'avantage de clôture du test hôte.
Le coût d'apprentissage est non nul et la fréquence réelle des hits chez l'utilisateur
n'a pas été mesurée. Les appels du moteur et la conversation qui lance le skill
sont deux coûts distincts : zéro appel backend ne signifie pas que toute l'invocation
du skill est gratuite. Le coût de la conversation appelante n'est pas instrumenté.

L'économie exacte de quota d'abonnement sur un nouveau goal n'est pas établie.
L'objectif anti-boucle de −30 % de temps et −50 % sur entrée hors cache et sortie
est accepté pour la suite ; il n'est pas atteint ou démontré par cet emballage.

## Validation de cette couche skill

16 exécutions directes/lanceur, 416 contrôles : mêmes résultats et compteurs,
2,346 s en CLI et 2,319 s via le lanceur. Une vraie invocation Codex a pris 19,18 s
et utilisé 7 656 tokens hors cache + sortie, avec 0 appel backend du moteur.
Le coût appelant existe : le skill complet ne reproduit pas le zéro consommation
d'un lancement sans modèle. Voir launcher-parity.json et caller-invocation.json.
