"""Recalculate the human report from retained live artifacts, without API calls."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path

from goalpilot.engine import atomic_json


def build(root=Path('.')):
    tests=json.loads((root/'reports/tests.json').read_text())
    micro=json.loads((root/'reports/live-004/report.json').read_text())
    holdouts=json.loads((root/'reports/live-004/holdouts.json').read_text())
    vague=json.loads((root/'reports/vague-live-001/report.json').read_text())
    smoke_path=root/'reports/default-live-001/report.json'
    smoke=json.loads(smoke_path.read_text()) if smoke_path.exists() else None
    held={(x['task'],x['mode']):x for x in holdouts['results']}
    records=[]
    for item in micro['runs']:
        task='notes' if 'notes' in item['goal'].lower() else 'ledger'
        records.append({'experiment':'microtasks','task':task,'mode':item['mode'],
            'external_success':held[(task,item['mode'])]['all_holdouts_passed'] and item['contract_passed'],
            'status':item['status'],'seconds':item['active_seconds'],'sessions':item['agent_calls'],'usage':item['usage']})
    for item in vague['results']:
        records.append({'experiment':'open_ended','task':'notes, goal ouvert','mode':item['mode'],
            'external_success':item['external_goal_success'],'status':item['internal_status'],
            'seconds':item['execution_seconds_including_planning'],'sessions':item['agent_calls'],'usage':item['usage']})
    if smoke:
        records.append({'experiment':'default_smoke','task':'notes, délais par défaut','mode':'supervised',
            'external_success':smoke['external_goal_success'],'status':smoke['internal_status'],
            'seconds':smoke['execution_seconds_including_planning'],'sessions':smoke['agent_calls'],'usage':smoke['usage']})
    micro_counts={mode:{'successes':sum(x['external_success'] for x in records if x['experiment']=='microtasks' and x['mode']==mode),
                       'trials':sum(x['experiment']=='microtasks' and x['mode']==mode for x in records)} for mode in ('direct','supervised')}
    direct_score=f"{micro_counts['direct']['successes']}/{micro_counts['direct']['trials']}"
    supervised_score=f"{micro_counts['supervised']['successes']}/{micro_counts['supervised']['trials']}"
    data={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'tests':tests,'records':records,
        'real_sessions_started':sum(x['sessions'] for x in records),
        'sessions_without_usage':sum(x['usage']['calls_without_usage'] for x in records),
        'known_reported_tokens_lower_bound':sum(x['usage']['total_tokens'] for x in records),
        'whole_campaign_token_comparison_available':all(x['usage']['usage_complete'] for x in records),
        'microtask_comparison':micro['comparison'],'open_ended_comparison':vague['comparison'],
        'default_smoke_is_independent_efficacy_trial':False,
        'microtask_external_success_counts':micro_counts,
        'conclusion':'The tested short-budget settings did not improve completion. Default smoke tests functionality only. No demonstrated subscription-quota savings or evidence on representative long ambitious goals.'}
    planning_path=root/'reports/default-live-001/mission-planning/result.json'
    if smoke and planning_path.exists():
        planning=json.loads(planning_path.read_text())
        planning_tokens=sum(planning['usage'][key] for key in ('input_tokens','output_tokens')) if planning.get('usage') else None
        data['default_planning_overhead']={
            'seconds':planning['duration_seconds'],
            'time_share_percent':100*planning['duration_seconds']/smoke['execution_seconds_including_planning'],
            'reported_tokens':planning_tokens,
            'reported_token_share_percent':100*planning_tokens/smoke['usage']['total_tokens'] if planning_tokens is not None and smoke['usage']['usage_complete'] and smoke['usage']['total_tokens'] else None}
    atomic_json(root/'reports/real-evaluation.json',data)
    rows=[]
    html_rows=[]
    for item in records:
        seconds=f"{item['seconds']:.3f} s" if item['seconds'] is not None else 'non conservée¹'
        tokens=f"{item['usage']['total_tokens']:,}".replace(',',' ') if item['usage']['usage_complete'] else 'inconnus²'
        success='oui' if item['external_success'] else 'non'
        mode='direct' if item['mode']=='direct' else 'GoalPilot'
        rows.append(f"| {item['task']} | {mode} | {success} | {seconds} | {tokens} | {item['sessions']} |")
        html_rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [item['task'],mode,success,seconds,tokens,item['sessions']])+'</tr>')
    table='\n'.join(rows)
    default_text=(f"Le contrôle avec les délais par défaut termine avec `{smoke['internal_status']}` et réussit **{smoke['checks_passed']}/{smoke['checks_total']} contrôles externes**. Il utilise {smoke['agent_calls']} sessions, cadrage compris. C'est un test d'intégration supplémentaire sur le même projet de notes, pas un nouvel exemple indépendant ni une comparaison à budget égal." if smoke else 'Le contrôle avec les délais par défaut n’a pas de résultat disponible.')
    if smoke and smoke['usage']['usage_complete']:
        default_text+=f" Consommation rapportée complète : {smoke['usage']['total_tokens']:,} tokens, dont {smoke['usage']['cached_input_tokens']:,} en cache (inclus). Le seuil de 100 000 tokens est souple et a été dépassé pendant un appel : il ne constitue pas une limite ferme de quota."
    if data.get('default_planning_overhead'):
        overhead=data['default_planning_overhead']
        default_text+=f" Le cadrage représente {overhead['seconds']:.3f} secondes, soit {overhead['time_share_percent']:.2f} % du temps observé pour ce cas."
    md=f'''# Évaluation réelle de GoalPilot

Résultats recalculés le {data['generated_at_utc']}. [Rapport visuel](reports/real-evaluation.html) · [Données et calculs](reports/real-evaluation.json).

## Résultat pratique

Sur les petites tâches techniques, Codex direct obtient **{direct_score}** et GoalPilot **{supervised_score}** avec les paramètres courts testés. Les contrôles externes réservés à l'évaluateur confirment ces résultats. Cela ne démontre aucun avantage général de GoalPilot. Le nombre de projets est trop faible, et leur périmètre trop petit, pour conclure sur les longs goals.

| Cas | Exécution | Contrôles externes réussis | Temps actif | Tokens rapportés complets | Sessions Codex |
|---|---|---|---:|---:|---:|
{table}

¹ Le premier évaluateur n'avait pas conservé le chronomètre du cadrage en échec. La limite configurée était de 60 secondes ; le temps exact et l'usage n'ont pas été reconstruits artificiellement. Ce défaut de journalisation est corrigé pour les appels futurs.

² Le CLI ne renvoie son usage final qu'à la fin d'un tour. Les sessions interrompues n'ont pas émis cet événement. Leur consommation est inconnue : **zéro tokens rapportés ne signifie pas zéro tokens consommés**. Le rapport supprime les différences de tokens lorsque l'une des conditions est incomplète.

## Protocole et limites

- **Deux microtâches appariées** : notes et agrégation CSV. Mêmes fichiers, objectif détaillé, critères visibles et plafonds pour les deux conditions. Temps par condition 120 s, maximum 3 sessions, essais supervisés de 40 s, seuil souple de 20 000 tokens. Direct dispose d'une session continue. L'ordre est alterné entre les projets. Les tests réservés n'ont pas été fournis dans les prompts ni utilisés pour réparer les résultats.
- **Un objectif ouvert sur les notes** : formulation « termine ce projet pour en faire un outil personnel fiable », avec interface documentée dans le dépôt. Temps par condition 180 s, maximum 3 sessions, essais supervisés de 120 s et cadrage de 60 s inclus. Le cadrage supervisé échoue avant implémentation ; la condition directe est tout de même exécutée. Les critères d'évaluation sont figés avant le début. Ce projet réutilise la famille notes : ce n'est pas un troisième projet indépendant.
- **Un contrôle aux délais par défaut** : temps 600 s, cadrage 90 s, essais 180 s, maximum 4 sessions. Il est distinct des comparaisons, avec un budget différent.
- Tous ces résultats proviennent de véritables sessions du CLI connecté. Les acteurs scriptés de l'ancien laboratoire sont exclus de ces chiffres. `sessions` désigne les lancements de Codex, pas le nombre de requêtes internes au modèle.
- `tokens = input_tokens + output_tokens` ; le cache est inclus dans les entrées. Il ne faut pas additionner les tokens en cache à nouveau, ni convertir ces nombres en pourcentage du quota d'abonnement. Un seuil de tokens est observé entre sessions et peut être dépassé dans une session.
- Échantillon minuscule, un passage par condition, effets d'ordre/cache et variabilité non contrôlés. Aucun résultat sur des goals représentatifs de plusieurs heures, aucune satisfaction personnelle mesurée. Ces chiffres décrivent ces exécutions, sans estimer un bénéfice causal général.

## Contrôle du parcours normal

{default_text}

## Usage observé

**{data['real_sessions_started']} sessions réelles** ont été démarrées pour cette campagne connectée, dont **{data['sessions_without_usage']} sans mesure finale de consommation**. La somme des mesures disponibles est de **{data['known_reported_tokens_lower_bound']:,} tokens rapportés** ; il s'agit d'une borne inférieure du total, pas du coût complet. Les refus d'authentification des essais antérieurs ne sont pas inclus dans ce décompte.

**Aucune économie de quota n'est démontrée.** Les reprises courtes peuvent dégrader le résultat ; l'observation des fichiers et les vérifications seules ne suffisent pas à rendre l'agent plus efficace. Le parcours normal est présenté séparément afin de ne pas remplacer des essais ratés par un essai plus favorable.

## Vérification du code et corrections

**{tests['passed']}/{tests['tests_run']} tests locaux passent en {tests['duration_seconds']:.6f} s**, sans appel d'API pendant la suite. Ces tests vérifient les mécanismes, pas l'utilité sur tes objectifs. Ils couvrent aussi la séparation des tests réservés, le coût du cadrage, la conservation des résultats en échec, la reprise d'une expérience sans réexécuter les conditions terminées et l'absence de fausse économie lorsque l'usage manque.

L'audit autonome précédent avait aussi révélé deux défauts corrigés : abandon prématuré d'un pipeline encore actif et tentatives inutiles avec un vérificateur externe absent. [Avant correction](reports/autonomous-audit-001/audit.json) · [Après correction](reports/autonomous-audit-002/audit.json).

## Reproduire

Depuis la racine du projet :

```bash
python3 validate.py
python3 -m goalpilot benchmark --live --output /tmp/goalpilot-micro-nouveau --wall-seconds 120 --attempt-seconds 40 --max-calls 3 --max-tokens 20000
python3 -m evaluation.vague_goal --live --output /tmp/goalpilot-ouvert-nouveau
python3 -m evaluation.default_smoke --live --output /tmp/goalpilot-defaut-nouveau
```

Les commandes `--live` consomment réellement l'usage de ton compte. Les traces de cette livraison sont conservées dans [live-004](reports/live-004/report.json), [les tests réservés](reports/live-004/holdouts.json), [l'objectif ouvert](reports/vague-live-001/report.json) et [le contrôle par défaut](reports/default-live-001/report.json).
'''
    (root/'MEASUREMENTS.md').write_text(md)
    body=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — évaluation réelle</title>
<style>:root{{color-scheme:dark}}body{{font:16px/1.6 system-ui;background:#0d1422;color:#dce6f4;margin:0}}main{{max-width:1100px;margin:auto;padding:40px 22px}}h1{{font-size:38px}}.card{{padding:24px;border:1px solid #344259;background:#172235;border-radius:16px;margin:24px 0}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #344259}}.scroll{{overflow-x:auto}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}}a{{color:#94d7f0}}</style>
<main><p>GOALPILOT / ÉVALUATION CONNECTÉE</p><h1>Des essais réels.<br>Un bénéfice encore non démontré.</h1>
<div class="card"><b>Microtâches : Codex direct {direct_score}, GoalPilot {supervised_score}.</b><p>Résultats confirmés par des contrôles non fournis à l'agent. Aucune économie de quota démontrée. Ces petits cas ne représentent pas des goals de plusieurs heures.</p></div>
<div class="scroll"><table><thead><tr><th>Cas</th><th>Exécution</th><th>Contrôles externes</th><th>Temps actif</th><th>Tokens complets</th><th>Sessions</th></tr></thead><tbody>{''.join(html_rows)}</tbody></table></div>
<p>¹ Cadrage interrompu : durée exacte non conservée, limite configurée de 60 s. ² Usage final non émis : consommation inconnue, aucune économie calculable.</p>
<div class="card"><b>{tests['passed']}/{tests['tests_run']} tests locaux réussis</b> en {tests['duration_seconds']:.3f} s. <p>{html.escape(default_text)}</p></div>
<h2>Méthode, calculs et limites</h2><pre>{html.escape(md)}</pre></main></html>'''
    (root/'reports/real-evaluation.html').write_text(body)
    return data


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
