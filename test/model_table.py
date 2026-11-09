"""Compact per-model table (final full-task passes, first version in parentheses, paired counts) from a stage summary.

    uv run python -m test.model_table --summary test/todomvc_dna/results/summary-samples5.json --arms free dna
    uv run python -m test.model_table --summary artifacts/webbench-dna-seed1/summary.json --arms free free_lib dna

Zero API.  Prints Markdown and LaTeX rows; the paired column counts rows (same model, task[, sample]) passed only by
`dna` / only by the first listed baseline.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

NAMES = {'free': 'Free', 'free_lib': 'Free+Lib', 'dna': 'GUI-DNA', 'dna_unchecked': 'Plan-', 'rule': 'Rule'}
SHORT = {'qwen/qwen3-coder-30b-a3b-instruct': 'Qwen3-Coder-30B-A3B', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral-Small-3.2-24B',
         'google/gemma-3-12b-it': 'Gemma-3-12B', 'deepseek/deepseek-v4-flash': 'DeepSeek-V4-Flash', 'deepseek/deepseek-v4-pro-0813': 'DeepSeek-V4-Pro',
         'openai/gpt-oss-120b': 'GPT-OSS-120B', 'google/gemini-2.5-flash': 'Gemini-2.5-Flash', 'openai/gpt-5-mini': 'GPT-5-mini',
         'anthropic/claude-haiku-4.5': 'Claude-Haiku-4.5', 'openai/gpt-5': 'GPT-5'}


def cell(a):
    return f"{a['final_all']}" + (f" ({a['first_all']})" if a['first_all'] != a['final_all'] else '')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--arms', nargs='+', default=['free', 'dna'])
    args = parser.parse_args()
    s = json.loads(args.summary.read_text())
    baseline, arms = args.arms[0], args.arms
    totals = {a: [0, 0, 0] for a in arms}
    paired_total = [0, 0]
    print('| 模型 | ' + ' | '.join(NAMES[a] for a in arms) + f' | 配对：仅 GUI-DNA / 仅 {NAMES[baseline]} |')
    print('|---|' + '---:|' * len(arms) + '---|')
    tex = []
    for m in s['models']:
        cells, ok = [], True
        for a in arms:
            e = m['arms'].get(a)
            if not e or e['n'] == 0:
                cells.append('--'); ok = False
                continue
            cells.append(cell(e))
            totals[a][0] += e['final_all']; totals[a][1] += e['first_all']; totals[a][2] += e['n']
        pairs = [(r[baseline], r['dna']) for r in m['rows'] if r.get(baseline) and r.get('dna')]
        d_only = sum(d['final_all'] and not f['final_all'] for f, d in pairs)
        b_only = sum(f['final_all'] and not d['final_all'] for f, d in pairs)
        paired_total[0] += d_only; paired_total[1] += b_only
        n = m['arms'][arms[-1]]['n'] if m['arms'].get(arms[-1]) else 0
        print(f"| {SHORT.get(m['model'], m['model'])} (/{n}) | " + ' | '.join(cells) + f' | {d_only} / {b_only} |')
        tex.append(f"{SHORT.get(m['model'], m['model'])} & " + ' & '.join(cells) + f" & {d_only} / {b_only} \\\\")
    tot = ' | '.join(f"{totals[a][0]}/{totals[a][2]}" + (f" ({totals[a][1]})" if totals[a][1] != totals[a][0] else '') for a in arms)
    print(f'| **合计** | {tot} | {paired_total[0]} / {paired_total[1]} |')
    print('\nLaTeX rows:')
    print('\n'.join(tex))
    print('Total & ' + ' & '.join(f"{totals[a][0]}/{totals[a][2]}" + (f" ({totals[a][1]})" if totals[a][1] != totals[a][0] else '') for a in arms) + f" & {paired_total[0]} / {paired_total[1]} \\\\")


if __name__ == '__main__':
    main()
