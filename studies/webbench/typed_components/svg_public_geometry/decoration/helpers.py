"""Recover same-response helper declarations and replay strictly the original chart plans."""
from pathlib import Path
import json
import subprocess

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from . import run as stage

OUT=ROOT/'artifacts/svg-helper-reception-20261126'
HERE=Path(__file__).resolve().parent
RESULT=HERE/'helpers-result.json'


def main():
    files=[Path(__file__),HERE/'helpers.cjs',HERE/'helpers-protocol.md',Path(stage.__file__),stage.OUT/'seal.json']
    libraries={}
    rejected=[]
    for tag in stage.geometry.TAGS:
        f=stage.OUT/tag/'library.json'
        files.append(f)
        libraries[tag]=read(f)
        for event in libraries[tag]['attempts']:
            if event.get('reason')!='Expected just the declared two-argument function':continue
            name=event['module']
            receipts=list((stage.OUT/tag/'calls'/name).glob('transmission-*/settled.json'))
            assert len(receipts)==1
            res=receipts[0].with_name('response.json')
            assert sha(res)==read(receipts[0])['response_sha256']
            files.extend([res,receipts[0]])
            rejected.append((tag,name,res))
    reg=OUT/'registration.json'
    sources={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():core.save(reg,dict(utc=now(),sources=sources,requests=0))
    assert read(reg)['sources']==sources
    seal=OUT/'seal.json'
    if not seal.exists():
        rows=[]
        for tag,lib in libraries.items():
            checks=lib['final']
            hooks=dict(lib['functions'])
            records=[]
            base=[r for r in read(stage.geometry.OUT/'seal.json')['rows'] if r['tag']==tag]
            fixed=next(r for r in base if r['arm']=='fixed')
            for _,name,res in (r for r in rejected if r[0]==tag):
                raw=read(res)['choices'][0]['message']['content']
                proc=subprocess.run(['node',str(HERE/'helpers.cjs')],input=json.dumps(dict(name=name,raw=raw)),text=True,capture_output=True,timeout=12)
                if proc.returncode:
                    records.append(dict(name=name,retained=False,reason='No standalone function module'))
                    continue
                trial={**hooks,name:proc.stdout}
                candidate=stage.emit(fixed,trial,OUT/tag/'public'/name)
                after=stage.observe(candidate)
                gains=set(after['passed'])-set(checks['passed'])
                keep=stage.geometry.accept(checks,after) and any(k.split('/')[-1] in stage.ACTIONS[name] for k in gains)
                records.append(dict(name=name,retained=keep,public=after))
                if keep:hooks,checks=trial,after
            lib.update(helper_attempts=records,final=checks)
            core.save(OUT/tag/'public.json',{k:v for k,v in lib.items() if k!='functions'})
            for r in base:
                candidate=stage.emit(r,hooks,OUT/tag/r['arm']/str(r['task'])) if hooks and r['status']=='valid' else {}
                rows.append({**r,**candidate})
        core.save(seal,dict(registration=sha(reg),rows=rows,public={t:sha(OUT/t/'public.json') for t in libraries}))
    saved=read(seal)
    assert saved['registration']==sha(reg) and all(sha(OUT/t/'public.json')==s for t,s in saved['public'].items())
    harness=browser.verify_contract(stage.PROJECT)
    assert harness==read(stage.geometry.OUT/'registration.json')['harness']
    results=browser.evaluate(saved['rows'],OUT,{stage.PROJECT:harness},3)
    core.save(RESULT,dict(registration=sha(reg),seal=sha(seal),new_calls=0,libraries={t:read(OUT/t/'public.json') for t in libraries},
        rows=[dict(tag=r['tag'],arm=r['arm'],task=r['task'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in results]))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):main()
