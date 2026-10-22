"""Keep original negative result, scaling primary, and exploratory pooling distinct."""
import html,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from evaluation.triple.report import calculate
from tools.audit_triple import audit
ROOT=Path(__file__).resolve().parents[1]


def build():
    earlier=ROOT/'reports/triple-live-002';output=ROOT/'reports/integrated-live-001'
    m=json.loads((output/'protocol.json').read_text());oldm=json.loads((earlier/'protocol.json').read_text())
    old=[json.loads((earlier/'trials'/x['id']/'record.json').read_text())for x in oldm['order']]
    rows=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
    check=audit(output);data=calculate(rows,m);full=len(rows)==2
    oldcheck=audit(earlier)
    oldintegrity=oldcheck['complete']and oldcheck['source_snapshot_intact']and oldcheck['all_known_usage_matches_raw']and oldcheck['all_paired_initial_files_identical']and not oldcheck['possible_hidden_source_commands']and not oldcheck.get('possible_unmeasured_delegation')
    integrity=check['source_snapshot_intact']and check['all_known_usage_matches_raw']and check['all_paired_initial_files_identical']and not check['possible_hidden_source_commands']and not check.get('possible_unmeasured_delegation')
    eligible=full and data['eligible']and integrity
    g,d=data['groups']['goalpilot'],data['groups']['direct'];savings=data['savings_percent']
    primary=eligible and g['completed_goals']>d['completed_goals']and all(savings[k]is not None and savings[k]>=15 for k in ('seconds','reported_tokens','uncached_input_plus_output'))
    pm={**oldm,'order':oldm['order']+m['order'],'cases':oldm['cases']+['integrated']}
    pooled=calculate(old+rows,pm)
    for item in (data,pooled):
        if not all(v['usage_complete']for v in item['groups'].values()):
            item['savings_percent']['reported_tokens']=None;item['savings_percent']['uncached_input_plus_output']=None
    result={'integrated_primary_met':primary,'integrated':data,'audit':check,
        'exploratory_pooled_criterion_met':pooled['joint_preregistered_criterion_met']and eligible and oldintegrity,
        'exploratory_pooled':pooled,'extension_protocol':m,
        'original_study_primary_met':False,
        'interpretation':'The original 12-trial study failed its joint criterion and is retained unchanged. The integration is new but reuses its three components. This is a predeclared scaling extension and exploratory pooled summary, not four independent held-out projects or population proof.'}
    atomic_json(ROOT/'reports/integrated-proof.json',result)
    esc=lambda x:html.escape(str(x))
    table=''.join(f'<tr><td>{esc(r["mode"])}</td><td>{r["success"]}</td><td>{sum(j["passed"]for j in r["judgments"])}/{len(r["judgments"])}</td><td>{r["seconds"]:.3f}</td><td>{r["usage"]["total_tokens"]:,}</td><td>{r["usage"]["total_tokens"]-r["usage"]["cached_input_tokens"]:,}</td><td>{esc([j["id"]for j in r["judgments"]if not j["passed"]])}</td></tr>'for r in rows)
    title='Trois gains observés sur le goal intégré.'if primary else'Les trois gains ne sont pas établis sur le goal intégré.'
    if not full:title='Évaluation intégrée en cours.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — goal intégré</title>
<style>body{{max-width:1100px;margin:auto;padding:36px 20px;background:#101a28;color:#e9eff8;font:16px/1.6 system-ui}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #35475b}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1a2b40;padding:20px;border-radius:12px}}a{{color:#8bddc5}}.scroll{{overflow:auto}}</style>
<h1>{title}</h1><p>Un seul objectif plus large : les trois bibliothèques reliées à un journal persistant avec migrations, idempotence, révisions, concurrence et exports. Même produit inchangé, même modèle, mêmes fichiers et plafond de dix minutes. L’intégration est nouvelle ; les composants ont déjà été évalués.</p>
<div class="scroll"><table><tr><th>Mode</th><th>Livré</th><th>Groupes cachés</th><th>Secondes</th><th>Tokens</th><th>Hors cache + sortie</th><th>Échecs</th></tr>{table}</table></div>
<h2>Critère primaire de cette extension</h2><p>Davantage de goals livrés et au moins 15 % de moins en temps total, tokens rapportés et tokens hors cache + sortie. Les compteurs doivent être complets. Aucun incident de session n’est provoqué ; les tests applicatifs vérifient notamment le rollback avec une erreur SQLite.</p><pre>{esc(json.dumps({'primary_met':primary,'complete':full,'groups':data['groups'],'savings_percent':savings},ensure_ascii=False,indent=2))}</pre>
<h2>Résumé exploratoire regroupé</h2><p>Ce regroupement avait été déclaré avant les nouveaux résultats, après l’échec de la première étude. Il ne remplace pas ce résultat négatif. Les économies par goal livré incluent tous les coûts des essais, y compris les échecs. Les coûts absolus restent visibles ; les projets et répétitions sont corrélés.</p><pre>{esc(json.dumps({'criterion_met':result['exploratory_pooled_criterion_met'],'groups':pooled['groups'],'savings_percent':pooled['savings_percent'],'quality_wins':pooled['quality_wins'],'quality_losses':pooled['quality_losses']},ensure_ascii=False,indent=2))}</pre>
<h2>Limites</h2><p>Une paire sur une intégration synthétique ne prouve ni le taux de réussite général ni l’efficacité sur tes propres goals de plusieurs heures. Le contrôle est le même modèle dans un contexte séparé. Aucun retour du juge caché ne sert aux corrections. L’audit des commandes n’est pas une preuve exhaustive d’absence de lecture. Aucune conversion exacte en quota d’abonnement.</p>
<p><a href="triple-proof.html">Première étude, conservée</a> · <a href="integrated-live-001/protocol.json">Protocole figé de l’extension</a> · <a href="integrated-proof.json">Données et audits</a></p></html>'''
    (ROOT/'reports/integrated-proof.html').write_text(page)
    print(json.dumps({'complete':full,'integrated_primary_met':primary,'groups':data['groups'],'savings_percent':savings,'exploratory_pooled_criterion_met':result['exploratory_pooled_criterion_met']},indent=2))
    return result


if __name__=='__main__':build()
