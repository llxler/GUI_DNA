"""Replay the registered responses, distinguishing unavailable controls from runner errors."""
from pathlib import Path
from unittest.mock import patch

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import run as mode

OLD = mode.OUT
OUT = ROOT/'artifacts/table-selection-mode-replay-20261127'
TRACE = mode.original.reserve_once


def trace(page, cases):
    groups = TRACE(page, cases)
    for group in groups.values():
        for step in group['steps']:
            if step['action'] == 'browser' and step.get('error', '').startswith('Locator.click: Timeout'):
                step['action'] = 'requested-control-unavailable'
    return groups


def cached(_, case, destination, messages, stage, max_tokens):
    project, tag, rep = case
    assert stage == 'build' and tag == 'qwen9'
    body = mode.prior.base.template(project, tag, stage) | dict(messages=messages, max_tokens=max_tokens, reasoning={'enabled':False})
    if rep == 'b':
        body['seed'] += 1
    folder = OLD/destination.relative_to(OUT)/'transmission-1'
    assert read(folder/'request.json')['body'] == body
    assert sha(folder/'response.json') == read(folder/'settled.json')['response_sha256']
    return read(folder/'response.json')['choices'][0]['message']['content']


def main():
    old_reg = mode.register()
    receipts = sorted(OLD.glob('*/functions/*/transmission-1/settled.json'))
    assert len(receipts) == 8 and not (OLD/'seal.json').exists()
    sources = [old_reg, Path(__file__), mode.HERE/'LOCATOR.md', *receipts]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    reg = OUT/'registration.json'
    if not reg.exists():
        core.save(reg, dict(utc=now(), sources=hashes, api_calls=0))
    assert read(reg)['sources'] == hashes
    cost = ledger_read.totals(OLD/'budget.sqlite3')
    assert cost['unsettled_calls'] == 0 and cost['calls'] == 8
    with patch.multiple(mode, OUT=OUT, register=lambda:reg, Ledger=lambda *_:None), patch.object(mode.original,'reserve_once',trace), patch.object(mode.prior.base,'request',cached):
        mode.generate()
        with patch.object(mode.prior.previous.reducers.ledger_read,'totals',lambda db: cost if db == OUT/'budget.sqlite3' else unknown_db(db)):
            mode.score()


def unknown_db(db):
    raise ValueError(f'Unexpected scoring ledger: {db}')


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        main()
