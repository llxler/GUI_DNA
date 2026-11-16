"""Prepare, generate or score a separate one-repeat frontier cohort."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import argparse
from gui_dna.budget import Ledger
from gui_dna.provider import ProviderError
from test.streaming_provider_v2 import StreamingOpenRouter
from test.ledger_read import totals
from test.history_replay.run import ROOT,read,dump,sha,digest,now
from .adapt import HERE,OUT,configured,configuration,verify


def prepare():
    with configured() as modules:
        modules[2].prepare()
    paths=[ROOT/'test/matched_feedback'/name for name in ('__init__.py','core.py','browser.py','prepare.py','run.py','evaluate.py','PROTOCOL.md')]
    dump(OUT/'shared-dependencies.json',{'frozen_utc':now(),'sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
        'scope':'Shared frozen functions; frontier adapter only changes explicitly declared paths/model/configuration/repeat count.'})


def generate():
    previous=totals(ROOT/'artifacts/matched-feedback-20261116/budget.sqlite3')
    assert previous['stop_usd']==0 and (ROOT/'artifacts/matched-feedback-20261116/generation-complete.json').exists()
    allocation=read(ROOT/'artifacts/review-20261116/budget-plan.json')['stages'][OUT.name]
    assert allocation=={'cap':3.5,'stop':3.2}
    credit=read(ROOT/'artifacts/review-20261116/credits-before-frontier.json')
    assert credit['effective_remaining_usd']>=3.5
    with configured() as modules:
        verify();core,_,_,shared_run,_,_=modules
        assert not (OUT/'generation-started.json').exists()
        ledger=Ledger(OUT/'budget.sqlite3',3.5,3.2)
        original=StreamingOpenRouter(configuration(),ledger)
        class DeadlineClient:
            def call(self,*args,**kwargs):
                if datetime.now(timezone.utc)>=datetime.fromisoformat('2026-11-16T06:00:00+00:00'):
                    raise ProviderError('Frontier admission deadline reached; no request sent')
                return original.call(*args,**kwargs)
        client=DeadlineClient()
        dump(OUT/'generation-started.json',{'started_utc':now(),'snapshot_sha256':sha(OUT/'snapshot.json'),
            'shared_dependencies_sha256':sha(OUT/'shared-dependencies.json')})
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                records=list(pool.map(lambda j:shared_run.one(client,j),core.jobs()))
        finally:Ledger(OUT/'budget.sqlite3',3.5,0.)
        assert len(records)==15 and all(r['status']=='complete' for r in records),'Incomplete frontier chain; no hidden scoring'
        paths=[p for p in (OUT/'runs').rglob('*') if p.is_file()]
        dump(OUT/'candidate-snapshot.json',{'finished_utc':now(),'sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths}})
        dump(OUT/'generation-complete.json',{'finished_utc':now(),'candidates':len(records),'records_sha256':digest(records),
            'candidate_snapshot_sha256':sha(OUT/'candidate-snapshot.json')})


def evaluate():
    with configured() as modules:
        verify();modules[4].main()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','generate','evaluate'])
    globals()[parser.parse_args().phase]()
