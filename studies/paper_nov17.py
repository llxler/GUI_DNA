"""Generate and verify the local draw appendix from reconstructed observations."""
from __future__ import annotations
import argparse
from pathlib import Path
from test.history_replay.run import ROOT, read, dump, sha
from test.paper_cells import table_rows, numbers

PAPER=ROOT/'DNA_latex'
MODELS=('openai/gpt-oss-120b','openai/gpt-5')
BUILDERS=('openai/gpt-5','anthropic/claude-sonnet-4.5')
NAMES={'openai/gpt-oss-120b':'GPT-OSS-120B','openai/gpt-5':'GPT-5',
       'anthropic/claude-sonnet-4.5':'Sonnet 4.5',None:'None'}


def cells(data):
    result=[]
    for model in MODELS:
        for builder in [None,*BUILDERS]:
            row=[NAMES[model],NAMES[builder]]
            for endpoint in ('current','history'):
                for method in ('free_lib','plan'):
                    if builder is None and method=='plan':
                        row.append(None)
                        continue
                    name='free' if builder is None else method
                    selected=[g for g in data['groups'] if g['model']==model and g['builder']==builder
                        and g['method']==name and g['label']=='final' and g['endpoint']==endpoint]
                    assert len(selected)==1 and selected[0]['status']=='complete'
                    row.append((selected[0]['passed'],selected[0]['total']))
            result.append(row)
    return result


def appendix(data):
    rows=[]
    for row in cells(data):
        rendered=[str(value) if i<2 else ('--' if value is None else f'{value[0]}/{value[1]}') for i,value in enumerate(row)]
        rows.append(' & '.join(rendered)+r' \\')
    costs=data['costs']
    text=r'''\section{A Public Graphics Project: Web-Bench Draw}
\label{app:draw}

\paragraph{Selection and protocol.}
We add the public \texttt{draw} project to cover SVG drawing, move/rotate/zoom
and touch interactions. Selection uses these public requirements and absence
of external assets, not model scores; it remains a convenience sample.
The project requires SCSS, so every method, reference and control uses the same
fixed Vite 7.1.5 server with sass-embedded 1.83.1, Playwright 1.57.0 and Chromium.
The unchanged final reference passes all 21 official files and 70 tests before
paid generation; blank pages fail each of the five selected current files.
This runtime is a separate protocol from the earlier static-server cohort.

GPT-5 medium and Claude Sonnet 4.5 each receive only all public requirement
descriptions and propose a library, closed data schema, compiler and two
documentation examples. Neither sees tests, reference code, supplied slots
or an application shell. Both packages pass format, deterministic compilation
and generic load checks on their first response; these checks do not verify
behavior. The construction ceiling is 26,000 output tokens.

GPT-OSS-120B low and GPT-5 medium then independently implement cumulative
prefixes through tasks 4, 8, 12, 16 and 20. Each produces five no-library pages
and, per library, five plans and five same-library programs: 50 candidates.
Both same-library arms receive byte-identical user messages. Code may invoke
the entire frozen compiler through unrestricted \code{build(files,compile)},
change its output or replace it. Every arm has a 12,000-token output ceiling
and at most two format/load repairs, with no behavior feedback.
All generation finishes before candidate scoring. First and final refer to
raw first and last responses, including invalid output; earlier executable
versions are not substituted. There are no missing transport observations.

\begin{table}[h]
\centering
\caption{Draw final passes on five fixed milestones per library and generator.
Code without a library appears once per generator. Current tests and full
history are distinct endpoints; first-response counts are identical here.}
\label{tab:draw}
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}llrrrr@{}}
\toprule
& & \multicolumn{2}{c}{Current} & \multicolumn{2}{c}{Full history} \\
\cmidrule(lr){3-4}\cmidrule(lr){5-6}
Generator & Library builder & Code & Plan & Code & Plan \\
\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule
\end{tabular}
\end{table}

Plans and same-library code agree on all 20 current-file pairs (14 passes
each). Full history yields two plan and three code passes; the only discordant
pair is GPT-5 using the Sonnet library at task 4, which code passes.
No-library code passes 3/10 current files and 2/10 histories. These correlated
milestones are one additional application, not independent project replications.

\paragraph{Fixed pages and the proposed interface.}
The final-task plan page, reused unchanged at all five milestones, matches
every task-specific plan outcome across both endpoints (40/40 comparisons).
The two GPT-5 library examples each pass 4/5 current files and 1/5 histories.
Sonnet's examples pass 3/5 and 1/5 current files, with neither passing a full
history. These controls are fixed before scores are read, not selected for
success. Overall, 280 first/final/control comparisons reuse 124 distinct
source-and-test reports, with exact source recompilation checked separately.

The GPT-5 builder exposes only \code{theme} and \code{labelSize}; its compiler
copies the interaction JavaScript unchanged. A post-hoc byte audit exhausts
all 162 schema-valid configurations, including omitted fields: there are 106
different complete source maps, two HTML variants and 53 SCSS variants, but
one version each of \code{index.js} and \code{app.js}. This is a styling interface,
not evidence of learned behavior decomposition. HTML/CSS may still change
interaction geometry, so this audit does not establish behavioral equivalence
or a full-history reachability bound. The Sonnet interface instead exposes
11 fields, including tool defaults, geometry thresholds and interaction flags.

\paragraph{Actual computation and interpretation.}
The 62 billed calls comprise two construction calls, 26 GPT-OSS calls and
34 GPT-5 calls. Ten GPT-5 code responses terminate at the length ceiling
(seven without a library and three with one); all remain in the evidence.
GPT-5 code chains use 128,782 completion tokens with the library, including
58,112 reasoning tokens, versus 17,070 and 16,192 for plans.
The corresponding receipt charges are \$1.42088125 and \$0.279097;
the two library constructions cost \$0.33819325 together.
'''+f"All new receipt charges total \\${data['provider_billed_usd']:.8f}; the conservative\nledger totals \\${costs['settled_usd']:.6f} after rounding each call upward to microdollars.\n"+r'''
All three ledgers are closed with no unknown reservations. Human time and
local browser compute are unpriced. Short plans reduce generation cost in
this setting, while fixed controls and the thin GPT-5 interface prevent
attributing the functional gains to per-task planning. Full prompts, raw
streams, packages, control pages and report hashes are retained.
'''
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    source=ROOT/'test/results/webbench-draw-20261117.json'
    data=read(source)
    target=PAPER/'nov17_draw.tex'
    if args.write:
        target.write_text(appendix(data))
    expected=cells(data)
    actual=[row for row in table_rows(target,'tab:draw') if row[0].strip() in ('GPT-OSS-120B','GPT-5')]
    assert len(actual)==len(expected)
    checks=[]
    for a,e in zip(actual,expected):
        assert a[0].strip()==e[0] and a[1].strip()==e[1]
        for column in range(2,6):
            observed=numbers(a[column])
            wanted=list(e[column]) if e[column] else []
            assert observed==wanted,(e[:2],column,observed,wanted)
            checks.append({'row':e[:2],'column':column,'observed':observed,'expected':wanted})
    assert data['method_totals']['first']==data['method_totals']['final']
    assert data['fixed_final_agreement']=={'same':40,'total':40}
    audit=read(ROOT/'test/results/draw-interface-audit-20261117.json')
    assert audit['legal_configurations']==162 and audit['distinct_source_maps']==106 and audit['all_javascript_unchanged']
    bom=read(ROOT/'test/results/assertion-audit-20261117.json')
    main_text=(PAPER/'main.tex').read_text()
    assert 'fig:failure-case' not in main_text
    assert bom['six_file_sensitivity']['methods']=={'plan':{'passed':79,'total':216},'free_lib':{'passed':78,'total':216},'free':{'passed':39,'total':108}}
    assert '79/216' in main_text and '78/216' in main_text
    dump(ROOT/'test/results/paper-nov17-audit.json',{'all_passed':True,
        'table':'tab:draw','cells':checks,'specified_cells':len(checks),
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
            (source,ROOT/'test/results/draw-interface-audit-20261117.json',ROOT/'test/results/assertion-audit-20261117.json')},
        'manuscript_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
            (target,PAPER/'main.tex',PAPER/'public_feedback_audits.tex')},
        'scope':'New draw table, fixed-page agreement, interface byte counts and selected BOM sensitivity claims; not exhaustive manuscript review.'})
    print(f'Checked {len(checks)} specified cells in tab:draw')


if __name__=='__main__':
    main()
