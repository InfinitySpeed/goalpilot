"""Build the final descriptive summary from retained, already-judged records."""
import csv,html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def build():
    a=json.loads((ROOT/'reports/triple-proof.json').read_text())
    b=json.loads((ROOT/'reports/integrated-proof.json').read_text())
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    first=a['measurement'];extension=b['integrated'];pooled=b['exploratory_pooled']
    def table(data):
        d,g=(data['groups'][k]for k in('direct','goalpilot'))
        s=data['savings_percent']
        return '\n'.join([
          '| Mesure | Codex CLI direct | GoalPilot 0.4.0 | Écart GoalPilot |',
          '|---|---:|---:|---:|',
          f"| Goals livrés | {d['completed_goals']}/{d['runs']} | {g['completed_goals']}/{g['runs']} | {g['completed_goals']-d['completed_goals']:+d} |",
          f"| Temps total, secondes | {d['seconds']:.6f} | {g['seconds']:.6f} | {-s['seconds']:+.2f} % |",
          f"| Tokens entrée + sortie | {d['reported_tokens']:,} | {g['reported_tokens']:,} | {-s['reported_tokens']:+.2f} % |",
          f"| Entrée hors cache + sortie | {d['uncached_input_plus_output']:,} | {g['uncached_input_plus_output']:,} | {-s['uncached_input_plus_output']:+.2f} % |",
          f"| Tours modèle | {d['agent_turns']} | {g['agent_turns']} | |",
        ])
    text=f'''# Temps, conclusions et tokens — mesures du 21 octobre 2026

**Le gain conjoint demandé n’est pas démontré.** Les 14 exécutions réelles concluent toutes : 7/7 de chaque côté. Le goal intégré montre une économie de temps et des deux mesures de tokens. La première étude ne montre aucune économie hors cache, et aucun essai n’établit un supplément de goals conclus.

[Rapport lisible](reports/proof.html) · [Première étude](reports/triple-proof.html) · [Extension](reports/integrated-proof.html) · [CSV des 14 essais](reports/proof-trials.csv)

## Première étude préenregistrée : 12 exécutions

Trois bibliothèques nouvelles : horaires avec changement d’heure et persistance SQLite, traitements relationnels CSV/Decimal, résolution de dépendances SemVer. Deux répétitions par bibliothèque et par condition, ordre alterné puis inversé. Quatre défauts sémantiques par bibliothèque, dont une partie exposée par les tests publics. Six groupes cachés et deux graines par essai. Les répétitions ne sont pas des projets indépendants.

{table(first)}

Le critère figé exigeait simultanément au moins un goal livré supplémentaire sans régression appariée et au moins 15 % de moins en temps, tokens rapportés ET hors cache + sortie par goal livré, coûts de tous les échecs inclus. **Critère non atteint.** Les 14,84 % de temps ne sont pas arrondis au seuil de 15 %. Aucun défaut caché ni fausse clôture n’a été observé dans ces essais.

## Extension bornée : un goal intégré, deux exécutions

Déclarée après le résultat négatif précédent. Les composants sont réutilisés ; l’intégration, le journal persistant, les révisions, migrations, concurrence, lots atomiques et exports sont nouveaux. Même produit inchangé, ordre tiré avec une graine fixe, GoalPilot en premier. Vingt-quatre groupes cachés sur deux graines par exécution, soit 48/48 réussis chacun.

{table(extension)}

Sur ce goal : **{extension['savings_percent']['seconds']:.2f} % de temps, {extension['savings_percent']['reported_tokens']:.2f} % de tokens rapportés et {extension['savings_percent']['uncached_input_plus_output']:.2f} % de hors cache + sortie économisés**, à réussite égale. Le critère primaire exigeait aussi une conclusion supplémentaire ; il est donc **non atteint**. Une paire ne prouve pas un avantage général. L’extension ne remplace pas la première étude.

## Regroupement exploratoire annoncé avant l’extension

{table(pooled)}

Ce regroupement a été annoncé après l’échec de la première étude, avant les résultats de l’extension. **Il reste exploratoire.** Les composants et répétitions sont corrélés ; il ne représente pas quatre projets indépendants. Sur ces exécutions, la différence de temps cumulé est de {pooled['groups']['direct']['seconds']-pooled['groups']['goalpilot']['seconds']:.6f} secondes et celle de tokens rapportés est de {pooled['groups']['direct']['reported_tokens']-pooled['groups']['goalpilot']['reported_tokens']:,}. Le hors cache + sortie augmente de {pooled['groups']['goalpilot']['uncached_input_plus_output']-pooled['groups']['direct']['uncached_input_plus_output']:,} tokens. Avec 7 réussites de chaque côté, les pourcentages par goal livré et en total sont identiques.

## Ce qui est mesuré

- Un succès exige tous les groupes du juge caché réussis **et** une sortie normale de la mission. Un simple message « terminé » ne suffit pas.
- Le temps actif inclut la préparation du contexte, les appels, les contre-exemples, les vérifications et la fermeture du processus. Le temps du juge caché externe est exclu symétriquement.
- Tokens rapportés = entrée + sortie. Hors cache + sortie = entrée − entrée en cache + sortie. Le cache fait partie de l’entrée et n’est jamais ajouté deux fois. Cela ne donne pas le quota d’abonnement ni un prix exact.
- Tous les essais, coûts et échecs éventuels sont conservés ; aucun résultat du juge caché n’aide à corriger le livrable. Le juge vérifie les interfaces publiques originales et a été testé sur références correctes et défauts isolés avant les appels.
- Les 21 tours réels des deux études ont des compteurs complets : **2 758 834 tokens rapportés au total**. C’est le coût mesuré de l’évaluation, pas une économie. Un pré-essai technique interrompu après lancement prématuré est conservé séparément avec usage inconnu ; le coût intégral de cette itération est donc supérieur ou égal à ce total.

Le pré-essai n’a donné aucun jugement de qualité : aucune modification du projet, aucune sortie finale. Le lancement avait précédé la prise en compte d’un échec CI ; le processus a été arrêté et une variable de chemin masquée a été corrigée avant une nouvelle inscription. Les sources des cas et juges sont restées identiques. Cet arrêt de l’hôte n’est pas compté comme un échec du comparateur. [Trace et justification](reports/triple-live-001/technical-pilot.json).

## Intégrité et limites

Les empreintes des sources figées sont intactes ; les sept paires partent de fichiers identiques ; les 21 différences de compteurs correspondent aux événements bruts. Le modèle observé est gpt-6.1-sol dans tous les appels. Aucun événement de sous-agent ni marqueur de chemin du juge caché n’a été trouvé dans les commandes examinées. Cette recherche ne constitue pas un audit exhaustif des accès aux fichiers. [Audit initial](reports/triple-live-002/audit.json) · [Audit extension](reports/integrated-live-001/audit.json).

Le comparateur est une session autonome de **Codex CLI direct**, pas une évaluation du `/goal` natif de l’application. Les missions synthétiques ont un besoin initial bref et une documentation publique détaillée. Elles ne prouvent ni ta satisfaction, ni un gain sur tes objectifs vagues de plusieurs heures. Les caches, l’ordre et la variabilité des sorties limitent les comparaisons. Le contrôle du produit emploie le même modèle dans un contexte séparé, avec des erreurs possiblement communes.

Les protocoles et leurs copies préenregistrées sont inchangés. Les [sources exactes 0.4.0](reports/reproduction-v0.4.0/README.txt) passent 120/120 tests hors ligne ; ce complément de reproduction a été assemblé après inscription, et ses sources correspondent aux empreintes d’origine. Son premier essai hors ligne manquait du dossier de scripts de support ; cette erreur d’assemblage et son résultat sont conservés, puis le paquet complet a passé les 120 tests.

La livraison courante **0.4.1** passe **{ci['passed']}/{ci['tests_run']} tests en {ci['duration_seconds']:.6f} s**, sans API. Elle ajoute deux corrections après les mesures : détection conservatrice des suites unittest avant gel (les suites pytest/m mixtes ne sont pas traitées comme unittest), et affichage des contre-exemples parmi les appels de contrôle. Ces correctifs sont testés localement ; aucune nouvelle mesure réelle n’est attribuée à cette version. [Résultat CI](reports/tests.json).

Les études et résultats négatifs précédents restent dans [MEASUREMENTS-v3.md](MEASUREMENTS-v3.md), [MEASUREMENTS-v2.md](MEASUREMENTS-v2.md) et leurs dossiers de preuves.
'''.replace('pytest/m mixtes','pytest ou mixtes')
    (ROOT/'MEASUREMENTS.md').write_text(text)
    rows=[]
    for name in('triple-live-002','integrated-live-001'):
        m=json.loads((ROOT/'reports'/name/'protocol.json').read_text())
        for trial in m['order']:
            r=json.loads((ROOT/'reports'/name/'trials'/trial['id']/'record.json').read_text())
            rows.append({'study':name,'id':r['id'],'mode':r['mode'],'status':r['status'],'success':r['success'],'seconds':r['seconds'],'reported_tokens':r['usage']['total_tokens'],'uncached_input_plus_output':r['usage']['total_tokens']-r['usage']['cached_input_tokens'],'usage_complete':r['usage']['usage_complete'],'hidden_groups_passed':sum(j['passed']for j in r['judgments']),'hidden_groups_total':len(r['judgments'])})
    with(ROOT/'reports/proof-trials.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    esc=html.escape
    htmlrows=''
    for title,data in(('Étude initiale (6 goals × 2 conditions)',first),('Extension intégrée (1 goal × 2 conditions)',extension),('Total exploratoire (7 goals × 2 conditions)',pooled)):
        d,g=(data['groups'][k]for k in('direct','goalpilot'));s=data['savings_percent']
        htmlrows+=f"<tr><td>{esc(title)}</td><td>{d['completed_goals']}/{d['runs']} → {g['completed_goals']}/{g['runs']}</td><td>{s['seconds']:.2f} %</td><td>{s['reported_tokens']:.2f} %</td><td>{s['uncached_input_plus_output']:.2f} %</td></tr>"
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — preuve et limites</title><style>body{{max-width:1080px;margin:auto;padding:38px 20px;font:17px/1.65 system-ui;background:#101b2a;color:#edf3fa}}h1{{line-height:1.15;max-width:850px}}a{{color:#8edfc9}}table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{padding:14px 9px;text-align:left;border-bottom:1px solid #3a4c63}}.scroll{{overflow:auto}}.lead{{font-size:22px}}small{{color:#b5c7db}}.box{{background:#1c3048;padding:20px;border-radius:12px;margin:25px 0}}</style>
<p><small>GOALPILOT 0.4.0 · 14 EXÉCUTIONS RÉELLES · 21 TOURS MESURÉS · 21 OCTOBRE 2026</small></p><h1>Du temps économisé. Aucun supplément de goals conclus démontré.</h1>
<p class="lead">7/7 goals livrés dans chaque condition. Les trois gains demandés ensemble restent <strong>non établis</strong>.</p>
<div class="scroll"><table><tr><th>Comparaison</th><th>Livrés direct → GoalPilot</th><th>Temps économisé</th><th>Tokens économisés</th><th>Hors cache + sortie économisés</th></tr>{htmlrows}</table></div>
<p>Un pourcentage négatif indique une consommation supplémentaire. Les économies sont calculées par rapport à Codex CLI direct. Les deux conditions ont le même nombre de réussites ; les pourcentages totaux et par réussite coïncident.</p>
<div class="box"><strong>Goal intégré : 458 → 204 secondes, 559 188 → 259 953 tokens.</strong><p>48/48 groupes cachés réussis chacun. Une seule paire sur une intégration nouvelle de composants déjà évalués. L’extension a été déclarée après le résultat négatif initial et ne le remplace pas.</p></div>
<p>Budgets et critères figés, même modèle gpt-6.1-sol, départs identiques. Aucun retour des juges cachés n’a servi aux corrections. Les 240 groupes de vérification ont tous réussi ; ils partagent des composants et des entrées et ne sont pas 240 observations indépendantes.</p>
<p>La première étude et l’extension échouent à leurs critères conjoints, qui exigeaient une conclusion supplémentaire. Le regroupement reste exploratoire. Il ne prouve ni un gain sur les goals personnels de plusieurs heures, ni une conversion exacte en quota d’abonnement.</p>
<p><strong>Coût connu de l’évaluation : 2 758 834 tokens</strong>, plus un pré-essai technique à consommation inconnue conservé séparément. Le produit courant 0.4.1 comporte deux correctifs locaux ultérieurs et passe {ci['passed']}/{ci['tests_run']} tests ; les mesures réelles concernent les sources 0.4.0 conservées.</p>
<p><a href="../MEASUREMENTS.md">Méthode et chiffres détaillés</a> · <a href="triple-proof.html">Étude initiale</a> · <a href="integrated-proof.html">Extension et résumé exploratoire</a> · <a href="proof-trials.csv">14 essais en CSV</a> · <a href="reproduction-v0.4.0/README.txt">Reproduction des sources exactes</a></p></html>'''
    (ROOT/'reports/proof.html').write_text(page)
    assert len(rows)==14 and sum(r['hidden_groups_total']for r in rows)==240
    assert sum(r['reported_tokens']for r in rows)==2758834
    print(json.dumps({'runs':len(rows),'hidden_groups':240,'known_evaluation_tokens':2758834,'joint_gain_proven':False,'current_offline_tests_passed':ci['passed']}))


if __name__=='__main__':build()
