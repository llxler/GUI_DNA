"""Replay the originally delivered patch at its independently corroborated file path."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
import re

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.line_contract import run as lines
from studies.study_io import ROOT, digest, read, sha

HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'artifacts/self-normalized-table-20261124'
OUT=ROOT/'artifacts/self-binding-20261124'
PROJECT='table'
TAG='oss'
BASE=SOURCE/TAG
OUTPUT=ROOT/'studies/results/self-binding-table-20261124.json'

def register():
    dest=OUT/'registered.json'
    if dest.exists():
        verify()
        return
    paths=[HERE/'BINDING.md',Path(__file__),Path(method.__file__),Path(lines.__file__),Path(browser.__file__),
           SOURCE/'registered.json',SOURCE/'public.json',SOURCE/'browser.json',BASE/'seal.json',
           BASE/'build/status.json',BASE/'build/manifest.json',BASE/'build/initial-source.json',
           BASE/'build/initial-public-check.json',BASE/'build/repair-public-check.json',
           BASE/'build/source-repair/request.json',BASE/'build/source-repair/response.json',
           BASE/'build/source-repair/settled.json']
    paths.extend(BASE/'plans'/str(i)/'status.json' for i in range(1,21))
    core.save(dest,{'utc':core.now(),'source_model':read(BASE/'seal.json')['model'],'project':PROJECT,
              'targets':list(range(1,21)),'new_api_calls':0,'new_usd':0,
              'files':{str(p.relative_to(ROOT)):sha(p) for p in paths}})

def verify():
    for p,h in read(OUT/'registered.json')['files'].items():
        if sha(ROOT/p)!=h: raise ValueError('Frozen binding input changed: '+p)

def locate(files, errors, patch):
    names=set()
    for error in errors:
        imports=re.findall(r"""module\s+['"]([^'"]+)['"]\s+does not provide an export""",error)
        for imp in imports:
            matched=[name for name in files if PurePosixPath(name).name==PurePosixPath(imp).name]
            if len(matched)==1: names.add(matched[0])
    first=next((s.strip() for s in patch.splitlines() if s.strip()),'')
    owner=re.fullmatch(r'//\s*(?:file:\s*)?(?:\./)?([\w./-]+\.(?:m?js|css))\s*',first,re.I)
    return owner[1] if owner and names=={owner[1]} else None

def materialize():
    verify()
    public=read(SOURCE/'public.json')
    spec=read(BASE/'build/manifest.json')
    files=read(BASE/'build/initial-source.json')
    original=read(BASE/'build/initial-public-check.json')
    response=BASE/'build/source-repair/response.json'
    assert sha(response)==read(BASE/'build/source-repair/settled.json')['response_sha256']
    patch=method.source(read(response)['choices'][0]['message']['content'])
    target=locate(files,original['load_errors'],patch)
    if not target: raise ValueError('Independent source identification did not agree')
    import json
    sent=read(BASE/'build/source-repair/request.json')['body']['messages'][-1]['content']
    addressed=json.loads(sent)['requested_file']
    if addressed==target: raise ValueError('Unchanged destination, ineligible for the diagnostic')
    sources=files|{target:patch}
    check=lines.public_check(public,spec,sources,OUT/'first')
    core.save(OUT/'public-check.json',check)
    pages={}
    for task in range(1,21):
        plan=read(BASE/'plans'/str(task)/'status.json')
        if plan['status']!='valid': raise ValueError('Source deployment lacks a received valid plan')
        pages[str(task)]=method.emit(public,sources,plan['plan'],OUT/'plans'/str(task))
    core.save(OUT/'seal.json',{'registration_sha256':sha(OUT/'registered.json'),'addressed_path':addressed,
        'corroborated_path':target,'initial_source_sha256':sha(BASE/'build/initial-source.json'),
        'original_patch_response_sha256':sha(response),'public_check_sha256':sha(OUT/'public-check.json'),
        'new_source_hashes':check['files'],'pages':pages})

def evaluate():
    verify()
    browser.OUT=OUT
    seal=read(OUT/'seal.json')
    assert seal['registration_sha256']==sha(OUT/'registered.json')
    assert seal['public_check_sha256']==sha(OUT/'public-check.json')
    contract=browser.verify_contract(PROJECT)
    assert contract==read(SOURCE/'browser.json')
    def one(job):
        arm,task=job
        path,files=((OUT/'first',seal['new_source_hashes']) if arm=='fixed' else
                    (OUT/'plans'/str(task),seal['pages'][str(task)]))
        score=browser.run_one(OUT,PROJECT,task,path,files,contract)
        return {'arm':arm,'task':task,'passed':score['passed'],'files_sha256':digest(files),
                'report_sha256':score['report_sha256']}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(one,[(a,i) for a in ('self','fixed') for i in range(1,21)]))
    core.save(OUT/'scores.json',results)

def publish(check=False):
    verify()
    seal=read(OUT/'seal.json')
    scores=read(OUT/'scores.json')
    old=read(BASE/'scores.json')
    assert len(scores)==len(old)==40
    summaries={}
    for arm in ('self','fixed'):
        rows=[r for r in scores if r['arm']==arm]
        prior={r['task']:r for r in old if r['arm']==arm}
        assert sorted(prior)==sorted(r['task'] for r in rows)==list(range(1,21))
        for r in rows:
            path=OUT/'browser/scores'/PROJECT/f'task-{r["task"]}'/r['files_sha256']/'score.json'
            contract=read(SOURCE/'browser.json')
            expected={'project':PROJECT,'task':r['task'],'files_digest':r['files_sha256'],'contract_digest':digest(contract)}
            receipt=browser.verify_receipt(OUT,path,expected)
            assert receipt['report_sha256']==r['report_sha256'] and receipt['passed']==r['passed']
            files=seal['new_source_hashes'] if arm=='fixed' else seal['pages'][str(r['task'])]
            page=OUT/'first' if arm=='fixed' else OUT/'plans'/str(r['task'])
            browser.verify_page(page,files,PROJECT)
            assert digest(files)==r['files_sha256']
        summaries[arm]={'original_pass':sum(r['passed'] for r in prior.values()),
                        'rebound_pass':sum(r['passed'] for r in rows),'matched':len(rows),
                        'gained':[r['task'] for r in rows if r['passed'] and not prior[r['task']]['passed']],
                        'lost':[r['task'] for r in rows if not r['passed'] and prior[r['task']]['passed']]}
    def quality(path):
        data=read(path)
        return {'load_errors':data['load_errors'],'probe':data['probe']}
    reg=read(OUT/'registered.json')
    result={'study':'Post-construction patch destination diagnostic','model':reg['source_model'],'project':PROJECT,
        'registered_utc':reg['utc'],'registration_sha256':sha(OUT/'registered.json'),'seal_sha256':sha(OUT/'seal.json'),
        'protocol_sha256':sha(HERE/'BINDING.md'),'upstream_commit':browser.UPSTREAM_COMMIT,'additional_api_calls':0,
        'additional_api_usd':0,'historical_source_scores_sha256':sha(BASE/'scores.json'),'addressed_path':seal['addressed_path'],
        'corroborated_path':seal['corroborated_path'],'patch_response_sha256':seal['original_patch_response_sha256'],
        'initial_source_sha256':seal['initial_source_sha256'],'public_checks':{
            'initial':quality(BASE/'build/initial-public-check.json'),
            'original_repair':quality(BASE/'build/repair-public-check.json'),
            'rebound_repair':quality(OUT/'public-check.json')},'summary':summaries,'rows':scores,
        'source_rows':[{k:r[k] for k in ('arm','task','passed','files_sha256','report_sha256')} for r in old]}
    if check:
        if result!=read(OUTPUT): raise ValueError('Published diagnostic differs from receipts')
    else: core.save(OUTPUT,result)
    print(summaries)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','materialize','evaluate','publish','check'))
    args=parser.parse_args()
    if args.action=='check': return publish(True)
    globals()[args.action]()

if __name__=='__main__': main()
