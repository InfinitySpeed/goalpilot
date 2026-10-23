"""Render the current four-goal comparison from source-bound provider evidence."""
import hashlib,json
from pathlib import Path
from audit_skill190 import analyze
ROOT=Path(__file__).resolve().parents[1]
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 p=ROOT/'reports/skill-190-2026-10-23.json';result=analyze(p);assert result['promotable'];scores=result['summary']['totals']
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(1,3,figsize=(12.6,4.2));labels=['Codex','GoalPilot 1.8','GoalPilot 1.9'];colors=['#94a3b8','#475569','#0f9f88']
 for ax,(key,title,scale,unit)in zip(axes,[('raw_tokens','Raw tokens (cached input included)',1000,'thousand'),('uncached_tokens','Uncached input + output',1000,'thousand'),('seconds','Whole-caller time',1,'seconds')]):
  vals=[scores[a][key]/scale for a in ('native','previous','current')];bars=ax.bar(labels,vals,color=colors,width=.6)
  ax.set_title(title,fontsize=11);ax.set_ylabel(unit);ax.set_ylim(0,max(vals)*1.22);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
  for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+max(vals)*.025,f'{v:.1f}',ha='center',fontsize=10)
 fig.suptitle('GoalPilot 1.9 — 4/4 independent behavioral checks in every arm',fontsize=14,fontweight='bold')
 fig.text(.5,.025,'Four known synthetic goals; Java/Python controls reused. Codex live only. One observation per task and arm; no universal or subscription-quota guarantee.',ha='center',fontsize=8,color='#475569')
 fig.tight_layout(rect=[0,.09,1,.91]);target=ROOT/'docs/assets/skill-190-benchmark';fig.savefig(str(target)+'.png',dpi=170);fig.savefig(str(target)+'.svg')
 target.with_suffix('.json').write_text(json.dumps({'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'totals':scores},indent=2)+'\n')
 print(str(target)+'.png')
if __name__=='__main__':main()
