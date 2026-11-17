"""Browser execution for explicitly selected official files.

Callers must set a new output directory. No cumulative-prefix scheduling is
provided; retired stages are reproduced using their original Git revision.
"""
from pathlib import Path
import shutil
import subprocess
from studies.study_io import ROOT, UPSTREAM, read, dump, sha, now, source_files, cases_by_file
from test.todomvc_dna.evaluate import Server, browser_env

OUT = None
RUNTIME = {'163': ROOT / 'test/webbench_dna/harness/node_modules',
           '157': ROOT / 'artifacts/webbench-expand-runtime-157/node_modules'}
COHORTS = {'expert': (None, '163'), 'interface': (None, '163'),
           'expansion': (None, '157'), 'frontier': (None, '157')}


def current_task_specs(task):
    if not isinstance(task, str) or not task.startswith('task-') or not task[5:].isdigit() or int(task[5:]) < 1:
        raise ValueError('Expected a positive official task id')
    return [task]


def check_explicit_specs(specs):
    if not specs or len(specs) != len(set(specs)):
        raise ValueError('Specify distinct official test files')
    tasks = {name for name in specs if name.startswith('task-')}
    # Also reject the retired task-only variant, while allowing sparse public
    # feedback subsets and a single initialization/loading calibration.
    if (len(tasks) > 1 or ('init' in specs and tasks)) and tasks == {f'task-{i}' for i in range(1, len(tasks) + 1)}:
        raise ValueError('Cumulative-prefix testing has been retired; use the current task file')


def harness_name(cohort, project):
    return ('expert' if cohort == 'expert' else ('163' if cohort == 'interface' else '157')) + '-' + project

def prepare_harness(cohort, project):
    if OUT is None:
        raise ValueError("Set an explicit output directory")
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

def grade(key, job, calibration=False):
    check_explicit_specs(job["specs"])
    if OUT is None:
        raise ValueError("Set an explicit output directory")
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
