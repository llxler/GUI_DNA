"""Complete only missing independent judgments on the published Direct/Human pair."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import sdk_navigation as navigation

main=navigation.main
HERE=main.gen.HERE
OUT=ROOT/'artifacts/webgen-rater-completion-20261128'
RESULT=HERE/'independent-completion.json'
CAP=4.50


def prior_upper():
    """Use each live stage's whole cap until its immutable final receipt exists."""
    from . import report
    nav=ROOT/'studies/webbench/table/keyboard_navigation'
    entries=[(n,p) for n,p in (
        ('webgen-site-completion',report.CANDIDATES),('webgen-site-completion-judge',report.JUDGMENTS),
        ('webgen-native-state',report.STATE/'candidates.json'),('webgen-native-state-judge',report.STATE/'judgments.json'),
        ('webgen-grounded-actions',report.STATE/'grounded-candidates.json'),('webgen-grounded-actions-judge',report.STATE/'grounded-judgments.json'),
        ('webgen-state-program-judge',report.STATE/'program-judgments.json'),('webgen-independent-flash',report.SECOND),
        ('webgen-native-tabs',report.TAB_VERDICTS),('webgen-vertical-primary',report.VERTICAL),('webgen-vertical-secondary',report.VERTICAL_SECOND),
        ('table-keyboard-navigation',nav/'result.json'),('table-membership-projection',nav/'projection-result.json'))]
    upper=0
    for name,file in entries:
        amounts=ledger_read.totals(ROOT/'artifacts'/(name+'-20261128')/'budget.sqlite3')
        upper+=round(amounts['exposure_usd' if file.exists() else 'cap_usd']*1e6)
    return upper/1e6


def score():
    import duckdb
    first=navigation.second_judge.RESULT
    revision=navigation.RESULTS['secondary']
    reg=OUT/'registration.json'
    while not reg.exists() and (not first.exists() or not revision.exists() or prior_upper()+CAP>20):
        if datetime.now(timezone.utc)>=main.gen.END:
            raise TimeoutError('Unable to reserve a complete independent audit within deadline')
        time.sleep(15)
    a,b=read(first),read(revision)
    assert a['model']==b['judge'] and a['calibration']['qualified'] and b['candidates']==sha(navigation.tab_layout.PAGES)
    sources=[Path(__file__),HERE/'RATER_COMPLETION.md',first,revision,navigation.tab_layout.PAGES,main.gen.CANDIDATES,
             main.gen.gen.SRC,Path(main.evaluator.__file__),Path(main.api.__file__)]
    sums={str(p.relative_to(ROOT)):sha(p) for p in sources}
    initial=[r for r in a['rows'] if r['arm']=='direct']+b['rows']
    assert len(initial)==18 and len({(r['site'],r['arm']) for r in initial})==18
    missing=[(r['site'],r['check'],r['arm']) for r in initial if r['status']!='judged']
    if not reg.exists():
        bound=prior_upper()
        balance=check_credits(CAP)
        assert bound+CAP<=20 and balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=main.gen.END.isoformat(),sources=sums,model=a['model'],cap=CAP,balance=balance,
                           previous_upper=bound,scheduled=[list(x) for x in sorted(missing)]))
    assert read(reg)['sources']==sums and read(reg)['scheduled']==[list(x) for x in sorted(missing)]
    if RESULT.exists():
        return
    raw=duckdb.sql('select id,ui_instruct from read_parquet(?) where id in (select unnest(?))',
                   params=[str(main.gen.gen.SRC),list(a['subset'])]).fetchall()
    checks={s:{k:ops[a['subset'][s]][k] for k in ('task','expected_result')} for s,ops in raw}
    direct=read(main.gen.CANDIDATES)['rows']['deepseek-flash']
    sdk=read(navigation.tab_layout.PAGES)['candidates']['deepseek-flash']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def grade(job):
        site,i,arm=job
        page=sdk[site]['vertical'] if arm=='human' else direct[site]['direct']
        f=ROOT/page['file'];assert sha(f)==page['sha256'] and a['subset'][site]==i
        dest=OUT/'checks'/site/arm
        verdict=main.evaluator.browser_job(lambda engine:main.evaluator.journey(ledger,a['model'],f.read_text(),arm=='human',checks[site],dest,engine))
        return dict(site=site,check=i,arm=arm,status=verdict['status'],verdict=verdict['verdict'],reason=verdict.get('reason'),source=sha(dest/'judgment.json'))
    missing.sort(key=lambda job:hashlib.sha256('/'.join(map(str,job)).encode()).digest())
    with patch.multiple(main.api,OUT=OUT,END=main.gen.END),patch.dict(main.api.PRICES,{a['model']:(.15,.6)}),ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(grade,missing))
    core.save(RESULT,dict(registration=sha(reg),direct_judgments=sha(first),human_judgments=sha(revision),model=a['model'],
                          subset=a['subset'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        score()
