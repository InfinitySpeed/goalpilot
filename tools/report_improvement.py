"""Keep the negative prototype and controlled recovery study in one honest report."""
import hashlib
import html
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
from goalpilot import __version__
from goalpilot.rpc import normalize_usage

ROOT=Path(__file__).resolve().parents[1]


def audit_usage(root):
    findings=[];totals={};models=set();suspect=[]
    for trial in sorted((root/'trials').iterdir()):
        for path in sorted((trial/'run/calls').glob('*/events.jsonl'),key=lambda p:int(p.parent.name)):
            snapshots=[];commands=[]
            for line in path.open():
                event=json.loads(line);p=event['packet']
                if p.get('method')=='thread/tokenUsage/updated':
                    snapshots.append((p['params']['threadId'],normalize_usage(p['params']['tokenUsage']['total'])))
                if p.get('method')=='item/completed' and p['params']['item']['type']=='commandExecution':commands.append(p['params']['item'].get('command',''))
            for command in commands:
                if any(x in command for x in ('evaluation/finish/judge','evaluation/recovery/judge','evaluation/recovery/reference','evaluation/finish/reference')):
                    suspect.append({'trial':trial.name,'call':path.parent.name,'marker':'possible hidden evaluator path in command'})
            actual=None
            if snapshots:
                thread,last=snapshots[-1];base=totals.get(thread,dict.fromkeys(last,0))
                actual={k:last[k]-base[k] for k in last};totals[thread]=last
            record=json.loads((trial/'record.json').read_text());index=int(path.parent.name)-1
            result=record['calls'][index].get('result',{})
            model=((result.get('telemetry') or {}).get('model') or {}).get('model')
            if model:models.add(model)
            usage=result.get('usage')
            findings.append({'trial':trial.name,'call':index+1,'usage_present':usage is not None,
                'raw_counter_matches':usage==actual if usage is not None else None,
                'usage_complete':result.get('usage_complete'),'model':model})
    return {'calls':findings,'known_usage_matches_raw_events':all(x['raw_counter_matches'] is not False for x in findings),
            'observed_models':sorted(models),'possible_hidden_source_command_markers':suspect,
            'limits':'Command markers are not a complete filesystem access audit. Missing streamed usage remains unknown, not zero.'}


def build():
    old=json.loads((ROOT/'reports/finish-live-001/report.json').read_text())
    root=ROOT/'reports/recovery-live-001';m=json.loads((root/'protocol.json').read_text())
    records=[json.loads(p.read_text()) for mode in m['order'] if (p:=root/'trials'/mode/'record.json').exists()]
    complete=len(records)==2
    advantage=complete and all(r['fault_triggered'] and not r['fatal'] for r in records) and records[1]['autonomous_success'] and not records[0]['autonomous_success']
    snapshot_ok=all(hashlib.sha256((root/'source_snapshot'/name).read_bytes()).hexdigest()==sha for name,sha in m['source_fingerprint'].items())
    details=[]
    for r in records:
        p=root/'trials'/r['mode']/'run/state.json'
        if p.exists():
            s=json.loads(p.read_text());first=s['verifications'][0]['checks'];last=s['verifications'][-1]['checks']
            details.append({'mode':r['mode'],'independent_requirements':len(first),'initial_failed':[x['id'] for x in first if not x['passed']],
                'final_failed':[x['id'] for x in last if not x['passed']],'blockers':s['contract'].get('unverified',[]),
                'limitations':s['contract']['limitations'],'strategies':[x['strategy'] for x in s['calls']]})
    tests=json.loads((ROOT/'reports/tests.json').read_text())
    out={'product_version':__version__,'adaptive_replay':json.loads((ROOT/'reports/adaptive-replay-001/report.json').read_text()),'offline_tests':tests,'cross_audit':json.loads((ROOT/'reports/cross-audit-001/report.json').read_text()),'normal_prototype_study':old,
        'recovery_study':{'complete':complete,'conditional_completion_advantage':advantage,
            'protocol':m,'source_snapshot_integrity':snapshot_ok,'details':details,'records':records},
        'limits':['The 0.3.0 normal prototype failed to conclude both goals although all artifacts were correct. This failure informed the 0.3.1 fix; those tasks are no longer held out.',
            'Recovery uses one fresh task and an injected timeout, not the frequency of natural stalls.',
            'Artifact correctness and normal mission completion are reported separately; the baseline may produce correct code before being interrupted.',
            'No general goal-success, multi-hour, user-satisfaction or exact subscription-quota advantage is established.']}
    if complete:
        out['raw_event_audit']={'normal':audit_usage(ROOT/'reports/finish-live-001'),'recovery':audit_usage(root)}
        advantage &= all(x['known_usage_matches_raw_events'] and x['observed_models']==['gpt-6.1-sol'] for x in out['raw_event_audit'].values())
        out['recovery_study']['conditional_completion_advantage']=advantage
    atomic_json(ROOT/'reports/improvement.json',out)
    esc=lambda v:html.escape(str(v))
    rows=''.join(f'<tr><td>{esc(r["mode"])}</td><td>{esc(r["status"])}</td><td>{sum(c["passed"] for c in r["checks"])}/{len(r["checks"])}</td><td>{"oui" if r["autonomous_success"] else "non"}</td><td>{r["seconds"]:.3f}</td><td>{len(r["calls"])}</td></tr>' for r in records)
    phrase='Clôture autonome obtenue après coupure : 1/1 contre 0/1.' if advantage else 'Essai de récupération incomplet ou critère de clôture non atteint.'
    page=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GoalPilot 0.3.2 — amélioration et preuves</title>
<style>body{{max-width:1000px;margin:0 auto;padding:40px 20px;background:#0d1725;color:#e7eef7;font:16px/1.6 system-ui}}h1{{font-size:36px;line-height:1.2}}p{{color:#bdcddd}}a{{color:#7cdec4}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #33435a}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;padding:20px;background:#19273a;border-radius:12px}}.scroll{{overflow:auto}}</style>
<h1>GoalPilot : mieux vérifier et savoir conclure</h1><p>{phrase} L’interruption est provoquée à 45 secondes sur un seul projet inédit ; elle ne mesure pas un taux général de réussite.</p>
<h2>Ce qui change</h2><p>La version finale 0.3.2 utilise un mode adaptatif : un premier rapport exploitable est vérifié localement, sans contrôle supplémentaire. Une interruption/absence de rapport déclenche la branche de contre-vérification et de reprise. --thorough impose le contrôle systématique. Le routage final a été rejoué hors ligne sur les sorties réelles des trois projets, sans API ; la récupération contrôlée ci-dessous a été testée en réel sur 0.3.1. Aucune nouvelle efficacité générale n’est attribuée à ce rejeu.</p><p>Réalisation, contrôle dans un contexte séparé, scénarios exécutables gelés hors du dépôt, correction dans le budget restant. Copie bornée des fichiers initiaux pour vérifier les données, reprise sans message final, budget persistant et suivi de la phase active. Les véritables exigences bloquées restent distinctes des limites générales de preuve.</p>
<h2>Essai réel de récupération</h2><div class="scroll"><table><tr><th>Version</th><th>Statut</th><th>Groupes cachés</th><th>Mission conclue</th><th>Secondes</th><th>Appels</th></tr>{rows}</table></div>
<p>La correction du code et la clôture du goal sont distinctes : un code déjà correct avant la coupure n’est pas un gain de qualité attribuable au superviseur. Tous les appels et délais sont comptés. Les consommations interrompues restent incomplètes ; aucune économie de quota n’est calculée.</p>
<pre>{esc(json.dumps(details,ensure_ascii=False,indent=2))}</pre>
<h2>L’échec conservé du premier prototype</h2><p>Sur deux autres projets inédits, tous les livrables des deux versions passent le juge caché. Le prototype 0.3.0 conclut pourtant 0/2 missions, contre 2/2 pour l’ancienne boucle : il traite des réserves comme « toutes les pannes futures ne sont pas prouvées » comme des exigences bloquantes. Il prend 519,466 s contre 269,374 s et rapporte 259 333 tokens contre 204 591. La version 0.3.1 corrige cette règle et conserve des originaux. Ce résultat négatif n’a pas été effacé ni reclassé après coup.</p>
<p><a href="finish-live-001/report.html">Campagne négative complète</a> · <a href="recovery-live-001/protocol.json">Protocole de récupération</a> · <a href="improvement.json">Toutes les données et audits</a></p>
<h2>Vérification croisée sans API</h2><p>Les 21 probes déjà générés ont été appliqués aux anciens livrables sur des copies. Vingt passent ; un dépend d’une signature de fonction privée et ne constitue pas un défaut confirmé. Aucun défaut supplémentaire confirmé. La consigne finale exige les interfaces publiques du contrat d’origine. Ce renforcement de consigne seul n’a pas fait l’objet d’un nouvel appel réel ; les sources exactes des essais restent gelées.</p><h2>Validation locale</h2><p>{tests['passed']}/{tests['tests_run']} tests réussis en {tests['duration_seconds']:.3f} s, sans API. Ces tests de mécanismes utilisent des doubles explicites et ne prouvent pas seuls l’utilité d’un modèle réel.</p>
<h2>Limites</h2><pre>{esc(json.dumps(out['limits'],ensure_ascii=False,indent=2))}</pre><p>Le vérificateur est le même modèle dans un contexte distinct : ses erreurs peuvent rester corrélées. Le juge caché n’a servi à aucune correction. Les empreintes contrôlent les fichiers gelés ; elles n’isolent pas l’exécution des probes.</p></html>'''
    (ROOT/'reports/improvement.html').write_text(page)
    print(json.dumps({'complete':complete,'advantage':advantage,'details':details,'records':[{k:r[k] for k in ('mode','status','seconds','fault_triggered','autonomous_success','artifact_success','usage')} for r in records]},ensure_ascii=False,indent=2))
    return out


if __name__=='__main__':build()
