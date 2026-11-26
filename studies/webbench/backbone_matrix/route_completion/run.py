"""Repeat actual requests for the four unavailable backbones, then complete reachable projects."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha, now
from .. import run as original

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/backbone-routes-20261126'
OLD = original.OUT
MODELS = ('gemini', 'mini', 'haiku', 'sonnet')
CAP = 2.90
END = datetime(2026, 11, 26, 4, 42, tzinfo=timezone.utc)


def register():
    path = OUT / 'registration.json'
    old = read(OLD / 'registered.json')
    files = {str(p.relative_to(ROOT)): sha(p) for p in
             (Path(__file__), HERE / 'PROTOCOL.md', Path(original.__file__), OLD / 'registered.json')}
    if not path.exists():
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(path, dict(utc=now(), sources=files, cap=CAP, balance=balance,
                             deadline=END.isoformat(), models=list(MODELS)))
    assert read(path)['sources'] == files
    core.save(OUT / 'registered.json', old)
    link = OUT / 'inputs'
    if not link.exists():
        link.symlink_to(OLD / 'inputs', target_is_directory=True)
    assert link.resolve() == (OLD / 'inputs').resolve()


def main():
    register()
    original.verify()
    ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
    records, reachable = {}, []
    for tag in MODELS:
        first = original.target(tag, 'table', 'direct', 1, ledger)
        records[tag] = dict(first=first, projects={})
        if first['status'] != 'missing':
            reachable.append(tag)
    for project in original.PROJECTS:
        for tag in reachable:
            original.build(tag, project, ledger)
        for n in original.TASKS:
            for tag in reachable:
                rows = records[tag]['projects'].setdefault(project, [])
                for arm in original.ARMS:
                    rows.append(original.target(tag, project, arm, n, ledger))
    seal = OUT / 'seal.json'
    core.save(seal, dict(registration=sha(OUT / 'registration.json'), records=records))
    assert read(seal)['registration'] == sha(OUT / 'registration.json')
    for data in records.values():
        for project, rows in data['projects'].items():
            tests = read(OUT / 'inputs' / project / 'browser.json')
            assert tests == browser.verify_contract(project)
            data['projects'][project] = browser.evaluate(rows, OUT, {project:tests}, 3)
    core.save(HERE / 'result.json', dict(registration=sha(OUT / 'registration.json'), seal=sha(seal),
              models=records, cost=ledger_read.totals(OUT / 'budget.sqlite3')))


if __name__ == '__main__':
    with browser.lock(OUT / 'run.lock'), patch.multiple(original, OUT=OUT, END=END):
        main()
