"""Use the calculator builder's original examples as a closed deployment interface."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
from unittest.mock import patch
import re

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.target_models import run as trial

calc = trial.calculator
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/calculator-example-selection-20261128'
TAGS = ('gemma','qwen9','oss','deepseek-flash')
CAP = .50


def register():
    f = OUT/'registration.json'
    inputs = [Path(__file__), HERE/'PROTOCOL.md', Path(calc.__file__), calc.GPT/'package.json', calc.OUT/'public.json',
              calc.HERE/'result.json', trial.HERE/'result.json', trial.OUT/'registration.json', calc.OUT/'registration.json']
    sums = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f,dict(utc=now(),deadline=trial.END.isoformat(),cap=CAP,balance=balance,sources=sums,
                         models={t:calc.action.settings('table',t,'plan')['model'] for t in TAGS},targets=list(range(1,21))))
    assert read(f)['sources']==sums
    return read(f)


def generate(reg):
    seal = OUT/'seal.json'
    if seal.exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub, pkg = read(calc.OUT/'public.json'), read(calc.GPT/'package.json')
    assert sha(calc.OUT/'public.json')==sha(trial.OUT/'public.json') and len(pkg['examples'])==2
    fixed=[]
    for i,e in enumerate(pkg['examples']):
        path=OUT/'examples'/str(i)
        files=core.emit('calculator',calc.expansion.compile_plan(pkg,e['plan']),path)
        fixed.append(calc.files.emit(path,files))
    public=calc.probe(fixed[0])
    if not public['arithmetic']:
        raise ValueError('Frozen first GPT-5 example no longer passes the original check')

    def one(job):
        tag,n=job
        out=OUT/tag/str(n)/'choice.json'
        if out.exists():
            return read(out)
        prompt=core.messages('Choose the existing calculator configuration that serves the current request. '
                             'Reply only with its number, 0 or 1. The first example uses the documented default settings.',
                             dict(public=core.prefix(pub,n),documentation=pkg['plan_documentation'],
                                  choices=[dict(number=i,**e) for i,e in enumerate(pkg['examples'])]))
        try:
            result=dict(status='invalid',reason='Expected 0 or 1')
            for attempt in range(2):
                raw=calc.base.request(ledger,('table',tag,'a'),out.parent/'calls'/str(attempt),prompt,'plan',250)
                token=calc.base.uncode(raw).strip()
                if re.fullmatch('[01]',token):
                    idx=int(token);result=fixed[idx]|dict(choice=idx);break
                prompt += [dict(role='assistant',content=raw),dict(role='user',content='Return only the digit 0 or 1.')]
        except calc.action.typed.MISSING as exc:
            result=dict(status='missing',reason=str(exc))
        core.save(out,dict(project='calculator',tag=tag,task=n,arm='selected',**result))
        return read(out)

    with patch.multiple(calc.base,OUT=OUT,END=trial.END,template=calc.action.settings),ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(one,product(TAGS,reg['targets'])))
    rows += [dict(project='calculator',tag=t,task=n,arm=f'fixed-{i}',**v)
             for t,n in product(TAGS,reg['targets']) for i,v in enumerate(fixed)]
    core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows,public=public))


def score(reg):
    result=HERE/'result.json'
    if result.exists():
        return
    s=read(OUT/'seal.json');assert s['registration']==sha(OUT/'registration.json')
    protocol=browser.verify_contract('calculator');assert protocol==read(trial.OUT/'registration.json')['harness']
    scored=browser.evaluate(s['rows'],OUT,{'calculator':protocol},3)
    by_model={m:[{k:v[k] for k in ('task','arm','status','report_sha256')} |
                 dict(choice=v.get('choice'),passed=False if v['status']=='invalid' else v['passed'])
                 for v in scored if v['tag']==t] for t,m in reg['models'].items()}
    core.save(result,dict(registration=s['registration'],seal=sha(OUT/'seal.json'),models=by_model,
                          public=s['public'],cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        reg=register()
        generate(reg)
        score(reg)
