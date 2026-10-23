"""Plot the current complete-skill results from independently audited provider evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    audited=subprocess.run([sys.executable,str(ROOT/'tools/audit_portable_invocation.py'),
        str(ROOT/'reports/portable-skill-170-2026-10-23.zip'),'--require-promotion'],check=True,capture_output=True,text=True)
    data=json.loads(audited.stdout)
    names=['Native Codex\n(historical)','Previous skill\n(fresh rerun)','GoalPilot 1.7\n(current)']
    rows=[data['historical_controls']['native'],data['primary']['old'],data['primary']['new']]
    colors=['#94a3b8','#334155','#0f9f88']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,
        'text.color':'#0f172a','xtick.color':'#334155','ytick.color':'#64748b'})
    fig,axes=plt.subplots(1,3,figsize=(15,6));fig.patch.set_facecolor('white')
    panels=[('Total elapsed time','Minutes',[r['seconds']/60 for r in rows],lambda v:f'{v:.2f}',None),
        ('Whole-caller raw tokens','Million tokens, including cached input',[r['raw']/1e6 for r in rows],lambda v:f'{v:.3f}M',None),
        ('Verified goal completion','Goals, reviewed behavioral checks',[r['verified_goals']for r in rows],lambda v:f'{v}/20',MaxNLocator(integer=True))]
    for ax,(title,label,values,fmt,locator)in zip(axes,panels):
        bars=ax.bar(names,values,color=colors,width=.6)
        bars[0].set_hatch('//');bars[0].set_edgecolor('#64748b')
        ax.set_title(title,loc='left',fontweight='bold',pad=18);ax.set_ylabel(label)
        ax.set_ylim(0,max(values)*1.22);ax.grid(axis='y',color='#e2e8f0');ax.set_axisbelow(True)
        if locator:
            ax.set_yticks([0,5,10,15,20]);ax.set_ylim(0,24)
        for bar,value in zip(bars,values):
            ax.text(bar.get_x()+bar.get_width()/2,value+max(values)*.025,fmt(value),ha='center',fontweight='bold')
    gain=data['savings_percent']['contemporary_old']
    fig.text(.06,.94,'GoalPilot | Complete-skill benchmark',fontsize=21,fontweight='bold')
    fig.text(.06,.885,'20 familiar synthetic Python service goals · full caller + independent judging · gpt-6.1-sol / LOW',color='#64748b')
    fig.text(.06,.155,f"Vs fresh old skill: {gain['raw']:.2f}% fewer raw tokens · {gain['uncached_plus_output']:.2f}% fewer uncached + output · {gain['seconds']:.2f}% less time",fontweight='bold')
    fig.text(.06,.10,'Previous/current skill runs are interleaved; native is historical. The historical old skill was faster than the new run.',fontsize=9,color='#475569')
    fig.text(.06,.06,'Known development cases, not a blind holdout or exact subscription-quota conversion. Full controls and grading: docs/PORTABLE-ENGINE.md',fontsize=9,color='#64748b')
    fig.subplots_adjust(left=.06,right=.98,top=.77,bottom=.29,wspace=.34)
    target=ROOT/'docs/assets/portable-benchmark'
    for ext in ('png','svg'):fig.savefig(str(target)+'.'+ext,dpi=150,facecolor='white')
    svg=Path(str(target)+'.svg')
    svg.write_text('\n'.join(line.rstrip()for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    receipt={'archive_sha256':hashlib.sha256((ROOT/'reports/portable-skill-170-2026-10-23.zip').read_bytes()).hexdigest(),
        'audit_promotable':data['promotable'],'rows':dict(zip(('native_historical','old_current','new_current'),rows)),
        'live_model_calls':0,'figures':['docs/assets/portable-benchmark.png','docs/assets/portable-benchmark.svg']}
    (target.parent/'portable-benchmark-data.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS: current charts generated from40 audited caller outcomes and frozen historical control;0 model calls.')


if __name__=='__main__':main()
