"""Diagnostic fixed page with every optional expression-editor UI binding disabled."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil

from studies import browser_jobs
from studies.expression_editor_sources.browser import HARNESS, RUNTIME_KEY
from studies.expression_editor_sources.core import OUT as TRIAL, RUNTIME, TASKS, render
from studies.interface_blind.core import write_files
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources.run import file_hashes, verify

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/expression-editor-empty-plan-20261123'
DEST=ROOT/'studies/results/expression-editor-empty-plan-20261123.json'
PLAN={'toolbar':[],'controllers':[]}
FIXED=('reference_full','starter','blank','upstream_final')


def freeze():
    if OUT.exists() or (TRIAL/'scores-complete.json').exists() or (TRIAL/'scores').exists():
        raise RuntimeError('Must preserve existing outputs and freeze before formal scoring')
    verify(read(TRIAL/'freeze.json')['inputs_sha256'])
    official=read(TRIAL/'controls-complete.json')['rows']
    harness=OUT/'harness'/HARNESS
    original=TRIAL/'harness'/HARNESS
    shutil.copytree(original,harness,symlinks=True)
    assert (harness/'node_modules').resolve()==(original/'node_modules').resolve()
    inputs=[HERE/'run.py',HERE/'PROTOCOL.md',TRIAL/'freeze.json',TRIAL/'controls-complete.json',TRIAL/'reference.json']
    for f in [harness/'playwright.config.cjs',harness/'package.json',*(harness/'test').glob('*.js')]:
        assert sha(f)==sha(original/f.relative_to(harness))
        inputs.append(f)
    for task in TASKS:
        for c in FIXED:
            raw=TRIAL/'calibration'/c/task/'report.json'
            assert sha(raw)==official[c+'/'+task]['report_sha256']
            inputs.extend((raw,raw.with_name('score.json')))
    page=OUT/'page'
    write_files(page,render('reference',read(TRIAL/'reference.json'),PLAN))
    inputs.extend(p for p in page.rglob('*') if p.is_file())
    dump(OUT/'freeze.json',{'frozen_utc':now(),'task_ids':TASKS,'plan':PLAN,'page_files_sha256':source_files(page),
                            'inputs_sha256':file_hashes(inputs),'parent_formal_scoring_started':False})


def summarize(targets):
    values={s:[targets[t][s]['passed'] for t in TASKS] for s in ('empty_plan',*FIXED)}
    return {'counts':{s:{'passed':sum(v),'observed':len(v)} for s,v in values.items()},
            'passed_with_optional_controls_off':[t for t in TASKS if targets[t]['empty_plan']['passed']],
            'all_enabled_only':[t for t in TASKS if targets[t]['reference_full']['passed'] and not targets[t]['empty_plan']['passed']],
            'empty_plan_only':[t for t in TASKS if targets[t]['empty_plan']['passed'] and not targets[t]['reference_full']['passed']]}


def generate():
    manifest=read(OUT/'freeze.json')
    verify(manifest['inputs_sha256'])
    assert source_files(OUT/'page')==manifest['page_files_sha256']
    browser_jobs.OUT=OUT
    browser_jobs.RUNTIME[RUNTIME_KEY]=RUNTIME/'node_modules'
    old=read(TRIAL/'controls-complete.json')['rows']
    def one(task):
        result=browser_jobs.grade(task,{'harness':HARNESS,'runtime':RUNTIME_KEY,
                'page':str((OUT/'page').relative_to(ROOT)),'files':manifest['page_files_sha256'],
                'specs':browser_jobs.current_task_specs(task)})
        assert set(result['tests'])=={task} and sha(OUT/'scores'/task/'report.json')==result['report_sha256']
        rows={'empty_plan':{'passed':result['all_passed'],'report_sha256':result['report_sha256']}}
        for c in FIXED:
            source=TRIAL/'calibration'/c/task
            rec=old[c+'/'+task]
            assert sha(source/'report.json')==rec['report_sha256'] and read(source/'score.json')['all_passed']==rec['passed']
            rows[c]=rec
        return task,rows
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=dict(pool.map(one,TASKS))
    return {'study':'expression-editor-empty-plan-20261123','project':'expression-editor','model_calls':0,
            'planned_task_files':len(TASKS),'new_browser_reports':len(TASKS),'frozen_utc':manifest['frozen_utc'],
            'scope':'Complete reference modules and a mounted editor, with every optional toolbar and controller disabled.',
            'plan':PLAN,'page_manifest_sha256':digest(manifest['page_files_sha256']),'freeze_sha256':sha(OUT/'freeze.json'),
            'targets':rows,'summary':summarize(rows)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','score','check','check-public'))
    args=parser.parse_args()
    if args.action=='freeze':
        freeze()
    elif args.action=='check-public':
        value=read(DEST)
        assert tuple(value['targets'])==TASKS and summarize(value['targets'])==value['summary']
        print(value['summary'])
    else:
        value=generate()
        if args.action=='score' and not DEST.exists():
            dump(DEST,value)
        assert read(DEST)==value
        print(value['summary'])
