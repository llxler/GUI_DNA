"""Run the independently budgeted extension with the exact first-batch procedure."""
import argparse
from pathlib import Path
from studies.ledger_read import totals
from studies.study_io import sha
from studies.webbench.backbone_matrix import run
from studies.public_library_transfer import browser

INITIAL = run.OUT
HERE = Path(__file__).resolve().parent
EXTRA = {'deepseek-pro': ('deepseek/deepseek-v4-pro-0813',3.5,.55,4.8),
         'deepseek-flash': ('deepseek/deepseek-v4-flash',1.5,.3,.9),
         'qwen9': ('qwen/qwen3.5-9b',1.5,.35,1.2)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','generate','score','report'))
    parser.add_argument('tag',choices=EXTRA,nargs='?')
    args=parser.parse_args()
    run.OUT=INITIAL.with_name('backbone-extension-20261124')
    browser.OUT=run.OUT
    original=run.MODELS
    run.MODELS=EXTRA
    if args.action=='register':
        claims={}
        for tag,(_,cap,*_) in original.items():
            db=INITIAL/tag/'budget.sqlite3'
            closed=INITIAL/tag/'seal.json'
            claims[tag]=totals(db)['exposure_usd'] if closed.exists() else cap
        assert sum(claims.values()) + sum(v[1] for v in EXTRA.values())<=20
        run.save(run.OUT/'approval.json',{'remaining_first_batch_liability':claims,
                     'parent_registry':sha(INITIAL/'registered.json'),
                     'sources':{p.name:sha(p) for p in (Path(__file__),HERE/'PROTOCOL.md')}})
        run.register()
    else:
        evidence=run.read(run.OUT/'approval.json')
        assert evidence['parent_registry']==sha(INITIAL/'registered.json')
        assert all(sha(HERE/p)==h for p,h in evidence['sources'].items())
        if args.action=='generate':
            run.generate(args.tag)
        else:
            from studies.webbench.backbone_matrix import report
            if args.action=='score':
                report.score_model(args.tag)
            else:
                report.OUTPUT=run.ROOT/'studies/results/backbone-extension-20261124.json'
                report.report()


if __name__=='__main__':
    main()
