"""Publish the complete cold/warm results without equating token proxies with quota."""
from pathlib import Path
import html
import json
ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'reports/quota-native-live-007'
    a=json.loads((out/'analysis.json').read_text());w=json.loads((out/'warm-analysis.json').read_text());ci=json.loads((ROOT/'reports/tests.json').read_text())
    rows=[json.loads(p.read_text())for p in(out/'trials').glob('*/record.json')]
    new=sum(r['usage']['total_tokens']for r in rows if r['mode']=='goalpilot')
    n=a['totals']['native_goal'];g=a['totals']['goalpilot'];s=a['savings_percent']
    from goalpilot import __version__
    def val(v):return 'non évalué'if v is None else f'{v:,.2f}'.replace(',',' ')
    def pct(k):return 'non évalué'if s.get(k)is None else f'{s[k]:+.2f} %'
    archives=ROOT/'docs';archives.mkdir(exist_ok=True)
    for source,dest in [('README.md','README-v0.8.1.md'),('MEASUREMENTS.md','MEASUREMENTS-v8.1.md')]:
        if not(archives/dest).exists():(archives/dest).write_bytes((ROOT/source).read_bytes())
    old=ROOT/'reports/release-decision.json';dest=archives/'release-decision-v0.8.1.json'
    if not dest.exists():dest.write_bytes(old.read_bytes())
    measured=f'''# GoalPilot {__version__} — mesures réelles

Deux expériences distinctes : nouvelle réalisation à cache vide, puis réutilisation d'une demande
strictement identique. Les résultats de réutilisation ne sont jamais mélangés aux premiers passages.
Le quota exact d'abonnement reste inconnu sur les premiers passages. Un hit vérifié n'effectue aucun
appel modèle : il ne consomme donc aucun quota d'inférence Codex pour cette répétition.

## Première réalisation : deux goals ambitieux connus

Contrôle : véritable Codex `/goal` natif, sessions persistantes et continuations automatiques.
Les DEUX contrôles proviennent de l'étude001, sont conservés et connus avant la conception du candidat.
Le candidat {__version__} est exécuté deux fois à neuf avec des caches isolés vides. Même modèle
gpt-6.1-sol, mêmes fichiers initiaux et mêmes contrats,900s maximum et6appels côté GoalPilot.
GoalPilot demande LOW au départ puis MEDIUM uniquement après échec des tests hôte ; les contrôles
natifs utilisent leur effort configuré/par défaut. Cela ne mesure pas l'effet du wrapper seul à effort égal.

| Mesure | Codex natif historique | GoalPilot neuf | Économie |
|---|---:|---:|---:|
| Goals clos et corrects | {n['closed_correct']}/2 | {g['closed_correct']}/2 | — |
| Groupes indépendants réussis | {n['groups_passed']}/52 | {g['groups_passed']}/52 | — |
| Temps complet,secondes | {val(n['seconds'])} | {val(g['seconds'])} | {pct('seconds')} |
| Tokens bruts,entrée+sortie | {n['raw_tokens']} | {g['raw_tokens']} | {pct('raw_tokens')} |
| Entrée hors cache+sortie,proxy | {n['uncached_tokens']} | {g['uncached_tokens']} | {pct('uncached_tokens')} |
| Tokens de sortie,raisonnement inclus | {n['output_tokens']} | {g['output_tokens']} | {pct('output_tokens')} |
| Tokens d'entrée hors cache | {n['uncached_input_tokens']} | {g['uncached_input_tokens']} | {pct('uncached_input_tokens')} |
| Tokens d'entrée en cache | {n['cached_input_tokens']} | {g['cached_input_tokens']} | {pct('cached_input_tokens')} |

Cible préenregistrée : aucune régression de qualité/clôture et au moins20% d'économie sur temps,
brut,hors-cache+sortie ET sortie. Cible atteinte : **{a['joint_20_percent_target_met']}**.
Intégrité complète : {a['integrity_verified']}. Compteurs complets : {a['usage_complete']}.
Les pourcentages décrivent cet échantillon connu et ces contrôles historiques ; pas de garantie populationnelle.
Les52contrôles vérifient le code. Un statut natif bloqué malgré un code correct correspond ici à une
limitation du sandbox HTTP : le gain de clôture n'est pas un gain de qualité du code.

## Réutilisation exacte,coût d'apprentissage séparé

{w['executed']}/6répétitions prévues exécutées ; **{w['correct_closed']}/6closes et correctes**.
**{w['model_calls']}appel modèle** pendant ces répétitions ; modèle interdit par le garde d'exécution.
Chaque résultat réutilisé est testé dans une copie temporaire avec les contrôles figés,puis
vérifié par le même correcteur indépendant26groupes. Il s'agit de vrais fichiers et processus,
sans nouvelle inférence ; les tests unitaires simulés restent une preuve distincte de mécanisme.

| Cas | Répétition moyenne | Premier passage GoalPilot | Codex natif historique | Temps gagné vs natif |
|---|---:|---:|---:|---:|
'''
    for case,c in w['time_comparisons'].items():
        measured+=f"| {case} | {c['mean_repeat_seconds']:.3f}s | {c['cold_goalpilot_seconds']:.3f}s | {c['historical_native_seconds']:.3f}s | {c['saving_vs_historical_native_percent']:.2f}% |\n"
    measured+='''
Ces hits concernent uniquement le même texte de goal et le même contenu/mode de tous les fichiers
inventoriés,avec instructions parentes et runtime compatibles. Ils ne prouvent aucune économie
sur une demande nouvelle,des données modifiées ou une intention vague devenue différente.
L'apprentissage initial coûte les tokens de la colonne GoalPilot neuf ; il n'est pas gratuit.
Les seuils d'amortissement théoriques par cas,avec cet apprentissage inclus,sont conservés dans
[warm-analysis.json](reports/quota-native-live-007/warm-analysis.json). Les exécutions natives répétées
utilisées dans ce calcul sont une hypothèse au coût historique,pas des exécutions réalisées en plus.

## Quota et coût des recherches

L'API ne renvoie que des pourcentages entiers du compte,avec arrondi/délai inconnus et activité
concurrente possible. Les compteurs de tokens,surtout le brut largement en cache,ne constituent
pas une conversion en quota. Même une baisse de toutes les catégories reste une mesure de tokens ;
le prix relatif des catégories et les règles du quota ne sont pas observables ici.
La seule affirmation de quota certaine pour la réutilisation : zéro inférence supplémentaire lors
d'un hit,puisque aucun appel modèle n'a lieu. Aucun pourcentage exact de quota économisé au premier
passage n'est établi.

'''
    measured+=f'''Cette nouvelle étude consomme **{new}tokens bruts CLI**. Les contrôles natifs archivés ne sont
pas facturés une seconde fois dans ce coût de recherche. Les recherches antérieures ont consommé
au moins3978571tokens bruts CLI dans l'itération précédente ; cumul historique avant cette étude :
au moins10969819. Cumul connu : **au moins{10969819+new}tokens CLI**. Les interruptions avec compteur
incomplet restent des bornes inférieures. La session de développement elle-même n'est pas instrumentée.
Aucun gain net global de quota,ni ROI financier du développement,n'est établi.

Tests locaux : **{ci['passed']}/{ci['tests_run']}**,{ci['duration_seconds']:.3f}s,zéro appel API.
Les tests refusent notamment goal/données modifiés,patch corrompu,critères modifiés et échec en staging.

## Preuves conservées

- [Protocole scellé](reports/quota-native-live-007/preregistered-protocol.json)
- [Mesures froides et quota affiché](reports/quota-native-live-007/analysis.json)
- [Audit des compteurs bruts et du vrai lifecycle natif](reports/quota-native-live-007/audit.json)
- [Répétitions exactes et amortissement](reports/quota-native-live-007/warm-analysis.json)
- [Essais individuels](reports/quota-native-live-007/trials.csv)
- [Tests locaux](reports/tests.json)

Toutes les anciennes études001–006 et leurs échecs,coûts et interruptions sont conservés.
La0.8.1 précédente était17.43% plus lente et produisait24.37% de sortie en plus malgré17.90% de
moins sur le proxy hors-cache+sortie. Elle ne satisfaisait pas l'objectif demandé.
'''
    (ROOT/'MEASUREMENTS.md').write_text(measured)
    (out/'RESULTS.md').write_text(measured.replace('(reports/quota-native-live-007/','(').replace('(reports/tests.json)','(../tests.json)'))
    (out/'report.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>GoalPilot0.9 — mesures</title><style>body{max-width:1100px;margin:3rem auto;padding:1rem;background:#10151e;color:#edf2f7;font:16px/1.5 system-ui}pre{white-space:pre-wrap}a{color:#83dcd0}</style><h1>GoalPilot : premiers passages et réutilisation séparés</h1><p><a href="RESULTS.md">Rapport</a> · <a href="analysis.json">Mesures froides</a> · <a href="warm-analysis.json">Répétitions</a></p><pre>'+html.escape(measured)+'</pre></html>')
    readme=f'''# GoalPilot {__version__}

Terminer des goals de code avec des vérifications locales et réduire le travail modèle superflu.

Cette version fournit localement les utilitaires de test JSONL/HTTP,demande des modifications ciblées,
fige les tests d'origine puis ceux de livraison,et corrige les échecs de vérification hôte.
Une livraison réutilisable est mémorisée : le même goal sur les mêmes fichiers initiaux peut être
rejoué sans nouvelle inférence,après vérification dans une copie temporaire.

Mesure actuelle : {g['closed_correct']}/2goals froids clos et corrects,{g['groups_passed']}/52contrôles ;
{pct('seconds')} de temps économisé,{pct('uncached_tokens')} sur entrée hors cache+sortie,
{pct('output_tokens')} sur la sortie,face à deux contrôles Codex `/goal` historiques connus.
Réutilisation exacte : {w['correct_closed']}/6répétitions correctes et closes,{w['model_calls']}appel modèle.
**Le pourcentage exact de quota économisé sur un nouveau goal n'est pas établi.**

[Mesures,méthode,limites et coûts complets](MEASUREMENTS.md).

Python3.11+,stdlib uniquement,Codex CLI authentifié.

```bash
python -m goalpilot go "Terminer ce projet de bout en bout" --repo /chemin/projet --run-dir /chemin/preuves/run-1
python -m goalpilot continue /chemin/preuves/run-1
python -m goalpilot status /chemin/preuves/run-1
python validate.py
```

`--cache-dir /chemin/cache` choisit le cache local partagé ; `--no-reuse` force une nouvelle réalisation.
Une modification du goal,des fichiers ou des données provoque un premier passage normal.
Une reprise de mission achevée revalide les contrôles sans appel modèle si tout passe encore.
Le cache ne réutilise que les livraisons à tests unittest figés compatibles ; les entrées sensibles,
symlinks,inventaires incomplets ou échecs de test rendent la réutilisation indisponible.

`--max-uncached-tokens` limite souplement entrée hors cache+sortie entre appels ; un appel peut
dépasser le plafond. `--thorough` demande une revue indépendante systématique et ignore le cache.
`--checks` accepte vos critères explicites ; `--fast` conserve l'ancienne boucle directe.
Les critères proposés par le réalisateur ne prouvent pas toute une intention personnelle.
Les projets sans suite unittest compatible utilisent le chemin de contre-vérification existant.
La réutilisation exacte ne couvre pas n'importe quelle nouvelle requête.

[Rapport HTML](reports/quota-native-live-007/report.html) · [Décision de version](reports/release-decision.json)
'''
    (ROOT/'README.md').write_text(readme)
    decision={'selected_version':__version__,'status':'measured_cold_candidate_and_exact_reuse_with_limits',
              'cold_study':'quota-native-live-007','cold_primary_target_met':a['joint_20_percent_target_met'],
              'cold_subscription_quota_saving_proven':False,'warm_exact_reuse_zero_model_calls_proven':w['correct_closed']==6 and w['model_calls']==0,
              'all_arbitrary_goals_efficiency_proven':False,'cold':a,'warm':{k:v for k,v in w.items()if k!='rows'},
              'offline_tests':ci,'new_research_raw_tokens':new,'lifetime_known_cli_raw_lower_bound':10969819+new,
              'development_session_tokens_unknown':True,'limits':'Known historical native controls,2familiar synthetic cases,deliberate reasoning-policy difference. No general quota conversion. Warm wins require strict exact repeat; initial learning charged separately.'}
    (ROOT/'reports/release-decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    (ROOT/'docs/FINISH.md').write_text(readme+'\n\n'+measured)
    print(json.dumps({k:v for k,v in decision.items()if k not in ('cold','warm','offline_tests')},indent=2))


if __name__=='__main__':main()
