"""Trace the actual keyboard dispatch and replace only the model-owned navigation function."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,UPSTREAM,now,read,sha
from ..action_sequences.selection_mode import offline as last, validate
from studies.webgen_bench.site_completion import generate as campaign

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-keyboard-navigation-20261128'
CAP=.20
FRESH={'left_down_right':[('click',1,2,False),('ArrowLeft',1,1,False),('ArrowDown',2,1,False),('ArrowRight',2,2,False)],
       'tab_reverse_up':[('click',2,1,False),('Tab',2,2,False),('Shift+Tab',2,1,False),('ArrowUp',1,1,False)]}
TRACE="""const coord = c => c ? [c.parentElement.rowIndex,c.cellIndex] : null;
 const snapshot = () => ({active:coord(ctx.active),selected:[...ctx.selected].map(coord),edit:ctx.active?.isContentEditable});
 const call = (name,...args) => {
   if (!handlers[name]) return;
   const before=snapshot(); const item={name,before};
   if(name==='navigate'){const up=ctx.active && ctx.table.rows[ctx.active.parentElement.rowIndex-1]?.cells[ctx.active.cellIndex];
     item.key=args[0].key;item.above=coord(up);item.aboveEditable=up?.isContentEditable;
     item.aboveContentEditableAttribute=up?.getAttribute('contenteditable');}
   if(name==='markSelection')item.requested=[...args[0]].map(coord);
   window.dispatchLog.push(item);
   try {return handlers[name](ctx,...args);} catch(e){item.error=String(e);throw e;} finally {item.after=snapshot();}
 };"""
HOST="const call = (name, ...args) => {\n  if (handlers[name]) return handlers[name](ctx, ...args);\n};"


def dispatch_trace(record):
    root=ROOT/record['page']
    browser.verify_page(root,record['files'],'table')
    code=(root/'index.js').read_text()
    assert code.count(HOST)==1
    with browser.serve('table',root) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        p=engine.new_page(service_workers='block')
        p.set_default_timeout(4500)
        def serve(route):
            path=urlsplit(route.request.url)
            if path.netloc!=urlsplit(url).netloc:
                return route.abort()
            if path.path=='/index.js':
                return route.fulfill(content_type='application/javascript',body=code.replace(HOST,'window.dispatchLog=[];'+TRACE))
            return route.continue_()
        p.route('**/*',serve);p.goto(url+'/index.html')
        p.locator('table tr').nth(2).locator(':scope > :is(td,th)').nth(1).click()
        p.keyboard.press('ArrowUp')
        records=p.evaluate('window.dispatchLog')
        assert any(r['name']=='navigate' for r in records)
        return [r for r in records if r['name'] in ('cellClick','markSelection','navigate')]


def emit(record,rep,old,new):
    root=ROOT/record['page']
    browser.verify_page(root,record['files'],'table')
    files={k:(root/k).read_text() for k in record['files'] if not k.startswith('assets/')}
    key='common/key.js'
    if old in files[key]:
        assert files[key].count(old)==1
        files[key]=files[key].replace(old,new)
    elif 'export function navigate' in files[key]:
        raise ValueError('Unknown navigation function')
    suffix=hashlib.sha256(record['page'].encode()).hexdigest()[:16]
    dest=OUT/'pages'/rep/suffix
    return record|dict(page=str(dest.relative_to(ROOT)),files=core.emit('table',files,dest))


def run():
    mode=last.mode
    pub=mode.prior.previous.prior.PUBLIC
    reg=OUT/'registration.json'
    sources=[Path(__file__),HERE/'PROTOCOL.md',Path(validate.__file__),last.OUT/'seal.json',
             mode.HERE/'result.json',pub,*(last.OUT/r/'library.json' for r in 'ab')]
    hashes={str(f.relative_to(ROOT)):sha(f) for f in sources}
    if not reg.exists():
        # Allow for the full remaining website evaluation capacities and their unsettled calls.
        closed=sum(ledger_read.totals(ROOT/'artifacts'/(name+'-20261128')/'budget.sqlite3')['exposure_usd'] for name in
                   ('webgen-site-completion','webgen-native-state','webgen-grounded-actions','webgen-grounded-actions-judge'))
        assert closed+11.50+4.30+1.30+CAP<=20
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<campaign.END
        core.save(reg,dict(utc=now(),sources=hashes,deadline=campaign.END.isoformat(),seeds=[2026112801,2026112802],cap=CAP,balance=balance))
    assert read(reg)['sources']==hashes
    result=HERE/'result.json'
    if result.exists():
        return
    previous=read(last.OUT/'seal.json')['rows']
    fixed={rep:next(r for r in previous if r['arm']=='fixed-'+rep and r['task']==1) for rep in 'ab'}
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def repair(rep):
        saved=OUT/rep/'library.json'
        if saved.exists():
            return read(saved)
        old=read(last.OUT/rep/'library.json')['parts']['navigate']
        trace=dispatch_trace(fixed[rep])
        msg=mode.prior.build.messages('navigate',read(pub))
        msg += [dict(role='assistant',content=old),dict(role='user',content='Repair your complete navigate(ctx,event). Only keydown calls it. '
                 'The real ArrowUp trace on a selected cell is '+str(trace)+'. Outside editing accept actual table body cells irrespective of '
                 'whether the destination can edit text. Use cell.parentElement.rowIndex and cell.cellIndex with table.rows, and ctx.select([next],next,next). '
                 'Check active.isContentEditable; an attribute with value false does not mean editable. Handle four arrows and Tab/Shift+Tab, '
                 'keeping unrelated event handlers unchanged. Return only the named function.')]
        proposed=old
        try:
            raw=mode.prior.base.request(ledger,('table','qwen9',rep),OUT/rep/'call',msg,'build',3000)
            proposed=mode.prior.build.extract('navigate',raw)
        except (mode.prior.previous.prior.ERRORS+mode.prior.previous.prior.MISSING):
            pass
        control=validate.evaluate(ROOT/fixed[rep]['page'])
        candidate=emit(fixed[rep],rep,old,proposed)
        new=validate.evaluate(ROOT/candidate['page'])
        before={k for k,v in control.items() if v['passed']}
        after={k for k,v in new.items() if v['passed']}
        val=dict(old=old,proposed=proposed,retained=after>before,trace=trace,baseline=control,attempt=new)
        core.save(saved,val)
        return val
    def settings(_,tag,phase):
        return mode.prior.previous.prior.old.settings('table',tag,phase)|{'seed':2026112801}
    with patch.multiple(mode.prior.base,OUT=OUT,END=campaign.END,template=settings),ThreadPoolExecutor(max_workers=2) as workers:
        libs=dict(zip('ab',workers.map(repair,'ab'),strict=True))
    rows=[]
    for record in previous:
        if record['arm']=='starter' or record['status']!='valid':
            rows.append(record)
        else:
            rep=record['arm'][-1];lib=libs[rep]
            rows.append(emit(record,'accepted-'+rep,lib['old'],lib['proposed']) if lib['retained'] else record)
    seal=OUT/'seal.json'
    core.save(seal,dict(registration=sha(reg),libraries={r:sha(OUT/r/'library.json') for r in libs},rows=rows))
    paths={'reference':UPSTREAM/'projects/table/src','starter':UPSTREAM/'projects/table/src-init'}
    for r in 'ab':
        paths['old-'+r]=ROOT/fixed[r]['page']
        paths['accepted-'+r]=ROOT/next(x for x in rows if x['arm']=='fixed-'+r and x['task']==1)['page']
    with patch.object(validate,'CASES',FRESH):
        held={arm:validate.evaluate(path) for arm,path in paths.items()}
    calibration={k:held['reference'][k]['passed'] and not held['starter'][k]['passed'] for k in FRESH}
    proto=browser.verify_contract('table')
    assert proto==read(pub.with_name('browser.json'))
    scored=browser.evaluate(rows,OUT,{'table':proto},3)
    compact=[{k:v.get(k) for k in ('task','arm','status','report_sha256')}|dict(passed=False if v['status']=='invalid' else v.get('passed')) for v in scored]
    direct=[v for v in read(mode.HERE/'result.json')['rows'] if v['arm']=='direct']
    core.save(result,dict(registration=sha(reg),seal=sha(seal),direct_source=sha(mode.HERE/'result.json'),
        libraries={r:{k:v for k,v in lib.items() if k not in ('old','proposed')}|
                   dict(source=sha(last.OUT/r/'library.json'),proposed_sha256=hashlib.sha256(lib['proposed'].encode()).hexdigest()) for r,lib in libs.items()},
        heldout=held,calibrated=calibration,rows=compact+direct,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        run()
