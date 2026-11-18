"""Run the independent static-layout replication with the frozen workflow implementation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import shutil

from studies import browser_jobs
from studies.ledger_read import totals
from studies.matched_canvas import analyze, evaluate, run
from studies.study_io import ROOT, UPSTREAM, dump, now, read, sha, source_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/matched-flex-20261118'
PROJECT = UPSTREAM / 'projects/flex'
PUBLIC = OUT / 'public/flex'
RESULT = ROOT / 'studies/results/matched-flex-20261118.json'
PRIOR = ('matched-canvas-20261118', 'canvas-capacity-20261118')


def score(page, task, key, calibration=False):
    assert task in run.TASKS
    browser_jobs.OUT = OUT
    job = {'harness':'157-flex', 'runtime':'157','page':str(page.relative_to(ROOT)),
           'files':source_files(page),'specs':[task]}
    result = browser_jobs.grade(key,job,calibration)
    assert set(result['tests']) == {task}
    return {'passed':result['all_passed'],'report_sha256':result['report_sha256']}


def calibrate():
    browser_jobs.OUT = OUT
    browser_jobs.prepare_harness('expansion','flex')
    reference = OUT/'controls/reference'
    blank = OUT/'controls/blank'
    if not reference.exists():
        shutil.copytree(PROJECT/'src',reference)
    assert source_files(reference) == source_files(PROJECT/'src')
    blank.mkdir(parents=True,exist_ok=True)
    (blank/'index.html').write_text('<!doctype html><title>Blank</title>')
    def one(item):
        page, task = item
        key = page.name+'/'+task
        return key,score(page,task,key,calibration=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(one,[(p,t) for t in run.TASKS for p in (reference,blank)]))
    dump(OUT/'calibration.json',results)


def budget():
    cap_file = OUT/'budget-plan.json'
    if cap_file.exists():
        return read(cap_file)['cap']
    prior = {}
    for stage in PRIOR:
        for arm,rep in run.GROUPS:
            path = ROOT/'artifacts'/stage/f'{arm}-{rep}'/'budget.sqlite3'
            value = totals(path)
            assert value['stop_usd'] == 0 and (path.parent/'complete.json').exists()
            prior[f'{stage}/{arm}-{rep}'] = value['exposure_usd']
    credits = read(OUT/'credits.json')
    exposure = sum(Decimal(str(value)) for value in prior.values())
    room = min(Decimal(20)-exposure,Decimal(str(credits['effective_remaining_usd'])))
    cap = min(Decimal(4),(room/4).quantize(Decimal('.01'),rounding=ROUND_FLOOR))
    assert credits['sufficient'] and cap >= 2 and exposure+4*cap <= 20
    dump(cap_file,{'cap':float(cap),'prior_exposure_usd':prior,'credits_sha256':sha(OUT/'credits.json')})
    return float(cap)


def configure():
    assert not (PROJECT/'assets').exists()
    (PUBLIC/'assets').mkdir(parents=True,exist_ok=True)
    tasks = PUBLIC/'tasks.jsonl'
    if not tasks.exists():
        shutil.copyfile(PROJECT/'tasks.jsonl',tasks)
    assert sha(tasks) == sha(PROJECT/'tasks.jsonl') and not any((PUBLIC/'assets').iterdir())
    calibration = read(OUT/'calibration.json')
    assert all(calibration['reference/'+t]['passed'] and not calibration['blank/'+t]['passed'] for t in run.TASKS)
    for module in (run, evaluate, analyze):
        module.OUT = OUT
    run.PROJECT = PUBLIC
    # The original asset copy function is specific to canvas. Flex has no bundled assets.
    run.add_assets = lambda page: None
    evaluate.score = score
    run.CONFIG = {**run.CONFIG,'max_tokens':32000}
    analyze.CONFIG = run.CONFIG
    analyze.LIMIT = run.LIMIT = budget()
    paths = [HERE/'run.py',HERE/'PROTOCOL.md',OUT/'budget-plan.json',OUT/'credits.json']
    paths.extend(p for p in PROJECT.rglob('*') if p.is_file())
    manifest = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    frozen = OUT/'extension.json'
    if frozen.exists():
        assert read(frozen)['sha256'] == manifest
    else:
        dump(frozen,{'utc':now(),'sha256':manifest})


def main(action):
    if action == 'calibrate':
        calibrate()
        return
    configure()
    if action == 'generate':
        run.main()
    elif action == 'score':
        evaluate.evaluate()
    else:
        result = analyze.reconstruct()
        result.update(project='flex', scope='Independent responsive-layout replication with matched public requirements and spending caps.',
                      extension_sha256=sha(OUT/'extension.json'))
        dump(RESULT,result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['calibrate','generate','score','analyze'])
    main(parser.parse_args().action)
