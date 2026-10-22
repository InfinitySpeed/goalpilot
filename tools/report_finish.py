"""Summarize frozen finish trials without further remote calls."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json


def report(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text())
    records=[json.loads(p.read_text()) for x in m['order'] if (p:=output/'trials'/x['id']/'record.json').exists()]
    groups={}
    for mode in ('v2','v3'):
        rows=[x for x in records if x['mode']==mode]
        successes=sum(x['autonomous_success'] for x in rows)
        complete=all(x['usage']['usage_complete'] for x in rows)
        tokens=sum(x['usage']['total_tokens'] for x in rows)
        uncached=sum(x['usage']['total_tokens']-x['usage']['cached_input_tokens'] for x in rows)
        groups[mode]={'runs':len(rows),'completed_goals':successes,'seconds':sum(x['seconds'] for x in rows),
            'agent_calls':sum(len(x['calls']) for x in rows),'reported_tokens':tokens,
            'uncached_input_plus_output':uncached,'usage_complete':complete,
            'tokens_per_success':tokens/successes if successes and complete else None,
            'uncached_per_success':uncached/successes if successes and complete else None,
            'false_completion':sum(x['status'] in ('completed','scope_passed') and not x['artifact_success'] for x in rows),
            'passed_judgments':sum(y['passed'] for x in rows for y in x['judgments']),
            'total_judgments':sum(len(x['judgments']) for x in rows)}
    pairs=[]
    for case in m['cases']:
        old=next((x for x in records if x['case']==case['name'] and x['mode']=='v2'),None)
        new=next((x for x in records if x['case']==case['name'] and x['mode']=='v3'),None)
        if old and new:pairs.append({'case':case['name'],'old_success':old['autonomous_success'],'new_success':new['autonomous_success']})
    wins=sum(x['new_success'] and not x['old_success'] for x in pairs)
    losses=sum(x['old_success'] and not x['new_success'] for x in pairs)
    complete=len(records)==len(m['order'])
    observed_models=set()
    source_unchanged=True
    for name,sha in m['source_fingerprint'].items():
        p=output/'source_snapshot'/name
        source_unchanged &= hashlib.sha256(p.read_bytes()).hexdigest()==sha
    audit_findings=[]
    for x in records:
        trial=output/'trials'/x['id'];state_path=trial/'run/state.json'
        if state_path.exists():
            state=json.loads(state_path.read_text())
            if x['mode']=='v3':
                first=state['verifications'][0]['checks'];last=state['verifications'][-1]['checks']
                audit_findings.append({'id':x['id'],'requirements':len(first),
                    'initially_failed':[c['id'] for c in first if not c['passed']],
                    'finally_failed':[c['id'] for c in last if not c['passed']],
                    'repair_calls':sum(c['strategy'] not in ('build','audit') for c in state['calls']),
                    'unverified':state['contract'].get('unverified',[])})
        for c in x['calls']:
            model=(c.get('result',{}).get('telemetry') or {}).get('model',{}).get('model')
            if model:observed_models.add(model)
    efficacy=complete and source_unchanged and len(observed_models)==1 and wins>=1 and losses==0 and not any(x['fatal'] for x in records)
    out={'campaign':str(output),'protocol':m,'groups':groups,'pairs':pairs,'wins':wins,'losses':losses,
         'complete':complete,'source_snapshot_integrity':source_unchanged,'observed_models':sorted(observed_models),
         'delivery_improvement_observed':efficacy,'audit_findings':audit_findings,
         'trials':[{k:x[k] for k in ('id','case','mode','seconds','status','artifact_success','autonomous_success','usage','error')} for x in records]}
    atomic_json(output/'report.json',out)
    esc=lambda x:html.escape(str(x))
    rows=''.join(f'<tr><td>{esc(x["id"])}</td><td>{esc(x["status"])}</td><td>{"oui" if x["autonomous_success"] else "non"}</td><td>{x["seconds"]:.2f}</td><td>{x["usage"]["total_tokens"]:,}</td><td>{esc([c["id"] for c in x["judgments"] if not c["passed"]])}</td></tr>' for x in records)
    conclusion='Avantage de livraison observé sur ces deux projets.' if efficacy else 'Le critère préenregistré de gain de livraison n’est pas atteint.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GoalPilot 0.3 — contrôle indépendant</title>
<style>body{{background:#101724;color:#e8edf5;font:16px/1.6 system-ui;margin:auto;max-width:1100px;padding:36px 20px}}h1{{font-size:36px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #354157}}pre{{white-space:pre-wrap;background:#1b2739;padding:20px;border-radius:12px;overflow-wrap:anywhere}}a{{color:#8bdaca}}.scroll{{overflow:auto}}p{{color:#bfccdd}}</style>
<h1>GoalPilot 0.3 : livrer, vérifier, corriger</h1><p>{conclusion} Deux projets inédits, même modèle et plafond de 600 secondes, tests cachés indépendants. Aucun chiffre de quota d’abonnement.</p>
<div class="scroll"><table><thead><tr><th>Essai</th><th>État produit</th><th>Goal livré</th><th>Secondes</th><th>Tokens rapportés</th><th>Échecs cachés</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Coût de tous les essais</h2><pre>{esc(json.dumps(groups,indent=2,ensure_ascii=False))}</pre>
<h2>Défauts trouvés et corrections</h2><pre>{esc(json.dumps(audit_findings,indent=2,ensure_ascii=False))}</pre>
<h2>Interprétation</h2><p>Le succès exige tous les groupes cachés sur les deux jeux d’entrées et un état final normal. Un échec reste dans les coûts. La contre-vérification utilise le même modèle dans un contexte distinct ; ce n’est pas un oracle. Le juge caché n’a servi à aucune correction.</p>
<p>Deux projets synthétiques, une répétition chacun et dix minutes de budget ne prouvent pas une amélioration générale sur des goals personnels de plusieurs heures. Les références et mutants ont éprouvé le juge avant les appels. Les tours manquants ou partiels interdisent un calcul d’économie complète.</p>
<h2>Protocole figé avant les appels</h2><pre>{esc(json.dumps(m,indent=2,ensure_ascii=False))}</pre><p><a href="report.json">Données JSON</a> · <a href="protocol.json">Protocole original</a></p></html>'''
    (output/'report.html').write_text(page)
    print(json.dumps({k:out[k] for k in ('complete','groups','wins','losses','delivery_improvement_observed','audit_findings')},indent=2,ensure_ascii=False))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();report(a.output)
