"""Freeze old candidate sources and evaluate exact same-page prefix conjunctions."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from test.todomvc_dna.evaluate import Server, browser_env

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/history-replay-20261115'
UPSTREAM = ROOT / 'artifacts/web-bench'
RUNTIME = {'163': ROOT / 'test/webbench_dna/harness/node_modules',
           '157': ROOT / 'artifacts/webbench-expand-runtime-157/node_modules'}
COHORTS = {'expert': ('webbench-dna-6', '163'),
           'interface': ('interface-blind-final-2', '163'),
           'expansion': ('webbench-expand-run', '157'),
           'frontier': ('webbench-expand-frontier-2', '157')}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def cases_by_file(report):
    result = {}
    def walk(suite):
        for spec in suite.get('specs', []):
            name = Path(spec['file']).name.removesuffix('.spec.js')
            for test in spec.get('tests', []):
                statuses = [r['status'] for r in test.get('results', [])]
                result.setdefault(name, []).append({'title': spec['title'], 'statuses': statuses,
                    'passed': bool(statuses) and all(s == 'passed' for s in statuses)})
        for child in suite.get('suites', []):
            walk(child)
    for suite in report.get('suites', []):
        walk(suite)
    return result


def source_files(page, expert=False):
    if expert:
        names = ['index.html']
        if (page / 'candidate.js').exists():
            names.append('candidate.js')
        return {n: sha(page / n) for n in names}
    manifest = page / 'source-manifest.json'
    if manifest.exists():
        files = read(manifest)['files_sha256']
    else:
        files = {p.relative_to(page).as_posix(): sha(p) for p in page.rglob('*') if p.is_file()}
    assert all(sha(page / n) == h for n, h in files.items()), str(page)
    return files


def harness_name(cohort, project):
    return ('expert' if cohort == 'expert' else ('163' if cohort == 'interface' else '157')) + '-' + project


def prepare_harness(cohort, project):
    name = harness_name(cohort, project)
    target = OUT / 'harness' / name
    if target.exists():
        return name
    source = ROOT / 'test/webbench_dna/harness/dom1-tests' if cohort == 'expert' else UPSTREAM / 'projects' / project / 'test'
    shutil.copytree(source, target / 'test')
    runtime = COHORTS[cohort][1]
    package_type = read(UPSTREAM / 'projects' / project / 'package.json').get('type', 'commonjs')
    dump(target / 'package.json', {'type': package_type})
    timeout, expect = (12000, 3000) if cohort == 'expert' else (30000, 5000)
    config = """const {defineConfig, devices} = require('@playwright/test');
module.exports = defineConfig({testDir:'./test', timeout:%d, expect:{timeout:%d},
 fullyParallel:false, workers:1, retries:0, forbidOnly:true,
 reporter:[['json',{outputFile:process.env.REPORT_FILE}]],
 use:{baseURL:process.env.CANDIDATE_URL, trace:'off', headless:true},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
""" % (timeout, expect)
    (target / 'playwright.config.cjs').write_text(config)
    (target / 'node_modules').symlink_to(RUNTIME[runtime], target_is_directory=True)
    return name


def prepare():
    assert not (OUT / 'inputs.json').exists()
    rows, jobs, frozen, controls = [], {}, {}, []
    def freeze(path):
        frozen[str(path.relative_to(ROOT))] = sha(path)
    def add(row, page, old, first_final='final'):
        k = int(row['task'].split('-')[1])
        name = prepare_harness(row['cohort'], row['project'])
        job = None
        if page:
            files = source_files(page, row['cohort'] == 'expert')
            for file in files:
                freeze(page / file)
            specs = ['init', *[f'task-{i}' for i in range(1, k + 1)]]
            ident = {'harness': name, 'files': files, 'specs': specs}
            key = digest(ident)
            jobs.setdefault(key, {**ident, 'page': str(page.relative_to(ROOT)), 'runtime': COHORTS[row['cohort']][1],
                                  'project': row['project']})
            job = key
        rows.append({**row, 'label': first_final, 'old_current_passed': old, 'score_key': job,
                     'page': str(page.relative_to(ROOT)) if page else None})
    expert_summary = read(ROOT / 'test/webbench_dna/results/summary.json')
    selected = []
    for model in expert_summary['models']:
        if model['model'] == 'google/gemma-3-12b-it':
            continue
        for entry in model['rows']:
            for method in expert_summary['arms']:
                if method == 'rule' and model is not expert_summary['models'][0]:
                    continue
                selected.append(ROOT / 'artifacts/webbench-dna-6/runs' / model['model'].replace('/', '__') / method / entry['task'] / 'record.json')
    for cohort, (stage, runtime) in COHORTS.items():
        paths = selected if cohort == 'expert' else sorted((ROOT / 'artifacts' / stage / 'runs').rglob('record.json'))
        assert len(paths) == {'expert':580, 'interface':400, 'expansion':600, 'frontier':60}[cohort]
        for path in paths:
            record = read(path)
            assert record.get('status', 'complete') == 'complete'
            freeze(path)
            hidden_path = path.with_name('hidden.json')
            hidden = read(hidden_path)
            freeze(hidden_path)
            row = {'cohort':cohort, 'project':record.get('project', 'dom1'), 'builder':record.get('builder'),
                   'model':record['model'] if record.get('arm') != 'rule' else None,
                   'method':record.get('method', record.get('arm')), 'task':record['task'],
                   'record':str(path.relative_to(ROOT))}
            for label in ('first', 'final'):
                version = record['versions'][0 if label == 'first' else -1] if record['versions'] else None
                add(row, path.parent / version if version else None, bool(hidden[label]['all_passed']), label)
            if cohort in ('interface', 'frontier') and row['method'] == 'plan' and row['task'] == 'task-20':
                page = path.parent / record['versions'][-1] if record['versions'] else None
                controls.append((row, page))
    sources = ROOT / 'artifacts/webbench-expand-controls/sources.json'
    freeze(sources)
    old_controls = read(ROOT / 'artifacts/webbench-expand-controls/results.json')['rows']
    freeze(ROOT / 'artifacts/webbench-expand-controls/results.json')
    for source in read(sources):
        for k in range(1, 21):
            row = {k2:v for k2,v in source.items() if k2 != 'page'}
            row.update(cohort='expansion', method='control/' + row.pop('control'), task=f'task-{k}', record=None)
            old = next(x['passed'] for x in old_controls if all(x[n] == row[n] for n in ('project','builder','model','task')) and 'control/' + x['control'] == row['method'])
            add(row, ROOT / source['page'] if source['page'] else None, old)
            if source['control'].startswith('example-') and k in (4,8,12,16,20):
                add({**row, 'cohort':'frontier'}, ROOT / source['page'] if source['page'] else None, old)
    for row, page in controls:
        for k in (range(1,21) if row['cohort'] == 'interface' else (4,8,12,16,20)):
            add({**row, 'method':'control/final-plan', 'task':f'task-{k}'}, page, None)
    calibration = {}
    seen = set()
    for row in rows:
        name = harness_name(row['cohort'], row['project'])
        if name in seen:
            continue
        seen.add(name)
        if row['cohort'] == 'expert':
            rule = next(r for r in rows if r['cohort']=='expert' and r['method']=='rule' and r['task']=='task-20' and r['label']=='final')
            page = ROOT / rule['page']
        else:
            page = UPSTREAM / 'projects' / row['project'] / 'src'
        files = source_files(page, row['cohort'] == 'expert')
        for file in files:
            freeze(page / file)
        common = {'harness':name, 'runtime':COHORTS[row['cohort']][1], 'project':row['project']}
        calibration[name + '/reference'] = {**common,'page':str(page.relative_to(ROOT)), 'files':files,
                                           'specs':['init', *[f'task-{i}' for i in range(1,21)]], 'all_tests':True}
        blank = OUT / 'blank' / name
        blank.mkdir(parents=True, exist_ok=True)
        (blank / 'index.html').write_text('<!doctype html><title>blank</title>')
        freeze(blank / 'index.html')
        calibration[name + '/negative'] = {**common,'page':str(blank.relative_to(ROOT)),
            'files':source_files(blank), 'specs':['task-1'], 'all_tests':False}
    for p in [HERE / 'run.py', HERE / 'PROTOCOL.md', ROOT / 'test/todomvc_dna/evaluate.py']:
        freeze(p)
    for p in (OUT / 'harness').rglob('*'):
        if p.is_file() and 'node_modules' not in p.parts:
            freeze(p)
    for runtime in RUNTIME.values():
        freeze(runtime / '@playwright/test/package.json')
        freeze(runtime.parent / 'package-lock.json')
        for name in ('index.js','css.js'):
            path = runtime / '@web-bench/test-util' / name
            if path.exists():
                freeze(path)
    dump(OUT / 'inputs.json', {'rows':rows,'jobs':jobs,'calibration':calibration,
                              'scope':'Fixed complete historical cohorts; same-page raw history, no assertion exclusions.'})
    freeze(OUT / 'inputs.json')
    dump(OUT / 'snapshot.json', {'frozen_utc':now(), 'sha256':frozen,
                               'upstream_commit':'7b31ca2b786eef120dd49ce63dd03d0c0006046d'})
    print('Frozen',len(rows),'comparisons',len(jobs),'unique history jobs',flush=True)
    from collections import Counter
    print(Counter(j['project'] for j in jobs.values()),flush=True)


def verify():
    snapshot = read(OUT / 'snapshot.json')
    for path, value in snapshot['sha256'].items():
        assert sha(ROOT / path) == value, path
    return read(OUT / 'inputs.json')


def grade(key, job, calibration=False):
    folder = OUT / ('calibration' if calibration else 'scores') / key
    if (folder / 'score.json').exists():
        saved = read(folder / 'score.json')
        assert saved['report_sha256'] == sha(folder / 'report.json')
        return saved
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'report.json'
    assert not report.exists(), 'Preserve partial reports; explicit infrastructure recovery required'
    page = ROOT / job['page']
    assert all(sha(page / n) == h for n,h in job['files'].items())
    server = Server(page)
    try:
        env = {**browser_env(), 'REPORT_FILE':str(report), 'CI':'1', 'WORKERS':'1',
               'CANDIDATE_URL':f'http://127.0.0.1:{server.port}', 'EVAL_PROJECT_ROOT':str(page)}
        command = ['node',str(RUNTIME[job['runtime']] / '@playwright/test/cli.js'),'test',
                   '--config','playwright.config.cjs','--workers=1', '--max-failures=' + ('0' if job.get('all_tests') else '1'),
                   '--output',str(folder / 'playwright-output')]
        command += ['test/' + name + '.spec.js' for name in job['specs']]
        done = subprocess.run(command,cwd=OUT / 'harness' / job['harness'],env=env,capture_output=True,text=True,timeout=1500)
    finally:
        server.close()
    (folder / 'runner.txt').write_text(done.stdout + done.stderr)
    assert report.exists(), (key,done.stderr[-1000:])
    payload = read(report)
    errors = [e for e in payload.get('errors',[]) if 'maximum allowed failures' not in e.get('message','')]
    assert not errors, errors
    cases = cases_by_file(payload)
    assert set(cases).issubset(job['specs'])
    passed = set(cases)==set(job['specs']) and all(v and all(c['passed'] for c in v) for v in cases.values())
    failed = any(s in ('failed','timedOut') for v in cases.values() for c in v for s in c['statuses'])
    assert passed or failed, 'Incomplete execution without decisive failure'
    if job.get('all_tests'):
        assert set(cases)==set(job['specs']) and all(c['statuses'] and not any(s in ('skipped','interrupted') for s in c['statuses']) for v in cases.values() for c in v)
    value = {'all_passed':passed,'tests':cases,'exit_code':done.returncode,'report_sha256':sha(report),
             'candidate_outcome_exact':True,'test_level_mean_valid':passed,'finished_utc':now()}
    dump(folder / 'score.json',value)
    return value


def calibrate():
    inputs = verify()
    def one(item):
        key, job = item
        value = grade(key,job,True)
        print('calibration',key,value['all_passed'],flush=True)
        return key,value
    jobs = list(inputs['calibration'].items())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(one,[j for j in jobs if j[1]['project'] != 'bom']))
    for item in jobs:
        if item[1]['project']=='bom':
            key,value=one(item)
            results[key]=value
    assert all(not v['all_passed'] for k,v in results.items() if k.endswith('/negative'))
    dump(OUT / 'calibration-complete.json',{'finished_utc':now(),'inputs_sha256':digest(inputs),
        'reference_failures':{k:[s for s,c in v['tests'].items() if not all(t['passed'] for t in c)] for k,v in results.items() if k.endswith('/reference')}})


def evaluate():
    inputs = verify()
    calibration = read(OUT / 'calibration-complete.json')
    assert calibration['inputs_sha256']==digest(inputs)
    started=OUT / 'grading-started.json'
    if not started.exists():
        dump(started,{'started_utc':now(),'inputs_sha256':digest(inputs),'calibration_sha256':digest(calibration)})
    assert read(started)['inputs_sha256']==digest(inputs)
    assert read(OUT/'snapshot.json')['frozen_utc'] <= calibration['finished_utc'] <= read(started)['started_utc']
    def group(jobs,workers,label):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i,_ in enumerate(pool.map(lambda item:grade(*item),jobs),1):
                if i%10==0 or i==len(jobs):
                    print(label,i,'/',len(jobs),flush=True)
    items=list(inputs['jobs'].items())
    # A separate serial BOM queue overlaps only non-BOM work.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(group,[j for j in items if (j[1]['project']=='bom')==is_bom],1 if is_bom else 4,'bom' if is_bom else 'other') for is_bom in (True,False)]
        for future in futures:
            future.result()
    dump(OUT/'evaluation-complete.json',{'finished_utc':now(),'inputs_sha256':digest(inputs),'jobs':len(items)})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','calibrate','evaluate'])
    args=parser.parse_args()
    {'prepare':prepare,'calibrate':calibrate,'evaluate':evaluate}[args.phase]()
