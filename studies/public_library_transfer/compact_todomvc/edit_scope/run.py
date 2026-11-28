"""Separate prohibitions on live actions from constraints on storage or display."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.state_examples import evidence
from studies.study_io import ROOT, now, read, sha

state = evidence.state
weak = state.todo.WEAK
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/todo-edit-scope-20261128'
END = datetime(2026, 11, 28, 10, 32, tzinfo=timezone.utc)
CAP = .40
EFFECTS = {
    'toggle': 'Change the completed status of one item in the current session.',
    'toggleAll': 'Change the completed status of all items in the current session.',
    'edit': 'Start editing, commit a title, or cancel a title edit in the current session.',
    'clearCompleted': 'Remove completed items now.',
    'routing': 'Switch the visible filter now.',
}
PROBES = {
    'p1': ('An operator may open an existing title for editing. Keep the other controls available.', True),
    'p2': ('An operator may not open an existing title for editing. Keep the other controls available.', False),
    'p3': ('An operator may open an existing title for editing. Do not store which title is being edited across a refresh.', True),
    'p4': ('Allow renaming an item in place during this visit.', True),
    'p5': ('Forbid renaming an item in place during this visit.', False),
    'p6': ('An item can be renamed in place. After reopening the app, the editor must never resume the prior editing session.', True),
}
INSTRUCTION = (
    'Your controller already works with all switches enabled. Classify only explicit prohibitions in the brief. '
    'Use scope live_action when the user is forbidden from performing an action now, stored_data for what may '
    'survive a reload, and presentation for visibility. These scopes are independent. For instance, not storing '
    'the selected filter does not prevent a user from changing filters now. Omitted features stay enabled. '
    'Return only a JSON array. Each entry must have scope, option, and quote (an exact excerpt). For live_action '
    'choose the switch whose live effect is explicitly forbidden. For stored_data or presentation use null for '
    'option. Use [] when there is no prohibition.'
)


def apply(raw, brief, options):
    proposals, parser = evidence.decode(raw)
    if not isinstance(proposals, list):
        raise ValueError('Expected a list of scoped prohibitions')
    disabled = []
    for item in proposals:
        if not isinstance(item, dict) or set(item) != {'scope', 'option', 'quote'}:
            raise ValueError('Malformed prohibition')
        scope, opt, quote = item['scope'], item['option'], item['quote']
        if scope not in ('live_action', 'stored_data', 'presentation') or not isinstance(quote, str) or not quote.strip():
            raise ValueError('Invalid scope or quotation')
        if scope == 'live_action':
            if opt not in options:
                raise ValueError('Unknown live switch')
            if quote.casefold() in brief.casefold() and opt not in disabled:
                disabled.append(opt)
        elif opt is not None:
            raise ValueError('Only live prohibitions can name a switch')
    return disabled, proposals, parser


def decide(tag, rep, key, brief, lib, ledger):
    dest = OUT / tag / rep / key
    record = dest / 'decision.json'
    if record.exists():
        return read(record)
    options = {k: EFFECTS[k] for k in lib['options']}
    prompt = core.messages(INSTRUCTION, dict(brief=brief, switches=options))
    try:
        raw = state.todo.BASE.request(ledger, ('todomvc', tag, rep), dest / 'call', prompt, 'plan', 1400)
        disabled, proposals, parser = apply(raw, brief, options)
        code = state.todo.MOD.assemble(lib['functions'], {k: k not in disabled for k in state.ALL})
        row = dict(status='valid', disabled=disabled, proposals=proposals, parser=parser,
                   candidate=state.candidate(dest / 'page', code))
    except state.todo.slots.EVENTS.MISSING as exc:
        row = dict(status='missing', reason=str(exc))
    except (ValueError, TypeError) as exc:
        row = dict(status='invalid', reason=str(exc))
    core.save(record, row)
    return read(record)


def generate():
    reg, seal = OUT / 'registration.json', OUT / 'seal.json'
    briefs = {t['id']: t['requirement'] for t in weak.domain.tasks()}
    inputs = [Path(__file__), HERE / 'score.py', HERE / 'PROTOCOL.md', Path(evidence.__file__),
              state.HERE / 'result.json', evidence.RESULT, Path(state.todo.MOD.__file__)]
    libs = {(t, r): state.OUT / t / r / 'library.json' for t in state.TAGS for r in 'ab'}
    sources = {str(p.relative_to(ROOT)): sha(p) for p in [*inputs, *libs.values()]}
    if not reg.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(reg, dict(utc=now(), deadline=END.isoformat(), cap=CAP, balance=balance,
                            sources=sources, briefs=briefs, probes=PROBES))
    if sources != read(reg)['sources'] or briefs != read(reg)['briefs']:
        raise ValueError('Registration changed')
    if seal.exists():
        return
    ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
    jobs = {}
    records = {t: {} for t in state.TAGS}
    texts = briefs | {k: v[0] for k, v in PROBES.items()}
    with patch.multiple(state.todo.BASE, OUT=OUT, END=END, template=state.todo.slots.EVENTS.template), \
            ThreadPoolExecutor(max_workers=4) as pool:
        for (tag, rep), path in libs.items():
            lib = read(path)
            if lib['status'] != 'valid':
                raise ValueError('Expected admitted controller')
            records[tag][rep] = {}
            for key, brief in texts.items():
                jobs[tag, rep, key] = pool.submit(decide, tag, rep, key, brief, lib, ledger)
        for (tag, rep, key), task in jobs.items():
            records[tag][rep][key] = task.result()
    core.save(seal, dict(registration=sha(reg), decisions=records))


if __name__ == '__main__':
    from . import score
    with browser.lock(OUT / 'study.lock'):
        generate()
        score.evaluate()
