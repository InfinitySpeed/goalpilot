"""Render only recomputed, whole-caller measurements for the generalized release."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit_generalization import analyze

ROOT=Path(__file__).resolve().parents[1]

def main():
    report=ROOT/'reports/native-generalization-2026-10-23.json'
    data=analyze(report);assert data['promotable']
    names=['Native Codex','GoalPilot r2','GoalPilot 1.8'];arms=['native','old','new']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(12,4.5));fig.patch.set_facecolor('white')
    for ax,(key,title,unit,scale)in zip(axes,[('raw_tokens','Raw tokens','Thousands, including cached input',1000),('uncached_plus_output','Uncached input + output','Thousands of tokens',1000),('seconds','Elapsed caller time','Minutes',60)]):
        values=[data['scores'][a][key]/scale for a in arms]
        bars=ax.bar(names,values,color=['#94a3b8','#334155','#0f9f88'],width=.6)
        ax.set_title(title,loc='left',fontweight='bold');ax.set_ylabel(unit);ax.set_ylim(0,max(values)*1.25);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);ax.tick_params(axis='x',labelsize=8)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+max(values)*.03,f'{value:.2f}',ha='center',fontweight='bold')
    gain=data['savings_vs_native_percent']
    fig.text(.06,.94,'GoalPilot | Generalized skill benchmark',fontsize=17,fontweight='bold')
    fig.text(.06,.88,'8 synthetic goals / 5 stacks | full caller | gpt-6.1-sol / LOW',fontsize=10,color='#475569')
    fig.text(.06,.115,f"Vs native: {gain['raw_tokens']:.1f}% fewer raw tokens | {gain['uncached_plus_output']:.1f}% fewer uncached + output | {gain['seconds']:.1f}% less time",fontweight='bold')
    fig.text(.06,.055,'Known development cases; sequential reused controls; not a subscription-quota conversion. Details: docs/GENERALIZATION.md',fontsize=8,color='#475569')
    fig.subplots_adjust(left=.065,right=.98,top=.75,bottom=.27,wspace=.4)
    target=ROOT/'docs/assets/portable-benchmark'
    for ext in('png','svg'):fig.savefig(str(target)+'.'+ext,dpi=100,facecolor='white')
    svg=Path(str(target)+'.svg');svg.write_text(chr(10).join(line.rstrip()for line in svg.read_text().splitlines())+chr(10))
    plt.close(fig)
    (target.parent/'portable-benchmark-data.json').write_text(json.dumps(data,indent=2)+'\n')
    print('PASS: chart recomputed from24 retained caller outcomes;0 model calls.')

if __name__=='__main__':main()
