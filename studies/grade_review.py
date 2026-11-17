"""Offline scoring of saved blind-library and name-sensitivity candidates.

Uses unchanged official assertions and timeouts; TodoMVC selects the enabled tests
and stops after the first counterexample. This yields exact task pass/fail, not a
complete test-level score. No provider or ledger is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from test.todomvc_dna import domain as td, evaluate as te
from test.todomvc_dna.review_evaluate import grade as todo_grade
from test.webbench_dna import domain as wd, evaluate as we


def grade_record(path, server):
    rec = json.loads(path.read_text())
    folder = path.parent
    suite = rec.get('suite', 'todomvc')
    target = folder / 'hidden.json'
    if target.exists():
        old = json.loads(target.read_text())
        values = [old['first'], old['final']] if 'first' in old else [old]
        valid = all((v.get('total') and not v.get('note')) or v.get('note') == 'no usable version' for v in values)
        legacy_todo = suite == 'todomvc' and any(not v.get('short_circuit') and v.get('note') != 'no usable version' for v in values)
        if valid and not legacy_todo:
            return
        if legacy_todo:
            previous = target.read_bytes()
            (folder / ('hidden-before-review-' + hashlib.sha256(previous).hexdigest()[:12] + '.json')).write_bytes(previous)
    tasks = td.tasks() if suite == 'todomvc' else wd.tasks()
    task = next(t for t in tasks if t['id'] == rec['task'])

    def score(version):
        page = folder / version
        if suite == 'todomvc':
            return todo_grade(server.url(page / 'index.html'), page / 'review-report.json', task['features'])
        value = we.grade(page, task, page / 'review-report.json')
        if value.get('note') or not value['total']:
            raise RuntimeError(f'{page}: harness failure: {value.get("note")}')
        return value

    if rec['versions']:
        final = score(rec['versions'][-1])
        if 'builder' in rec:
            first = final if rec['versions'][0] == rec['versions'][-1] else score(rec['versions'][0])
            value = {'first': first, 'final': final}
        else:
            value = final
    else:
        empty = {'passed': 0, 'total': len(td.hidden_subset(task['features'])) if suite == 'todomvc' else 0,
                 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
        value = {'first': empty, 'final': empty} if 'builder' in rec else empty
    target.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    provenance = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'todo_evaluator_sha256': hashlib.sha256(Path(__file__).with_name('todomvc_dna').joinpath('review_evaluate.py').read_bytes()).hexdigest(),
                  'protocol': 'Official assertions and timeouts; enabled TodoMVC subset; stop after first failure; task pass/fail only. Isolated output directories.',
                  'cache_policy': 'Retain valid earlier scores; prior evaluator fingerprints are preserved separately.'}
    manifest = args.stage / 'review-evaluation.json'
    if manifest.exists() and json.loads(manifest.read_text()) != provenance:
        previous = manifest.read_bytes()
        archive = args.stage / ('review-evaluation-' + hashlib.sha256(previous).hexdigest()[:12] + '.json')
        archive.write_bytes(previous)
    manifest.write_text(json.dumps(provenance, indent=2) + '\n')
    records = sorted((args.stage / 'runs').rglob('record.json'))
    server = te.Server(args.stage)
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, _ in enumerate(pool.map(lambda path: grade_record(path, server), records), 1):
                if i % 20 == 0 or i == len(records):
                    print(f'graded {i}/{len(records)}', flush=True)
    finally:
        server.close()


if __name__ == '__main__':
    main()
