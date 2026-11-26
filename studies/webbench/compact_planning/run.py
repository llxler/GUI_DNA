"""Generate and check compact selections against the libraries in the submitted table."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import combinations, product
import json
from pathlib import Path
import re
import shutil
from unittest.mock import patch

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from studies.webbench.self_build_modules import run as base
from studies.webbench.self_build_modules.score import controls

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/compact-planning-20261125'
END = datetime(2026, 11, 25, 14, 35, tzinfo=timezone.utc)
CAP = 4
CELLS = {
    'table': {'human': ['qwen'], 'gpt5-library': ['qwen9','qwen','oss','deepseek-flash','deepseek-pro'],
              'self': ['mistral','qwen']},
    'svg-chart': {'gpt5-library': ['gemma'], 'self': ['gemma','qwen','deepseek-flash','deepseek-pro']},
    'form': {'gpt5-library': ['qwen'], 'self': ['gemma','qwen9','mistral','qwen']},
}
STAGES = {'modules':'delivery','entry':'entry','observed options':'options','module links':'links'}
MATRIX = ROOT/'studies/results/paper-performance-matrix.json'
RESULT = HERE/'result.json'


def register():
    path = OUT/'registration.json'
    if path.exists():
        reg = read(path)
        assert all(sha(ROOT/k)==v for k,v in reg['sources'].items())
        return reg
    from studies.paper_performance import current_group
    matrix = read(MATRIX)
    sources = [Path(__file__), HERE/'PROTOCOL.md', Path(base.__file__), Path(core.__file__), Path(browser.__file__)]
    cells = []
    for project, arms in CELLS.items():
        for arm, tags in arms.items():
            for tag in tags:
                model, source, original = controls(project,tag)
                old = base.old_root(project,tag)
                group = current_group(matrix[model],project)
                targets = group['targets']
                pkg = old/'inputs'/project/(arm+'.json')
                old_status = {str(t):original[arm][t]['status'] for t in targets}
                if arm=='self':
                    reg = matrix[model].get('self_recovery',{}).get(project,{}).get('first',{})
                    if reg.get('complete'):
                        root = ROOT / ('artifacts/webbench-self-'+STAGES[reg['preparation']]+'-20261125')/project/tag/'a'
                        state = read(root/'build/status.json')
                        pkg = ROOT/state['package']
                        assert sha(pkg)==state['package_sha256']
                        old_status = {str(t):read(root/'plans'/str(t)/'result.json')['status'] for t in targets}
                    else:
                        pkg = old/tag/project/'build/package.json'
                assert arm in group['passed']
                sources.extend([pkg,source,old/'inputs'/project/'browser.json',old/'inputs'/project/'public.json'])
                cells.append(dict(project=project,tag=tag,arm=arm,model=model,targets=targets,
                                  previous=group['passed'][arm],old_status=old_status,
                                  package=str(pkg.relative_to(ROOT)),direct=group['passed']['direct']))
    balance = check_credits(CAP)
    assert balance['sufficient']
    core.save(path,dict(utc=now(),deadline=END.isoformat(),cap=CAP,balance=balance,cells=cells,
                         sources={str(f.relative_to(ROOT)):sha(f) for f in sources}))
    return read(path)


def choices(pkg, arm, project):
    examples = [e['plan'] for e in pkg.get('examples',[])]
    if arm=='human':
        names = pkg['plan_schema']['properties']['controllers']['items']['enum']
        return [{'controllers':list(names)}]+[{'controllers':list(s)} for i in range(len(names)) for s in combinations(names,i)]
    if arm!='self':
        return examples
    fields = pkg['plan_schema']['properties']
    variants = product(*([True,False] if v['type']=='boolean' else v['enum'] for v in fields.values()))
    plans = [dict(zip(fields,values)) for values in variants]
    return [examples[0],*(p for p in plans if p!=examples[0])]


def make_messages(public,n,pkg,menu,open_form):
    reqs = '\n'.join(r['description'] for r in public['requirements'][:n])
    if open_form:
        return core.messages('Implement the public requirements by returning only the final complete survey configuration as JSON. Use the literal requested labels, options and order.',
                             dict(requirements=reqs,interface=pkg['plan_schema'],example=menu[0]))
    keys = list(menu[0])
    encoded = '\n'.join(f'{i}: '+json.dumps([row.get(k) for k in keys] if all(set(x)==set(keys) for x in menu) else row,
                                             separators=(',',':')) for i,row in enumerate(menu))
    return [dict(role='system',content='You select one numbered configuration for a reusable web application. Output ONLY its integer index.'),
            dict(role='user',content=f'Requirements through the current task:\n{reqs}\nLibrary controls:\n'+
                 str(pkg.get('plan_documentation',pkg.get('design','')))[:4000]+
                 f'\nField order: {keys}\nComplete configurations (index: values):\n{encoded}\nSelect one index. Answer with its digits only.')]


def compile_page(project,arm,pkg,plan,public,dest):
    if arm=='self':
        core.materialize(project,pkg,plan,dest)
    else:
        compiler = base.original.table_compile if project=='table' else base.original.chart_compile
        core.emit(project,base.original.validate_files(public['starter'] | compiler(pkg,plan)),dest)
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=browser.tree(dest))


def produce(cell, ledger):
    p,t,a = (cell[k] for k in ('project','tag','arm'))
    root = OUT/p/t/a
    if (root/'seal.json').exists():
        return
    pub = read(base.old_root(p,t)/'inputs'/p/'public.json')
    pkg = read(ROOT/cell['package'])
    menu = choices(pkg,a,p)
    fixed = compile_page(p,a,pkg,menu[0],pub,root/'fixed')
    free_form = p=='form' and a=='gpt5-library'
    def one(n):
        dest=root/str(n)
        try:
            text=base.request(ledger,(p,t,'a'),dest/'call',make_messages(pub,n,pkg,menu,free_form),'plan',4096 if free_form else 1024)
            value=base.uncode(text).strip()
            if free_form:
                plan=base.parse_json(value)
            else:
                if not re.fullmatch(r'[0-9]{1,4}',value) or int(value)>=len(menu):
                    raise ValueError('Expected one in-range integer')
                plan=menu[int(value)]
            row=compile_page(p,a,pkg,plan,pub,dest/'page')
            row['plan']=plan
        except (BudgetStop,base.original.Unavailable) as exc:
            row=dict(status='missing',reason=str(exc))
        except base.ERRORS as exc:
            row=dict(status='invalid',reason=str(exc)[:300])
        return dict(project=p,task=n,arm=a,**row)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(one,cell['targets']))
    core.save(root/'seal.json',dict(registration=sha(OUT/'registration.json'),fixed=fixed,rows=rows))
    print('sealed',p,t,a,flush=True)


def evaluate(c):
    p,t,a = (c[k] for k in ('project','tag','arm'))
    root=OUT/p/t/a
    seal=read(root/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    protocol=browser.verify_contract(p)
    assert protocol==read(base.old_root(p,t)/'inputs'/p/'browser.json')
    rows=seal['rows']+[dict(project=p,task=n,arm='fixed',**seal['fixed']) for n in c['targets']]
    for row in rows:
        if row['status']!='valid':
            continue
        key=digest(row['files'])
        rel=Path('browser/scores')/p/f"task-{row['task']}"/key/'score.json'
        if (OUT/rel).exists():
            continue
        for old in sorted((ROOT/'artifacts').glob('*/'+str(rel))):
            peer=old.parents[5]
            expected=dict(project=p,task=row['task'],files_digest=key,contract_digest=digest(protocol))
            if read(old).get('contract_digest')!=expected['contract_digest']:
                continue
            verified=browser.verify_receipt(peer,old,expected)
            raw=peer/verified['report']
            dest=OUT/rel.parent/'reused-report.json'
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(raw,dest)
            core.save(OUT/rel,dict(verified,report=str(dest.relative_to(OUT)),source_receipt=str(old.relative_to(ROOT)),
                                   source_receipt_sha256=sha(old),source_report=str(raw.relative_to(ROOT))))
            break
    scored=browser.evaluate(rows,OUT,{p:protocol},4)
    results=[{k:v for k,v in r.items() if k in ('arm','task','status','reason','report_sha256','passed')} for r in scored]
    for r in results:
        if r['status']=='invalid':r['passed']=False
    data=dict(**c,seal_sha256=sha(root/'seal.json'),rows=results)
    for name in (a,'fixed'):
        rs=[r for r in results if r['arm']==name]
        data[name+'_passes']=sum(r['passed'] is True for r in rs)
        data[name+'_observed']=sum(r['passed'] is not None for r in rs)
    core.save(root/'comparison.json',data)
    print('scored',p,t,a,c['previous'],data[a+'_passes'],data['fixed_passes'],flush=True)


def main():
    import os,time
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        with patch.multiple(base,OUT=OUT,END=END),ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda c:produce(c,ledger),reg['cells']))
    if args.action=='score':
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        for c in reg['cells']:
            folder=OUT/c['project']/c['tag']/c['arm']
            while not (folder/'seal.json').exists():
                if datetime.now(timezone.utc)>END: return
                time.sleep(2)
            if not (folder/'comparison.json').exists(): evaluate(c)
    if args.action=='publish':
        cells=[read(OUT/c['project']/c['tag']/c['arm']/'comparison.json') for c in reg['cells']]
        core.save(RESULT,dict(cells=cells,registration_sha256=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    main()
