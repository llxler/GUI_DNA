"""Propagate an incomplete fresh foundation through the locked pipeline without imputation."""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import read,sha,now
from . import run,bounded


def gate(mod,previous,fn):
    def apply(tag,rep,pub,ledger):
        f=run.OUT/previous/tag/rep/'library.json'
        record=read(f)
        missing=sorted(set(run.parent.build.ACTIONS)-set(record.get('functions',{})))
        if not missing:return fn(tag,rep,pub,ledger)
        dest=mod.OUT/tag/rep/'library.json'
        core.save(dest,dict(tag=tag,rep=rep,status='build_failed',reason='Incomplete predecessor action set',
            predecessor_sha256=sha(f),missing=missing,public=[],functions=record.get('functions',{})))
        return read(dest)
    return apply


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(run.OUT/(phase+'.lock')),ExitStack() as stack:
        f=run.OUT/'incomplete-registration.json'
        evidence=dict(source=sha(Path(__file__)),public_worker=sha(Path(bounded.__file__)),registration=sha(run.OUT/'registration.json'),
            rule='The original public-action follow-up requires all fifteen functions. Carry incomplete builds forward as failed, without any new source requests or deployments. Time-bound public browser checks by 35s and 60s; retain both timeout receipts.')
        if not f.exists():core.save(f,dict(utc=now(),policy=evidence))
        assert read(f)['policy']==evidence
        for mod,name,method in [(run.feedback,'foundation','prepare'),(run.contracts,'feedback','prepare')]:
            stack.enter_context(patch.object(mod,method,gate(mod,name,getattr(mod,method))))
        bind=run.projection.bind
        checked_bind=gate(run.projection,'contracts',lambda tag,rep,pub,ledger:bind(ledger,tag,rep,pub))
        stack.enter_context(patch.object(run.projection,'bind',lambda ledger,tag,rep,pub:checked_bind(tag,rep,pub,ledger)))
        stack.enter_context(patch.object(run.parent.public,'measure',bounded.measure))
        stack.enter_context(patch.object(run.projection,'observe',lambda c:bounded.measure(run.projection.OUT,c,'range')))
        run.main(phase)
