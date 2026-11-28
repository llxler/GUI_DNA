"""Pair the two original-author requests with the archived table/document event observations."""
from datetime import datetime, timezone
from pathlib import Path
import json
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..author_repair import run as author

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/table-menu-event-trace-20261128'
RESULT = HERE/'result.json'
FIRST = author.OUT
TRACE = author.diagnosis.diagnose.RESULT
CAP = .50


def register(cells):
    path=OUT/'registration.json'
    previous=read(FIRST/'registration.json')
    assert len(cells)==5
    # Public observations and the original responses suffice even before official scoring.
    history=[FIRST/rep/'builder.json' for rep in 'ab']
    records=[Path(__file__), HERE/'PROTOCOL.md', TRACE, Path(author.__file__), FIRST/'registration.json', *history]
    sources={str(f.relative_to(ROOT)):sha(f) for f in records}
    if not path.exists():
        base=previous['previous_upper_usd']
        assert base+author.CAP+CAP<=20
        assert not (ROOT/'artifacts/webgen-missing-verdicts-20261128/registration.json').exists()
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<author.campaign.END
        core.save(path,dict(utc=now(),cap=CAP,previous_upper_usd=base+author.CAP,
                            deadline=author.campaign.END.isoformat(),sources=sources,balance=balance,
                            seeds=previous['seeds'],model=previous['model']))
    assert read(path)['sources']==sources
    return path


def run():
    original_out=author.OUT
    original_request=author.base.request
    observations=read(TRACE)['controls']
    trail=observations['0']['contextmenu']
    assert trail==[{'phase':'table','visible':True},{'phase':'document','visible':False}]
    assert all(v['contextmenu']==trail for v in observations.values())
    def request(ledger,case,folder,messages,phase,limit):
        tag=case[2]
        paths=list((original_out/tag/'request').glob('*/settled.json'))
        assert len(paths)==1
        before=read(paths[0].parent/'request.json')['body']
        assert before['messages']==messages
        extra={'role':'user','content':'One more public observation from the same body-cell right click. '
               'Menu visibility as the event propagates, in order: '+json.dumps(trail)+'. Return the same JSON edit.'}
        return original_request(ledger,case,folder,[*messages,extra],phase,limit)
    # Keep the original candidate and experiment files byte-identical.
    with patch.multiple(author,OUT=OUT,RESULT=RESULT,register=register),patch.object(author.base,'request',request):
        author.run()


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        run()
