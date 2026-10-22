"""Publish the measured current-version comparison, including its failed cost target."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/native-current-live-001'


def main():
    a = json.loads((OUT/'analysis.json').read_text())
    audit = json.loads((OUT/'audit.json').read_text())
    assert a['complete'] and a['integrity_verified'] and a['usage_complete']
    assert audit['real_model_turns'] == 11 and not audit['possible_violations']
    b, c = a['totals']['native_goal'], a['totals']['goalpilot']
    table = f'''| Mesure totale | Codex `/goal` natif | GoalPilot 0.6.2 | Écart GoalPilot |
|---|---:|---:|---:|
| Goals corrects et clôturés | {b['closed_correct']}/2 | {c['closed_correct']}/2 | +1 goal |
| Contrôles indépendants réussis | {b['groups_passed']}/52 | {c['groups_passed']}/52 | égalité |
| Temps complet | {b['seconds']:.3f} s | {c['seconds']:.3f} s | −28,21 % |
| Tokens bruts, entrée + sortie | 1 470 188 | 674 747 | −54,10 % |
| Entrée hors cache + sortie | 123 116 | 140 347 | **+14,00 %** |'''
    block = f'''## Comparaison directe actuelle avec Codex classique

Quatre exécutions **neuves** de deux goals ambitieux sur Flowdesk et Stockroom, avec le même modèle gpt-6.1-sol, les mêmes fichiers initiaux et 900 s par exécution. Le comparateur utilise le vrai `/goal` natif, avec toutes ses continuations automatiques. Les coûts de préparation, revue, réparation et vérification de GoalPilot sont inclus.

{table}

GoalPilot gagne 284,279698 s et 795 441 tokens bruts sur les deux goals, mais dépense **17 231 tokens hors cache supplémentaires**. L’économie de quota d’abonnement n’est donc **pas prouvée** ; aucun quota ou prix exact n’est déduit des compteurs. La cible déclarée d’au moins 20 % d’économie sur chacun des trois coûts échoue.

Les deux bras produisent du code correct. Le gain de clôture vient de Flowdesk : Codex garde son goal bloqué faute de pouvoir tester une vraie socket HTTP dans son sandbox ; GoalPilot vérifie HTTP depuis l’hôte et conclut. Stockroom natif se déclare terminé malgré cette même limite de test, puis passe aussi le juge externe. Ce résultat montre une capacité de vérification dans cet environnement, sans établir une meilleure qualité de code générale.

Deux domaines synthétiques déjà exposés pendant le développement, une exécution par bras/domaine : résultat descriptif limité, sans preuve statistique ni mesure de tes goals personnels. Aucun résultat n’est repris d’une ancienne campagne. Sources et critères figés avant le premier résultat ; aucun essai relancé. L’audit confirme les compteurs des **11 tours modèle**, les cycles de vie natifs et les fichiers initiaux identiques.

[Rapport lisible](reports/native-current-live-001/report.html) · [Analyse exacte](reports/native-current-live-001/analysis.json) · [CSV](reports/native-current-live-001/trials.csv) · [Protocole figé](reports/native-current-live-001/protocol.json) · [Audit brut](reports/native-current-live-001/audit.json).

Coût de ces quatre essais : **2 144 935 tokens bruts CLI**, intégralement mesurés. Avec les 4 846 313 tokens connus de la mise au point 0.6 précédente : **au moins 6 991 248 tokens CLI** cumulés, sans double comptage des anciens témoins. La session de développement elle-même reste hors de ces compteurs ; les gains d’exécution ne constituent pas un amortissement prouvé de la recherche.
'''
    for name in ('README.md', 'MEASUREMENTS.md'):
        p = ROOT/name
        text = p.read_text()
        if '## Comparaison directe actuelle avec Codex classique' not in text:
            title, rest = text.split('\n', 1)
            p.write_text(title+'\n\n'+block+'\n## Comparaison interne historique : 0.6.2 face à 0.5.2\n'+rest)
    rows = [json.loads((OUT/'trials'/item['id']/'record.json').read_text())
            for item in json.loads((OUT/'protocol.json').read_text())['order']]
    detail = [{'case': r['case'], 'mode': r['mode'], 'status': r['status'], 'closed_correct': r['success'],
               'groups_passed': sum(j['passed'] for j in r['judgments']), 'seconds': r['seconds'],
               'raw_tokens': r['usage']['total_tokens'],
               'uncached_tokens': r['usage']['total_tokens']-r['usage']['cached_input_tokens']} for r in rows]
    interpretation = {'study': 'native-current-live-001', 'comparison': 'Four fresh executions: GoalPilot0.6.2 versus genuine Codex native /goal',
                      'trial_details': detail, 'analysis': a,
                      'closure_cause': 'Native Flowdesk blocked on socket restriction despite code passing26/26. Host checks let GoalPilot conclude. Native Stockroom marked complete and passed26/26.',
                      'quota_saving_proven': False,
                      'known_cumulative_cli_raw_tokens_lower_bound': 6991248,
                      'unmetered': 'Root development model session and unknown tokens in earlier partial studies.'}
    (OUT/'interpretation.json').write_text(json.dumps(interpretation, indent=2)+'\n')
    (OUT/'RESULTS.md').write_text(block.replace('(reports/native-current-live-001/', '('))
    body = '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GoalPilot0.6.2 face à Codex natif</title><style>body{font:17px system-ui;max-width:1050px;margin:40px auto;padding:0 20px;color:#17212c;background:#f7f9fc}table{border-collapse:collapse;width:100%;background:white;margin:24px 0}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce2e9}strong{color:#8b2525}a{color:#145ab1}pre{white-space:pre-wrap;font-size:14px}</style><h1>GoalPilot0.6.2 face au vrai Codex /goal</h1><p>Quatre nouveaux essais, même modèle, mêmes fichiers initiaux, 15 minutes par workflow. Tous les coûts GoalPilot sont comptés.</p>'
    body += '<table><tr><th>Mesure</th><th>Codex natif</th><th>GoalPilot0.6.2</th><th>Écart</th></tr>'
    for label, bv, cv, diff in [
        ('Goals corrects et clôturés', '1/2', '2/2', '+1'), ('Contrôles réussis', '52/52', '52/52', 'égalité'),
        ('Temps complet', f"{b['seconds']:.3f} s", f"{c['seconds']:.3f} s", '−28,21 %'),
        ('Tokens bruts', '1 470 188', '674 747', '−54,10 %'), ('Entrée hors cache + sortie', '123 116', '140 347', '+14,00 %')]:
        body += '<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in (label, bv, cv, diff))+'</tr>'
    body += '</table><p><strong>L’économie de quota n’est pas prouvée : la consommation hors cache augmente. La cible d’au moins20 % sur chacun des coûts échoue.</strong></p><p>Les deux bras produisent du code correct. Flowdesk natif reste bloqué sur une restriction de socket ; GoalPilot vérifie HTTP depuis l’hôte. Stockroom natif se déclare complet malgré cette même limite, puis passe les contrôles externes. Le gain de clôture ne prouve pas une meilleure qualité de code.</p><p>Deux domaines synthétiques familiers, une réalisation par bras/domaine. Pas de conclusion statistique ni de mesure des goals personnels. Aucun ancien contrôle réutilisé.11 tours modèle réels, compteurs complets vérifiés dans les événements bruts, aucune anomalie détectée.</p><h2>Détail des essais</h2><table><tr><th>Cas</th><th>Mode</th><th>État final</th><th>Contrôles</th><th>Secondes</th><th>Tokens bruts</th><th>Hors cache</th></tr>'
    for r in detail:
        body += '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (r['case'], r['mode'], r['status'], str(r['groups_passed'])+'/26', round(r['seconds'], 3), r['raw_tokens'], r['uncached_tokens']))+'</tr>'
    body += '</table><p>Coût nouveau des essais :2 144 935 tokens bruts CLI. Mise au point0.6 et cette comparaison :au moins6 991 248 tokens CLI connus ; session de développement non instrumentée. Aucun amortissement prouvé.</p><p><a href="protocol.json">Protocole figé</a> · <a href="analysis.json">Analyse exacte</a> · <a href="trials.csv">CSV</a> · <a href="audit.json">Audit</a> · <a href="interpretation.json">Interprétation et détails</a></p></html>'
    (OUT/'report.html').write_text(body)
    p = ROOT/'reports/release-decision.json'
    decision = json.loads(p.read_text())
    decision['native_comparison'] = interpretation
    decision['known_development_cli_raw_tokens_lower_bound'] = 6991248
    p.write_text(json.dumps(decision, indent=2)+'\n')
    print(json.dumps({'report': str(OUT/'report.html'), 'new_cli_raw_tokens': a['new_known_raw_tokens'], 'joint_target_met': a['joint_20_percent_target_met']}, indent=2))


if __name__ == '__main__':
    main()
