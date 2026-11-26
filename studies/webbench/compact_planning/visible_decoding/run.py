"""Repeat the four affected routes with a visible-answer decoding budget."""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.compact_planning import run as compact
from studies.webbench.self_build_modules import run as base

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/compact-visible-20261125'
CAP = .75


def register():
    path = OUT / 'registration.json'
    if path.exists():
        reg = read(path)
        assert all(sha(ROOT / p) == h for p, h in reg['sources'].items())
        return reg
    parent = compact.register()
    files = [Path(__file__), HERE / 'PROTOCOL.md', Path(compact.__file__), compact.OUT / 'registration.json']
    cells = [c for c in parent['cells'] if c['tag'] in ('qwen9', 'deepseek-flash')]
    assert len(cells) == 4
    balance = check_credits(CAP)
    assert balance['sufficient']
    core.save(path, dict(utc=now(), cap=CAP, deadline=compact.END.isoformat(), balance=balance, cells=cells,
                         sources={str(f.relative_to(ROOT)): sha(f) for f in files}))
    return read(path)


def main(action):
    reg = register()
    if action == 'generate':
        original, template = base.request, base.template
        def request(ledger, case, root, messages, stage, limit):
            return original(ledger, case, root, messages, stage, 8192)
        def settings(project, tag, stage):
            return dict(template(project, tag, stage), reasoning={'enabled': False})
        ledger = Ledger(OUT / 'budget.sqlite3', CAP, CAP)
        with patch.object(compact,'OUT',OUT), patch.multiple(base, OUT=OUT, END=compact.END, template=settings,
                                                           request=request), ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda c: compact.produce(c, ledger), reg['cells']))
    if action == 'score':
        import time
        from datetime import datetime, timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):
                os.environ.pop(k)
        browser.OUT = OUT
        with patch.object(compact, 'OUT', OUT):
            for c in reg['cells']:
                root = OUT / c['project'] / c['tag'] / c['arm']
                while not (root / 'seal.json').exists():
                    if datetime.now(timezone.utc) >= compact.END: return
                    time.sleep(2)
                if not (root / 'comparison.json').exists(): compact.evaluate(c)
    if action == 'publish':
        cells = [read(OUT/c['project']/c['tag']/c['arm']/'comparison.json') for c in reg['cells']]
        core.save(HERE/'result.json', dict(registration_sha256=sha(OUT/'registration.json'), cells=cells,
                                          cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register','generate','score','publish'))
    main(parser.parse_args().action)
