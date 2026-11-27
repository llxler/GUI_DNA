"""Measure the effect of handing truncated direct documents to the native HTML parser."""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ...component_contracts import evaluate as first, report
from ...functional_pilot import evaluate as evaluator, generate as gen

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/webgen-native-html-20261127'
PAGES = HERE/'candidates.json'
RESULT = HERE/'judgments.json'
SOURCE = {'development': gen.OUT, 'holdout': first.run.OUT}
START = re.compile(r'<!doctype\s+html\b|<html(?:\s|>)', re.I)


def prepare():
    cohort, rows = report.website_groups()
    errors = {(r['batch'], r['model'], r['site'], r['arm']) for r in rows if r['status'] == 'start_failed'}
    assert errors == {('development','qwen9','000011','direct'), ('holdout','qwen9','000085','direct')}
    sources = [Path(__file__), HERE/'PROTOCOL.md', gen.SRC, Path(evaluator.__file__), Path(first.api.__file__)]
    records = {}
    for batch, tag, site, arm in sorted(errors):
        control = cohort['cohorts'][batch]['qwen/qwen3.5-9b']['sources']['direct']
        root = SOURCE[batch]/'jobs'/tag/site/arm
        sources.extend([ROOT/control['candidates'], ROOT/control['judgments'], root/'record.json'])
        assert read(root/'record.json')['reason'] == 'Expected a complete HTML document'
        trials = []
        for index in (0,1):
            request = root/str(index)/'transmission-1/request.json'
            response = request.with_name('response.json')
            settled = request.with_name('settled.json')
            sources.extend([request, response, settled])
            assert read(settled)['response_sha256'] == sha(response)
            res = read(response)
            choice = res['choices'][0]
            raw = choice['message']['content']
            match = START.search(raw)
            trial = dict(attempt=index, response_sha256=sha(response), finish_reason=choice['finish_reason'],
                         length=len(raw), tokens=res['usage']['completion_tokens'], found=bool(match))
            if match:
                html = raw[match.start():]
                path = OUT/batch/site/str(index)/'index.html'
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_bytes(html.encode('utf-8'))
                assert path.read_bytes() == html.encode('utf-8')
                trial.update(html=str(path.relative_to(ROOT)), sha256=sha(path))
            trials.append(trial)
        assert trials[0]['found']
        records[batch] = dict(model=tag, site=site, method=arm, evaluated_attempt=0, original=control, attempts=trials)
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not PAGES.exists():
        core.save(PAGES, dict(utc=now(), records=records, sources=hashes))
    assert read(PAGES)['sources'] == hashes and read(PAGES)['records'] == records


def score():
    import duckdb
    prepare()
    if RESULT.exists():
        return
    previous = HERE.parent/'secondary-completion.json'
    assert previous.is_file(), 'The independent rater ledger is still active'
    sums = [ledger_read.totals(ROOT/'artifacts'/(name+'-20261127')/'budget.sqlite3')['exposure_usd']
            for key,name in report.LEDGERS.items() if key.endswith('_judge') and name != 'webgen-native-html']
    cap = min(.72, round(5.75 - sum(sums), 6))
    assert cap > 0
    reg = OUT/'judge-registration.json'
    if not reg.exists():
        balance = check_credits(cap)
        assert balance['sufficient']
        core.save(reg, dict(utc=now(), deadline=first.run.END.isoformat(), cap=cap, balance=balance,
                            candidates=sha(PAGES), closed_secondary=sha(previous), previous_exposure=round(sum(sums),6)))
    assert read(reg)['candidates'] == sha(PAGES) and read(reg)['cap'] == cap
    ledger = Ledger(OUT/'budget.sqlite3',cap,cap)
    model = first.api.ALTERNATE
    with patch.multiple(first.api, OUT=OUT, END=first.run.END), patch.object(first,'OUT',OUT):
        route = first.calibrate(ledger,model)
        data = dict(duckdb.sql('select id, ui_instruct from read_parquet(?)', params=[str(gen.SRC)]).fetchall())
        jobs = []
        for batch,record in read(PAGES)['records'].items():
            site = record['site']
            trial = record['attempts'][0]
            path = ROOT/trial['html']
            assert sha(path) == trial['sha256']
            for index,raw in enumerate(data[site]):
                jobs.append((batch,site,index,path,{k:raw[k] for k in ('task','expected_result')}))
        def grade(job):
            batch,site,index,path,task = job
            dest = OUT/'checks'/batch/str(index)
            if route['qualified']:
                answer = evaluator.browser_job(lambda engine: evaluator.journey(ledger,model,path.read_text(),False,task,dest,engine))
                receipt = sha(dest/'judgment.json')
            else:
                answer = dict(status='missing', verdict=None, reason='Calibration failed')
                receipt = None
            return dict(batch=batch,site=site,check=index,status=answer['status'],verdict=answer['verdict'],
                        reason=answer.get('reason'),source=receipt)
        with ThreadPoolExecutor(max_workers=2) as workers:
            rows = list(workers.map(grade,jobs))
    assert Counter(r['batch'] for r in rows) == {'development':9, 'holdout':7}
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(PAGES),model=model,calibration=route,rows=rows,
                          cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','score'))
    arg = parser.parse_args().action
    with browser.lock(OUT/'run.lock'):
        if arg == 'prepare':
            prepare()
        else:
            score()
