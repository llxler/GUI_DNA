"""Link only existing same-library exports observed to be unbound on a public mixed page."""
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import run as survey

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/survey-witnessed-links-20261126'
PARENT=survey.OUT


def register():
    f=OUT/'registration.json'
    paths=[Path(__file__),HERE/'link.cjs',HERE/'PROTOCOL.md',Path(survey.__file__),PARENT/'registration.json']
    for tag in survey.TAGS:
        paths.extend(PARENT/tag/r/'library.json' for r in survey.FROZEN[tag])
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not f.exists():core.save(f,dict(utc=now(),sources=hashes,new_calls=0))
    assert read(f)['sources']==hashes


def cause(errors):
    for stack in errors:
        if not isinstance(stack,list) or len(stack)<2:continue
        hit=re.search(r'ReferenceError:\s*([A-Za-z_$][\w$]*) is not defined',stack[0])
        if hit:
            for frame in stack[1:]:
                site=re.search(r'/(common/[^/():]+\.js):\d+',frame)
                if site:return hit[1],site[1]
    return None


def prepare(tag,r):
    f=OUT/tag/r/'library.json'
    if f.exists():return read(f)
    src=read(PARENT/tag/r/'library.json')
    pkg=src['package']
    history=[]
    with patch.object(survey,'OUT',OUT):
        checks=survey.public(pkg,False,f.parent/'public/initial')
        initial=checks
        tried=set()
        for turn in range(5):
            pair=cause(checks['errors'])
            if not pair or pair in tried:break
            tried.add(pair)
            symbol,owner=pair
            op=subprocess.run(['node',str(HERE/'link.cjs')],input=json.dumps(dict(files=pkg['files'],owner=owner,symbol=symbol)),
                              capture_output=True,text=True,timeout=15)
            if op.returncode or not op.stdout.strip():
                history.append(dict(owner=owner,symbol=symbol,retained=False));break
            patched={**pkg,'files':{**pkg['files'],owner:op.stdout+pkg['files'][owner]}}
            after=survey.public(patched,False,f.parent/'public'/str(turn+1))
            keep=cause(after['errors'])!=pair and all(not v or after['checks'][k] for k,v in checks['checks'].items())
            history.append(dict(owner=owner,symbol=symbol,import_code=op.stdout.strip(),retained=keep))
            if not keep:break
            pkg,checks=patched,after
    core.save(f,dict(package=pkg,initial=initial,after=checks,edits=history))
    return read(f)


def main(phase):
    register()
    libs={(t,r):prepare(t,r) for t in survey.TAGS for r in survey.FROZEN[t]}
    if phase=='prepare':return
    parent=read(PARENT/'seal.json')
    assert parent['registration']==sha(PARENT/'registration.json') and all(sha(PARENT/k)==v for k,v in parent['sources'].items())
    f=OUT/'seal.json'
    if not f.exists():
        rows=[]
        for (t,r),lib in libs.items():
            folder=OUT/t/r
            fixed=survey.compile_page(lib['package'],survey.EXAMPLE,False,folder/'fixed')
            for n in range(1,21):
                pre=PARENT/t/'targets'/str(n)
                prev=next(v for v in read(pre/'rows.json') if v['arm']=='self-'+r)
                if prev['status']!='valid' or not any(e['retained'] for e in lib['edits']):
                    value={k:prev[k] for k in ('status','page','files','reason') if k in prev}
                else:
                    raw,_=survey.receiver.delivered([pre/'shared-call'])
                    p=survey.semantic(raw)
                    value=survey.compile_page(lib['package'],p,False,folder/'targets'/str(n))
                rows.extend([dict(tag=t,rep=r,task=n,project='form',arm='self',**value),
                             dict(tag=t,rep=r,task=n,project='form',arm='fixed',**fixed)])
        core.save(f,dict(registration=sha(OUT/'registration.json'),parent=sha(PARENT/'seal.json'),rows=rows))
    assert read(f)['registration']==sha(OUT/'registration.json') and read(f)['parent']==sha(PARENT/'seal.json')
    proto=browser.verify_contract('form')
    assert proto==read(survey.BASE/'browser.json')
    graded=browser.evaluate(read(f)['rows'],OUT,{'form':proto},3)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(f),new_calls=0,
          libraries={t:{r:{k:v for k,v in libs[t,r].items() if k!='package'} for r in survey.FROZEN[t]} for t in survey.TAGS},
          rows=[dict(tag=r['tag'],rep=r['rep'],arm=r['arm'],task=r['task'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],
                     report_sha256=r.get('report_sha256')) for r in graded]))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('prepare','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
