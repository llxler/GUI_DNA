"""Request one live permission per switch and apply each decision to both frozen libraries."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sys
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.edit_scope import run as prior, score
from studies.study_io import ROOT, now, read, sha

state, weak, evidence = prior.state, prior.weak, prior.evidence
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/todo-edit-choices-20261128'
CAP = .40
PROBES = prior.PROBES | {
    'p7': ('Existing entries can have their wording changed whenever needed.', True),
    'p8': ('Lock the wording of existing entries so the user cannot start changing an item title.', False),
    'p9': ('Let people revise existing entry names. Discard any transient edit session when the list is reopened.', True),
}


def choose(ledger, tag, brief, option, folder):
    prompt = core.messages(
        'Choose the permission for one live user action. A = allowed, including when the brief is silent. '
        'B = the brief prohibits the user from doing this action during the visit. A restriction on what '
        'may be saved after refreshing, or what is shown when the list is empty, is separate. '
        'Reply only with A or B.',
        dict(action=prior.EFFECTS[option], public_requirement=brief))
    for attempt in range(2):
        raw = state.todo.BASE.request(ledger, ('todomvc', tag, 'a'), folder / str(attempt), prompt, 'plan', 180)
        text = state.todo.BASE.uncode(raw).strip()
        match = re.fullmatch(r'(?:option\s+)?([AB])[.!]?', text, re.I)
        if match:
            return match[1].upper()
        prompt += [dict(role='assistant', content=raw), dict(role='user', content='Answer using a single letter A or B.')]
    raise ValueError('Expected one unambiguous permission for ' + option)


def decision(ledger, tag, key, brief, option):
    folder = OUT / tag / 'decisions' / key / option
    path = folder / 'decision.json'
    if not path.exists():
        try:
            result = dict(status='valid', choice=choose(ledger, tag, brief, option, folder))
        except state.todo.slots.EVENTS.MISSING as exc:
            result = dict(status='missing', reason=str(exc))
        except ValueError as exc:
            result = dict(status='invalid', reason=str(exc))
        core.save(path, result)
    return read(path)


def generate():
    reg, seal = OUT / 'registration.json', OUT / 'seal.json'
    briefs = {x['id']: x['requirement'] for x in weak.domain.tasks()} | {k: v[0] for k, v in PROBES.items()}
    libs = {(t, r): state.OUT / t / r / 'library.json' for t in state.TAGS for r in 'ab'}
    files = [Path(__file__), HERE / 'PROTOCOL.md', Path(score.__file__), Path(prior.__file__), prior.HERE / 'result.json',
             prior.OUT / 'registration.json', Path(state.todo.MOD.__file__), *libs.values()]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in files}
    if not reg.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(reg, dict(utc=now(), deadline=prior.END.isoformat(), cap=CAP, balance=balance,
                            sources=sums, briefs=briefs, probes=PROBES))
    if read(reg)['sources'] != sums or read(reg)['briefs'] != briefs:
        raise ValueError('Registered input changed')
    if seal.exists():
        return
    ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
    records = {}
    with patch.multiple(state.todo.BASE, OUT=OUT, END=prior.END, template=state.todo.slots.EVENTS.template), \
            ThreadPoolExecutor(max_workers=4) as pool:
        for tag in state.TAGS:
            records[tag] = {}
            libraries = {r: read(libs[tag, r]) for r in 'ab'}
            options = sorted(set().union(*(v['options'] for v in libraries.values())))
            jobs = {(k, opt): pool.submit(decision, ledger, tag, k, brief, opt)
                    for k, brief in briefs.items() for opt in options}
            for r, lib in libraries.items():
                if lib['status'] != 'valid':
                    raise ValueError('Expected admitted controller')
                records[tag][r] = {}
                for key in briefs:
                    votes = {o: jobs[key, o].result() for o in lib['options']}
                    statuses = {v['status'] for v in votes.values()}
                    if statuses != {'valid'}:
                        row = dict(status='missing' if 'missing' in statuses else 'invalid', votes=votes)
                    else:
                        disabled = [o for o, v in votes.items() if v['choice'] == 'B']
                        code = state.todo.MOD.assemble(lib['functions'], {k: k not in disabled for k in state.ALL})
                        row = dict(status='valid', disabled=disabled, votes=votes,
                                   candidate=state.candidate(OUT / tag / r / key / 'page', code))
                    records[tag][r][key] = row
    core.save(seal, dict(registration=sha(reg), decisions=records))


if __name__ == '__main__':
    with browser.lock(OUT / 'study.lock'):
        generate()
        with patch.object(score, 'run', sys.modules[__name__]):
            score.evaluate()
