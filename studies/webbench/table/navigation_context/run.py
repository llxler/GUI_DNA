"""Pair fresh navigation implementations with and without a failed predecessor in the prompt."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import shutil

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, UPSTREAM, now, read, sha
from studies.webbench.table.keyboard_contract import run as previous

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-navigation-context-20261128'
KEYS = [(condition, seed) for seed in (2026112821, 2026112822) for condition in ('fresh', 'with-source')]
NEW = {
    'up_right_down_left': [('click',2,1,False),('ArrowUp',1,1,False),('ArrowRight',1,2,False),('ArrowDown',2,2,False),('ArrowLeft',2,1,False)],
    'edit_tab_reverse_down': [('click',1,1,False),('Enter',1,1,True),('Escape',1,1,False),('Tab',1,2,False),('Shift+Tab',1,1,False),('ArrowDown',2,1,False)],
}
CAP = .20


def render(row, lib, parts, label):
    with patch.object(previous.earlier, 'OUT', OUT):
        return previous.earlier.render(row, 'b', lib, parts, label)


def register():
    pkg = previous.OUT / 'b/library.json'
    paths = [Path(__file__), HERE/'PROTOCOL.md', previous.OUT/'seal.json', pkg, Path(previous.__file__),
             Path(previous.earlier.__file__), Path(previous.prior.validate.__file__)]
    reg = OUT/'registration.json'
    sums = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not reg.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(reg, dict(utc=now(), deadline=previous.prior.campaign.END.isoformat(), cap=CAP, balance=balance,
                            sources=sums, conditions=KEYS, holdout=NEW, primary=KEYS[0]))
    assert read(reg)['sources'] == sums


def generate():
    seal = OUT/'seal.json'
    if seal.exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3', CAP, CAP)
    mode = previous.mode
    old = read(previous.OUT/'b/library.json')
    lib = old['parts']
    assert not old['changed']
    measured_source = next((previous.OUT/'b/index-and-projection').glob('*/common/table.js')).read_text()
    response = next((previous.earlier.OUT/'b/proposal').glob('*/transmission-1/response.json'))
    projector = mode.prior.build.extract('markSelection', read(response)['choices'][0]['message']['content'])
    assert projector in measured_source and all(previous.earlier.public_contract(projector).values())
    rows = [v for v in read(previous.OUT/'seal.json')['rows'] if v['arm'] in ('starter','fixed-b','self-b')]
    original_arms = {v['arm'] for v in read(previous.OUT/'seal.json')['rows'] if v['arm'].endswith('-b')}
    assert {v['arm'] for v in rows} == original_arms | {'starter'}
    fixed = next(v for v in rows if v['arm']=='fixed-b')
    training = previous.prior.validate.CASES | previous.earlier.CASES
    studies = {}
    for condition, seed in KEYS:
        label = f'{condition}-{seed}'
        folder = OUT/label
        description = dict(
            interface='function navigate(ctx,event); ctx.table is an HTMLTableElement; ctx.active is a TD in its tbody. Outside edit mode the TDs are selectable but NOT editable.',
            semantics='Move one body cell for four arrow keys, Tab to the next cell and Shift+Tab to the preceding one. Publish a selection through ctx.select([destination], destination, destination). Use bounding checks, keep in the table body. Read event.shiftKey because a reverse Tab still has key Tab.',
            examples=['A non-editing ordinary TD at row 2 column 2 with a body row above: ArrowUp must call ctx.select with the TD at row 1 column 2.',
                      'From the middle of a body row, Shift+Tab must call ctx.select with the preceding cell.'],
            observed=old['steps']['index-and-projection']['trace'])
        if condition=='with-source':
            description['previous_source'] = lib['navigate']
        message = core.messages('Implement the specified DOM action as one short JavaScript function. Use the native row and column indices; ordinary table body cells are navigable. Return only the requested function.',description)
        def settings(project, tag, stage):
            return mode.prior.previous.prior.old.settings('table',tag,stage) | {'seed':seed}
        try:
            # Rep a preserves the declared API seed in both conditions; b below identifies the frozen source library.
            with patch.multiple(mode.prior.base, OUT=OUT, END=previous.prior.campaign.END, template=settings):
                raw = mode.prior.base.request(ledger, ('table','qwen9','a'), folder/'call', message, 'build', 1800)
            fn = mode.prior.build.extract('navigate',raw)
            parts = lib | dict(navigate=fn, markSelection=projector)
            page = render(fixed,lib,parts,label)
            public = previous.measured(ROOT/page['page'], training)
            item = dict(status='valid',admitted=all(v['passed'] for v in public.values()), public=public,
                        page=page, function_sha256=hashlib.sha256(fn.encode()).hexdigest())
            if (condition,seed)==KEYS[0] and item['admitted']:
                core.save(OUT/'primary-library.json',parts)
        except mode.prior.previous.prior.MISSING as exc:
            item = dict(status='missing',admitted=False,reason=str(exc))
        except mode.prior.previous.prior.ERRORS as exc:
            item = dict(status='invalid',admitted=False,reason=str(exc))
        studies[label] = item
    primary = studies['fresh-'+str(KEYS[0][1])]
    if primary['admitted']:
        parts = read(OUT/'primary-library.json')
        rows = [render(r,lib,parts,'primary') if r['arm']!='starter' and r['status']=='valid' else r for r in rows]
    core.save(seal,dict(registration=sha(OUT/'registration.json'), candidates=studies, rows=rows, original_fixed=fixed))


def score():
    dest = HERE/'result.json'
    if dest.exists():
        return
    seal = read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    paths = {k:UPSTREAM/'projects/table'/v for k,v in [('reference','src'),('starter','src-init')]}
    paths['previous-b'] = ROOT/seal['original_fixed']['page']
    for k,v in seal['candidates'].items():
        if v['status']=='valid':
            paths[k] = ROOT/v['page']['page']
    measurements = {k:previous.measured(p,NEW) for k,p in paths.items()}
    protocol = browser.verify_contract('table')
    assert protocol==read(previous.mode.prior.previous.prior.PUBLIC.with_name('browser.json'))
    # For unchanged files use the same official reports only after checking contract, page bytes, target and verdict.
    for row in seal['rows']:
        if row['status']!='valid':
            continue
        files = browser.digest(row['files'])
        key = Path('browser/scores/table') / f'task-{row["task"]}' / files / 'score.json'
        dest_receipt = OUT / key
        if dest_receipt.exists():
            continue
        peer = previous.earlier.OUT
        original = peer / key
        if original.exists():
            expected = dict(project='table', task=row['task'], files_digest=files, contract_digest=browser.digest(protocol))
            verified = browser.verify_receipt(peer,original,expected)
            copy = dest_receipt.with_name('reused-report.json')
            copy.parent.mkdir(exist_ok=True,parents=True)
            shutil.copyfile(peer/verified['report'],copy)
            core.save(dest_receipt, dict(verified,report=str(copy.relative_to(OUT)),source_receipt=str(original.relative_to(ROOT)),
                                         source_receipt_sha256=sha(original),source_report=str((peer/verified['report']).relative_to(ROOT))))
    graded = browser.evaluate(seal['rows'],OUT,{'table':protocol},3)
    compact = [{k:r[k] for k in ('arm','task','status','report_sha256')} |
               dict(passed=False if r['status']=='invalid' else r['passed']) for r in graded]
    compact += [r for r in read(previous.earlier.RESULT)['rows'] if r['arm']=='direct']
    core.save(dest,dict(registration=seal['registration'],seal=sha(OUT/'seal.json'), rows=compact,heldout=measurements,
                        candidates={k:{a:b for a,b in v.items() if a!='page'} for k,v in seal['candidates'].items()},
                        cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        register()
        generate()
        score()
