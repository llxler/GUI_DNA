"""Evaluate every controller subset against each independent official table task."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies import browser_jobs
from studies.interface_blind.core import write_files
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources.core import CONTROLLERS, OUT as TRIAL, TASKS, render
from studies.table_library_sources.run import HARNESS, file_hashes, verify

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/table-controller-enumeration-20261123'
RESULTS = ROOT/'studies/results/table-library-sources-20261123.json'
MASKS = tuple(range(1 << len(CONTROLLERS)))


def controls(mask):
    return [c for index,c in enumerate(CONTROLLERS) if mask & (1<<index)]


def key(mask,task):
    return f'config-{mask:02d}/{task}'


def reuse_index():
    items={}
    for task in TASKS:
        for page,folder in [(TRIAL/'control-pages/reference_full', TRIAL/'calibration/reference_full'/task),
              (TRIAL/'candidates/reference'/task/'first/page', TRIAL/'scores/reference'/task/'first')]:
            files=source_files(page)
            raw=read(folder/'score.json')
            assert set(raw['tests'])=={task} and sha(folder/'report.json')==raw['report_sha256']
            item={'page':str(page.relative_to(ROOT)),'raw_dir':str(folder.relative_to(ROOT)),
                  'page_files_sha256':files,'report_sha256':raw['report_sha256'],'passed':raw['all_passed']}
            index=(digest(files),task)
            if index in items:
                assert items[index]['passed']==item['passed']
            else:
                items[index]=item
    return items


def freeze():
    if OUT.exists():
        raise RuntimeError('Preserve existing frozen board')
    historical=read(TRIAL/'freeze.json')
    verify(historical['inputs_sha256'])
    reference=read(TRIAL/'reference-package.json')
    original=read(RESULTS)
    assert original['summaries']['first']['by_arm_common']['reference']['observed']==len(TASKS)
    browser_jobs.OUT=OUT
    assert browser_jobs.prepare_harness('expansion','table')==HARNESS
    harness=OUT/'harness'/HARNESS
    prior=TRIAL/'harness'/HARNESS
    files=[p for p in (harness/'test').rglob('*') if p.is_file()]+[harness/'playwright.config.cjs',harness/'package.json']
    assert all(sha(p)==sha(prior/p.relative_to(harness)) for p in files)
    pages={}
    for mask in MASKS:
        page=OUT/'pages'/f'config-{mask:02d}'
        write_files(page,render('reference',reference,{'controllers':controls(mask)}))
        pages[mask]=source_files(page)
    assert len({digest(p) for p in pages.values()})==len(MASKS)
    assert pages[MASKS[-1]]==source_files(TRIAL/'control-pages/reference_full')
    known=reuse_index()
    reused={}
    for mask in MASKS:
        for task in TASKS:
            old=known.get((digest(pages[mask]),task))
            if old is not None:
                assert old['page_files_sha256']==pages[mask]
                reused[key(mask,task)]={f:v for f,v in old.items() if f!='page_files_sha256'}
                files += [ROOT/old['raw_dir']/'score.json',ROOT/old['raw_dir']/'report.json']
    files += [HERE/'run.py',HERE/'PROTOCOL.md',RESULTS,TRIAL/'freeze.json',TRIAL/'reference-package.json',
             ROOT/'studies/browser_jobs.py',ROOT/'studies/study_io.py',
             ROOT/'studies/table_library_sources/core.py',ROOT/'studies/table_library_sources/run.py',
             ROOT/'studies/interface_blind/core.py',ROOT/'studies/interface_blind/compile.cjs',
             ROOT/'studies/webbench_expand/core.py',ROOT/'studies/webbench_expand/schema.py',
             ROOT/'artifacts/webbench-expand-runtime-157/package-lock.json']
    dump(OUT/'freeze.json',{'frozen_utc':now(),'inputs_sha256':file_hashes(files),'tasks':TASKS,'controllers':CONTROLLERS,
                   'prior_results_known':True,'pages_sha256':pages,'reused':reused})


def run():
    manifest=read(OUT/'freeze.json')
    verify(manifest['inputs_sha256'])
    browser_jobs.OUT=OUT
    def one(job):
        mask,task=job
        name=key(mask,task)
        page=OUT/'pages'/f'config-{mask:02d}'
        hashes=manifest['pages_sha256'][str(mask)]
        assert source_files(page)==hashes
        known=manifest['reused'].get(name)
        if known is not None:
            assert hashes==source_files(ROOT/known['page'])
            original=ROOT/known['raw_dir']
            summary=read(original/'score.json')
            assert sha(original/'report.json')==known['report_sha256']==summary['report_sha256']
            assert known['passed']==summary['all_passed'] and set(summary['tests'])=={task}
            return name,{'passed':known['passed'],'report_sha256':known['report_sha256'],'reused':True}
        result=browser_jobs.grade(name,{'harness':HARNESS,'runtime':'157','page':str(page.relative_to(ROOT)),
                     'files':hashes,'specs':browser_jobs.current_task_specs(task)})
        return name,{'passed':result['all_passed'],'report_sha256':result['report_sha256'],'reused':False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=dict(pool.map(one,[(m,t) for t in TASKS for m in MASKS]))
    dump(OUT/'complete.json',{'frozen_sha256':sha(OUT/'freeze.json'),'completed_utc':now(),'rows':rows})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','run'))
    args=parser.parse_args()
    (freeze if args.action=='freeze' else run)()
