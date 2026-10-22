"""Create a qualified evidence summary; all gates must pass before a positive claim."""
import csv,html,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.triple.report import report
from goalpilot.engine import atomic_json
from tools.audit_triple import audit

ROOT=Path(__file__).resolve().parents[1]


def build(output):
    output=Path(output).resolve();data=report(output);checks=audit(output);m=data['protocol']
    records=[json.loads(p.read_text())for x in m['order']if(p:=output/'trials'/x['id']/'record.json').exists()]
    integrity=checks['source_snapshot_intact']and checks['all_known_usage_matches_raw']and checks['all_paired_initial_files_identical']and not checks['possible_hidden_source_commands']and not checks.get('possible_unmeasured_delegation')
    qualified=data['joint_preregistered_criterion_met']and checks['complete']and integrity
    pairs=[]
    for item in data['pairs']:
        same=[r for r in records if r['case']==item['case']and r['repeat']==item['repeat']]
        d=next(r for r in same if r['mode']=='direct');g=next(r for r in same if r['mode']=='goalpilot')
        pairs.append({**item,'seconds_reduction_percent':100*(1-g['seconds']/d['seconds']),
            'reported_token_reduction_percent':100*(1-g['usage']['total_tokens']/d['usage']['total_tokens'])if d['usage']['total_tokens']and g['usage']['usage_complete']and d['usage']['usage_complete']else None})
    result={'qualified_joint_gain_observed':qualified,'measurement':data,'audit':checks,'paired_resources':pairs,
        'technical_pilot':json.loads((ROOT/'reports/triple-live-001/technical-pilot.json').read_text()),
        'scope':'Costs per fully delivered goal include all trial costs, including failures. Absolute costs reported separately. Descriptive result on 3 synthetic projects, not universal proof. Pilot interruption is not counted as a baseline failure.'}
    atomic_json(ROOT/'reports/triple-proof.json',result)
    columns=['id','case','repeat','mode','status','success','seconds','agent_turns','reported_tokens','cached_input_tokens','uncached_input_plus_output','usage_complete']
    with (output/'trials.csv').open('w',newline='')as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for r in records:writer.writerow({k:r[k]for k in ('id','case','repeat','mode','status','success','seconds')}|{'agent_turns':len(r['calls']),'reported_tokens':r['usage']['total_tokens'],'cached_input_tokens':r['usage']['cached_input_tokens'],'uncached_input_plus_output':r['usage']['total_tokens']-r['usage']['cached_input_tokens'],'usage_complete':r['usage']['usage_complete']})
    esc=lambda v:html.escape(str(v))
    rows=''.join(f'<tr><td>{esc(r["id"])}</td><td>{"oui"if r["success"]else"non"}</td><td>{r["seconds"]:.3f}</td><td>{r["usage"]["total_tokens"]:,}</td><td>{r["usage"]["total_tokens"]-r["usage"]["cached_input_tokens"]:,}</td><td>{esc([x["id"]for x in r["judgments"]if not x["passed"]])}</td></tr>'for r in records)
    title='Les trois gains préenregistrés sont observés sur cette campagne.'if qualified else'Les trois gains préenregistrés ne sont pas démontrés par cette campagne.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GoalPilot — bilan des trois gains</title>
<style>body{{max-width:1100px;margin:auto;padding:36px 20px;background:#101a28;color:#e9f0f7;font:16px/1.6 system-ui}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1b2b40;padding:20px;border-radius:10px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #35465c}}a{{color:#86dec4}}.scroll{{overflow:auto}}</style>
<h1>{title}</h1><p>Les économies principales sont calculées <strong>par objectif complètement livré</strong> : coûts de tous les essais, y compris les échecs, divisés par le nombre de réussites. Les coûts totaux restent visibles. Un gain par objectif livré ne signifie pas nécessairement un coût total inférieur.</p>
<h2>Résultats</h2><pre>{esc(json.dumps({k:data[k]for k in ('complete','eligible','groups','quality_wins','quality_losses','savings_percent')},ensure_ascii=False,indent=2))}</pre>
<div class="scroll"><table><tr><th>Essai</th><th>Livré</th><th>Secondes</th><th>Tokens totaux</th><th>Hors cache + sortie</th><th>Échecs cachés</th></tr>{rows}</table></div>
<h2>Ce qui a été comparé</h2><p>Codex direct et GoalPilot 0.4.0, même modèle gpt-6.1-sol, mêmes fichiers initiaux, 300 secondes par essai, trois bibliothèques nouvelles : horaires avec changements d’heure, traitements relationnels CSV et résolution SemVer. Deux répétitions, ordre inversé. Aucun incident injecté. Les tests cachés n’aident jamais les corrections. Chaque objectif exige six groupes réussis sur deux graines et une sortie normale.</p>
<p>Le produit prépare le contexte et les tests d’origine, puis génère au plus deux probes ciblés si ces tests échouent initialement. Ces probes sont gelés avant les modifications. La reprise conserve les budgets et tente de récupérer un compte rendu dans le travail engagé. Tout ce coût est inclus.</p>
<h2>Intégrité et limites</h2><pre>{esc(json.dumps({k:checks[k]for k in ('complete','source_snapshot_intact','all_known_usage_matches_raw','all_paired_initial_files_identical','model_calls','known_token_lower_bound','possible_hidden_source_commands')},ensure_ascii=False,indent=2))}</pre>
<p>Trois projets synthétiques avec des contrats détaillés et des défauts sémantiques préparés, pas des goals personnels de plusieurs heures. Les répétitions sont corrélées. Il s’agit d’observations sur ces essais, pas d’une preuve universelle. Aucun quota d’abonnement exact ni satisfaction humaine n’est mesuré. Le contrôle des marqueurs de commandes ne constitue pas un audit exhaustif du système de fichiers.</p>
<p>Un pré-essai technique a été interrompu par l’hôte après un lancement prématuré : aucun résultat de qualité n’a été jugé, les sources du projet sont restées inchangées et son coût est conservé à part, avec usage inconnu. Il n’est pas compté comme un échec comparatif. Les cas et juges n’ont pas été ajustés après cet incident ; seule l’erreur générique de variable du superviseur a été corrigée avant la nouvelle inscription.</p>
<p><a href="triple-live-002/report.html">Protocole et campagne complète</a> · <a href="triple-live-002/trials.csv">CSV des essais</a> · <a href="triple-proof.json">Données et audit</a></p></html>'''
    (ROOT/'reports/triple-proof.html').write_text(page)
    print(json.dumps({'complete':data['complete'],'qualified_joint_gain_observed':qualified,'groups':data['groups'],'savings_percent':data['savings_percent'],'quality_wins':data['quality_wins'],'quality_losses':data['quality_losses']},indent=2))
    return result


if __name__=='__main__':build(sys.argv[1])
