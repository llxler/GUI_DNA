"""Let the original builder repair button declarations without modifying its arithmetic code."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import html
import json
import re

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.starter_transfer import run as transfer

trial = transfer.trial
calc = trial.calculator
HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/calculator-keypad-labels-20261128'
ORIG = trial.OUT/'gemma/build/a/0'
CAP = .30
BUTTON = re.compile(r"""<button onclick="calculate\('([^'<>\\"]{1,12})'\)">([^<>]{1,14})</button>""")
TOKEN = re.compile(r'[\wπ√×÷.^+/*=()\-]{1,12}')
HELD = [('6','*','4',24),('8','-','5',3),('9','/','3',3)]


def rewrite(document, updates):
    keys = list(dict.fromkeys(BUTTON.findall(document)))
    if not isinstance(updates,list) or len(updates)>len(keys):
        raise ValueError('Expected a list of button declarations')
    edits = {}
    for row in updates:
        i, buttons = row['index'], row['buttons']
        if type(i) is not int or not 0<=i<len(keys) or i in edits or not isinstance(buttons,list) or not 1<=len(buttons)<=3:
            raise ValueError('Invalid button edit')
        out = []
        for btn in buttons:
            if set(btn)!={'label','argument'} or not all(isinstance(x,str) and TOKEN.fullmatch(x) for x in btn.values()):
                raise ValueError('Button requires a literal caption and argument')
            out.append('<button onclick="calculate(\''+btn['argument']+'\')">'+html.escape(btn['label'])+'</button>')
        edits[i]=''.join(out)
    return BUTTON.sub(lambda m:edits.get(keys.index(m.groups()),m[0]),document)


def register():
    paths=[Path(__file__),HERE/'PROTOCOL.md',transfer.HERE/'result.json',ORIG/'full/index.html',trial.OUT/'registration.json',
           trial.OUT/'gemma/build/a/library.json', Path(calc.__file__),*ORIG.glob('groups/transmission-*/settled.json')]
    keys={str(p.relative_to(ROOT)):sha(p) for p in paths}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f,dict(utc=now(),deadline=trial.END.isoformat(),cap=CAP,balance=balance,sources=keys,seeds=[2026112841,2026112842],held=HELD))
    assert read(f)['sources']==keys
    return read(f)


def generate(reg):
    if (OUT/'seal.json').exists():
        return
    document=(ORIG/'full/index.html').read_text()
    pub=read(trial.OUT/'public.json')
    settled,=ORIG.glob('groups/transmission-*/settled.json')
    reply=settled.with_name('response.json')
    assert sha(reply)==read(settled)['response_sha256']
    groups=calc.survey.receiver.first_object(read(reply)['choices'][0]['message']['content'])
    inventory=list(dict.fromkeys(BUTTON.findall(document)))
    prompt=core.messages('Repair the clickable keypad of YOUR existing calculator. Some visible labels do not call '
                         'the indicated operation and other required keys are inaccessible. Preserve working operations. '
                         'You can replace an indexed HTML button with one to three buttons, each invoking the existing calculate(argument). '
                         'Return only a JSON array of {"index":integer,"buttons":[{"label":"visible caption","argument":"value"}]}. '
                         'Omit unchanged entries. Do not write JavaScript. Make all digits, four operators, equals and clear reachable.',
                         dict(current_buttons=[dict(index=i,argument=k,label=v) for i,(k,v) in enumerate(inventory)],
                              public_requirements=pub['requirements'], calculate=document.split('function calculate(value)',1)[1].split("document.getElementById('toggle').addEventListener",1)[0][:5300]))
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    rows,libraries={},{}
    for i,seed in enumerate(reg['seeds'],1):
        rep=str(i)
        def settings(p,t,phase):
            return calc.action.settings('table',t,phase)|{'seed':seed}
        with patch.multiple(calc.base,OUT=OUT,END=trial.END,template=settings):
            try:
                raw=calc.base.request(ledger,('table','gemma','a'),OUT/rep/'repair',prompt,'build',1900)
                updates=json.loads(calc.base.uncode(raw))
                fixed_doc=rewrite(document,updates)
                full=calc.page(fixed_doc,groups,groups,OUT/rep/'fixed');off=calc.page(fixed_doc,groups,[],OUT/rep/'off')
                a,b=calc.probe(full),calc.probe(off)
                labels={s for v in groups.values() for s in v}
                admitted=a['arithmetic'] and b['arithmetic'] and bool((set(a['functional']) & labels)-set(b['buttons']))
                record=dict(status='valid' if admitted else 'build_failed',edits=updates,full=a,off=b,page=full)
            except calc.action.typed.MISSING as exc:
                record=dict(status='missing',reason=str(exc))
            except calc.base.ERRORS as exc:
                record=dict(status='invalid',reason=str(exc))
            libraries[rep]=record;rows[rep]=[]
            if record['status']!='valid':
                continue
            def plan(n):
                dest=OUT/rep/'plans'/str(n)
                msg=core.messages('Choose which optional calculator key groups to expose for the current requirement. Return one JSON array of group names. Basic arithmetic stays enabled.',
                                  dict(public=core.prefix(pub,n),available=groups))
                try:
                    text=calc.base.request(ledger,('table','gemma','a'),dest/'call',msg,'plan',1500)
                    selected=json.loads(calc.base.uncode(text))
                    if not isinstance(selected,list) or any(k not in groups for k in selected):
                        raise ValueError('Unknown key group')
                    val=calc.page(fixed_doc,groups,selected,dest/'page')
                except calc.action.typed.MISSING as exc:
                    val=dict(status='missing',reason=str(exc))
                except calc.base.ERRORS as exc:
                    val=dict(status='invalid',reason=str(exc))
                return [dict(project='calculator',task=n,arm=arm,rep=rep,**v) for arm,v in [('planned',val),('fixed',full)]]
            with ThreadPoolExecutor(max_workers=3) as pool:
                rows[rep]=[v for group in pool.map(plan,range(1,21)) for v in group]
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),libraries=libraries,rows=rows))


def new_arithmetic(path):
    observations=[]
    with browser.serve('calculator',path) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        page=engine.new_page(service_workers='block')
        from urllib.parse import urlsplit
        page.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        for left,op,right,want in HELD:
            page.goto(url)
            got=page.evaluate("""keys => {
                const buttons=[...document.querySelectorAll('button')];
                for (const k of keys) {
                    const b=buttons.find(v=>v.textContent.trim()===k && v.getClientRects().length);
                    if(!b)return null;
                    b.click();
                }
                return document.querySelector('#display')?.value;
            }""",[left,op,right,'='])
            try:
                passed=float(got)==want
            except (ValueError,TypeError):
                passed=False
            observations.append(dict(want=want,got=got,passed=passed))
    return observations


def score():
    result=HERE/'result.json'
    if result.exists():
        return
    s=read(OUT/'seal.json')
    assert s['registration']==sha(OUT/'registration.json')
    held={'original':new_arithmetic(ORIG/'full')}
    for k,l in s['libraries'].items():
        if 'page' in l:
            held[k]=new_arithmetic(ROOT/l['page']['page'])
    proto=browser.verify_contract('calculator')
    assert proto==read(trial.OUT/'registration.json')['harness']
    graded=browser.evaluate([r for rows in s['rows'].values() for r in rows],OUT,{'calculator':proto},3)
    core.save(result, dict(registration=s['registration'],seal=sha(OUT/'seal.json'),heldout=held,
                           libraries={k:{a:b for a,b in v.items() if a!='page'} for k,v in s['libraries'].items()},
                           rows=[{k:v[k] for k in ('rep','arm','task','status','report_sha256')} |
                                 dict(passed=False if v['status']=='invalid' else v['passed']) for v in graded],
                           cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        generate(register())
        score()
