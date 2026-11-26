"""Retry only the sealed questionnaire source request that lacked delivery."""
from pathlib import Path
from unittest.mock import patch
import httpx

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from .. import run as study

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/survey-transport-20261126'
CAP=.15
TAG='mistral'
TASK=20


def main():
    src=study.OUT/TAG/'targets'/str(TASK)
    original=src/'direct-call/transmission-1/request.json'
    body=read(original)['body']
    old=read(study.OUT/'seal.json')
    assert sha(src/'rows.json')==old['sources'][str((src/'rows.json').relative_to(study.OUT))]
    missing=[r for f in study.OUT.glob('*/targets/*/rows.json') for r in read(f) if r['status']=='missing']
    assert [(r['tag'],r['task'],r['arm']) for r in missing]==[(TAG,TASK,'direct')]
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(study.__file__),study.OUT/'seal.json',original,
           src/'direct-call/transmission-2/request.json',src/'rows.json']
    assert read(files[-2])['body']==body
    f=OUT/'registration.json'
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        bal=check_credits(CAP)
        assert bal['sufficient']
        core.save(f,dict(utc=now(),sources=sums,balance=bal,cap=CAP,deadline=study.action.END.isoformat()))
    assert read(f)['sources']==sums
    pub=read(study.BASE/'public.json')
    api=study.action.compact.base
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    seal=OUT/'seal.json'
    if not seal.exists():
        post=httpx.post
        def send(*args,**kwargs):
            assert kwargs['json']==body
            return post(*args,**{**kwargs,'timeout':httpx.Timeout(450,connect=25)})
        try:
            with patch.multiple(api,OUT=OUT,END=study.action.END,template=study.action.settings),patch.object(httpx,'post',send):
                raw=api.request(ledger,('table',TAG,'a'),OUT/'direct-call',core.direct_messages(pub,TASK),'plan',8192)
            try:
                val=study.receiver.first_object(raw)
                inputs=core.files_map(val['files']) if isinstance(val['files'],list) else study.validate_files(val['files'])
            except (ValueError,KeyError,TypeError,AttributeError):
                inputs={'index.html':study.document.parse_document(raw)}
            path=OUT/'page'
            result=dict(status='valid',page=str(path.relative_to(ROOT)),files=core.emit('form',{**pub['starter'],**inputs},path))
        except study.action.typed.MISSING as exc:result=dict(status='missing',reason=str(exc))
        except api.ERRORS as exc:result=dict(status='invalid',reason=str(exc)[:280])
        core.save(seal,dict(registration=sha(f),rows=[dict(project='form',task=TASK,arm='direct',tag=TAG,**result)]))
    saved=read(seal)
    assert saved['registration']==sha(f)
    harness=browser.verify_contract('form')
    assert harness==read(study.BASE/'browser.json')
    r,=browser.evaluate(saved['rows'],OUT,{'form':harness},1)
    core.save(HERE/'result.json',dict(registration=sha(f),seal=sha(seal),cost=ledger_read.totals(OUT/'budget.sqlite3'),
              rows=[dict(tag=TAG,task=TASK,arm='direct',status=r['status'],passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256'))]))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):main()
