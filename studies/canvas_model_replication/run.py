"""Independent model replication on the original matched canvas project."""
import argparse
from decimal import Decimal
from pathlib import Path
import shutil
from studies.canvas_capacity.controls import run_probes
from studies.ledger_read import totals
from studies.matched_canvas import analyze, browser, evaluate, run
from studies.study_io import ROOT, dump, now, read, sha

HERE = Path(__file__).resolve().parent
STAGE = 'canvas-sonnet-20261118'
OUT = ROOT/'artifacts'/STAGE
RESULT = ROOT/'studies/results'/f'{STAGE}.json'
BASE = browser.OUT
MODEL = 'anthropic/claude-sonnet-4.5'
LIMIT = 3


def configure():
    spec = OUT/'budget-plan.json'
    if not spec.exists():
        bills = {}
        for stage in ('matched-canvas-20261118','canvas-capacity-20261118','matched-flex-20261118'):
            for arm,rep in run.GROUPS:
                group = ROOT/'artifacts'/stage/f'{arm}-{rep}'
                assert (group/'complete.json').exists()
                cost = totals(group/'budget.sqlite3')
                assert cost['stop_usd'] == 0
                bills[f'{stage}/{arm}-{rep}'] = cost['exposure_usd']
        credit = read(OUT/'credits.json')
        assert credit['sufficient'] and credit['effective_remaining_usd'] >= 4*LIMIT
        assert sum(Decimal(str(v)) for v in bills.values()) + 4*LIMIT <= 20
        dump(spec,{'prior_exposure_usd':bills, 'cap_per_group':LIMIT, 'credits_sha256':sha(OUT/'credits.json')})
    for name in ('calibration','harness','controls'):
        if not (OUT/name).exists():
            (OUT/name).symlink_to(BASE/name,target_is_directory=True)
    if not (OUT/'calibration.json').exists():
        shutil.copyfile(BASE/'calibration.json',OUT/'calibration.json')
    paths = [HERE/'PROTOCOL.md', HERE/'run.py', spec, OUT/'credits.json', BASE/'protocol-freeze.json']
    snapshot = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    if (OUT/'extension.json').exists():
        assert read(OUT/'extension.json')['sha256'] == snapshot
    else:
        dump(OUT/'extension.json',{'utc':now(),'sha256':snapshot})
    for module in (run, browser, evaluate, analyze):
        module.OUT = OUT
    run.MODEL = analyze.MODEL = MODEL
    run.CONFIG = analyze.CONFIG = {'models':[MODEL], 'max_tokens':32000, 'temperature':0.6,
        'price_caps_per_million':{'prompt':3,'completion':15},'provider_order':{MODEL:['Anthropic']}}
    run.LIMIT = analyze.LIMIT = LIMIT


def main(action):
    configure()
    if action == 'generate':
        run.main()
    elif action == 'score':
        evaluate.evaluate()
    elif action == 'controls':
        run_probes(OUT,STAGE)
    else:
        result = analyze.reconstruct()
        result.update(extension_sha256=sha(OUT/'extension.json'),scope='Independent Claude Sonnet 4.5 replication on canvas with matched public information and spending cap.')
        dump(RESULT,result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['generate','score','analyze','controls'])
    main(parser.parse_args().action)
