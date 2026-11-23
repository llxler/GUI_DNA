"""Reallocate two 16k preparation opportunities to one 32k response per workflow."""
import argparse
from contextlib import contextmanager
from pathlib import Path

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.expression_editor_sources import core
from studies.expression_editor_unseen_requirements import run as runner
from studies.ledger_read import totals
from studies.study_io import ROOT, dump, now, read, sha
from studies.table_library_sources.run import file_hashes, verify

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/expression-editor-window-20261123'
OLD = core.OUT
PEERS = ('table-library-sources-20261123', 'svg-chart-interfaces-20261123',
         'expression-editor-sources-20261123', 'expression-editor-unseen-20261123')


def freeze(cap):
    if (OUT / 'freeze.json').exists():
        assert read(OUT / 'freeze.json')['budget_usd'] == cap
        return
    reg = read(OUT / 'registration.json')
    assert sha(HERE / 'PROTOCOL.md') == reg['protocol_sha256']
    assert sha(OLD / 'freeze.json') == reg['parent_freeze_sha256']
    assert sha(OLD / 'controls-complete.json') == reg['parent_calibration_sha256']
    controls = read(OLD / 'controls-complete.json')['rows']
    for task in core.TASKS:
        assert controls['upstream_final/' + task]['passed'] and not controls['blank/' + task]['passed']
    exposure = {}
    for name in PEERS:
        peer = ROOT / 'artifacts' / name
        assert (peer / 'generation-complete.json').exists(), 'Wait for peer spending to close'
        exposure[name] = totals(peer / 'budget.sqlite3')['exposure_usd']
    supplement = ROOT / 'artifacts/expression-editor-unseen-notes-admission-20261123'
    assert (supplement / 'paid-closed.json').exists(), 'Wait for admission supplement to finish'
    exposure[supplement.name] = totals(supplement / 'budget.sqlite3')['exposure_usd'] if (supplement / 'budget.sqlite3').exists() else 0
    opening = read(ROOT / 'artifacts/editorial-20261123/opening-credits.json')['effective_remaining_usd']
    if not 0 < cap <= 1.00 or sum(exposure.values()) + cap > min(10, opening):
        raise BudgetStop('Independent ledger does not fit funded session exposure')
    credit = check_credits(cap)
    if not credit['sufficient']:
        raise BudgetStop('Insufficient balance')
    for arm in runner.ARMS:
        messages = read(OLD / 'prep-prompts' / f'{arm}.json')
        assert messages == core.preparation(arm)
        dump(OUT / 'prep-prompts' / f'{arm}.json', messages)
    shared = read(OLD / 'freeze.json')['inputs_sha256']
    verify(shared)
    paths = [HERE / 'PROTOCOL.md', HERE / 'run.py', OUT / 'registration.json', Path(runner.__file__),
             OLD / 'freeze.json', OLD / 'controls-complete.json', *runner.folder_files(OUT / 'prep-prompts')]
    dump(OUT / 'freeze.json', {'utc': now(), 'budget_usd': cap, 'credits': credit, 'other_closed_exposure': exposure,
         'prepare_targets': list(core.TASKS), 'deployment': list(core.TASKS), 'prepare_max_tokens': 32000,
         'prepare_attempts': 1, 'inputs_sha256': shared | file_hashes(paths)})


@contextmanager
def window_contract():
    previous = runner.OUT, runner.LATE, runner.browser.OUT
    try:
        runner.OUT, runner.LATE = OUT, core.TASKS
        yield
    finally:
        runner.OUT, runner.LATE, runner.browser.OUT = previous


def prepare():
    with window_contract():
        return prepare_in_window()


def prepare_in_window():
    assert runner.OUT == OUT and runner.LATE == core.TASKS
    runner.locked('freeze.json')
    if (OUT / 'preparation-complete.json').exists():
        return runner.locked('preparation-complete.json')
    api = runner.api_client()
    def one(arm):
        folder = OUT / 'preparation' / arm
        prompt = read(OUT / 'prep-prompts' / f'{arm}.json')
        assert prompt == core.preparation(arm)
        def save(obj, where):
            result = core.validate_preparation(arm, obj, where / 'validation')
            dump(folder / 'artifact.json', result)
            return {'artifact_sha256': sha(folder / 'artifact.json')}
        row = runner.attempt(api, folder / 'first', core.BUILDER, prompt, 'prepare-' + arm + '-first', 32000, save)
        return arm, {'first': row}
    # Independent queues are sent sequentially so provider-side credit holds cannot block the other arm.
    rows = dict(one(arm) for arm in ('direct', 'ai'))
    dump(OUT / 'preparation-complete.json', {'utc': now(), 'arms': rows,
         'inputs_sha256': file_hashes([OUT / 'freeze.json', *runner.folder_files(OUT / 'preparation')])})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('freeze', 'prepare', 'generate', 'score'))
    parser.add_argument('--budget-usd', type=float)
    args = parser.parse_args()
    if args.phase == 'freeze':
        if args.budget_usd is None:
            parser.error('A funded limit is required')
        freeze(args.budget_usd)
    elif args.phase == 'prepare':
        prepare()
    else:
        with window_contract():
            if args.phase == 'generate':
                runner.generate()
            else:
                runner.score()
