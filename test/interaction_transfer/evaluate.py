"""Freeze all complete candidates and deterministic controls before hidden scoring."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from .core import ROOT,BUILD,RUN,CALIBRATION,dump,digest
from .run import verify,now
from . import controls
from .fixtures import heldout
from .browser import evaluate


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    verify();assert not (RUN/'scoring-inputs.json').exists()
    barrier=read(RUN/'generation-complete.json')
    assert barrier['candidates']==36 and barrier['transport_incomplete']==0
    if not (controls.OUT/'inputs.json').exists():controls.prepare()
    rows,jobs,files=[],{},{}
    def add(row,page):
        row={**row,'score_key':None,'page':str(page.relative_to(ROOT)) if page else None}
        if page:
            manifest=read(page/'source-manifest.json')['files_sha256']
            for name,value in manifest.items():
                path=page/name
                assert sha(path)==value
                files[str(path.relative_to(ROOT))]=value
            key=digest({'project':row['project'],'files':manifest,'cases':heldout(row['project'])})
            jobs.setdefault(key,{'project':row['project'],'page':str(page.relative_to(ROOT)),'files_sha256':manifest})
            row['score_key']=key
        rows.append(row)
    for path,value in barrier['records_by_path_sha256'].items():
        folder=RUN/path;record=read(folder/'record.json');assert digest(record)==value and record['status']=='complete'
        metadata={k:record[k] for k in ('project','builder','condition','model','method','task')}
        for label in ('first','final'):
            version=('version-0' if 'version-0' in record['versions'] else None) if label=='first' else (record['versions'][-1] if record['versions'] else None)
            add({**metadata,'kind':'candidate','label':label,'record':str((folder/'record.json').relative_to(ROOT)),
                 'unavailable_library':record.get('unavailable_library',False)},folder/version if version else None)
    for source in read(controls.OUT/'inputs.json')['rows']:
        add({k:v for k,v in {**source,'kind':'control','label':'final'}.items() if k!='page'},ROOT/source['page'] if source['page'] else None)
    dump(RUN/'scoring-inputs.json',{'rows':rows,'jobs':jobs,'generation_sha256':digest(barrier)})
    for root in (RUN/'runs',BUILD/'libraries',controls.OUT):
        for p in root.rglob('*'):
            if p.is_file() and 'playwright-output' not in p.parts:files[str(p.relative_to(ROOT))]=sha(p)
    for p in (RUN/'scoring-inputs.json',RUN/'generation-complete.json',CALIBRATION/'frozen.json'):files[str(p.relative_to(ROOT))]=sha(p)
    dump(RUN/'scoring-snapshot.json',{'frozen_utc':now(),'sha256':files})
    print('Frozen',len(rows),'comparisons',len(jobs),'unique pages',flush=True)


def verify_scoring():
    verify()
    for p,value in read(RUN/'scoring-snapshot.json')['sha256'].items():assert sha(ROOT/p)==value,p
    inputs=read(RUN/'scoring-inputs.json')
    assert inputs['generation_sha256']==digest(read(RUN/'generation-complete.json'))
    return inputs


def score():
    inputs=verify_scoring()
    start=RUN/'grading-started.json'
    if not start.exists():dump(start,{'started_utc':now(),'inputs_sha256':digest(inputs)})
    assert read(start)['inputs_sha256']==digest(inputs)
    assert read(RUN/'generation-complete.json')['finished_utc']<=read(RUN/'scoring-snapshot.json')['frozen_utc']<=read(start)['started_utc']
    def one(item):
        key,job=item;folder=RUN/'scores'/key
        if (folder/'receipt.json').exists():
            assert sha(folder/'report.json')==read(folder/'receipt.json')['report_sha256'];return
        assert not (folder/'report.json').exists(),'Preserve partial reports'
        report=evaluate(ROOT/job['page'],job['project'],heldout(job['project']))
        dump(folder/'report.json',report)
        dump(folder/'receipt.json',{'finished_utc':now(),'report_sha256':sha(folder/'report.json')})
        print(job['project'],key[:10],report['passed'],'/',report['total'],flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(one,inputs['jobs'].items()))
    dump(RUN/'evaluation-complete.json',{'finished_utc':now(),'inputs_sha256':digest(inputs),'jobs':len(inputs['jobs'])})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','score'])
    {'prepare':prepare,'score':score}[p.parse_args().phase]()
