"""Draw matched-prefix endpoint outcomes from the audited final-candidate table."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = json.loads((ROOT / 'test/results/prefix-factorial.json').read_text())
    assert result['audit']['generation_before_hidden_grading']
    keys = [(model, prefix, method)
            for model in ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct')
            for prefix in ('self', 'reference') for method in ('free_lib', 'plan')]
    index = {(r['model'], r['prefix'], r['method'], r['scope'], r['k']): r['passed']
             for r in result['rows'] if r['label'] == 'final'}
    labels = [f"{'GPT-OSS' if 'gpt-oss' in m else 'Mistral'} / {p.title()} / {'Code' if f == 'free_lib' else 'Plan'}"
              for m, p, f in keys]
    plt.rcParams.update({'font.size': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42})
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.4), layout='constrained')
    colors = ['#e3e6e9', '#2166ac']
    for ax, scope, title in zip(axes, ('current', 'history'), ('Current task file', 'Initial layout + all task files through k')):
        values = [[int(index[m, p, f, scope, k]) for k in range(1, 21)] for m, p, f in keys]
        ax.imshow(values, cmap=ListedColormap(colors), vmin=0, vmax=1, aspect='auto', interpolation='nearest')
        ax.set_yticks(range(8), [f'{label} ({sum(row)}/20)' for label, row in zip(labels, values)])
        ax.set_xticks(range(20), range(1, 21))
        ax.set_xlabel('Task k')
        ax.set_title(title, fontsize=10, pad=10)
        ax.set_xticks([k - .5 for k in range(21)], minor=True)
        ax.set_yticks([k - .5 for k in range(9)], minor=True)
        ax.grid(which='minor', color='white', linewidth=1)
        ax.tick_params(which='minor', bottom=False, left=False)
        ax.tick_params(axis='both', length=0)
        ax.axhline(3.5, color='#555555', linewidth=1)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.legend(handles=[Patch(facecolor=colors[1], label='All selected assertions pass'),
                        Patch(facecolor=colors[0], label='At least one failure / no executable output')],
               loc='outside lower center', ncol=2, frameon=False)
    target = ROOT / 'DNA_latex/figures'
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / 'matched_prefix_endpoints.pdf', bbox_inches='tight')
    preview = ROOT / 'artifacts/review-20261114/matched_prefix_endpoints.png'
    fig.savefig(preview, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(target / 'matched_prefix_endpoints.pdf')


if __name__ == '__main__':
    main()
