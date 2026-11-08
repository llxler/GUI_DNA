"""Per-task pass map for Web-Bench dom1 (paper figure).  Zero API.

    uv run --with matplotlib python -m test.webbench_dna.taskmap_figure [--out DNA_latex/figures]

Reads test/webbench_dna/results/summary.json.  One row per (model, method) for Free and GUI-DNA, a final row for
the requirement-blind Rule plan (identical for every model), one column per task; a filled cell means every
official test of that task passed on the final version.  Writes webbench_taskmap.pdf (for LaTeX) and .png (preview).
Only the final version is drawn: first and final differ for a single cell (Gemini-2.5-Flash, Free, task 11).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / 'test/webbench_dna/results/summary.json'
SHORT = {'google/gemma-3-12b-it': 'Gemma-3-12B', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral-Small-3.2-24B',
         'qwen/qwen3-coder-30b-a3b-instruct': 'Qwen3-Coder-30B-A3B', 'openai/gpt-oss-120b': 'GPT-OSS-120B',
         'deepseek/deepseek-v4-flash': 'DeepSeek-V4-Flash', 'openai/gpt-5-mini': 'GPT-5-mini',
         'anthropic/claude-haiku-4.5': 'Claude-Haiku-4.5', 'google/gemini-2.5-flash': 'Gemini-2.5-Flash'}
INK = '#1f2937'          # text
PASS = '#2f5d8a'         # one hue; filled = pass
FAIL_FILL = '#f3f4f6'    # empty = fail
FAIL_EDGE = '#c4c8cf'
LEVEL = {'easy': '#9fb7cf', 'moderate': '#6b8fb3', 'challenging': '#2f5d8a'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'DNA_latex/figures')
    args = parser.parse_args()
    summary = json.loads(SUMMARY.read_text())
    tasks = summary['tasks']
    models = sorted(summary['models'], key=lambda m: (m['arms']['free']['final_all'], m['arms']['dna']['final_all']))
    rows = []   # (label, passes list, group index, is_first_of_group)
    for gi, m in enumerate(models):
        for arm, label in (('free', 'Free'), ('dna', 'GUI-DNA')):
            passes = [bool(r[arm] and r[arm]['final_all']) for r in m['rows']]
            rows.append((SHORT.get(m['model'], m['model']), label, passes, gi))
    rule = [bool(r['rule'] and r['rule']['final_all']) for r in models[0]['rows']]
    rows.append(('Rule (any model)', '', rule, len(models)))

    n_rows, n_cols = len(rows), len(tasks)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 6.5, 'text.color': INK, 'axes.edgecolor': INK})
    fig_w, fig_h = 3.3, 0.135 * n_rows + 0.55
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.subplots_adjust(left=0.40, right=0.90, top=0.86, bottom=0.02)
    gap = 0.14
    for i, (model, arm, passes, gi) in enumerate(rows):
        y = n_rows - 1 - i
        for j, ok in enumerate(passes):
            ax.add_patch(Rectangle((j + gap / 2, y + gap / 2), 1 - gap, 1 - gap, facecolor=PASS if ok else FAIL_FILL,
                                   edgecolor=PASS if ok else FAIL_EDGE, linewidth=0.4, joinstyle='round'))
        ax.text(n_cols + 0.4, y + 0.5, f'{sum(passes)}', va='center', ha='left', fontsize=6, color=INK)
        if arm:
            ax.text(-0.3, y + 0.5, arm, va='center', ha='right', fontsize=6, color=INK)
    # model names centred on their pair of rows; separators between models
    for gi, m in enumerate(models):
        y_top = n_rows - 1 - 2 * gi
        ax.text(-3.0, y_top, SHORT.get(m['model'], m['model']), va='center', ha='right', fontsize=6, color=INK, fontweight='bold')
        if gi > 0:
            ax.plot([-6.5, n_cols + 1.5], [y_top + 1, y_top + 1], color=FAIL_EDGE, linewidth=0.4, clip_on=False)
    ax.text(-3.0, 0.5, 'Rule', va='center', ha='right', fontsize=6, color=INK, fontweight='bold')
    ax.plot([-6.5, n_cols + 1.5], [1, 1], color=FAIL_EDGE, linewidth=0.4, clip_on=False)
    # task numbers and difficulty band
    for j, t in enumerate(tasks):
        ax.text(j + 0.5, n_rows + 0.25, str(j + 1), ha='center', va='bottom', fontsize=5.2, color=INK)
        ax.add_patch(Rectangle((j + gap / 2, n_rows + 1.0), 1 - gap, 0.28, facecolor=LEVEL[t['level']], edgecolor='none'))
    spans = {}
    for j, t in enumerate(tasks):
        spans.setdefault(t['level'], []).append(j)
    for level, js in spans.items():
        runs, start = [], js[0]
        for a, b in zip(js, js[1:] + [None]):
            if b != a + 1:
                runs.append((start, a))
                start = b
        for a, b in runs:
            if b - a >= 1:
                ax.text((a + b + 1) / 2, n_rows + 1.45, level, ha='center', va='bottom', fontsize=5.2, color=INK)
    ax.text(n_cols + 0.4, n_rows + 0.25, '/20', ha='left', va='bottom', fontsize=5.2, color=INK)
    ax.text(-0.3, n_rows + 0.25, 'task', ha='right', va='bottom', fontsize=5.2, color=INK)
    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows + 1.9)
    ax.axis('off')
    args.out.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out / 'webbench_taskmap.pdf')
    fig.savefig(args.out / 'webbench_taskmap.png', dpi=220)
    print('wrote', args.out / 'webbench_taskmap.pdf', 'rows', n_rows)


if __name__ == '__main__':
    main()
