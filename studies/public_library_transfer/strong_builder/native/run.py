"""Test native JSON configuration delivery for both previously sealed strong libraries."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, digest, read, sha
from .. import run as primary

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/strong-builder-native-20261124'
CAP = 0.50
SEED = 20261124


def verify():
    registered = read(OUT/'registered.json')
    for path, checksum in registered['files'].items():
        if sha(ROOT/path) != checksum:
            raise ValueError(f'Changed native experiment input: {path}')
    return registered


def register():
    if (OUT/'registered.json').exists():
        verify()
        return
    balance = check_credits(CAP * len(primary.REPLICAS))
    if not balance['sufficient']:
        raise BudgetStop('Insufficient balance')
    sources = read(primary.OUT/'sources.json')
    files = [Path(__file__), HERE/'PROTOCOL.md', Path(transport.__file__), Path(core.__file__),
             Path(browser.__file__), primary.OUT/'sources.json', primary.OUT/'seal.json',
             primary.OUT/'inputs/table/public.json', primary.OUT/'inputs/table/browser.json',
             ROOT/'studies/public_library_transfer/deployments/historical/run.py']
    for replica in primary.REPLICAS:
        source = sources[replica]
        path = ROOT/source['folder']/'package.json'
        if source['archived'] or source['builder']!=primary.BUILDER or sha(path)!=source['package_sha256']:
            raise ValueError(f'Unexpected primary source: {replica}')
        files.append(path)
    core.save(OUT/'registered.json',
              {'utc':core.now(),'model':transport.MODEL,'builder':primary.BUILDER,'seed':SEED,
               'max_tokens':8192,'per_replica_cap_usd':CAP,'deadline':transport.END.isoformat(),
               'tasks':primary.TASKS,'balance':balance,
               'files':{str(path.relative_to(ROOT)):sha(path) for path in files}})


def target(replica, task, ledger, data, package):
    folder = OUT/replica/f'task-{task}'
    if (folder/'candidate.json').exists():
        return read(folder/'candidate.json')
    row = {'replica':replica,'project':primary.PROJECT,'task':task,'status':'missing'}
    route = OUT/replica/'route-closed.json'
    if route.exists():
        row['reason'] = read(route)['reason']
    else:
        try:
            answer = transport.request(folder/'call',ledger,core.plan_messages(data,task,package),
                                       f'{replica}/{task}',8192,seed=SEED,schema=package['plan_schema'])
            response = folder/'call/response.json'
            choice = read(response)
            row.update(response_sha256=sha(response), provider=choice.get('provider'), returned_model=choice['model'],
                       finish_reason=choice['choices'][0].get('finish_reason'))
            plan = parse_json(answer)
            page = folder/'page'
            files = core.materialize(primary.PROJECT,package,plan,page)
            row.update(status='valid',page=str(page.relative_to(ROOT)),files=files,plan=plan)
        except (transport.Unavailable,BudgetStop) as exc:
            row['reason'] = str(exc)
            if str(exc) in ('HTTP 400','HTTP 401','HTTP 402','HTTP 403','HTTP 404'):
                browser.preserve_json(route, {'reason':str(exc)})
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
            row.update(status='invalid',reason=f'{type(exc).__name__}: {exc}'[:350])
    core.save(folder/'candidate.json',row)
    return row


def generate():
    verify()
    sources = read(primary.OUT/'sources.json')
    with browser.lock(OUT/'generate.lock'):
        if (OUT/'seal.json').exists():
            return
        data = read(primary.OUT/'inputs/table/public.json')
        def replica_run(replica):
            ledger = Ledger(OUT/replica/'budget.sqlite3',CAP,CAP)
            package = read(ROOT/sources[replica]['folder']/'package.json')
            head = target(replica,1,ledger,data,package)
            with ThreadPoolExecutor(max_workers=2) as pool:
                tail = list(pool.map(lambda n:target(replica,n,ledger,data,package),primary.TASKS[1:]))
            return [head,*tail]
        with ThreadPoolExecutor(max_workers=2) as pool:
            groups = list(pool.map(replica_run,primary.REPLICAS))
        core.save(OUT/'seal.json',{'utc':core.now(),'registered_sha256':sha(OUT/'registered.json'),
                                   'candidates':[r for rows in groups for r in rows]})


def score():
    registered = verify()
    seal = read(OUT/'seal.json')
    assert seal['registered_sha256']==sha(OUT/'registered.json')
    prior = read(primary.RESULT)
    assert prior['seal_sha256']==sha(primary.OUT/'seal.json')
    protocol = browser.verify_contract(primary.PROJECT)
    assert protocol == read(primary.OUT/'inputs/table/browser.json')
    primary.configure()
    rows = browser.evaluate(seal['candidates'],primary.OUT,{primary.PROJECT:protocol},4)
    report = {}
    for replica in primary.REPLICAS:
        position = [r for r in rows if r['replica']==replica]
        assert sorted(r['task'] for r in position)==list(primary.TASKS)
        outcomes = prior['sources'][replica]['outcomes']
        result = {'passed':[],'missing':[],'invalid':[]}
        for r in position:
            if r['status']=='invalid':
                r['passed'] = False
                result['invalid'].append(r['task'])
            if r['passed'] is True:
                result['passed'].append(r['task'])
            elif r['passed'] is None:
                result['missing'].append(r['task'])
        result['routing'] = dict(Counter(r.get('provider') for r in position if 'provider' in r))
        result['baseline'] = {arm:outcomes[arm] for arm in ('selected','fixed')}
        result['budget'] = totals(OUT/replica/'budget.sqlite3')
        result['package_sha256'] = prior['sources'][replica]['package_sha256']
        report[replica] = result
    public_rows = [{k:v for k,v in r.items() if k in ('replica','task','status','passed','provider','returned_model',
                                                        'finish_reason','response_sha256','report_sha256')} for r in rows]
    core.save(HERE/'result.json', {'project':primary.PROJECT,'deployer':transport.MODEL,'builder':primary.BUILDER,
                                   'registered_utc':registered['utc'],'registration_sha256':sha(OUT/'registered.json'),
                                   'seal_sha256':sha(OUT/'seal.json'),'previous_result_sha256':sha(primary.RESULT),
                                   'sources':report,'rows':public_rows})
    print(report)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('register','generate','score'))
    args = parser.parse_args()
    {'register':register,'generate':generate,'score':score}[args.command]()
