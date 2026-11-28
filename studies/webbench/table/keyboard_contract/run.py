"""Trace a real collection-index error and validate the model's navigation/selection contract."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, UPSTREAM, now, read, sha
from studies.webbench.table.keyboard_navigation import projection as earlier

prior = earlier.previous
mode = prior.last.mode
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-keyboard-contract-20261128'
CAP = .20
NEW = {
    'left_up_tab_down': [('click', 2, 2, False), ('ArrowLeft', 2, 1, False), ('ArrowUp', 1, 1, False),
                         ('Tab', 1, 2, False), ('ArrowDown', 2, 2, False)],
    'down_right_backtab': [('click', 1, 0, False), ('ArrowDown', 2, 0, False), ('ArrowRight', 2, 1, False),
                           ('Shift+Tab', 2, 0, False)],
}


def render(row, rep, old, updated, label):
    with patch.object(earlier, 'OUT', OUT):
        return earlier.render(row, rep, old, updated, label)


def measured(page, cases):
    with patch.object(prior.validate, 'CASES', cases):
        return prior.validate.evaluate(page)


def register():
    paths = [Path(__file__), HERE / 'PROTOCOL.md', earlier.RESULT, earlier.OUT / 'seal.json',
             Path(earlier.__file__), Path(prior.__file__), Path(prior.validate.__file__)]
    for r in 'ab':
        paths += [earlier.OUT / r / 'library.json', *sorted((earlier.OUT / r / 'proposal').rglob('settled.json'))]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    f = OUT / 'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f, dict(utc=now(), deadline=prior.campaign.END.isoformat(), cap=CAP, balance=balance,
                          sources=sums, new=NEW, targets=list(range(1, 21))))
    if read(f)['sources'] != sums:
        raise ValueError('Frozen input changed')


def revise(rep, base, fixed, ledger, training):
    f = OUT / rep / 'library.json'
    if f.exists():
        return read(f)
    initial = measured(ROOT / fixed['page'], training)
    chosen, steps = base, {}
    if not all(x['passed'] for x in initial.values()):
        # Inspect the collection-only control separately, before changing selection semantics.
        fn = base['navigate'].replace('currentRow.cells.indexOf(ctx.active)', 'Array.prototype.indexOf.call(currentRow.cells, ctx.active)')
        if fn == base['navigate']:
            raise ValueError('Observed collection call missing in failing library')
        variant = base | {'navigate': fn}
        indexed = render(fixed, rep, base, variant, 'index-only')
        steps['index-only'] = dict(trace=prior.dispatch_trace(indexed), public=measured(ROOT / indexed['page'], training))
        receipts = sorted((earlier.OUT / rep / 'proposal').rglob('settled.json'))
        last = receipts[-1]
        response = last.with_name('response.json')
        if sha(response) != read(last)['response_sha256']:
            raise ValueError('Projector response changed')
        projection = mode.prior.build.extract('markSelection', read(response)['choices'][0]['message']['content'])
        expected = read(earlier.OUT / rep / 'library.json')['proposals'][-1]['fingerprint']
        if hashlib.sha256(projection.encode()).hexdigest() != expected or not all(earlier.public_contract(projection).values()):
            raise ValueError('Projector does not match the admitted same-model response')
        candidate = variant | dict(markSelection=projection)
        page = render(fixed, rep, base, candidate, 'index-and-projection')
        trace = prior.dispatch_trace(page)
        observed = measured(ROOT / page['page'], training)
        steps['index-and-projection'] = dict(trace=trace, public=observed)
        message = core.messages(
            'Write exactly one JavaScript function navigate(ctx,event). The host calls it on keydown for Arrow keys '
            'and Tab. In a live table ctx.active is the current TD. Its cellIndex gives the column; '
            'its parentElement.rowIndex gives the row within ctx.table.rows (including header). '
            'The model-owned markSelection already publishes membership when called as ctx.select([cell],cell,cell). '
            'Move to the neighbouring body cell outside editing; use shiftKey to reverse Tab. A navigation event '
            'must both change the active position and publish the visible selection. Use cell objects, ignoring '
            'header rows and absent destinations. Leave live text edits alone. No helpers from other files.',
            dict(original_navigation=fn, browser_trace=trace,
                 public_first_failures={k: next((s for s in v['steps'] if not s['passed']), None) for k, v in observed.items()}))
        for attempt in range(2):
            folder = OUT / rep / 'calls' / str(attempt)
            try:
                raw = mode.prior.base.request(ledger, ('table', 'qwen9', rep), folder, message, 'build', 2400)
                fixed_fn = mode.prior.build.extract('navigate', raw)
                trial = candidate | dict(navigate=fixed_fn)
                row = render(fixed, rep, base, trial, 'proposal-' + str(attempt))
                checks = measured(ROOT / row['page'], training)
                steps[str(attempt)] = dict(public=checks, response_function=hashlib.sha256(fixed_fn.encode()).hexdigest())
                if all(v['passed'] for v in checks.values()):
                    chosen = trial
                    break
                failures = [next(s for s in v['steps'] if not s['passed']) for v in checks.values() if not v['passed']]
                message += [dict(role='assistant', content=raw), dict(role='user', content='Correct the entire function. Public failed steps: ' + json.dumps(failures))]
            except mode.prior.previous.prior.MISSING as exc:
                steps[str(attempt)] = dict(missing=str(exc))
                break
            except mode.prior.previous.prior.ERRORS as exc:
                steps[str(attempt)] = dict(invalid=str(exc))
                break
    core.save(f, dict(parts=chosen, changed=chosen != base, initial=initial, steps=steps))
    return read(f)


def main():
    register()
    seal = OUT / 'seal.json'
    original = read(earlier.OUT / 'seal.json')['rows']
    libraries = {r: read(earlier.OUT / r / 'library.json')['parts'] for r in 'ab'}
    fixed = {r: next(v for v in original if v['arm'] == 'fixed-' + r and v['task'] == 1) for r in 'ab'}
    if not seal.exists():
        ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
        def settings(p, tag, phase):
            return mode.prior.previous.prior.old.settings('table', tag, phase) | {'seed': 2026112810}
        training = prior.validate.CASES | earlier.CASES
        with patch.multiple(mode.prior.base, OUT=OUT, END=prior.campaign.END, template=settings):
            updates = {r: revise(r, libraries[r], fixed[r], ledger, training) for r in 'ab'}
        rows = []
        for row in original:
            rep = row['arm'][-1]
            if rep in updates and row['status'] == 'valid' and updates[rep]['changed']:
                row = render(row, rep, libraries[rep], updates[rep]['parts'], 'frozen')
            rows.append(row)
        core.save(seal, dict(registration=sha(OUT / 'registration.json'), rows=rows,
                             libraries={r: sha(OUT / r / 'library.json') for r in 'ab'}))
    result = HERE / 'result.json'
    if result.exists():
        return
    frozen = read(seal)
    assert frozen['registration'] == sha(OUT / 'registration.json')
    for r, fingerprint in frozen['libraries'].items():
        assert sha(OUT / r / 'library.json') == fingerprint
    paths = {k: UPSTREAM / 'projects/table' / folder for k, folder in [('reference','src'), ('starter','src-init')]}
    for rep in 'ab':
        paths['before-' + rep] = ROOT / fixed[rep]['page']
        paths['after-' + rep] = ROOT / next(row['page'] for row in frozen['rows'] if row['arm'] == 'fixed-' + rep)
    held = {k: measured(path, NEW) for k, path in paths.items()}
    protocol = browser.verify_contract('table')
    assert protocol == read(mode.prior.previous.prior.PUBLIC.with_name('browser.json'))
    graded = browser.evaluate(frozen['rows'], OUT, {'table': protocol}, 3)
    rows = [{k: v[k] for k in ('task','arm','status','report_sha256')} |
            dict(passed=False if v['status']=='invalid' else v['passed']) for v in graded]
    rows += [r for r in read(earlier.RESULT)['rows'] if r['arm'] == 'direct']
    core.save(result, dict(registration=frozen['registration'], seal=sha(seal), prior=sha(earlier.RESULT),
                           heldout=held, rows=rows, cost=ledger_read.totals(OUT / 'budget.sqlite3'),
                           libraries={r: {k:v for k,v in read(OUT / r / 'library.json').items() if k!='parts'} for r in 'ab'}))


if __name__ == '__main__':
    with browser.lock(OUT / 'study.lock'):
        main()
