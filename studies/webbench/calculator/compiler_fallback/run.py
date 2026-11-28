"""Obtain fresh full plans and use a builder-supplied example only on a compiler rejection."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import re
import shutil
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.example_selection import run as examples

calc, trial = examples.calc, examples.trial
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/calculator-compiler-fallback-20261128'
CAP = 1.50
TAGS = (*examples.TAGS, 'mistral')
SEED = 2026112851


def register():
    reg = OUT / 'registration.json'
    registered = [Path(__file__), HERE/'PROTOCOL.md', Path(calc.__file__), Path(examples.__file__),
                  examples.HERE/'result.json', examples.OUT/'seal.json', calc.GPT/'package.json', trial.OUT/'public.json',
                  trial.OUT/'registration.json', Path(calc.expansion.__file__), Path(calc.survey.receiver.__file__)]
    sums = {str(p.relative_to(ROOT)):sha(p) for p in registered}
    if not reg.exists():
        stages = ('calculator-target-models','calculator-starter-transfer','calculator-keypad-labels','calculator-example-selection',
                  'todo-edit-scope','todo-edit-choices','todo-filtered-view','todo-route-preservation','table-keyboard-contract',
                  'table-navigation-context','table-coordinate-navigation','table-coordinate-reception')
        prev = read(ROOT/'studies/results/webgen-site-completion-20261128.json')['campaign']['exposure_usd']
        spent = sum(round(ledger_read.totals(ROOT/'artifacts'/(s+'-20261128')/'budget.sqlite3')['exposure_usd']*1e6) for s in stages)
        file_cap = read(ROOT/'artifacts/file-explorer-target-models-20261128/registration.json')['cap']
        ceiling = (round(prev*1e6)+spent)/1e6+file_cap+CAP
        if ceiling>20:
            raise RuntimeError('Campaign ceiling would be exceeded')
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(reg,dict(utc=now(),deadline=trial.END.isoformat(),cap=CAP,balance=balance,
                           cumulative_ceiling=ceiling,sources=sums,seed=SEED,targets=list(range(1,21)),
                           models={t:calc.action.settings('table',t,'plan')['model'] for t in TAGS}))
    assert read(reg)['sources']==sums
    return read(reg)


def generate(reg):
    seal = OUT/'seal.json'
    if seal.exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pkg, pub = read(calc.GPT/'package.json'), read(trial.OUT/'public.json')
    fixed=[]
    for i,e in enumerate(pkg['examples']):
        dest=OUT/'fixed'/str(i)
        fixed.append(calc.files.emit(dest,core.emit('calculator',calc.expansion.compile_plan(pkg,e['plan']),dest)))
    assert len(fixed)==2 and calc.probe(fixed[0])['arithmetic']

    def deploy(job):
        tag,n=job
        folder=OUT/tag/str(n)
        dest=folder/'record.json'
        if dest.exists():
            return read(dest)
        page=folder/'native'
        try:
            raw=calc.base.request(ledger,('table',tag,'a'),folder/'calls/native',core.plan_messages(pub,n,pkg),'plan',3800)
            plan=calc.survey.receiver.first_object(raw)
            native=calc.files.emit(page,core.emit('calculator',calc.expansion.compile_plan(pkg,plan),page))
        except calc.action.typed.MISSING as exc:
            native=dict(status='missing',reason=str(exc))
        except calc.base.ERRORS as exc:
            native=dict(status='invalid',reason=str(exc)[:200])
        final,choice = native,None
        if native['status']=='invalid':
            prompt=core.messages('The compiler rejected your configuration. Choose an existing calculator configuration for this request. '
                                 'Reply with just its number, 0 or 1. The first example uses the documented defaults.',
                                 dict(public=core.prefix(pub,n),documentation=pkg['plan_documentation'],
                                      choices=[dict(number=i,**e) for i,e in enumerate(pkg['examples'])]))
            try:
                final=dict(status='invalid',reason='Expected example 0 or 1')
                for attempt in range(2):
                    raw=calc.base.request(ledger,('table',tag,'a'),folder/'calls/example'/str(attempt),prompt,'plan',250)
                    value=calc.base.uncode(raw).strip()
                    if re.fullmatch('[01]',value):
                        choice=int(value)
                        final=fixed[choice]
                        break
                    prompt += [dict(role='assistant',content=raw),dict(role='user',content='Only the digit 0 or 1.')]
            except calc.action.typed.MISSING as exc:
                final=dict(status='missing',reason=str(exc))
        core.save(dest,[dict(project='calculator',tag=tag,task=n,arm=arm,**record) for arm,record in
                        [('native',native),('final',final|dict(triggered=native['status']=='invalid',choice=choice)),
                         ('fixed-0',fixed[0]),('fixed-1',fixed[1])]])
        return read(dest)

    def settings(p,t,phase):
        return calc.action.settings('table',t,phase)|{'seed':reg['seed']}
    with patch.multiple(calc.base,OUT=OUT,END=trial.END,template=settings),ThreadPoolExecutor(max_workers=5) as pool:
        rows=[v for group in pool.map(deploy,product(TAGS,reg['targets'])) for v in group]
    core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows))


def score(reg):
    dest=HERE/'result.json'
    if dest.exists():
        return
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    protocol=browser.verify_contract('calculator')
    assert protocol==read(trial.OUT/'registration.json')['harness']
    # Reuse only the exact official contract, target and source tree (including browser assets).
    for row in seal['rows']:
        if row['status']!='valid':
            continue
        fingerprint=browser.digest(row['files'])
        rel=Path('browser/scores/calculator')/f'task-{row["task"]}'/fingerprint/'score.json'
        local=OUT/rel
        if local.exists():
            continue
        for peer in (examples.OUT,trial.OUT,calc.OUT):
            original=peer/rel
            if not original.exists():
                continue
            expected=dict(project='calculator',task=row['task'],files_digest=fingerprint,contract_digest=browser.digest(protocol))
            v=browser.verify_receipt(peer,original,expected)
            raw=local.with_name('reused-report.json')
            raw.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(peer/v['report'],raw)
            core.save(local,dict(v,report=str(raw.relative_to(OUT)),source_receipt=str(original.relative_to(ROOT)),
                                 source_receipt_sha256=sha(original),source_report=str((peer/v['report']).relative_to(ROOT))))
            break
    scored=browser.evaluate(seal['rows'],OUT,{'calculator':protocol},4)
    models={m:[dict(task=r['task'],arm=r['arm'],status=r['status'],triggered=r.get('triggered'),choice=r.get('choice'),
                    passed=False if r['status']=='invalid' else r['passed'],report_sha256=r['report_sha256'],
                    files_digest=browser.digest(r['files']) if r['status']=='valid' else None)
               for r in scored if r['tag']==t] for t,m in reg['models'].items()}
    core.save(dest,dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),models=models,
                        cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        reg=register()
        generate(reg)
        score(reg)
