"""Evaluate a separate compiler-only switch-scope diagnostic on the sealed Gemma rows."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

from studies.public_library_transfer import browser
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.study_io import ROOT, now, read, sha
from .. import run as parent

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/todomvc-gemma-switch-scope-20261124'
RESULT = HERE / 'result.json'


def envelope(raw):
    block = re.fullmatch(r'\s*```(javascript|js|json)?[^\S\n]*\n(.*?)\n\s*```\s*', raw, re.S | re.I)
    source = block.group(2) if block else raw
    try:
        obj = json.loads(source)
    except ValueError:
        return source
    return obj['source'] if isinstance(obj, dict) and isinstance(obj.get('source'), str) else source


def scope(source):
    result = subprocess.run(['node', str(HERE / 'repair.cjs'), str(parent.binding.ACORN)],
                            input=source, capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def location(row):
    return Path('candidates') / row['group'] / row['stage'] / row['arm'] / row['task'] / 'files.json'


def prepare():
    reg = read(OUT / 'registration.json')
    assert reg['protocol_sha256'] == sha(HERE / 'PROTOCOL.md')
    assert reg['parent_seal_sha256'] == sha(parent.OUT / 'seal.json')
    marker = OUT / 'seal.json'
    if marker.exists():
        return
    original = read(parent.OUT / 'seal.json')
    assert all(sha(parent.OUT / f) == h for f, h in original['sources'].items())
    public = read(parent.OUT / 'public.json')
    rows = []
    for old in original['rows']:
        row = dict(old, diagnostic='unchanged')
        if old['status'] != 'invalid' or old['arm'] not in ('fixed', 'direct'):
            rows.append(row)
            continue
        name = old['task'] if old['arm'] == 'direct' else old['group']
        path = parent.OUT / 'source-attempts' / name
        audit = read(path / 'audit.json')
        phase = 'repair' if old['stage'] == 'final' and audit['repair'] == 'accepted' else 'initial'
        receipts = list((path / phase).glob('*/settled.json'))
        if len(receipts) != 1:
            raise RuntimeError(f'Expected exactly one usable source for {name} {phase}')
        reply = receipts[0].parent / 'response.json'
        raw = read(reply)['choices'][0]['message']['content']
        source = envelope(raw)
        evidence = scope(source)
        revised = evidence.pop('source', None)
        row.update(diagnostic=evidence['status'], evidence=evidence, response_sha256=sha(reply),
                   input_source_sha256=parent.public.digest(source))
        if revised is not None:
            ast = parent.raw_program(revised)
            if ast is None or ast['code'] != revised:
                row['diagnostic'] = 'cannot_deliver_complete_program'
            else:
                file = OUT / location(row)
                browser.preserve_json(file, {'candidate.js': revised})
                row.update(status='valid', files_sha256=sha(file))
                features = (list(public['builder']['spec']) if old['arm'] == 'fixed' else
                            parent.public.task_features(public['builder'], public['targets'][old['task']]))
                row['public_checks'] = parent.public.evaluate_public(revised, features)
        rows.append(row)
    browser.preserve_json(marker, {'utc': now(), 'registration': reg, 'sources': {
        str(p.relative_to(ROOT)): sha(p) for p in (HERE/'PROTOCOL.md', HERE/'repair.cjs', Path(__file__),
                                                   parent.binding.ACORN, parent.OUT/'seal.json')}, 'rows': rows})


def score():
    seal = read(OUT / 'seal.json')
    assert all(sha(ROOT / name) == h for name, h in seal['sources'].items())
    original = read(parent.RESULT)
    assert original['seal_sha256'] == seal['registration']['parent_seal_sha256']
    targets, _ = parent.suite.inputs()
    server = evaluate.todo.Server(OUT)

    def one(pair):
        row, old = pair
        assert all(row[k] == old[k] for k in ('arm', 'task', 'stage', 'group'))
        if row['status'] != 'valid':
            return dict(row, passed=None if row['status'] == 'missing' else False)
        task = row['task']
        if row['diagnostic'] == 'unchanged':
            assert sha(parent.OUT / location(row)) == old['files_sha256'] == row['files_sha256']
            dest = parent.OUT / 'scores' / task / row['files_sha256']
            verified = parent.binding.official(dest, targets[task], row)
            assert all(verified[k] == old[k] for k in ('passed', 'official_tests', 'report_sha256'))
            return verified
        file = OUT / location(row)
        assert sha(file) == row['files_sha256']
        dest = OUT / 'scores' / task / row['files_sha256']
        with browser.lock(dest / '.lock'):
            if not (dest / 'verdict.json').exists():
                with browser.browser_slot():
                    evaluate.score(('todomvc', targets[task], read(file), dest, server))
        return parent.binding.official(dest, targets[task], row)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(one, zip(seal['rows'], original['rows'], strict=True)))
    finally:
        server.close()
    browser.preserve_json(RESULT, {'parent_result_sha256': sha(parent.RESULT), 'registered': seal['registration'],
                                 'sealed_utc': seal['utc'], 'seal_sha256': sha(OUT / 'seal.json'),
                                 'sources': seal['sources'], 'additional_model_calls': 0, 'rows': rows,
                                 'paired': parent.paired(rows)})
    check()


def check():
    result = read(RESULT)
    assert result['paired'] == parent.paired(result['rows'])
    assert result['parent_result_sha256'] == sha(parent.RESULT)
    original = read(parent.RESULT)
    assert len(result['rows']) == len(original['rows']) == 80 and result['additional_model_calls'] == 0
    for row, old in zip(result['rows'], original['rows'], strict=True):
        assert all(row[k] == old[k] for k in ('arm', 'task', 'stage', 'group'))
        if row['diagnostic'] == 'unchanged':
            assert all(row.get(k) == old.get(k) for k in ('status', 'files_sha256', 'report_sha256', 'passed'))
    for p in (HERE / 'repair.cjs', Path(__file__), HERE / 'PROTOCOL.md'):
        assert result['sources'][str(p.relative_to(ROOT))] == sha(p)
    print({k: {a: len(v) for a, v in r['passed'].items()} for k, r in result['paired'].items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'score', 'check'))
    args = parser.parse_args()
    {'prepare': prepare, 'score': score, 'check': check}[args.action]()
