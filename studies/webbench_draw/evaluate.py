"""Freeze completed generation and score exact pages, without any API calls."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.history_replay.run import read, now, sha, source_files, digest, dump
from test.ledger_read import totals
from .core import ROOT, HERE, BUILD, BUILDERS, STAGES, MILESTONES, slug
from .browser import OUT, grade, prepare_harness


def prepare():
    target = OUT / 'inputs.json'
    assert not target.exists(), 'Do not replace a frozen evaluation manifest'
    rows, jobs, frozen = [], {}, {}
    def freeze(path):
        frozen[str(path.relative_to(ROOT))] = sha(path)
    for out in [BUILD, *STAGES.values()]:
        assert read(out / 'generation-complete.json')
        assert totals(out / 'budget.sqlite3')['stop_usd'] == 0
        manifest = read(out / 'review-manifest.json')
        for name, checksum in manifest['sha256'].items():
            assert sha(ROOT / name) == checksum, name
        for path in out.rglob('*.json'):
            if 'node_modules' not in path.parts:
                freeze(path)
    for path in HERE.iterdir():
        if path.suffix in ('.py','.mjs','.cjs') and path.name != 'analyze.py':
            freeze(path)
    freeze(HERE / 'PROTOCOL.md')
    def add(info, page, label):
        k = int(info['task'].split('-')[1])
        files = source_files(page) if page else None
        if page:
            for name in files:
                freeze(page / name)
        for endpoint, specs in [('current',[f'task-{k}']), ('history',['init', *[f'task-{i}' for i in range(1,k+1)]])]:
            key = digest({'files':files,'specs':specs}) if page else None
            if page:
                jobs.setdefault(key, {'page':str(page.relative_to(ROOT)), 'files':files,'specs':specs})
            rows.append({**info, 'label':label, 'endpoint':endpoint,'score_key':key,
                'page':str(page.relative_to(ROOT)) if page else None})
    for model, out in STAGES.items():
        for path in sorted((out / 'runs').rglob('record.json')):
            record = read(path)
            info = {key:record[key] for key in ('project','builder','model','method','task','status')}
            info['record'] = str(path.relative_to(ROOT))
            for label, index in [('first',0),('final',-1)]:
                version = record['attempts'][index]['version'] if record['attempts'] else None
                page = path.parent / version if version else None
                add(info, page, label)
            if record['method'] == 'plan' and record['task'] == 'task-20':
                version = record['attempts'][-1]['version'] if record['attempts'] else None
                page = path.parent / version if version else None
                for k in MILESTONES:
                    add({**info,'method':'control/final-plan','task':f'task-{k}'}, page, 'final')
    for builder in BUILDERS:
        folder = BUILD / 'libraries' / slug(builder)
        record = read(folder / 'record.json')
        if record['status'] != 'frozen':
            continue
        for index in range(2):
            page = folder / f"validation-{record['selected_attempt']}/example-{index}"
            for k in MILESTONES:
                add({'project':'draw','builder':builder,'model':None,'method':f'control/example-{index}',
                    'task':f'task-{k}', 'status':'complete','record':str((folder / 'record.json').relative_to(ROOT))},page,'final')
    harness = prepare_harness()
    for path in harness.rglob('*'):
        if path.is_file():
            freeze(path)
    dump(target, {'created_utc':now(),'planned_candidates':50,'rows':rows,'jobs':jobs,'sha256':frozen})
    print(f'Frozen {len(rows)} endpoints; {len(jobs)} unique reports', flush=True)


def score(workers):
    manifest = read(OUT / 'inputs.json')
    for name, checksum in manifest['sha256'].items():
        assert sha(ROOT / name) == checksum, name
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda pair:grade(*pair), manifest['jobs'].items()))
    dump(OUT / 'evaluation-complete.json', {'finished_utc':now(),'reports':len(results),
        'inputs_sha256':sha(OUT / 'inputs.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','score'])
    parser.add_argument('--workers',type=int,default=4)
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else score(args.workers)
