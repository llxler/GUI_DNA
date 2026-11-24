"""Score every discrete setting when the strong-builder library has at most four."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from . import run

HERE = Path(__file__).resolve().parent
OUT = run.OUT/'capacity'
LIMIT = 4


def configurations(package):
    properties = package['plan_schema']['properties']
    domains = []
    for schema in properties.values():
        domains.append((False,True) if schema['type']=='boolean' else schema['enum'])
    return [dict(zip(properties, values)) for values in product(*domains)]


def register():
    record = OUT/'registered.json'
    if record.exists():
        verify()
        return
    if (run.OUT/'seal.json').exists() or (run.OUT/'browser/scores').exists():
        raise ValueError('Configuration diagnostic must be registered before primary scoring')
    sources = read(run.OUT/'sources.json')
    frozen = [HERE/'CAPACITY.md', Path(__file__), Path(core.__file__), Path(browser.__file__),
              run.OUT/'sources.json', run.OUT/'inputs/table/browser.json']
    spaces = {}
    for replica, source in sources.items():
        if source['status'] != 'valid':
            spaces[replica] = {'status':source['status']}
            continue
        path = ROOT/source['folder']/'package.json'
        frozen.append(path)
        assert sha(path) == source['package_sha256']
        plans = configurations(read(path))
        spaces[replica] = {'size':len(plans), 'plans':plans if len(plans)<=LIMIT else None}
    core.save(record, {'utc':core.now(),'limit':LIMIT,'spaces':spaces,'tasks':run.TASKS,
                       'files':{str(path.relative_to(ROOT)):sha(path) for path in frozen}})


def verify():
    record = read(OUT/'registered.json')
    for path, checksum in record['files'].items():
        if sha(ROOT/path)!=checksum:
            raise ValueError(f'Changed capacity input: {path}')
    return record


def score():
    run.configure()
    record = verify()
    if not (run.OUT/'seal.json').exists():
        raise ValueError('Deployments must be sealed first')
    protocol = browser.verify_contract(run.PROJECT)
    assert protocol == read(run.OUT/'inputs/table/browser.json')
    sources = read(run.OUT/'sources.json')
    results = {}
    for replica, space in record['spaces'].items():
        if not space.get('plans'):
            results[replica] = {**space, 'exhaustive':False}
            continue
        package = read(ROOT/sources[replica]['folder']/'package.json')
        plans = space['plans']
        pages = []
        for index, plan in enumerate(plans):
            page = OUT/replica/f'config-{index}'
            files = core.materialize(run.PROJECT, package, plan, page)
            pages.append((page,files))
        def one(job):
            index, task = job
            page, files = pages[index]
            receipt = browser.run_one(run.OUT,run.PROJECT,task,page,files,protocol)
            return {'config':index,'task':task,'passed':receipt['passed'],'report_sha256':receipt['report_sha256']}
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(one, product(range(len(plans)),run.TASKS)))
        by_task = {str(n):sum(r['passed'] for r in rows if r['task']==n) for n in run.TASKS}
        results[replica] = {'size':len(plans), 'exhaustive':True, 'plans':plans,
                            'pass_count_by_task':by_task,'reachable':[int(n) for n,k in by_task.items() if k],
                            'by_config':[[r['task'] for r in rows if r['config']==i and r['passed']]
                                         for i in range(len(plans))], 'rows':rows}
    core.save(HERE/'capacity.json', {'registered_utc':record['utc'],'registration_sha256':sha(OUT/'registered.json'),
                                     'deployer_seal_sha256':sha(run.OUT/'seal.json'), 'spaces':results})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('register','score'))
    args = parser.parse_args()
    (register if args.command=='register' else score)()
