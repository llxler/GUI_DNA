"""Compare selected literal manuscript cells with reconstructed source counts.

The manuscript remains local. This is an explicitly bounded transcription
audit, not a claim that all tables, prose, citations or rounding were checked.
"""
import argparse
from pathlib import Path
import re
from test.history_replay.run import ROOT, read, dump, sha
from test.paper_replay_coverage import table_inventory

PAPER=ROOT/'DNA_latex'


def table_rows(path,label):
    text=path.read_text()
    tables=re.findall(r'\\begin\{table\*?\}.*?\\end\{table\*?\}',text,re.S)
    selected=[t for t in tables if '\\label{'+label+'}' in t]
    assert len(selected)==1,label
    return [line.split('&') for line in selected[0].splitlines() if '&' in line and line.rstrip().endswith('\\\\')]


def numbers(cell):
    return list(map(int,re.findall(r'\d+',cell.replace('{,}','').replace(',',''))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'test/results/paper-cell-audit.json')
    args = parser.parse_args()
    included_sources, inventory = table_inventory()
    active_tables = {row['id']: ROOT/row['file'] for row in inventory}
    checks=[];sources=set();manuscripts={ROOT/name for name in included_sources}
    def load(name):
        path=ROOT/name;sources.add(path);return read(path)
    def rows(label):
        path=active_tables[label]
        manuscripts.add(path)
        return table_rows(path,label)
    def check(table,row,column,cell,expected):
        observed=numbers(cell)
        assert observed==list(expected),(table,row,column,observed,expected)
        checks.append({'table':table,'row':row,'column':column,'observed':observed,'expected':list(expected)})
    if 'tab:draw' in active_tables:
        from test.paper_nov17 import cells as draw_cells
        expected = draw_cells(load('test/results/webbench-draw-20261117.json'))
        actual = [row for row in rows('tab:draw') if row[0].strip() in ('GPT-OSS-120B','GPT-5')]
        assert len(actual) == len(expected)
        for observed,wanted in zip(actual,expected):
            assert observed[0].strip() == wanted[0] and observed[1].strip() == wanted[1]
            for column in range(2,6):
                check('tab:draw','/'.join(wanted[:2]),str(column),observed[column],wanted[column] or [])
    primary=load('test/results/primary-replay.json')
    mainrows=rows('tab:main')
    for suite,macro in [('todomvc',r'\todomvc'),('webbench',r'\webbench')]:
        summary=next(s for s in primary['suites'] if s['suite']==suite)
        line=next(r for r in mainrows if r[0].strip().startswith(macro))
        for col,method in enumerate(('free','free_lib','dna_unchecked','dna'),2):
            value=summary['primary'][method];check('tab:main',suite,method,line[col],[value['final_all'],value['n']])
        value=summary['rule_not_repeated_across_models'];check('tab:main',suite,'rule',line[6],[value['final_all'],value['n']])
        saved=load(f'test/{suite}_dna/results/summary.json')
        pairs=[r for m in saved['models'] if m['model'] in summary['primary_models'] for r in m['rows'] if r.get('free') and r.get('dna')]
        wins=sum(r['dna']['final_all'] and not r['free']['final_all'] for r in pairs)
        losses=sum(r['free']['final_all'] and not r['dna']['final_all'] for r in pairs)
        check('tab:main',suite,'paired-only',line[7],[wins,losses])
    legacy_rows=[r for r in mainrows if r[0].strip().startswith(r'\listsuite')]
    if legacy_rows:
        scale=load('test/results/scale-table-replay.json')
        for col,method in enumerate(('linked_js','dna','plan_unchecked','plan_checked'),2):
            selected=[r for r in scale['summary'] if r['method']==method]
            check('tab:main','List-16',method,legacy_rows[0][col],[sum(r['passed'] for r in selected),sum(r['n'] for r in selected)])
    new=load('test/results/new-tables-replay.json')
    expansion=next(t for t in new['tables'] if t['name']=='webbench_expand')['groups']
    interface_rows=[r for r in rows('tab:interface-main') if r[0].strip().startswith(r'\texttt')]
    for row in interface_rows:
        project=re.search(r'\\texttt\{([^}]+)\}',row[0]).group(1)
        model='openai/gpt-oss-120b' if 'GPT-OSS' in row[1] else 'mistralai/mistral-small-3.2-24b-instruct'
        chosen=[g for g in expansion if g['project']==project and g['model']==model]
        for col,method in ((2,'free_lib'),(3,'plan')):
            check('tab:interface-main',project+'/'+model,method,row[col],[sum(g[method] for g in chosen),sum(g['n'] for g in chosen)])
    history=load('test/results/history-replay.json')['rows']
    history_rows=[r for r in rows('tab:history-main') if '/' in r[1]]
    cohorts=[('expert','free_lib'),('expert','dna'),('interface','free_lib'),('interface','plan'),
             ('expansion','free_lib'),('expansion','plan'),('expansion','control/final-plan')]
    assert len(history_rows)==len(cohorts)
    for row,(cohort,method) in zip(history_rows,cohorts):
        selected=[r for r in history if r['cohort']==cohort and r['method']==method and r['label']=='final']
        old=sum(r['old_current_passed'] for r in selected) if method!='control/final-plan' else sum(g['fixed_final'] for g in expansion)
        check('tab:history-main',cohort+'/'+method,'current',row[1],[old,len(selected)])
        check('tab:history-main',cohort+'/'+method,'history',row[2],[sum(r['history_passed'] for r in selected),len(selected)])
    if 'tab:heldout-main' in active_tables:
        heldout=next(t for t in new['tables'] if t['name']=='heldout_main')['groups']
        for row in rows('tab:heldout-main'):
            if row[0].strip() not in ('Calculator','Table'):continue
            project=row[0].strip().lower();model='openai/gpt-oss-120b' if 'GPT-OSS' in row[1] else 'mistralai/mistral-small-3.2-24b-instruct'
            selected=[g for g in heldout if g['project']==project and g['model']==model]
            assert len({(g['free'],g['n']) for g in selected})==1
            check('tab:heldout-main',project+'/'+model,'free',row[2],[selected[0]['free'],selected[0]['n']])
            for col,method in ((3,'free_lib'),(4,'plan'),(5,'delta')):
                check('tab:heldout-main',project+'/'+model,method,row[col],[sum(g[method] for g in selected),sum(g['n'] for g in selected)])
    aliases={'DeepSeek-V4-Pro':'deepseek/deepseek-v4-pro-0813','Qwen3-Coder-30B-A3B':'qwen/qwen3-coder-30b-a3b-instruct',
        'Mistral-Small-3.2-24B':'mistralai/mistral-small-3.2-24b-instruct','Gemma-3-12B':'google/gemma-3-12b-it',
        'GPT-5-mini':'openai/gpt-5-mini','GPT-OSS-120B':'openai/gpt-oss-120b',
        'Gemini-2.5-Flash':'google/gemini-2.5-flash','Claude-Haiku-4.5':'anthropic/claude-haiku-4.5'}
    todo=next(s for s in primary['suites'] if s['suite']=='todomvc')
    saved=load('test/todomvc_dna/results/summary.json')
    for row in rows('tab:todomvc-full'):
        label=row[0].strip()
        if label not in aliases and label!='Total':continue
        models=todo['models'] if label=='Total' else [m for m in todo['models'] if m['model']==aliases[label]]
        assert models
        for col,method in enumerate(('free','rule','dna','free_lib','dna_unchecked'),1):
            final=sum(m['counts'][method]['final_all'] for m in models);first=sum(m['counts'][method]['first_all'] for m in models)
            observed=numbers(row[col]);expected=[final,first] if len(observed)==2 else [final]
            if len(observed)==1:assert first==final
            check('tab:todomvc-full',label,method,row[col],expected)
        selected_models={m['model'] for m in models}
        paired=[r for m in saved['models'] if m['model'] in selected_models for r in m['rows']]
        check('tab:todomvc-full',label,'paired-only',row[6],
            [sum(r['dna']['final_all'] and not r['free']['final_all'] for r in paired),
             sum(r['free']['final_all'] and not r['dna']['final_all'] for r in paired)])
    if 'tab:matched-feedback' in active_tables:
        from decimal import Decimal
        cohorts={name:load(path) for name,path in (
            ('GPT-OSS-120B','test/results/matched-feedback.json'),
            ('GPT-5 medium','test/results/matched-feedback-frontier.json'))}
        methods={'Code':'free','Code + library':'free_lib','Plan':'plan'}
        if 'tab:matched-feedback-main' in active_tables:
            for row in rows('tab:matched-feedback-main'):
                model=row[0].strip()
                if model not in cohorts:continue
                for col,method in enumerate(('free','free_lib','plan'),1):
                    group=cohorts[model]['groups'][method+'/final/history']
                    check('tab:matched-feedback-main',model,method,row[col],[group['passed'],group['total']])
        for row in rows('tab:matched-feedback'):
            model=row[0].strip();method=methods.get(row[1].strip())
            if model not in cohorts or not method:continue
            data=cohorts[model];pub=data['public_summary'][method]
            check('tab:matched-feedback',model+'/'+method,'public',row[2],
                [pub['first_all_passed'],pub['total'],pub['final_all_passed'],pub['total']])
            endpoints=('current',) if len(row)==4 else ('current','withheld','history')
            for col,endpoint in enumerate(endpoints,3):
                first=data['groups'][method+'/first/'+endpoint];final=data['groups'][method+'/final/'+endpoint]
                check('tab:matched-feedback',model+'/'+method,endpoint,row[col],
                    [first['passed'],first['total'],final['passed'],final['total']])
        for row in rows('tab:matched-feedback-usage'):
            model=row[0].strip();method=methods.get(row[1].strip())
            if model not in cohorts or not method:continue
            usage=cohorts[model]['usage'][method]
            for col,key in enumerate(('requests','prompt_tokens','cached_prompt_tokens','completion_tokens','reasoning_tokens'),2):
                check('tab:matched-feedback-usage',model+'/'+method,key,row[col],[usage.get(key,0)])
            actual=re.findall(r'\d+\.\d+',row[7]);assert len(actual)==1
            observed=int(Decimal(actual[0])*1_000_000);expected=usage['cost_micro_usd']
            assert observed==expected
            checks.append({'table':'tab:matched-feedback-usage','row':model+'/'+method,'column':'cost_micro_usd',
                'observed':[observed],'expected':[expected]})
    if 'tab:schema-search' in active_tables:
        search=load('test/results/schema-search.json')
        for row in rows('tab:schema-search'):
            project=row[0].strip()
            if project not in ('calculator','table','bom'):continue
            builder='openai/gpt-5' if row[1].strip()=='GPT-5' else 'anthropic/claude-sonnet-4.5'
            library=next(x for x in search['libraries'] if x['project']==project and x['builder']==builder)
            key=project+'/'+builder
            check('tab:schema-search',key,'pool',row[2],[library['population_size']])
            check('tab:schema-search',key,'selected',row[3],[library['selected_count']])
            for col,endpoint in enumerate(('current','history'),4):
                group=search['groups'][key+'/'+endpoint]
                check('tab:schema-search',key,endpoint,row[col],[group['passed'],group['total']])
    if 'tab:cost' in active_tables:
        from decimal import Decimal
        original=load('test/results/table-details-replay.json')['original_costs']['rows']
        cost_labels={
            r'\duo (probe and comparison)': 'WebApp1K-Duo',
            'TodoMVC, eight-model study': 'TodoMVC original',
            r'TodoMVC, samples 3--5 (\cref{app:samples})': 'TodoMVC samples 3-5',
            r'\webbench, eight-model study (incl.\ the regeneration of \cref{app:transport})': 'Web-Bench original',
            r'\webbench, seeds 2--3 (\cref{app:samples})': 'Web-Bench seeds 2-3',
            r'\webbench, GPT-5 (\cref{sec:strength})': 'Web-Bench GPT-5 original',
        }
        public_subtotal=sum(r['settled_microusd'] for r in original if r['study'] in cost_labels.values())
        for row in rows('tab:cost'):
            label=row[0].strip()
            if label in cost_labels:
                expected=next(r['displayed_usd'] for r in original if r['study']==cost_labels[label])
            elif label=='Public-suite subtotal':
                expected=f'{Decimal(public_subtotal)/1_000_000:.2f}'
            else:
                continue
            observed=re.findall(r'\d+\.\d+',row[1])
            assert observed==[expected],(label,observed,expected)
            cents=int(Decimal(expected)*100)
            checks.append({'table':'tab:cost','row':label,'column':'settled_cents',
                           'observed':[cents],'expected':[cents]})
    result={'all_passed':True,'checked_cells':len(checks),'checked_numeric_values':sum(len(c['observed']) for c in checks),
        'tables':sorted({c['table'] for c in checks}),'checks':checks,
        'manuscript_sources_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(manuscripts)},
        'data_sources_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(sources)},
        'scope':'Only tables reachable from the current manuscript input tree are considered; unused archived TeX files are excluded. Literal cells listed here are compared with reconstructed results and retained paired rows. Matched-feedback costs are checked in micro-dollars; public-suite ledger subtotals are checked at displayed precision. Unlisted cells, prose, statistical intervals, other costs and citations are not covered. Does not rerun browsers or establish independent human review.'}
    dump(args.report,result)
    print({k:result[k] for k in ('all_passed','checked_cells','checked_numeric_values','tables')})


if __name__=='__main__':main()
