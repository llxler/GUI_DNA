"""Repair model-owned event handlers, holding the earlier Qwen plans fixed."""
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, UPSTREAM, now, read, sha
from .. import run as prior
from ..single_slot import run as original
from . import validate

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-selection-mode-20261127'
CAP = .16
SEED = 2026112721
FILES = ('cellClick', 'editingKeys', 'markSelection', 'navigate')
CANDIDATES = [FILES, ('cellClick',), ('cellClick', 'editingKeys'), ('markSelection', 'navigate'), ('navigate',)]
RULES = {
    'cellClick': 'Single clicking a cell selects it without starting editing, including after a previous selection. Dblclick is dispatched to a DIFFERENT function. Respect shift and modifier selection.',
    'editingKeys': 'Enter on a selected cell begins editing. Escape from editing disables editing but keeps that same cell selected and active. Respect Delete and select-all. Distinguish visible selection from editing.',
    'markSelection': 'cells is ALREADY the iterable of selected actual cell elements. Use its exact members. active and anchor are actual elements or null. The renderer reads ctx.selected afterwards. Do not recompute a rectangle or infer rowIndex on a cell.',
    'navigate': 'Outside edit mode count the active cell row via its parent tr.rowIndex, col via cellIndex. Use actual live table rows and their cells. Arrow keys preserve the perpendicular coordinate. Tab wraps, Shift+Tab reverses. Use ctx.select(cells,active,anchor) to reflect the new selection. Arbitrary row/col insertions may precede this event.',
}


def register():
    dest = OUT / 'registration.json'
    sources = [Path(__file__), Path(validate.__file__), HERE/'PROTOCOL.md', original.OUT/'seal.json',
               original.HERE/'result.json', prior.previous.prior.PUBLIC, Path(prior.__file__),
               Path(original.__file__), Path(prior.build.__file__), prior.build.HERE/'host.js',
               *(original.OUT/r/'library.json' for r in 'ab')]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    if not dest.exists():
        from studies.webgen_bench.component_contracts import report
        previous = sum(ledger_read.totals(ROOT/'artifacts'/(name+'-20261127')/'budget.sqlite3')['exposure_usd']
                       for k, name in report.LEDGERS.items() if k.endswith('generation') and not k.startswith('todo') and name != 'table-selection-mode')
        assert previous + CAP <= 1.60
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(dest, dict(utc=now(), deadline=prior.END.isoformat(), sources=hashes, cap=CAP,
                             previous_generation_exposure=round(previous, 6), balance=balance, seeds=[SEED, SEED+1]))
    assert read(dest)['sources'] == hashes
    return dest


def observe(page, folder):
    report = folder / 'observed.json'
    if not report.exists():
        checks = dict(prior.previous.observe(page)['checks'])
        if set(checks) != set(prior.previous.CHECKS):
            raise RuntimeError('Incomplete set of public browser actions')
        sequences = original.reserve_once(ROOT / page['page'], prior.TRAIN)
        for name, group in sequences.items():
            if any(step['action'] == 'browser' for step in group['steps']):
                raise RuntimeError('Incomplete registered public browser sequence: '+name)
            for step in group['steps']:
                checks[name+'/'+step['action']] = step['passed']
                if step['action'] in ('select', 'select-after-insert'):
                    checks[name+'/selected-without-editing'] = step['passed'] and not step['state']['editing']
        core.save(report, dict(checks=checks, sequences=sequences))
    return read(report)['checks']


def repair(rep, pub, ledger):
    folder = OUT / rep
    dest = folder / 'library.json'
    if dest.exists():
        return read(dest)
    source = original.OUT/rep/'library.json'
    old = read(source)
    assert old['status'] == 'valid'

    def propose(name):
        messages = prior.build.messages(name, pub)
        messages.extend([dict(role='assistant', content=old['parts'][name]),
                         dict(role='user', content='Revise your own function. Preserve other required behaviors. '+RULES[name]+
                              ' Return only the complete named JavaScript function with the same signature.')])
        try:
            raw = prior.base.request(ledger, ('table', prior.TAG, rep), folder/'functions'/name, messages, 'build', 3100)
            return prior.build.extract(name, raw)
        except prior.previous.prior.ERRORS + prior.previous.prior.MISSING:
            return old['parts'][name]

    with ThreadPoolExecutor(max_workers=2) as workers:
        proposals = dict(zip(FILES, workers.map(propose, FILES), strict=True))
    history = []
    chosen = old['parts']
    baseline = set()
    retained = []
    for index, keys in enumerate([(), *CANDIDATES]):
        parts = old['parts'] | {key: proposals[key] for key in keys}
        trial = folder/'public'/str(index)
        candidate = prior.previous.projection.page(pub, parts, old['options'], old['binding'], trial/'page')
        checks = observe(candidate, trial)
        passed = {name for name, value in checks.items() if value}
        history.append(dict(requested=list(keys), checks=checks))
        if index == 0:
            baseline = passed
        elif passed > baseline:
            retained = [k for k in keys if parts[k] != old['parts'][k]]
            chosen = parts
            break
    core.save(dest, dict(origin=sha(source), status='valid', parts=chosen, changed=retained, options=old['options'],
                         binding=old['binding'], history=history))
    print(rep, 'changed', retained, 'public', len(baseline), len(passed), flush=True)
    return read(dest)


def generate():
    reg = register()
    if (OUT/'seal.json').exists():
        return
    pub = read(prior.previous.prior.PUBLIC)
    old_rows = read(original.OUT/'seal.json')['rows']
    lookup = {(r['arm'], r['task']): r for r in old_rows}
    ledger = Ledger(OUT/'budget.sqlite3', CAP, CAP)
    def settings(_, tag, phase):
        return prior.previous.prior.old.settings('table', tag, phase) | {'seed': SEED}
    with patch.multiple(prior.base, OUT=OUT, END=prior.END, template=settings):
        with ThreadPoolExecutor(max_workers=2) as workers:
            libs = dict(zip('ab', workers.map(lambda r: repair(r, pub, ledger), 'ab'), strict=True))
    rows = []
    for rep, lib in libs.items():
        old = read(original.OUT/rep/'library.json')
        def make(parts, options, folder):
            return prior.previous.projection.page(pub, parts, options, lib['binding'], folder)
        for task in range(1, 21):
            for arm in ('self-'+rep, 'fixed-'+rep):
                record = lookup[arm, task]
                if record['status'] != 'valid':
                    rows.append(record)
                    continue
                if arm.startswith('fixed'):
                    options = old['options']
                else:
                    transmissions = original.OUT/rep/'plans'/str(task)/'call'
                    receipts = [f for f in transmissions.glob('*/settled.json') if f.with_name('response.json').is_file()]
                    assert len(receipts) == 1
                    receipt, = receipts
                    req = read(receipt.with_name('request.json'))['body']
                    res = receipt.with_name('response.json')
                    assert sha(res) == read(receipt)['response_sha256']
                    response = prior.base.uncode(read(res)['choices'][0]['message']['content']).strip()
                    options = json.loads(req['messages'][-1]['content'])['profiles'][response]
                slot = '-'.join(options) or 'none'
                orig = make(old['parts'], options, OUT/rep/'original'/slot)
                assert orig['files'] == record['files'], (rep, task, arm)
                candidate = make(lib['parts'], options, OUT/rep/'updated'/slot)
                rows.append(dict(project='table', task=task, arm=arm, **candidate))
    rows.extend(row for row in old_rows if row['arm'] == 'starter')
    core.save(OUT/'seal.json', dict(registration=sha(reg), libs={r: sha(OUT/r/'library.json') for r in libs}, rows=rows))


def score():
    if not (HERE/'result.json').exists():
        with patch.multiple(prior.previous.reducers, OUT=OUT, HERE=HERE):
            prior.previous.reducers.score()
    dest = HERE/'validation.json'
    if dest.exists():
        return
    runs = {'reference': UPSTREAM/'projects/table/src', 'starter': UPSTREAM/'projects/table/src-init'}
    for label, root in [('original', original.OUT), ('updated', OUT)]:
        for rep in 'ab':
            page = next(r for r in read(root/'seal.json')['rows'] if r['arm'] == 'fixed-'+rep and r['task'] == 1)
            path = ROOT / page['page']
            browser.verify_page(path, page['files'], 'table')
            runs[label+'-'+rep] = path
    observations = {name: validate.evaluate(path) for name, path in runs.items()}
    core.save(dest, dict(score=sha(HERE/'result.json'), validation=sha(Path(validate.__file__)), observations=observations,
                         calibrated={k: observations['reference'][k]['passed'] and not observations['starter'][k]['passed'] for k in validate.CASES}))


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('generate', 'score'))
    arg = parser.parse_args().action
    with browser.lock(OUT/(arg+'.lock')):
        if arg == 'generate':
            generate()
        else:
            score()
