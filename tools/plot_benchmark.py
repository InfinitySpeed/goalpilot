"""Create publication figures from validated benchmark rows. Requires Matplotlib."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_benchmark import ROOT, load_and_verify


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    data = load_and_verify()
    totals = data['reviewed']['totals']
    baseline, pilot = totals['native'], totals['new']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'svg.fonttype': 'none', 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.spines.left': False,
                         'axes.labelcolor': '#475569', 'text.color': '#0f172a',
                         'xtick.color': '#334155', 'ytick.color': '#64748b'})
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), gridspec_kw={'width_ratios': [1, 1.25, 1.15]})
    fig.patch.set_facecolor('#ffffff')
    native_color, pilot_color = '#334155', '#0f9f88'
    names = ['Native Codex', 'GoalPilot']

    ax = axes[0]
    values = [baseline['seconds'] / 60, pilot['seconds'] / 60]
    ax.bar(names, values, color=[native_color, pilot_color], width=.55)
    ax.set_ylim(0, max(values) * 1.23)
    ax.set_ylabel('Minutes · all 20 attempts')
    ax.set_title('Total elapsed time', loc='left', fontweight='bold', pad=19)
    for i, value in enumerate(values):
        ax.text(i, value + 1.6, f'{value:.2f}', ha='center', fontweight='bold', fontsize=12)
    ax.text(.98, .95, f"{data['reviewed']['saving_percent']['seconds']:.1f}% less", transform=ax.transAxes,
            ha='right', va='top', color=pilot_color, fontweight='bold')

    ax = axes[1]
    fields = [('cached_input_tokens', 'Cached input', '#cbd5e1'),
              ('uncached_input', 'Uncached input', '#334155'),
              ('output_tokens', 'Output', '#0f9f88')]
    bottom = [0, 0]
    for key, label, color in fields:
        values = [arm['usage'][key] / 1_000_000 for arm in [baseline, pilot]]
        ax.bar(names, values, bottom=bottom, width=.55, label=label, color=color)
        bottom = [a + b for a, b in zip(bottom, values)]
    ax.set_ylim(0, max(bottom) * 1.23)
    ax.set_ylabel('Million raw tokens · cache included')
    ax.set_title('Whole-caller token usage', loc='left', fontweight='bold', pad=19)
    for i, value in enumerate(bottom):
        ax.text(i, value + .1, f'{value:.3f}M', ha='center', fontweight='bold', fontsize=12)
    ax.legend(loc='upper right', frameon=False, fontsize=8)

    ax = axes[2]
    positions = [0, 1]
    original = data['original']['totals']
    for arm, offset, color, label in [('native', -.19, native_color, 'Native Codex'), ('new', .19, pilot_color, 'GoalPilot')]:
        values = [original[arm]['successful'], totals[arm]['successful']]
        ax.bar([x + offset for x in positions], values, width=.34, color=color, label=label)
        for x, value in zip(positions, values):
            ax.text(x + offset, value + .35, f'{value}/20', ha='center', fontsize=9, fontweight='bold')
    ax.set_xticks(positions, ['Initial grader', 'After grader review'])
    ax.set_ylim(0, 24)
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.set_ylabel('Correct and normally closed goals')
    ax.set_title('Successful missions out of 20', loc='left', fontweight='bold', pad=19)
    ax.legend(loc='upper right', frameon=False, fontsize=8, ncol=2)

    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis='y', color='#e2e8f0', linewidth=.7)
        ax.tick_params(axis='both', length=0)
    fig.suptitle('GoalPilot  |  Measured against native Codex', x=.055, y=.98,
                 ha='left', fontsize=21, fontweight='bold')
    fig.text(.055, .89, '20 synthetic Python service missions · full caller cost · gpt-6.1-sol / LOW',
             fontsize=11, color='#64748b')
    fig.text(.055, .07, 'Same 20 attempts per tool, before/after grader review. No model reruns; generated implementations unchanged.',
             fontsize=9, color='#475569')
    fig.text(.055, .025, 'Known synthetic development cases, not a blinded holdout. Extra review time is included. Details: docs/BENCHMARKS.md',
             fontsize=9, color='#64748b')
    fig.subplots_adjust(left=.065, right=.985, bottom=.23, top=.76, wspace=.4)
    target = ROOT / 'docs/assets'
    target.mkdir(parents=True, exist_ok=True)
    for suffix in ['svg', 'png']:
        fig.savefig(target / ('benchmark.' + suffix), dpi=180, facecolor='white',
                    metadata={'Creator': 'GoalPilot benchmark plotting tool'})
    plt.close(fig)
    summary = {key: data[key] for key in ['original', 'reviewed', 'source_matches_measured']}
    (target / 'benchmark-data.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('Generated docs/assets/benchmark.svg, benchmark.png and benchmark-data.json from validated rows.')


if __name__ == '__main__':
    main()
