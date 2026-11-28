"""Test an explicit selection-membership contract independently of movement."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,UPSTREAM,now,read,sha
from . import run as previous

HERE=previous.HERE
OUT=ROOT/'artifacts/table-membership-projection-20261128'
RESULT=HERE/'projection-result.json'
CAP=.20
CASES={'down_left':[('click',1,2,False),('ArrowDown',2,2,False),('ArrowLeft',2,1,False)],
       'edit_then_down':[('click',1,0,False),('ArrowRight',1,1,False),('Enter',1,1,True),
                         ('Escape',1,1,False),('ArrowDown',2,1,False)]}


def public_contract(src):
    r=subprocess.run(['node',str(HERE/'projector_check.cjs')],input=json.dumps(src),text=True,capture_output=True,
                     timeout=8,check=True)
    return json.loads(r.stdout)


def render(row,rep,lib,parts,name):
    root=ROOT/row['page']
    browser.verify_page(root,row['files'],'table')
    files={k:(root/k).read_text() for k in row['files'] if not k.startswith('assets/')}
    for rel,handler in [('common/table.js','markSelection'),('common/key.js','navigate')]:
        old=lib[handler]
        if old not in files[rel]:
            assert 'export function '+handler not in files[rel]
        else:
            assert files[rel].count(old)==1
            files[rel]=files[rel].replace(old,parts[handler])
    suffix=hashlib.sha256(row['page'].encode()).hexdigest()[:16]
    dest=OUT/rep/name/suffix
    return row|dict(page=str(dest.relative_to(ROOT)),files=core.emit('table',files,dest))


def run():
    mode=previous.last.mode
    olddir=previous.last.OUT
    reg=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROJECTION.md',HERE/'projector_check.cjs',previous.OUT/'seal.json',olddir/'seal.json',
           *(previous.OUT/r/'library.json' for r in 'ab'),*(olddir/r/'library.json' for r in 'ab')]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        used=sum(ledger_read.totals(ROOT/'artifacts'/(n+'-20261128')/'budget.sqlite3')['exposure_usd'] for n in
                 ('webgen-site-completion','webgen-native-state','webgen-grounded-actions','webgen-grounded-actions-judge','table-keyboard-navigation'))
        assert used+11.50+4.30+1.30+1.0+CAP<=20
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<previous.campaign.END
        core.save(reg,dict(sources=hashes,utc=now(),deadline=previous.campaign.END.isoformat(),balance=balance,cap=CAP))
    assert read(reg)['sources']==hashes
    if RESULT.exists():
        return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    rows=read(olddir/'seal.json')['rows']
    libs={r:read(olddir/r/'library.json')['parts'] for r in 'ab'}
    fixed={r:next(x for x in rows if x['arm']=='fixed-'+r and x['task']==1) for r in 'ab'}
    def propose(rep):
        saved=OUT/rep/'library.json'
        if saved.exists():
            return read(saved)
        lib=libs[rep];old=lib['markSelection'];prior=read(previous.OUT/rep/'library.json')
        msg=core.messages('Implement the membership projection for a browser spreadsheet. Return exactly one JavaScript function.',
              dict(signature='function markSelection(ctx, cells, active, anchor)',inputs='cells is exactly the desired iterable of cell objects, potentially disjoint, empty, a Set or an Array. active and anchor are already calculated cells or null.',
                   effects='Save exactly the supplied cells as a Set in ctx.selected. Assign the provided active and anchor to ctx.active and ctx.anchor. A separate renderer displays them. The caller already performed all rectangle and keyboard geometry.',
                   old_function=old,public_trace=prior['trace'],contract=public_contract(old)))
        proposals=[]
        for attempt in range(2):
            try:
                raw=mode.prior.base.request(ledger,('table','qwen9',rep),OUT/rep/'proposal'/str(attempt),msg,'build',1600)
                fn=mode.prior.build.extract('markSelection',raw)
                check=public_contract(fn)
            except (mode.prior.previous.prior.ERRORS+mode.prior.previous.prior.MISSING) as err:
                proposals.append({'error':str(err)[:150]})
                break
            proposals.append(dict(check=check,fingerprint=hashlib.sha256(fn.encode()).hexdigest()))
            if all(check.values()):
                break
            msg.extend([dict(role='assistant',content=raw),dict(role='user',content='Public membership checks: '+json.dumps(check)+'. Return the complete corrected function.')])
        chosen=lib;choice='previous';observations={}
        if proposals and all(proposals[-1].get('check',{'error':False}).values()):
            for name,nav in [('projection',lib['navigate']),('projection-and-navigation',prior['proposed'])]:
                parts=lib|dict(markSelection=fn,navigate=nav)
                row=render(fixed[rep],rep,lib,parts,name)
                observations[name]=previous.validate.evaluate(ROOT/row['page'])
                if all(v['passed'] for v in observations[name].values()):
                    chosen=parts;choice=name
                    break
        result=dict(parts=chosen,choice=choice,public_original=public_contract(old),proposals=proposals,training=observations)
        core.save(saved,result)
        return result
    def settings(_,tag,phase):
        return mode.prior.previous.prior.old.settings('table',tag,phase)|{'seed':2026112803}
    with patch.multiple(mode.prior.base,OUT=OUT,END=previous.campaign.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
        selected=dict(zip('ab',pool.map(propose,'ab'),strict=True))
    frozen=[]
    for row in rows:
        if row['arm']=='starter' or row['status']!='valid':
            frozen.append(row)
            continue
        rep=row['arm'][-1]
        picked=selected[rep]
        frozen.append(row if picked['choice']=='previous' else render(row,rep,libs[rep],picked['parts'],'frozen'))
    seal=OUT/'seal.json'
    core.save(seal,dict(registration=sha(reg),libraries={r:sha(OUT/r/'library.json') for r in 'ab'},rows=frozen))
    roots={'reference':UPSTREAM/'projects/table/src','starter':UPSTREAM/'projects/table/src-init'}
    for rep in 'ab':
        roots['original-'+rep]=ROOT/fixed[rep]['page']
        roots['updated-'+rep]=ROOT/next(row for row in frozen if row['arm']=='fixed-'+rep and row['task']==1)['page']
    with patch.object(previous.validate,'CASES',CASES):
        held={name:previous.validate.evaluate(path) for name,path in roots.items()}
    calibration={k:held['reference'][k]['passed'] and not held['starter'][k]['passed'] for k in CASES}
    proto=browser.verify_contract('table')
    assert proto==read(mode.prior.previous.prior.PUBLIC.with_name('browser.json'))
    scored=browser.evaluate(frozen,OUT,{'table':proto},3)
    compact=[{k:v.get(k) for k in ('task','arm','status','report_sha256')}|dict(passed=False if v['status']=='invalid' else v.get('passed')) for v in scored]
    old_result=mode.HERE/'result.json'
    direct=[v for v in read(old_result)['rows'] if v['arm']=='direct']
    core.save(RESULT,dict(registration=sha(reg),seal=sha(seal),direct_source=sha(old_result),libraries={
        rep:{k:v for k,v in item.items() if k!='parts'} for rep,item in selected.items()},heldout=held,calibrated=calibration,
        rows=compact+direct,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        run()
