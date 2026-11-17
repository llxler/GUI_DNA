"""Export paper tables directly from the audited summaries (paper stays local)."""
from __future__ import annotations
import json
from .core import ROOT

NAMES = {'openai/gpt-5': 'GPT-5', 'anthropic/claude-sonnet-4.5': 'Sonnet 4.5',
         'openai/gpt-oss-120b': 'GPT-OSS', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral'}


def table(caption, columns, header, rows, label):
    return '\n'.join([r'\begin{table}[ht]', r'\centering\small',
        '\\caption{' + caption + '}', '\\label{' + label + '}',
        r'\setlength{\tabcolsep}{5pt}', '\\begin{tabular}{@{}' + columns + '@{}}',
        r'\toprule', ' & '.join(header) + r' \\', r'\midrule',
        *[' & '.join(map(str, row)) + r' \\' for row in rows],
        r'\bottomrule', r'\end{tabular}', r'\end{table}', ''])


def main():
    summary = json.loads((ROOT / 'test/results/webbench-expand.json').read_text())
    frontier = json.loads((ROOT / 'test/results/webbench-expand-frontier.json').read_text())
    groups = summary['groups']
    parts = []
    rows = [[g['project'], NAMES[g['builder']], NAMES[g['model']], g['free'], g['free_lib'], g['plan'],
             g['fixed_final'], f"{g['vs_free_lib']['wins']}/{g['vs_free_lib']['losses']}"] for g in groups]
    parts.append(table('Three-project expansion, all official task files. Each cell is passes out of 20; plain code is reused across builders. Fixed final reuses the last executable task-20 plan unchanged. W/L compares per-task plans with unrestricted same-library code.',
        'lllrrrrr', ['Project', 'Builder', 'Planner', 'Code', 'Code + library', 'Plan', 'Fixed final', 'W/L'], rows, 'tab:expansion'))
    rows = []
    for lib in summary['libraries']:
        g = next(g for g in groups if g['project'] == lib['project'] and g['builder'] == lib['builder'])
        rows.append([lib['project'], NAMES[lib['builder']], lib['files'], lib['source_bytes'], lib['compiler_bytes'],
                     lib['attempts'], g['example-0'], g['example-1']])
    parts.append(table('Frozen library sizes, observed builder attempts, and both unchanged documentation examples. Example counts are out of 20. Implementation can reside inside the compiler; file-map size alone understates library size.',
        'llrrrrrr', ['Project', 'Builder', 'Files', 'File bytes', 'Compiler bytes', 'Attempts', 'Ex. 0', 'Ex. 1'], rows, 'tab:expansion-libraries'))
    rows = []
    for project in summary['projects']:
        selected = [g['predefined_sensitivity'] for g in groups if g['project'] == project]
        n = sum(g['n'] for g in selected)
        rows.append([project, n, sum(g['free_lib'] for g in selected), sum(g['plan'] for g in selected),
                     sum(g['plan_wins_vs_free_lib'] for g in selected), sum(g['plan_losses_vs_free_lib'] for g in selected)])
    parts.append(table('Prespecified sensitivity analysis: omit only BOM tasks 7, 14 and 19 identified in reference-only calibration. Counts pool two builders and two planners, not independent applications.',
        'lrrrrr', ['Project', 'Paired candidates', 'Code + library', 'Plan', 'Plan wins', 'Plan losses'], rows, 'tab:expansion-sensitivity'))
    rows = [[g['project'], NAMES[g['builder']], g['free_lib'], g['plan'], g['fixed_final'], g['example-0'], g['example-1'],
             f"{g['plan_wins_vs_code']}/{g['plan_losses_vs_code']}"] for g in frontier['groups']]
    parts.append(table('Separate GPT-5 medium-reasoning pilot. Every cell has five prespecified milestones (4, 8, 12, 16, 20). Libraries, inputs, 12,000-token cap and repair allowance match; these scores are not pooled with the 600-candidate cohort. W/L compares plans with code.',
        'llrrrrrr', ['Project', 'Builder', 'Code + library', 'Plan', 'Fixed final', 'Ex. 0', 'Ex. 1', 'W/L'], rows, 'tab:expansion-frontier'))
    target = ROOT / 'DNA_latex/webbench_expansion_tables.tex'
    target.write_text('\n'.join(parts))
    print(target)


if __name__ == '__main__':
    main()
