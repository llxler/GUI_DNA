"""Ground local mutations in the public brief and verify their visible effects."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import argparse
import hashlib
import re

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import build, evaluate as earlier
from .. import sdk_audit

GEN=ROOT/'artifacts/webgen-grounded-actions-20261128'
JUDGE=ROOT/'artifacts/webgen-grounded-actions-judge-20261128'
PAGES=build.HERE/'grounded-candidates.json'
RESULT=build.HERE/'grounded-judgments.json'
CAP=.35
JUDGE_CAP=2.
SITES=(*build.SITES,sdk_audit.SITE)
PROMPT=build.PROMPT + """
First read the website brief as a product specification. A button that only displays a success message
does not update data. A table with a literal row does not change when the user submits a form.
These are the only behaviors the current actions and tables provide; you may add persistent local state.
List the distinct requested workflows in coverage. Each entry is {quote,scope,reason,control?}:
quote is a short verbatim phrase from the brief; scope is local, external, or read.
When real services are required, separate an achievable browser-side state change from the external service.
For each local entry, name in control an action in your spec, with a visible changing variable in the
same tab. Add a field display in related views when appropriate. A no-op spec needs an explicit explanation
for each requested workflow. Never imply real payment, delivery or real-time network data.
Return exactly {coverage:[...],initial:{...},sections:[...]} as JSON."""


def register(out,cap,files):
    path=out/'registration.json'
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files}
    if not path.exists():
        used=sum(ledger_read.totals(p/'budget.sqlite3')['exposure_usd'] for p in (build.main.OUT,build.OUT))
        assert used+earlier.CAP+earlier.primary.CAP+CAP+JUDGE_CAP <= 20
        balance=check_credits(cap)
        assert balance['sufficient'] and datetime.now(timezone.utc)<build.main.END
        core.save(path,dict(utc=now(),deadline=build.main.END.isoformat(),sources=hashes,balance=balance,cap=cap,
                            completed_generation_exposure=used,sites=SITES))
    assert read(path)['sources']==hashes
    return path


def validate(spec, brief):
    coverage=spec['coverage']
    if not isinstance(coverage,list) or not 1<=len(coverage)<=30:
        raise ValueError('Explain the requested workflows using one to thirty entries')
    controls={}
    for section in spec['sections']:
        for action in section['actions']:
            name=action['label']
            if name in controls:
                raise ValueError('Use distinct local action labels')
            if not any(change['field'] in section['display'] for change in action['changes']):
                raise ValueError('Show an affected value in the action tab')
            controls[name]=section['tab']
    local=set()
    for entry in coverage:
        quote=entry['quote']
        if not isinstance(quote,str) or not quote.strip() or quote.casefold() not in brief.casefold():
            raise ValueError('Each workflow requires a verbatim phrase from the website brief')
        if not isinstance(entry['reason'],str) or not entry['reason'].strip():
            raise ValueError('Explain the workflow scope')
        if entry['scope']=='local':
            if entry.get('control') not in controls:
                raise ValueError('A local workflow requires a named update control')
            local.add(entry['control'])
        elif entry['scope'] not in ('external','read'):
            raise ValueError('Unknown workflow scope')
    if set(controls)-local:
        raise ValueError('Every action must be tied to a quoted local workflow')


def observe(engine, html, spec):
    # Replay the first immediately enabled action on a fresh page. The same
    # choice order is used for the inert twin. No official operation is read.
    with build.pages.local_tab(engine,html,sdk=True) as tab:
        for section in spec['sections']:
            tab.get_by_text(section['tab'],exact=True).first.click()
            for action in section['actions']:
                button=tab.get_by_role('button',name=action['label'],exact=True).first
                if not button.is_visible() or not button.is_enabled():
                    continue
                key=next(c['field'] for c in action['changes'] if c['field'] in section['display'])
                label=section['display'][key]
                node=tab.get_by_text(re.compile('^'+re.escape(label)+r': .+$')).filter(visible=True).last
                if not node.is_visible():
                    continue
                before=node.inner_text()
                button.click()
                tab.wait_for_timeout(350)
                after=node.inner_text()
                return dict(tab=section['tab'],button=action['label'],field=key,before=before,after=after,changed=before!=after)
    return None


def generate():
    reg=register(GEN,CAP,[Path(__file__),build.HERE/'ACTION_PLAN.md',Path(build.__file__),build.CANDIDATES,build.main.CANDIDATES,sdk_audit.RESULT])
    if PAGES.exists():
        return
    assert all(v['active']['sha256']==v['inert']['sha256'] for v in read(build.CANDIDATES)['rows'].values())
    briefs=read(build.main.OUT/'briefs.json') | read(build.main.gen.OUT/'generation-input.json')
    ledger=Ledger(GEN/'budget.sqlite3',CAP,CAP)
    def one(site):
        dest=GEN/'plans'/site
        file=dest/'record.json'
        if file.exists():
            return read(file)
        if site==sdk_audit.SITE:
            planfile=build.main.native.OUT/'plans'/build.TAG/site/'record.json'
        else:
            planfile=build.main.OUT/'jobs'/build.TAG/site/'plan/record.json'
        cfg=read(planfile)['config']
        outline=[dict(tab=t['title'],components=[n.get('title') or n.get('label') or n['type'] for n in t['body']]) for t in cfg['body'][0]['tabs']]
        msg=core.messages(PROMPT,dict(brief=briefs[site],tabs=outline,format_example=build.EXAMPLE | {
            'coverage':[dict(quote='reserve credits',scope='local',reason='Reserving moves available credits into a local reservation.',control='Reserve two')]}))
        for i in range(2):
            try:
                raw=build.main.gen.call(ledger,build.TAG,dest/str(i),msg,'plan',5800)
                spec=build.main.gen.parse(raw)
                validate(spec,briefs[site])
                variants={a:build.pages.page(build.compile_updates(cfg,spec,a=='active'),'human') for a in ('active','inert')}
                pages={a:build.pages.write_html(GEN/'sites'/site/a,html) for a,html in variants.items()}
                core.save(dest/'extension.json',spec)
                break
            except build.main.gen.MISSING as exc:
                pages={a:dict(status='missing',reason=str(exc)) for a in ('active','inert')}
                break
            except (AttributeError,*build.main.gen.ERRORS) as exc:
                pages={a:dict(status='invalid',reason=str(exc)[:200]) for a in ('active','inert')}
                msg += [dict(role='assistant',content=raw),dict(role='user',content='Public format check: '+str(exc)[:180]+'. Return the complete corrected JSON.')]
        core.save(file,pages)
        return pages
    with patch.multiple(build.main.gen.BASE,OUT=GEN,END=build.main.END,template=build.main.gen.settings),ThreadPoolExecutor(max_workers=4) as pool:
        rows=dict(zip(SITES,pool.map(one,SITES),strict=True))
    specs={s:read(GEN/'plans'/s/'extension.json') for s in SITES if rows[s]['active']['status']=='valid'}
    seal=dict(registration=sha(reg),rows=rows,extensions=specs)
    core.save(GEN/'seal.json',seal)
    replay={}
    for s,spec in specs.items():
        replay[s]={}
        for a,v in rows[s].items():
            html=(ROOT/v['file']).read_text()
            replay[s][a]=build.evaluate.browser_job(lambda engine:observe(engine,html,spec))
    core.save(PAGES,seal|dict(seal=sha(GEN/'seal.json'),behavior=replay,cost=ledger_read.totals(GEN/'budget.sqlite3')))


def evaluate():
    import duckdb
    candidate=read(PAGES)
    assert candidate['seal']==sha(GEN/'seal.json') and candidate['rows']==read(GEN/'seal.json')['rows']
    reg=register(JUDGE,JUDGE_CAP,[Path(__file__),build.HERE/'ACTION_PLAN.md',PAGES,build.main.gen.SRC,earlier.primary.OUT/'calibration.json'])
    if RESULT.exists():
        return
    route=read(earlier.primary.OUT/'calibration.json')
    assert route['qualified']
    ops=duckdb.sql('select id, ui_instruct from read_parquet(?) where id in (select unnest(?))',
                   params=[str(build.main.gen.SRC),list(build.SITES)]).fetchall()
    tasks={(s,i):{k:x[k] for k in ('task','expected_result')} for s,cs in ops for i,x in enumerate(cs)}
    ledger=Ledger(JUDGE/'budget.sqlite3',JUDGE_CAP,JUDGE_CAP)
    jobs=[(s,i,a) for s,i in tasks for a in ('active','inert')]
    jobs.sort(key=lambda item:hashlib.sha256('/'.join(map(str,item)).encode()).digest())
    def grade(job):
        s,i,a=job
        page=candidate['rows'][s][a]
        base=dict(site=s,check=i,arm=a,verdict=None)
        if page['status']!='valid':
            return base|dict(status='start_failed' if page['status']=='invalid' else page['status'])
        f=ROOT/page['file']
        assert sha(f)==page['sha256']
        dest=JUDGE/'checks'/s/str(i)/a
        same=read(build.CANDIDATES)['rows'][s][a]
        previous=earlier.OUT/'checks'/s/str(i)/a/'judgment.json'
        if same.get('sha256')==page['sha256'] and previous.exists():
            val=read(previous)
            return base|dict(status=val['status'],verdict=val['verdict'],source=sha(previous),reused=str(previous.relative_to(ROOT)))
        val=build.evaluate.browser_job(lambda eng:build.evaluate.journey(ledger,route['model'],f.read_text(),True,tasks[s,i],dest,eng))
        return base|dict(status=val['status'],verdict=val['verdict'],reason=val.get('reason'),source=sha(dest/'judgment.json'))
    with patch.multiple(earlier.primary.api,OUT=JUDGE,END=build.main.END),patch.dict(earlier.primary.api.PRICES,{earlier.primary.api.ALTERNATE:(.15,.6)}),ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(grade,jobs))
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(PAGES),judge=route['model'],rows=rows,cost=ledger_read.totals(JUDGE/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('generate','evaluate'))
    phase=parser.parse_args().phase
    with browser.lock((GEN if phase=='generate' else JUDGE)/'run.lock'):
        (generate if phase=='generate' else evaluate)()
