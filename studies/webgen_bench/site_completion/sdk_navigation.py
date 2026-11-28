"""Re-evaluate every SDK page after making its tabs reachable in the fixed viewport."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import evaluate as main,second_judge,tab_layout

HERE=main.gen.HERE
BUDGETS={'primary':2.50,'secondary':.90}
FOLDERS={k:ROOT/'artifacts'/('webgen-vertical-'+k+'-20261128') for k in BUDGETS}
RESULTS={k:HERE/('vertical-'+k+'.json') for k in BUDGETS}


def evaluate(phase):
    import duckdb
    out=FOLDERS[phase];result=RESULTS[phase];cap=BUDGETS[phase]
    original=read(main.gen.CANDIDATES)
    layouts=read(tab_layout.PAGES)
    assert layouts['original']==sha(main.gen.CANDIDATES)
    sites=sorted(original['rows']['deepseek-flash'])
    models=list(original['rows']) if phase=='primary' else ['deepseek-flash']
    control=main.OUT/'calibration.json'
    if phase=='primary':
        cal=read(control)
        assert cal['qualified']
        model=cal['model']
    else:
        model=second_judge.MODEL
        working=second_judge.OUT/'calibration'/model.split('/')[-1]/'working/judgment.json'
        inert=working.parents[1]/'inert/judgment.json'
        assert read(working)['verdict']=='YES' and read(inert)['verdict']=='NO'
    endpoint=read(main.OUT/'registration.json') if phase=='primary' else read(second_judge.OUT/'registration.json')
    assert endpoint.get('alternate_price_routes') or endpoint.get('routes')
    sources=[Path(__file__),HERE/'SDK_NAVIGATION.md',tab_layout.PAGES,main.gen.CANDIDATES,main.gen.gen.SRC,
             Path(main.evaluator.__file__),Path(main.api.__file__)]
    sources += [control] if phase=='primary' else [working,inert,second_judge.OUT/'registration.json']
    fingerprints={str(f.relative_to(ROOT)):sha(f) for f in sources}
    reg=out/'registration.json'
    if not reg.exists():
        closed=sum(ledger_read.totals(ROOT/'artifacts'/(n+'-20261128')/'budget.sqlite3')['exposure_usd'] for n in (
            'webgen-site-completion','webgen-native-state','webgen-native-state-judge','webgen-grounded-actions',
            'webgen-grounded-actions-judge','webgen-native-tabs'))
        assert closed+11.5+1.30+1.+.20+.20+sum(BUDGETS.values())<=20
        balance=check_credits(cap)
        assert balance['sufficient'] and datetime.now(timezone.utc)<main.gen.END
        core.save(reg,dict(utc=now(),deadline=main.gen.END.isoformat(),sources=fingerprints,model=model,sites=sites,
                           models=models,cap=cap,balance=balance,closed_exposure=closed))
    assert read(reg)['sources']==fingerprints
    if result.exists():
        return
    raw=duckdb.sql('select id,ui_instruct from read_parquet(?) where id in (select unnest(?))',
                   params=[str(main.gen.gen.SRC),sites]).fetchall()
    subset=read(second_judge.OUT/'registration.json')['subset'] if phase=='secondary' else {}
    tasks={(s,i):{k:c[k] for k in ('task','expected_result')} for s,cs in raw for i,c in enumerate(cs)
           if not subset or i==subset[s]}
    jobs=[(tag,s,i) for s,i in tasks for tag in models]
    jobs.sort(key=lambda j:hashlib.sha256('/'.join(map(str,j)).encode()).digest())
    ledger=Ledger(out/'budget.sqlite3',cap,cap)
    def grade(job):
        tag,s,i=job
        page=layouts['candidates'][tag][s]['vertical']
        assert layouts['candidates'][tag][s]['horizontal']['sha256']==original['rows'][tag][s]['human']['sha256']
        file=ROOT/page['file']
        assert sha(file)==page['sha256']
        dest=out/'checks'/tag/s/str(i)
        if (dest/'judgment.json').exists():
            verdict=read(dest/'judgment.json')
        else:
            verdict=main.evaluator.browser_job(lambda eng:main.evaluator.journey(ledger,model,file.read_text(),True,tasks[s,i],dest,eng))
        return dict(model=tag,site=s,check=i,arm='human',status=verdict['status'],verdict=verdict['verdict'],
                    reason=verdict.get('reason'),source=sha(dest/'judgment.json'))
    with patch.multiple(main.api,OUT=out,END=main.gen.END),patch.dict(main.api.PRICES,{model:(.15,.6)}),ThreadPoolExecutor(max_workers=3 if phase=='primary' else 2) as pool:
        rows=list(pool.map(grade,jobs))
    core.save(result,dict(registration=sha(reg),candidates=sha(tab_layout.PAGES),original_candidates=sha(main.gen.CANDIDATES),
                          judge=model,phase=phase,rows=rows,cost=ledger_read.totals(out/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=BUDGETS)
    phase=parser.parse_args().phase
    with browser.lock(FOLDERS[phase]/'run.lock'):
        evaluate(phase)
