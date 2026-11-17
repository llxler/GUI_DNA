"""Continue only missing requests in a separate directory and closed-budget ledger."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import argparse
import shutil

from gui_dna.budget import Ledger
from gui_dna.provider import ProviderError
from test.streaming_provider_v2 import StreamingOpenRouter
from test.ledger_read import calls,totals
from studies.study_io import ROOT,read,dump,sha,digest,now
from test.matched_feedback_frontier import adapt

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/matched-feedback-frontier-continue-20261116'
PREVIOUS=adapt.OUT


def allocation():
    return read(ROOT/'artifacts/review-20261116/budget-plan.json')['stages'][OUT.name]


def configuration():
    value=adapt.configuration();limits=allocation()
    value.update(budget_usd=limits['cap'],stop_new_requests_usd=limits['stop'])
    return value


@contextmanager
def configured():
    with adapt.configured() as modules:
        changes=[]
        for module in modules:
            for name,value in [('OUT',OUT),('configuration',configuration)]:
                if hasattr(module,name):
                    changes.append((module,name,getattr(module,name)));setattr(module,name,value)
        try:yield modules
        finally:
            for module,name,old in reversed(changes):setattr(module,name,old)


def verify():
    for path,expected in read(OUT/'snapshot.json')['sha256'].items():assert sha(ROOT/path)==expected,path


class ReplayClient:
    def __init__(self,client,previous_calls):
        self.client=client;self.previous_calls={row['id']:row for row in previous_calls}

    def call(self,model,messages,folder,purpose,seed=None):
        folder=Path(folder);request=folder/'request.json';response=folder/'response.json'
        if request.exists():
            saved=read(request);entry=self.previous_calls[saved['call_id']]
            assert entry['actual'] is not None and response.exists(),'Uncertain request cannot be silently repeated'
            assert saved['body']['model']==model and saved['body']['messages']==messages,'Replay input changed'
            assert saved['body'].get('seed') is None and saved['body'].get('temperature') is None
            return read(response)['choices'][0]['message']['content']
        assert not response.exists()
        if datetime.now(timezone.utc)>=datetime.fromisoformat('2026-11-16T06:00:00+00:00'):
            raise ProviderError('Continuation admission deadline reached; no request sent')
        return self.client.call(model,messages,folder,purpose,seed=seed)


def prepare():
    old=totals(PREVIOUS/'budget.sqlite3')
    assert old['stop_usd']==0 and old['unsettled_calls']==0
    assert not (PREVIOUS/'generation-complete.json').exists() and not (PREVIOUS/'grading-started.json').exists()
    assert not OUT.exists()
    credit=read(ROOT/'artifacts/review-20261116/credits-before-frontier-continue.json');limits=allocation()
    assert 0<limits['stop']<=limits['cap']<=credit['effective_remaining_usd']
    old_files=[p for p in PREVIOUS.rglob('*') if p.is_file() and not p.is_symlink() and 'node_modules' not in p.parts]
    shutil.copytree(PREVIOUS,OUT,symlinks=True,ignore=shutil.ignore_patterns('budget.sqlite3','budget.sqlite3-wal','budget.sqlite3-shm','generation-started.json','snapshot.json'))
    # Only the derived input index changes paths; original reports/requests remain byte-identical.
    def relocate(value):
        if isinstance(value,str):return value.replace(str(PREVIOUS.relative_to(ROOT)),str(OUT.relative_to(ROOT)))
        if isinstance(value,list):return [relocate(v) for v in value]
        if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
        return value
    dump(OUT/'inputs.json',relocate(read(PREVIOUS/'inputs.json')))
    incomplete=[]
    for path in (OUT/'runs').rglob('record.json'):
        record=read(path)
        if record['status']!='complete':
            assert record['status']=='transport_or_budget_incomplete'
            path.rename(path.with_name('record-before-continuation.json'));incomplete.append(str(path.relative_to(ROOT)))
    assert incomplete
    dump(OUT/'continuation.json',{'created_utc':now(),'previous_stage':str(PREVIOUS.relative_to(ROOT)),
        'prior_ledgers':[str((PREVIOUS/'budget.sqlite3').relative_to(ROOT))],'incomplete_records':sorted(incomplete),
        'previous_cost':old,'allocation':limits,'workers':1,
        'scope':'Unchanged protocol, only missing budget-blocked requests; copied originals retained, complete chains not regenerated.'})
    paths=old_files+[p for p in HERE.iterdir() if p.name in ('run.py','PROTOCOL.md','__init__.py')]
    paths += [p for p in OUT.rglob('*') if p.is_file() and not p.is_symlink() and 'node_modules' not in p.parts and p.name!='record.json']
    paths += [ROOT/'test/matched_feedback_frontier/adapt.py',ROOT/'test/matched_feedback/run.py',ROOT/'test/matched_feedback/evaluate.py']
    frozen=dict(read(PREVIOUS/'snapshot.json')['sha256'])
    frozen.update({str(p.relative_to(ROOT)):sha(p) for p in paths})
    dump(OUT/'snapshot.json',{'frozen_utc':now(),'sha256':frozen})
    print('Prepared unchanged continuation:',len(incomplete),'incomplete chains',flush=True)


def generate():
    verify();assert not (OUT/'generation-started.json').exists()
    limits=allocation();ledger=Ledger(OUT/'budget.sqlite3',limits['cap'],limits['stop'])
    try:
        client=ReplayClient(StreamingOpenRouter(configuration(),ledger),calls(PREVIOUS/'budget.sqlite3'))
        dump(OUT/'generation-started.json',{'started_utc':now(),'snapshot_sha256':sha(OUT/'snapshot.json')})
        records=[]
        with configured() as modules:
            core,_,_,runner,_,_=modules
            for job in core.jobs():
                path=ROOT/job['folder']/'record.json'
                records.append(read(path) if path.exists() else runner.one(client,job))
    finally:Ledger(OUT/'budget.sqlite3',limits['cap'],0.)
    verify()
    assert len(records)==15 and all(r['status']=='complete' for r in records),'Continuation incomplete; no hidden scoring'
    paths=[p for p in (OUT/'runs').rglob('*') if p.is_file()]
    dump(OUT/'candidate-snapshot.json',{'finished_utc':now(),'sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths}})
    dump(OUT/'generation-complete.json',{'finished_utc':now(),'candidates':len(records),'records_sha256':digest(records),
        'candidate_snapshot_sha256':sha(OUT/'candidate-snapshot.json')})


def evaluate():
    verify()
    with configured() as modules:modules[4].main()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','generate','evaluate'])
    globals()[parser.parse_args().phase]()
