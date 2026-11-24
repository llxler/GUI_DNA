"""Locate losses before and after composing the already sealed React modules."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

from experiments.webapp1k_probe import REPO
from studies.public_library_transfer.other_benchmarks.duo_admission import single
from studies.study_io import ROOT, dump, now, read, sha
from .run import EXTRA, GROUPS, HERE, MODELS, ORIGINAL, OUT, RESULT

DIR = OUT/'single-feature-diagnosis'


def materialize():
    libs = read(OUT/'seal.json')['libraries']
    lookup = {}
    for tag, model in MODELS.items():
        lookup[model] = {}
        for group in GROUPS:
            old = libs[tag][group]
            response = read(ORIGINAL/tag/'build'/group/'call/response.json')
            raw = response['choices'][0]['message'].get('content') or ''
            delivered = subprocess.run(['node',str(HERE/'extract.cjs')],input=json.dumps(raw),text=True,
                                       capture_output=True,check=True,cwd=ROOT)
            sources = {e['id']:e['source'] for e in json.loads(delivered.stdout)['delivered']}
            frozen = {c['id']:c['source_sha256'] for c in old['components']}
            assert {k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()} == frozen
            for name, selected in old['mapping'].items():
                spec = REPO/'tests/react'/group/(name+'.test.js')
                entry = {'group':group,'test_sha256':sha(spec),'component':selected}
                if selected:
                    entry.update(source_sha256=frozen[selected])
                    source = DIR/'modules'/tag/group/(name+'.js')
                    source.parent.mkdir(parents=True,exist_ok=True)
                    source.write_text(sources[selected])
                lookup[model][name] = entry
    return lookup


def sources():
    return {str(p.relative_to(ROOT)):sha(p) for p in
            (HERE/'SINGLE.md', HERE/'single.py', Path(single.__code__.co_filename), RESULT, OUT/'seal.json')}


def register():
    reg = {'rows':materialize(),'sources':sources()}
    path = DIR/'registered.json'
    if path.exists():
        previous = read(path)
        assert all(previous[k] == v for k,v in reg.items())
    else:
        dump(path,dict(utc=now(),**reg))


def summary(rows, paired):
    result = {}
    for model, singles in rows.items():
        counts = {k:0 for k in ('incomplete_pair','both_singles_pass_pair_pass','both_singles_pass_pair_fail',
                                'single_failure_pair_fail','single_failure_pair_pass')}
        cases = {k:[] for k in counts}
        for task, entry in paired[model].items():
            a,b = (singles[k] for k in task.split('_'))
            if not a['component'] or not b['component']:
                key = 'incomplete_pair'
                assert not entry['matched']['passed']
            else:
                prefix = 'both_singles_pass' if a['passed'] and b['passed'] else 'single_failure'
                suffix = 'pair_pass' if entry['matched']['passed'] else 'pair_fail'
                key = prefix+'_'+suffix
            counts[key] += 1
            cases[key].append(task)
        result[model] = {'single_available':sum(bool(r['component']) for r in singles.values()),
                         'single_passed':sum(r.get('passed',False) for r in singles.values()),
                         'n_singles':len(singles),'n_pairs':len(paired[model]),'pair_counts':counts,'pair_ids':cases}
    return result


def score(workers):
    path = DIR/'registered.json'
    reg = read(path)
    assert reg['sources'] == sources()
    jobs = []
    rows = reg['rows']
    for tag,model in MODELS.items():
        for name,entry in rows[model].items():
            if not entry['component']:
                continue
            group = entry['group']
            source = DIR/'modules'/tag/group/(name+'.js')
            assert sha(source) == entry['source_sha256']
            jobs.append((entry,DIR/'scores'/tag/group/name,group,name,source.read_text()))
    def one(job):
        entry,folder,*arguments = job
        _,verdict = single((folder,*arguments))
        assert verdict['report_sha256'] == sha(folder/'jest.json')
        assert all(verdict[k] == entry[k] for k in ('test_sha256','source_sha256'))
        assertions = read(folder/'jest.json')['testResults'][0]['assertionResults']
        entry.update(passed=verdict['passed'], cases_passed=sum(t['status']=='passed' for t in assertions),
                     report_sha256=verdict['report_sha256'])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one,jobs))
    dump(HERE/'single-result.json', {'registered_utc':reg['utc'],'registered_sha256':sha(path),
                                     'sources':reg['sources'],'rows':rows,'summary':summary(rows,read(RESULT)['rows'])})


def check():
    data = read(HERE/'single-result.json')
    for path in (HERE/'SINGLE.md', HERE/'single.py', RESULT):
        assert data['sources'][str(path.relative_to(ROOT))] == sha(path)
    assert data['summary'] == summary(data['rows'], read(RESULT)['rows'])
    for model, rows in data['rows'].items():
        assert len(rows) == 15
        for e in rows.values():
            if e['component']:
                assert e['passed'] == (e['cases_passed'] == 2)
        print(model,data['summary'][model]['single_passed'],data['summary'][model]['pair_counts'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','score','check'))
    parser.add_argument('--workers',type=int,default=3)
    args = parser.parse_args()
    if args.action == 'score':
        score(args.workers)
    else:
        {'register':register, 'check':check}[args.action]()
