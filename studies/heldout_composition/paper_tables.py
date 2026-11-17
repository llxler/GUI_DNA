"""Export local-paper tables from the separately audited synthetic study."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'openai/gpt-5': 'GPT-5', 'anthropic/claude-sonnet-4.5': 'Sonnet 4.5',
         'openai/gpt-oss-120b': 'GPT-OSS', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral'}


def main():
    s = json.loads((ROOT / 'test/results/heldout-composition.json').read_text())
    groups = s['cohorts']['main']['groups']
    main_rows = []
    for project in ('calculator', 'table'):
        for model in ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct'):
            gs = [g for g in groups if g['project'] == project and g['model'] == model]
            assert len(gs) == 2 and gs[0]['free'] == gs[1]['free']
            main_rows.append(f"{project.title()} & {NAMES[model]} & {gs[0]['free']}/11 & {sum(g['free_lib'] for g in gs)}/22 & {sum(g['plan'] for g in gs)}/22 & {sum(g['delta'] for g in gs)}/22 " + r'\\')
    out = ROOT / 'DNA_latex'
    out.mkdir(exist_ok=True)
    header = r"""\begin{table}[t]
\centering\small
\setlength{\tabcolsep}{3pt}
\caption{Unseen synthetic combinations, not official Web-Bench. Code and plans pool two builders; no-library code is counted once. Delta uses no model and is reused across the two generator rows.}
\label{tab:heldout-main}
\begin{tabular}{@{}llrrrr@{}}
\toprule
Application & Generator & No lib. & Code+lib. & Plan & Delta \\
\midrule
"""
    footer = r"""\bottomrule\end{tabular}
\end{table}
"""
    (out / 'heldout_main_table.tex').write_text(header + '\n'.join(main_rows) + '\n' + footer)
    lines = [r'\begin{table*}[t]', r'\centering\small',
             r'\caption{Synthetic held-out combinations, separated by library builder and generator. Every denominator is 11. Development-example controls each score 0/11 per library. Delta is a deterministic composition of development-plan differences, reused across generators.}',
             r'\label{tab:heldout-full}', r'\begin{tabular}{@{}lllrrrrr@{}}', r'\toprule',
             r'Application & Builder & Generator & No library & Same-library code & Plan & Delta & Fixed final \\', r'\midrule']
    for g in groups:
        lines.append(f"{g['project']} & {NAMES[g['builder']]} & {NAMES[g['model']]} & {g['free']} & {g['free_lib']} & {g['plan']} & {g['delta']} & {g['fixed_final']} " + r'\\')
    lines += [r'\bottomrule\end{tabular}', r'\end{table*}', '', r'\begin{table*}[t]', r'\centering\small',
              r'\caption{Adopted response usage for the synthetic study. Output tokens include reasoning. These costs exclude unresolved transport reservations; the ledger totals are reported in the text.}',
              r'\label{tab:heldout-usage}', r'\begin{tabular}{@{}lrrrr@{}}', r'\toprule',
              r'Purpose & Input tokens & Output tokens & Reasoning tokens & USD \\', r'\midrule']
    for prefix, name in [('build', 'Library construction'), ('main/free', 'Main: no library'), ('main/free_lib', 'Main: same-library code'), ('main/plan', 'Main: plans'), ('strong/free_lib', 'GPT-5: same-library code'), ('strong/plan', 'GPT-5: plans')]:
        u = s['usage']
        lines.append(f"{name} & {u[prefix+'/prompt_tokens']:,} & {u[prefix+'/completion_tokens']:,} & {u[prefix+'/reasoning_tokens']:,} & {u[prefix+'/cost']:.6f} " + r'\\')
    lines += [r'\bottomrule\end{tabular}', r'\end{table*}', '']
    (out / 'heldout_tables.tex').write_text('\n'.join(lines))
    print('Wrote heldout_main_table.tex and heldout_tables.tex')


if __name__ == '__main__':
    main()
