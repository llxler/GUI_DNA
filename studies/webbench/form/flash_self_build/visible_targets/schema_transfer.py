"""Transfer the existing schema-only questionnaire prompt to the identical GPT-5 library."""
import argparse
import os
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,read,sha,now
from studies.webbench.compact_planning import run as compact
from studies.webbench.table.event_modules import focused
from . import run as previous

OUT=ROOT/'artifacts/flash-schema-transfer-20261125'
CAP=.40
RESULT=previous.HERE/'schema-transfer-result.json'


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==h for p,h in reg['sources'].items())
        return reg
    src=next(c for c in read(compact.RESULT)['cells'] if c['project']=='form' and c['arm']=='gpt5-library')
    package=previous.OLD/'inputs/form/gpt5-library.json'
    assert sha(package)==sha(ROOT/src['package'])
    earlier=[r for r in read(previous.RESULT)['rows'] if r['arm']=='gpt5-library']
    assert len(earlier)==20 and all(r['status']!='missing' for r in earlier)
    cell=dict(project='form',tag=previous.TAG,model=compact.base.template('form',previous.TAG,'plan')['model'],
              arm='gpt5-library',targets=list(range(1,21)),package=str(package.relative_to(ROOT)),
              previous=sum(r['passed'] is True for r in earlier))
    bound=focused.register()['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    files=[Path(__file__),previous.HERE/'schema-transfer.md',previous.RESULT,compact.RESULT,Path(compact.__file__),
           package,previous.OLD/'inputs/form/public.json',previous.OLD/'inputs/form/browser.json',focused.OUT/'registration.json']
    core.save(path,dict(utc=now(),cap=CAP,deadline=compact.END.isoformat(),balance=balance,combined_bound=bound,cell=cell,
                         sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def main(action):
    reg=register()
    c=reg['cell']
    if action=='generate':
        original_template,request=compact.base.template,compact.base.request
        def settings(p,t,s):return dict(original_template(p,t,s),reasoning={'enabled':False})
        def ask(ledger,case,folder,messages,stage,limit):return request(ledger,case,folder,messages,stage,8192)
        with patch.multiple(compact.base,OUT=OUT,END=compact.END,template=settings,request=ask),patch.object(compact,'OUT',OUT):
            compact.produce(c,Ledger(OUT/'budget.sqlite3',CAP,CAP))
    elif action=='score':
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        with patch.object(compact,'OUT',OUT):compact.evaluate(c)
        result=read(OUT/c['project']/c['tag']/c['arm']/'comparison.json')
        core.save(RESULT,dict(registration=sha(OUT/'registration.json'),cell=result,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
