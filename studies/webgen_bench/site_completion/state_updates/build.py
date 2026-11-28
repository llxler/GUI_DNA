"""Compile a declared state update to the SDK's native setValue action."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT, now, read, sha
from .. import generate as main
from ...functional_pilot import evaluate, pages

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/webgen-native-state-20261128'
CANDIDATES = HERE/'candidates.json'
SITES = ('000068','000084','000099')
TAG = 'deepseek-flash'
CAP = .70
EXAMPLE = {'initial':{'credits':7,'reserved':0},'sections':[{'tab':'Workshop','display':{'credits':'Credits','reserved':'Reserved'},
           'actions':[{'label':'Reserve two','changes':[{'field':'credits','op':'add','value':-2},
                      {'field':'reserved','op':'add','value':2}], 'requires':{'field':'credits','min':2}}]}]}
PROMPT = """Extend a website with local state only where the brief requests an observable change.
Return one JSON object {initial,sections}. initial maps up to 24 ASCII names to integer, plain string or boolean values.
sections is a list. Each section has tab (an existing exact tab title), display (dictionary mapping field names
to short display labels) and actions (list). An action has label, changes, and optional requires:{field,min}
to disable it until a numeric field reaches a threshold. Each change has field, op and value.
op set assigns a literal of the initial type, add changes an integer by a signed integer.
Use controls to perform the named workflows and display their effects when navigating between tabs.
Keep the overlay compact and labels distinct. Do not describe functionality you cannot implement.
If none is appropriate return empty initial/sections. No markup, expressions, code or URLs."""


def plain(value):
    if not isinstance(value,str) or not 1 <= len(value) <= 120 or re.search(r'[<>{}$]',value):
        raise ValueError('Expected 1-120 characters of literal plain text')
    return value


def identifiers(state):
    if not isinstance(state,dict) or len(state)>24:
        raise ValueError('Expected at most 24 named variables')
    for key,value in state.items():
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,39}',key) or key in ('constructor','prototype','__proto__'):
            raise ValueError('Invalid scalar name')
        if type(value) not in (int,str,bool) or type(value) is int and abs(value)>10**8:
            raise ValueError('Expected a bounded scalar initial value')
        if isinstance(value,str):
            plain(value)
    return {k:'wgState_'+k for k in state}


def compile_updates(config, spec, enabled):
    page=deepcopy(config)
    state=spec['initial']
    names=identifiers(state)
    tabs={t['title']:t for t in page['body'][0]['tabs']}
    if not isinstance(spec['sections'],list) or len(spec['sections'])>len(tabs):
        raise ValueError('Use one entry per existing tab')
    page['id']='wgStateRoot'
    if set(names.values()) & page['data'].keys():
        raise ValueError('State conflicts with an existing page field')
    page['data'].update({names[k]:v for k,v in state.items()})
    seen=set()
    for section in spec['sections']:
        title=section['tab']
        if title not in tabs or title in seen:
            raise ValueError('Use an existing distinct tab title')
        seen.add(title)
        items=[{'type':'tpl','tpl':plain(label)+': ${'+names[field]+'}'} for field,label in section['display'].items()]
        if not isinstance(section['actions'],list) or len(section['actions'])>12:
            raise ValueError('Expected at most twelve actions per view')
        for action in section['actions']:
            values={}
            for change in action['changes']:
                key,op,value=change['field'],change['op'],change['value']
                dest=names[key]
                if dest in values:
                    raise ValueError('Update each variable once per action')
                if op=='set' and type(value) is type(state[key]):
                    values[dest]=plain(value) if isinstance(value,str) else value
                elif op=='add' and type(state[key]) is int and type(value) is int and abs(value)<=10**8:
                    values[dest]='${'+dest+(' + ' if value>=0 else ' - ')+str(abs(value))+'}'
                else:
                    raise ValueError('Expected type-preserving set or signed integer add')
            if not values:
                raise ValueError('An action requires at least one update')
            button={'type':'button','label':plain(action['label'])}
            guard=action.get('requires')
            if guard:
                key,minimum=guard['field'],guard['min']
                if type(state[key]) is not int or type(minimum) is not int:
                    raise ValueError('Numeric balance required')
                button['disabledOn']=names[key]+' < '+str(minimum)
            if enabled:
                button['onEvent']={'click':{'actions':[{'actionType':'setValue','componentId':page['id'],'args':{'value':values}}]}}
            items.append(button)
        tabs[title]['body'][:0]=items
    return page


def public_controls():
    base=deepcopy(main.schema.SAMPLE)
    for s in base['body'][0]['tabs']:
        if not isinstance(s['body'],list):
            s['body']=[s['body']]
    result={}
    for enabled in (True,False):
        html=pages.page(compile_updates(base,EXAMPLE,enabled),'human')
        def replay(engine):
            with pages.local_tab(engine,html,sdk=True) as tab:
                tab.get_by_text('Workshop',exact=True).click()
                tab.get_by_text('Credits: 7',exact=True).wait_for()
                tab.get_by_text('Reserve two',exact=True).click()
                tab.get_by_text('Start',exact=True).click()
                tab.get_by_text('Workshop',exact=True).click()
                tab.get_by_text('Credits: '+('5' if enabled else '7'),exact=True).wait_for()
                tab.get_by_text('Reserved: '+('2' if enabled else '0'),exact=True).wait_for()
                return True
        result['active' if enabled else 'inert']=evaluate.browser_job(replay)
    return result


def generate():
    reg=OUT/'registration.json'
    hashes={str(f.relative_to(ROOT)):sha(f) for f in (Path(__file__),HERE/'PROTOCOL.md',main.HERE/'PROTOCOL.md',main.gen.SRC,main.gen.DIST)}
    if not reg.exists():
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<main.END
        core.save(reg,dict(utc=now(),deadline=main.END.isoformat(),cap=CAP,sources=hashes,balance=balance,sites=SITES))
    assert read(reg)['sources']==hashes
    if CANDIDATES.exists():
        return
    controls=public_controls()
    while not main.CANDIDATES.exists():
        if datetime.now(timezone.utc)>=main.END:
            raise TimeoutError('No sealed main candidates')
        time.sleep(5)
    briefs=read(main.OUT/'briefs.json')
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def build(site):
        directory=OUT/'plans'/site
        saved=directory/'record.json'
        if saved.exists():
            return read(saved)
        plan=read(main.OUT/'jobs'/TAG/site/'plan/record.json')
        if plan['status']!='valid':
            return {a:{'status':plan['status']} for a in ('active','inert')}
        cfg=plan['config']
        assert pages.page(cfg,'human').encode()==(ROOT/read(main.CANDIDATES)['rows'][TAG][site]['human']['file']).read_bytes()
        msg=core.messages(PROMPT,dict(brief=briefs[site],current_config=cfg,example=EXAMPLE))
        for i in range(2):
            try:
                raw=main.gen.call(ledger,TAG,directory/str(i),msg,'plan',5000)
                spec=main.gen.parse(raw)
                rows={a:pages.write_html(OUT/'sites'/site/a,pages.page(compile_updates(cfg,spec,a=='active'),'human')) for a in ('active','inert')}
                core.save(directory/'extension.json',spec)
                break
            except main.gen.MISSING as exc:
                rows={a:dict(status='missing',reason=str(exc)) for a in ('active','inert')}
                break
            except (AttributeError,*main.gen.ERRORS) as exc:
                rows={a:dict(status='invalid',reason=str(exc)[:180]) for a in ('active','inert')}
                msg += [dict(role='assistant',content=raw),dict(role='user',content='Public validation: '+str(exc)[:180]+'. Return the complete corrected JSON.')]
        core.save(saved,rows)
        return rows
    with patch.multiple(main.gen.BASE,OUT=OUT,END=main.END,template=main.gen.settings),ThreadPoolExecutor(max_workers=3) as workers:
        rows=dict(zip(SITES,workers.map(build,SITES),strict=True))
    seal=dict(registration=sha(reg),main_candidates=sha(main.CANDIDATES),public=controls,rows=rows)
    core.save(OUT/'seal.json',seal)
    core.save(CANDIDATES,seal|dict(seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
