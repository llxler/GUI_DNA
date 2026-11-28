"""Ask the original GPT-5 builder to repair its menu using only a public interaction."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import Error as BrowserError

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webgen_bench.site_completion import generate as campaign
from .. import run as diagnosis

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-menu-author-repair-20261128'
RESULT = HERE / 'result.json'
CAP = .50
TAG = 'gpt5-library'
protocol = diagnosis.prior
base = campaign.gen.BASE


def register(cells):
    from studies.webgen_bench.site_completion import report
    path = OUT / 'registration.json'
    inputs = [Path(__file__), HERE/'PROTOCOL.md', Path(diagnosis.__file__), Path(base.__file__),
              Path(protocol.compact.__file__), protocol.RESULT, diagnosis.HERE/'result.json',
              protocol.OUT/'registration.json', Path(browser.__file__)]
    for cell in cells:
        inputs.extend([ROOT/cell['package'], protocol.OUT/'table'/cell['tag']/TAG/'seal.json'])
    hashes = {str(f.relative_to(ROOT)):sha(f) for f in inputs}
    if not path.exists():
        previous = 0
        for name in [*report.LEDGERS.values(),'table-keyboard-navigation','table-membership-projection']:
            db = ROOT/'artifacts'/(name+'-20261128')/'budget.sqlite3'
            if name == 'webgen-missing-verdicts':
                assert not db.exists(), 'Schedule the missing-judge replay only after this build'
                continue
            amounts = ledger_read.totals(db)
            active = name in ('webgen-site-completion-judge','webgen-vertical-primary')
            previous += round(amounts['stop_usd' if active else 'exposure_usd'] * 1e6)
        assert previous/1e6 + CAP <= 20 and datetime.now(timezone.utc) < campaign.END
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(path, dict(utc=now(), cap=CAP, previous_upper_usd=previous/1e6,
                             deadline=campaign.END.isoformat(), sources=hashes, balance=balance,
                             seeds=[2026112805,2026112806], model='openai/gpt-5'))
    assert read(path)['sources'] == hashes
    return path


def build(rep, original, observation, ledger):
    folder = OUT/rep
    path = folder/'builder.json'
    if path.exists():
        return read(path)
    files = original['files']
    messages = core.messages(
        'Repair your browser-native spreadsheet library. Use the original sources and public interaction '
        'below. Keep the configuration and all other modules unchanged. Return JSON only with keys '
        'before and after, each a literal string. The before string must occur exactly once in index.js. '
        'Make one localized replacement. Retain all existing controls and support the public sequence.',
        dict(entry=files['index.js'], menu=files['common/menu.js'],
             interaction=['Right-click a body cell and inspect the menu.',
                          'Choose Insert Row Above. Check that one row was inserted.',
                          'Reopen the menu. Right-click outside the table and check that the menu closes.'],
             observed=observation))
    try:
        reply = base.request(ledger, ('table','gpt5',rep), folder/'request', messages,'build',2300)
        change = base.parse_json(base.uncode(reply))
        before,after = change['before'],change['after']
        if not isinstance(before,str) or not isinstance(after,str) or not before.strip() or files['index.js'].count(before)!=1 or before==after:
            raise ValueError('Expected a unique literal edit to index.js')
        core.save(path,dict(status='delivered',before=before,after=after))
    except (BudgetStop,base.original.Unavailable) as exc:
        core.save(path,dict(status='missing',reason=str(exc)))
    except base.ERRORS as exc:
        core.save(path,dict(status='invalid',reason=str(exc)))
    return read(path)


def run():
    cells = read(protocol.OUT/'registration.json')['cells']
    reg = register(cells)
    if RESULT.exists():
        assert read(RESULT)['registration']==sha(reg)
        return
    assert len({sha(ROOT/c['package']) for c in cells})==1
    pkg = read(ROOT/cells[0]['package'])
    public = core.public_input('table')
    profiles = protocol.choices(pkg,TAG,'table')
    def compile_profiles(library, name):
        return [protocol.compact.compile_page('table',TAG,library,p,public,OUT/name/str(i)) for i,p in enumerate(profiles)]
    original = compile_profiles(pkg,'original')
    with patch.object(diagnosis,'OUT',OUT):
        controls = [diagnosis.public(page) for page in original]
    old = read(diagnosis.HERE/'result.json')['public']
    assert all(c==old[str(i)]['before'] for i,c in enumerate(controls))
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def settings(project,tag,phase):
        return campaign.gen.transport.settings(project,tag,phase)|{'seed':read(reg)['seeds'][0]}
    seeds = {}
    sealed = []
    publications = {v['tag']:v for v in read(protocol.RESULT)['cells']}
    with patch.multiple(base,OUT=OUT,END=campaign.END,template=settings), patch.object(diagnosis,'OUT',OUT):
        for rep in ('a','b'):
            response = build(rep,pkg,controls[0],ledger)
            seeds[rep] = dict(status=response['status'],reply=sha(OUT/rep/'builder.json'))
            if response['status']!='delivered':
                continue
            new_files = pkg['files'] | {'index.js':pkg['files']['index.js'].replace(response['before'],response['after'],1)}
            pages = compile_profiles(pkg|{'files':new_files},rep+'/profiles')
            try:
                checks = [diagnosis.public(page) for page in pages]
            except BrowserError as exc:
                checks = [{'browser_error':str(exc).splitlines()[0][:280]}]
            valid = len(checks)==len(profiles) and all(all(c.get(k) is True for k in controls[0]) for c in checks)
            seeds[rep].update(status='valid' if valid else 'build_failed',checks=checks)
            if not valid:
                continue
            for i,page in enumerate(pages):
                sealed.extend(page|dict(project='table',arm='fixed',rep=rep,tag=str(i),task=n) for n in range(1,21))
            for c in cells:
                tag = c['tag']
                seal = protocol.OUT/'table'/tag/TAG/'seal.json'
                assert sha(seal)==publications[tag]['seal_sha256']
                for r in read(seal)['rows']:
                    if r['status']=='valid':
                        slot=profiles.index(r['plan'])
                        assert r['files']==original[slot]['files']
                        r=r|pages[slot]
                    sealed.append(r|dict(tag=tag,rep=rep,arm='planned'))
    seal = OUT/'seal.json'
    core.save(seal,dict(registration=sha(reg),libraries=seeds,rows=sealed))
    old_outcomes = {(c['tag'],v['task']):v['passed'] for c in publications.values()
                    for v in c['rows'] if v['arm']==TAG}
    source = browser.verify_contract('table')
    rows=[]
    for v in browser.evaluate(sealed,OUT,{'table':source},2):
        r={key:v[key] for key in ('rep','tag','arm','task','status')}
        r.update(passed=False if v['status']=='invalid' else v.get('passed'),report_sha256=v.get('report_sha256'))
        if r['arm']=='planned':
            r['original']=old_outcomes[r['tag'],r['task']]
        rows.append(r)
    core.save(RESULT,dict(registration=sha(reg),seal=sha(seal),model=read(reg)['model'],
                          generators={c['tag']:c['model'] for c in cells},original=sha(protocol.RESULT),
                          native_controls=controls,libraries=seeds,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        run()
