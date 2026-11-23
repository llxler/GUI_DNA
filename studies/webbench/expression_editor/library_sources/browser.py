"""Fixed local Chromium harness for the unchanged official expression-editor files."""
from pathlib import Path
import shutil
import subprocess

from studies import browser_jobs
from studies.study_io import ROOT, dump, read, sha, source_files
from studies.table_library_sources.run import file_hashes
from .core import HERE, OUT, PROJECT, RUNTIME, SOURCE

HARNESS = '157-' + PROJECT
RUNTIME_KEY = 'expression-editor-157'


def install():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for src, dest in ((HERE/'runtime-package.json',RUNTIME/'package.json'),
                      (HERE/'runtime-lock.json',RUNTIME/'package-lock.json')):
        if dest.exists():
            assert sha(src)==sha(dest)
        else:
            shutil.copy2(src,dest)
    util = ROOT/'studies/webbench_dna/harness/test-util'
    for path in util.rglob('*'):
        if path.is_file():
            dest = RUNTIME/'test-util'/path.relative_to(util)
            if dest.exists():
                assert sha(path)==sha(dest)
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,dest)
    if not (RUNTIME/'node_modules/tinycolor2/package.json').exists():
        subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=RUNTIME,check=True)
    assert read(RUNTIME/'node_modules/tinycolor2/package.json')['version']=='1.6.0'
    assert read(RUNTIME/'node_modules/@playwright/test/package.json')['version']=='1.57.0'


def harness():
    install()
    path = OUT/'harness'/HARNESS
    path.mkdir(parents=True)
    shutil.copytree(SOURCE/'test',path/'test')
    (path/'node_modules').symlink_to(RUNTIME/'node_modules',target_is_directory=True)
    dump(path/'package.json',{'type':'commonjs'})
    (path/'playwright.config.cjs').write_text("""const {defineConfig,devices}=require('@playwright/test');
module.exports=defineConfig({testDir:'./test',timeout:10000,expect:{timeout:5000},workers:1,retries:0,
fullyParallel:false,forbidOnly:true,reporter:[['json',{outputFile:process.env.REPORT_FILE}]],
use:{baseURL:process.env.CANDIDATE_URL,trace:'off',headless:true},
projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
""")
    for spec in (SOURCE/'test').glob('*.js'):
        assert sha(spec)==sha(path/'test'/spec.name)
    return file_hashes([p for p in (path/'test').rglob('*') if p.is_file()]
                +[path/'package.json',path/'playwright.config.cjs',RUNTIME/'package-lock.json',
                  RUNTIME/'node_modules/tinycolor2/tinycolor.js',*(RUNTIME/'test-util').glob('*.js')])


def score(key, task, page, control):
    browser_jobs.OUT = OUT
    browser_jobs.RUNTIME[RUNTIME_KEY] = RUNTIME/'node_modules'
    job = {'harness':HARNESS,'runtime':RUNTIME_KEY,'page':str(page.relative_to(ROOT)),
           'files':source_files(page),'specs':browser_jobs.current_task_specs(task)}
    result = browser_jobs.grade(key,job,calibration=control)
    return {'passed':result['all_passed'],'report_sha256':result['report_sha256']}
