"""Give Direct a separate syntax-only default-declaration repair sensitivity control."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess

from studies.study_io import ROOT, dump, now, read, sha
from .run import HERE, MODELS, OUT, ORIGINAL, RESULT, evaluate, inputs
from .direct import source_hash

DIRECT = HERE/'direct-result.json'
DIR = OUT/'default-declaration-control'
OUTCOME = HERE/'declaration-result.json'


def normalize(source):
    bad = list(re.finditer(r'^(?P<space>[ \t]*)default\s+function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(', source, re.M))
    if len(bad) != 1:
        return
    match, = bad
    start = match.start() + len(match['space'])
    name = re.escape(match['name'])
    if re.search(r'^\s*export\s+default\s+'+name+r'\s*;?\s*$', source,re.M):
        return source[:start] + re.sub(r'^default\s+', '', source[start:],count=1)
    if not re.search(r'\bexport\s+default\b', source):
        return source[:start]+'export '+source[start:]


def sources():
    return {str(p.relative_to(ROOT)):sha(p) for p in [HERE/'DECLARATION.md',HERE/'declaration.py',HERE/'direct.cjs',DIRECT,RESULT]}


def register():
    previous = read(DIRECT)['rows']
    tasks = inputs()
    rows = {}
    for tag,model in MODELS.items():
        rows[model] = statuses = {}
        for task,entry in previous[model].items():
            state = statuses[task] = {'original_source_sha256':entry['original_source_sha256'],'changed':False}
            module = tasks[task]['public']['module']+'.js'
            src = None
            if entry['disposition'] == 'recovered':
                path = OUT/'direct-control/files'/tag/(task+'.json')
                assert sha(path) == entry['candidate_sha256']
                src = read(path)[module]
            elif entry['original_status'] == 'valid':
                src = read(ORIGINAL/tag/'targets'/task/'direct/files.json')[module]
                assert source_hash(src) == entry['original_source_sha256']
            fixed = normalize(src or '')
            if fixed is None:
                continue
            check = subprocess.run(['node', str(HERE/'direct.cjs')],input=json.dumps({'original':fixed,'raw':''}),
                                   text=True,capture_output=True,check=True,cwd=ROOT)
            if json.loads(check.stdout) != {'source':fixed,'kind':'original'}:
                continue
            path = DIR/'files'/tag/(task+'.json')
            dump(path,{module:fixed})
            state.update(changed=True, files_sha256=sha(path), source_sha256=source_hash(fixed))
    marker = DIR/'seal.json'
    if marker.exists():
        old = read(marker)
        assert old['rows']==rows and old['sources']==sources()
    else:
        dump(marker, {'utc':now(),'rows':rows,'sources':sources()})


def score(workers):
    marker = DIR/'seal.json'
    sealed = read(marker)
    assert sealed['sources'] == sources()
    direct = read(DIRECT)['rows']
    tasks = inputs()
    jobs = []
    for tag,model in MODELS.items():
        for task,entry in sealed['rows'][model].items():
            previous = direct[model][task]
            entry.update(before=previous['symmetric_passed'], after=previous['symmetric_passed'],
                         report_sha256=previous['report_sha256'])
            if entry['changed']:
                jobs.append((tag,task,entry))
    def one(job):
        tag,task,entry = job
        path = DIR/'files'/tag/(task+'.json')
        assert sha(path) == entry['files_sha256']
        info = tasks[task]
        folder = DIR/'scores'/tag/task
        verdict = evaluate.score((info['group'],info,read(path),folder,None))
        assert verdict['report_sha256'] == sha(folder/'jest.json')
        entry.update(after=verdict['passed'],report_sha256=verdict['report_sha256'])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one,jobs))
    dump(OUTCOME,dict(**sealed,seal_sha256=sha(marker)))


def check():
    record = read(OUTCOME)
    assert record['sources'] == sources()
    original = read(DIRECT)['rows']
    for model, rows in record['rows'].items():
        assert set(rows) == set(original[model])
        for task,entry in rows.items():
            assert entry['before'] == original[model][task]['symmetric_passed']
            if not entry['changed']:
                assert entry['after'] == entry['before']
                assert entry['report_sha256'] == original[model][task]['report_sha256']
            else:
                assert entry['original_source_sha256'] != entry['source_sha256'] and entry['report_sha256']
        print(model,sum(v['changed'] for v in rows.values()),'changed;',
              sum(v['before'] for v in rows.values()),'->',sum(v['after'] for v in rows.values()))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register','score','check'))
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if args.action=='score':
        score(args.workers)
    else:
        {'register':register,'check':check}[args.action]()
