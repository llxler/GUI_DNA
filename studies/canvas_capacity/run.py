"""Independent repetition of the canvas pilot with a larger symmetric output cap."""
import argparse
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import shutil
from studies.study_io import ROOT, read, dump, sha, now
from studies.ledger_read import totals
from studies.matched_canvas import analyze, browser, evaluate, run

FIRST = browser.OUT
OUT = ROOT/'artifacts/canvas-capacity-20261118'
SUMMARY = ROOT/'studies/results/canvas-capacity-20261118.json'
HERE = Path(__file__).resolve().parent


def setup():
    assert (FIRST/'generated.json').exists()
    OUT.mkdir(parents=True,exist_ok=True)
    if not (OUT/'budget-plan.json').exists():
        ledgers = {f'{arm}-{rep}':totals(FIRST/f'{arm}-{rep}/budget.sqlite3') for arm,rep in run.GROUPS}
        assert all(v['stop_usd']==0 for v in ledgers.values())
        prior = sum(Decimal(str(v['exposure_usd'])) for v in ledgers.values())
        credits = read(OUT/'credits.json')
        assert credits['sufficient']
        room = min(Decimal(str(credits['effective_remaining_usd'])),Decimal(20)-prior)
        cap = min(Decimal(4), (room/4).quantize(Decimal('.01'), rounding=ROUND_FLOOR))
        assert cap >= 2 and prior + 4*cap <= 20
        dump(OUT/'budget-plan.json',{'cap':float(cap),'prior':ledgers,'credits_sha256':sha(OUT/'credits.json')})
    for name in ('calibration','controls','harness'):
        if not (OUT/name).exists():
            (OUT/name).symlink_to(FIRST/name,target_is_directory=True)
    if not (OUT/'calibration.json').exists():
        shutil.copyfile(FIRST/'calibration.json',OUT/'calibration.json')


def configure():
    for module in (run,evaluate,analyze,browser):
        module.OUT = OUT
    run.CONFIG = {**run.CONFIG,'max_tokens':32000}
    analyze.CONFIG = run.CONFIG
    analyze.LIMIT = run.LIMIT = read(OUT/'budget-plan.json')['cap']
    analyze.RESULT = SUMMARY


def check_protocol():
    files = [HERE/'run.py',HERE/'PROTOCOL.md',OUT/'budget-plan.json',OUT/'credits.json',FIRST/'protocol-freeze.json']
    data = {str(p.relative_to(ROOT)):sha(p) for p in files}
    if (OUT/'extension.json').exists():
        assert read(OUT/'extension.json')['sha256'] == data
    else:
        dump(OUT/'extension.json',{'sha256':data,'utc':now()})


def main(action):
    setup()
    configure()
    check_protocol()
    if action=='generate':
        run.main()
    elif action=='score':
        evaluate.evaluate()
    else:
        result = analyze.reconstruct()
        result.update(capacity_protocol_sha256=sha(OUT/'extension.json'), response_token_cap=32000)
        dump(SUMMARY,result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['generate','score','analyze'])
    main(parser.parse_args().action)
