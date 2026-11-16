"""Continue unchanged BOM configurations with an explicit calibration exception."""
import argparse
from datetime import datetime, timezone
import subprocess
from test.schema_search import run as original
from test.history_replay import run as history
from test.history_replay.run import ROOT, read, dump, sha, now, source_files

OUT=ROOT/'artifacts/schema-search-continue-20261116'
HERE=ROOT/'test/schema_search_continue'


def prepare():
    inputs=original.verify()
    assert not OUT.exists()
    assert not (original.OUT/'grading-started-bom.json').exists()
    selected={k:j for k,j in inputs['jobs'].items() if j['project']=='bom'}
    assert len(selected)==102
    assert not any((original.OUT/'scores'/k/'score.json').exists() for k in selected)
    assert (ROOT/'artifacts/matched-feedback-frontier-continue-20261116/evaluation-complete.json').exists()
    old=original.OUT/'calibration/bom'
    assert all(read(old/label/'score.json')['all_passed'] for label in ('current','history','blank'))
    OUT.mkdir(parents=True)
    (OUT/'inputs.json').write_bytes((original.OUT/'inputs.json').read_bytes())
    dump(OUT/'continuation.json',{'prior_stage':str(original.OUT.relative_to(ROOT)),
        'reason':'BOM blank task-20 unexpectedly passes; null satisfies toBeDefined and tests return early.',
        'candidate_jobs':len(selected),'original_inputs_sha256':sha(original.OUT/'inputs.json'),
        'original_bom_candidates_scored':0,'registered_utc':now()})
    history.OUT=OUT
    history.prepare_harness('expansion','bom')
    files={ROOT/p for p in read(original.OUT/'snapshot.json')['sha256']}
    files.update(p for p in old.rglob('*') if p.is_file())
    files.update(p for p in (OUT/'harness').rglob('*') if p.is_file() and 'node_modules' not in p.parts)
    files.update([HERE/'run.py',HERE/'PROTOCOL.md',HERE/'__init__.py',OUT/'inputs.json',OUT/'continuation.json'])
    dump(OUT/'snapshot.json',{'frozen_utc':now(),'sha256':{str(p.relative_to(ROOT)):sha(p) for p in files}})
    print('Frozen BOM continuation with preserved negative-control exception',flush=True)


def evaluate():
    for path,expected in read(OUT/'snapshot.json')['sha256'].items():assert sha(ROOT/path)==expected,path
    assert not (OUT/'grading-started-bom.json').exists()
    original.verify();history.OUT=OUT
    runtime=history.RUNTIME['157']/'@playwright/test'
    script="const {expect}=require(process.argv[1]);let a=true,b=true;try{expect(null).toBeDefined()}catch{a=false}try{expect(undefined).toBeDefined()}catch{b=false}console.log(JSON.stringify({null_passes:a,undefined_passes:b}));"
    done=subprocess.run(['node','-e',script,str(runtime)],check=True,capture_output=True,text=True)
    import json
    probe=json.loads(done.stdout);assert probe=={'null_passes':True,'undefined_passes':False}
    dump(OUT/'matcher-probe.json',{'script':script,'runtime':str(runtime.relative_to(ROOT)),'result':probe})
    specs=['init',*[f'task-{i}' for i in range(1,21)]]
    page=original.OUT/'blank/bom'
    job={'project':'bom','harness':'157-bom','runtime':'157','page':str(page.relative_to(ROOT)),
        'files':source_files(page),'specs':specs,'all_tests':False}
    assert not history.grade('bom/blank-history',job,True)['all_passed']
    dump(OUT/'grading-started-bom.json',{'started_utc':now(),'inputs_sha256':sha(OUT/'inputs.json')})
    selected=[(k,j) for k,j in read(OUT/'inputs.json')['jobs'].items() if j['project']=='bom']
    for i,(key,job) in enumerate(selected,1):
        assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-11-16T07:00:00+00:00')
        history.grade(key,job)
        if i%16==0 or i==len(selected):print('bom',i,'/',len(selected),flush=True)
    dump(OUT/'evaluation-complete-bom.json',{'finished_utc':now(),'inputs_sha256':sha(OUT/'inputs.json')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','evaluate']);args=p.parse_args()
    prepare() if args.action=='prepare' else evaluate()
