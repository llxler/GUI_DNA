"""Keep the DOM adapter fixed while a small model supplies the coordinate transition."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import subprocess

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, UPSTREAM, now, read, sha
from studies.webbench.table.navigation_context import run as context

previous = context.previous
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-coordinate-navigation-20261128'
CAP = .15
NEW = {
    'two_axes': [('click',2,0,False),('ArrowRight',2,1,False),('ArrowUp',1,1,False),('ArrowRight',1,2,False)],
    'tab_then_left': [('click',2,1,False),('Shift+Tab',2,0,False),('Tab',2,1,False),('ArrowLeft',2,0,False)],
    'end_edit_and_reverse': [('click',2,2,False),('Enter',2,2,True),('Escape',2,2,False),('Shift+Tab',2,1,False),('ArrowUp',1,1,False)],
}
ADAPTER = """function navigate(ctx, event) {
  const active = ctx.active;
  if (!active || active.isContentEditable) return;
  const section = active.closest('tbody');
  if (!section) return;
  const rows = section.rows;
  const r = active.parentElement.sectionRowIndex;
  const c = active.cellIndex;
  const decision = moveCell({row:r,col:c,rows:rows.length,cols:rows[r].cells.length,key:event.key,shift:event.shiftKey});
  if (!Array.isArray(decision) || decision.length !== 2 || !decision.every(Number.isInteger)) return;
  const next = rows[decision[0]]?.cells[decision[1]];
  if (!next) return;
  event.preventDefault();
  ctx.select([next], next, next);
  FUNCTION
}"""
NOOP = 'function moveCell(input) { return [input.row,input.col]; }'


def render(row, base, fn, projector, label):
    parts = base | dict(navigate=ADAPTER.replace('FUNCTION',fn), markSelection=projector)
    with patch.object(previous.earlier,'OUT',OUT):
        return previous.earlier.render(row,'b',base,parts,label)


def register():
    path = OUT / 'registration.json'
    inputs = [Path(__file__), HERE/'PROTOCOL.md', context.HERE/'result.json', context.OUT/'seal.json',
              previous.OUT/'b/library.json', Path(previous.earlier.__file__), Path(previous.prior.validate.__file__)]
    sums = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
    if not path.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(path, dict(utc=now(), deadline=previous.prior.campaign.END.isoformat(), cap=CAP, balance=balance,
                             sources=sums, seeds=[2026112831,2026112832], new=NEW))
    assert read(path)['sources']==sums
    return read(path)


def receive(raw):
    tools = previous.mode.prior.build.modules
    check = subprocess.run(['node',str(tools.HERE/'function.cjs'),str(tools.ACORN)],
                           input=json.dumps(dict(name='moveCell',arity=1,text=raw)), text=True,
                           capture_output=True, timeout=12)
    if check.returncode or not check.stdout.strip():
        raise ValueError('Expected a complete moveCell(input) function')
    return check.stdout.strip()


def generate(reg):
    if (OUT/'seal.json').exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3', CAP, CAP)
    old = read(previous.OUT/'b/library.json')['parts']
    orig = read(previous.OUT/'seal.json')['rows']
    frozen = [r for r in orig if r['arm'] in ('self-b','fixed-b')]
    fixed = next(r for r in frozen if r['arm']=='fixed-b')
    source = next((previous.earlier.OUT/'b/proposal').glob('*/transmission-1/response.json'))
    projector = previous.mode.prior.build.extract('markSelection',read(source)['choices'][0]['message']['content'])
    assert all(previous.earlier.public_contract(projector).values())
    noop = render(fixed,old,NOOP,projector,'no-motion')
    checks = previous.prior.validate.CASES | previous.earlier.CASES
    prompt = core.messages('Write just one JavaScript function moveCell(input). There is no DOM. Return an array of '
                           'two integers for the next body cell, keeping inside the grid. Each arrow moves by one in '
                           'the named direction. Tab moves forward, Shift+Tab backward in reading order. Allow '
                           'wrapping a Tab to the adjacent row within the grid. No helper outside the function.',
                           dict(input='Object with zero-based row, col, integer rows, cols, key (ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Tab), and boolean shift.',
                                example='Start in the middle of a row. ArrowLeft reaches the preceding column of the same row.'))
    records, candidates = {}, []
    for idx,seed in enumerate(reg['seeds'],1):
        label = str(idx)
        def settings(project, tag, stage):
            return previous.mode.prior.previous.prior.old.settings('table',tag,stage) | {'seed':seed}
        fn = None
        try:
            base = previous.mode.prior.base
            with patch.multiple(base, OUT=OUT, END=previous.prior.campaign.END, template=settings):
                raw = base.request(ledger,('table','qwen9','a'),OUT/label/'call',prompt,'build',1200)
            fn = receive(raw)
            page = render(fixed,old,fn,projector,'proposal-'+label)
            public = previous.measured(ROOT/page['page'],checks)
            admitted = all(v['passed'] for v in public.values())
            trial = dict(status='valid',admitted=admitted,public=public,page=page,source_sha256=hashlib.sha256(fn.encode()).hexdigest())
        except previous.mode.prior.previous.prior.MISSING as exc:
            trial = dict(status='missing',admitted=False,reason=str(exc))
        except ValueError as exc:
            trial = dict(status='invalid',admitted=False,reason=str(exc))
        records[label] = trial
        for row in frozen:
            v = render(row,old,fn,projector,'frozen-'+label) if trial['admitted'] and row['status']=='valid' else row
            candidates.append(v | dict(rep=label))
    core.save(OUT/'seal.json', dict(registration=sha(OUT/'registration.json'),fixed=fixed,noop=noop,trials=records,rows=candidates))


def score():
    result = HERE/'result.json'
    if result.exists():
        return
    seal = read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    paths = {k:UPSTREAM/'projects/table'/v for k,v in [('reference','src'),('starter','src-init')]}
    paths.update({k: ROOT/seal[k]['page'] for k in ('fixed','noop')})
    for k,v in seal['trials'].items():
        if v['status']=='valid':
            paths['proposal-'+k] = ROOT/v['page']['page']
    held = {k:previous.measured(path,NEW) for k,path in paths.items()}
    proto = browser.verify_contract('table')
    assert proto==read(previous.mode.prior.previous.prior.PUBLIC.with_name('browser.json'))
    scored = browser.evaluate(seal['rows'],OUT,{'table':proto},3)
    rows = [{k:v[k] for k in ('task','rep','arm','status','report_sha256')} |
            dict(passed=False if v['status']=='invalid' else v['passed']) for v in scored]
    rows += [r for r in read(context.HERE/'result.json')['rows'] if r['arm']=='direct']
    core.save(result, dict(seal=sha(OUT/'seal.json'),registration=seal['registration'],rows=rows,heldout=held,
                           trials={k:{a:b for a,b in v.items() if a!='page'} for k,v in seal['trials'].items()},
                           cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        generate(register())
        score()
