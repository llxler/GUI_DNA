"""Seal both finite Codex table configuration spaces, then grade every setting."""
import argparse
import itertools
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/public-library-transfer-table-space-20261123'
REMOTE = ROOT / 'artifacts/public-library-transfer-remote-20261123'
RESULT = ROOT / 'studies/results/public-library-transfer-table-space-20261123.json'
PLANNERS = {'Qwen/Qwen2.5-0.5B-Instruct': core.OUT, 'mistralai/mistral-small-3.2-24b-instruct': REMOTE}


def freeze():
    paths = [Path(__file__), HERE / 'PROTOCOL.md', Path(core.__file__), core.OUT / 'inputs/table.json']
    for root in PLANNERS.values():
        paths.extend((root / 'project-seals/table.json', root / 'browser/project-scores/table.json'))
    rows = []
    with browser.lock(OUT / 'registration.lock'):
        for rep, count in ((1, 2), (2, 8)):
            folder = core.OUT / 'builds/table' / f'codex-{rep}'
            package, admission = read(folder / 'package.json'), read(folder / 'status.json')
            if admission['status'] != 'valid' or admission['package_sha256'] != sha(folder / 'package.json'):
                raise ValueError('The sealed library differs from the accepted package')
            paths.extend((folder / 'package.json', folder / 'status.json'))
            properties = package['plan_schema']['properties']
            domains = [[False, True] if prop['type'] == 'boolean' else prop['enum'] for prop in properties.values()]
            settings = [dict(zip(properties, values)) for values in itertools.product(*domains)]
            if len(settings) != count or len({digest(v) for v in settings}) != count:
                raise ValueError('Expected the complete two- and eight-setting spaces')
            example = package['examples'][0]['plan']
            if example not in settings:
                raise ValueError('The predeclared default example is outside the legal domain')
            for idx, config in enumerate(settings, 1):
                page = OUT / 'pages' / f'replicate-{rep}' / f'setting-{idx}'
                files = core.materialize('table', package, config, page)
                rows.extend({'project': 'table', 'rep': rep, 'setting': idx, 'config': config,
                             'first_example': config == example, 'task': task, 'arm': 'enumeration',
                             'page': str(page.relative_to(ROOT)), 'files': files, 'status': 'valid'} for task in browser.TASKS)
        assert len(rows) == len({(r['rep'], r['setting'], r['task']) for r in rows}) == 200
        core.save(OUT / 'generation-sealed.json', {'post_hoc': True, 'model_calls': 0,
                  'sources': {str(p.relative_to(ROOT)): sha(p) for p in paths},
                  'contract_sha256': digest(browser.verify_contract('table')), 'rows': rows})


def score(workers):
    path = OUT / 'generation-sealed.json'
    seal = read(path)
    for source, expected in seal['sources'].items():
        if sha(ROOT / source) != expected:
            raise ValueError(f'Enumeration source changed: {source}')
    contract = browser.verify_contract('table')
    if digest(contract) != seal['contract_sha256']:
        raise ValueError('Frozen browser contract changed')
    fingerprint = sha(path)
    rows = browser.evaluate(seal['rows'], OUT, {'table': contract}, workers)
    if sha(path) != fingerprint:
        raise ValueError('Enumeration changed during scoring')
    core.save(OUT / 'scoring.json', {'seal_sha256': fingerprint, 'rows': rows})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'score'])
    parser.add_argument('--workers', type=int, choices=range(1, 7), default=2)
    args = parser.parse_args()
    if args.action == 'freeze':
        freeze()
    else:
        score(args.workers)
