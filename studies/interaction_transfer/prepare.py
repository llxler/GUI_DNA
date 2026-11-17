"""Calibrate fixtures before any API work, then freeze all experiment inputs."""
import argparse
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .domain import PROJECTS,development,target
from .fixtures import public_cases,heldout
from .reference import files
from .browser import evaluate
from test.interface_blind.core import ROOT,dump,digest,write_files

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/interaction-transfer-calibration-20261115'


def calibrate():
    assert not (OUT/'frozen.json').exists()
    public={project:[{**task,'public_cases':public_cases(project,i)} for i,task in enumerate(development(project))] for project in PROJECTS}
    dump(HERE/'public-development.json',public)
    jobs=[]
    for project in PROJECTS:
        page=OUT/'pages'/project/'reference'
        write_files(page,files(project))
        for task in public[project]:
            jobs.append((project,'public/'+task['id'],page,task['public_cases'],True))
        jobs.append((project,'hidden/reference',page,heldout(project),True))
        blank=OUT/'pages'/project/'blank';write_files(blank,{'index.html':'<!doctype html><title>blank</title>'})
        jobs.append((project,'negative/blank',blank,heldout(project)[:1],False))
    for project,mutation in [('todos','visible-index-delete'),('todos','persist-draft'),('rows','recreate-nodes')]:
        page=OUT/'pages'/project/mutation
        write_files(page,files(project,mutation))
        jobs.append((project,'negative/'+mutation,page,heldout(project),False))
    def one(job):
        project,name,page,cases,expected=job
        report=evaluate(page,project,cases)
        dump(OUT/'scores'/project/name/'report.json',report)
        print(project,name,report['passed'],'/',report['total'],'expected_all',expected,flush=True)
        return {'project':project,'name':name,'report':str((OUT/'scores'/project/name/'report.json').relative_to(ROOT)),
                'all_passed':report['all_passed'],'passed':report['passed'],'total':report['total'],'expected_all':expected}
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(one,jobs))
    dump(OUT/'calibration.json',{'rows':rows})
    assert all(r['all_passed']==r['expected_all'] for r in rows),'Calibration failed; no paid calls allowed'
    dump(OUT/'complete.json',{'calibration_sha256':digest(rows),'all_expectations_met':True})


def freeze():
    from .core import frozen_sources
    assert json.loads((OUT/'complete.json').read_text())['all_expectations_met']
    paths=frozen_sources()+[HERE/'prepare.py',HERE/'fixtures.py',HERE/'reference.py',HERE/'public-development.json',
        HERE/'PROTOCOL.md',HERE/'SOURCES.md',ROOT/'artifacts/interaction-transfer-sources-20261115/receipts.json']
    import importlib.metadata
    import playwright
    from playwright.sync_api import sync_playwright
    package=Path(playwright.__file__).parent/'driver/package/browsers.json'
    with sync_playwright() as pw:
        executable=Path(pw.chromium.executable_path)
    runtime={'playwright':importlib.metadata.version('playwright'),'browsers_manifest_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
             'chromium_executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest()}
    paths += list((OUT/'pages').rglob('index.html'))+list((OUT/'scores').rglob('report.json'))+[OUT/'complete.json',OUT/'calibration.json']
    from datetime import datetime,timezone
    value={'frozen_utc':datetime.now(timezone.utc).isoformat(),'runtime':runtime,'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
           'target_requirements':{p:target(p) for p in PROJECTS},'hidden_cases_sha256':{p:digest(heldout(p)) for p in PROJECTS}}
    assert not (OUT/'frozen.json').exists()
    dump(OUT/'frozen.json',value)
    print('All inputs and calibrated fixtures frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['calibrate','freeze'])
    {'calibrate':calibrate,'freeze':freeze}[parser.parse_args().phase]()
