"""Recover delivered named renderers and validate JavaScript inheritance on real public charts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import json
import os
import re
import subprocess

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.compact_todomvc.event_functions import delivery
from studies.study_io import ROOT,read,now,sha
from . import run as typed
from .unavailable import run as old

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/svg-admission-20261125'
CAP=.60
RESULT=HERE/'svg-admission-result.json'
TAGS=('qwen9','oss','mistral')
ACORN=delivery.events.modules.ACORN


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    files=[Path(__file__),HERE/'svg_admission.md',HERE/'inherited_fields.cjs',ACORN,old.HERE/'result.json',Path(typed.__file__)]
    cases=[]
    for t in TAGS:
        root=old.OUT/'svg-chart'/t
        seal=read(root/'seal.json')
        assert seal['status']=='build_failed'
        cases.append(seal['case'])
        files.extend([root/'seal.json',root/'A/modules.json',root/'A/build.json'])
        for f in sorted((root/'calls/A/build').rglob('settled.json')):files.extend([f,f.with_name('response.json')])
    bound=delivery.register()['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    core.save(path,dict(utc=now(),deadline=typed.compact.END.isoformat(),cap=CAP,combined_bound=bound,balance=balance,cases=cases,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def recovered(tag):
    comp=typed.charts.comp
    folder=old.OUT/'svg-chart'/tag
    sources=read(folder/'A/modules.json')
    locations={}
    for kind in ('base',*comp.KINDS):
        name=comp.path(kind)
        if name in sources:continue
        for f in sorted((folder/'calls/A/build'/kind/'initial').rglob('settled.json')):
            res=f.with_name('response.json')
            assert sha(res)==read(f)['response_sha256']
            raw=read(res)['choices'][0]['message']['content'] or ''
            blocks=re.findall(r'^[ \t]*`{3}(?:js|javascript)?[ \t]*\n(.*?)^[ \t]*`{3}[ \t]*$',raw,re.S|re.M|re.I)
            accepted=[]
            for candidate in blocks:
                try:accepted.append(comp.source(candidate,kind))
                except ValueError:pass
            if len(accepted)==1:
                sources[name]=accepted[0]
                locations[name]=str(res.relative_to(ROOT))
                break
    return sources,locations


def generate(case):
    t=case['builder'];p='svg-chart'
    root=OUT/p/t
    if (root/'seal.json').exists():return
    comp,svg=typed.charts.comp,typed.charts.base
    data=read(ROOT/case['public'])
    src,locations=recovered(t)
    attempts=[];edits={};rows=[]
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    orig=typed.base.template
    def template(project,tag,stage):
        settings=orig(project,tag,stage)
        if t=='qwen9':settings['reasoning']={'enabled':False}
        return settings
    def ask(ledger,name,messages,limit,schema=None):
        if schema is not None:messages=messages+[dict(role='user',content='Return only the JSON object. Required fields: '+json.dumps(schema['required']))]
        return typed.base.request(ledger,(p,t,'a'),root/'calls'/name,messages,'plan' if '/plan/' in name else 'build',8192)
    def draw(mods,iteration):
        base_page=svg.endpoint(root/f'probe-{iteration}',data,mods,svg.ALL)
        linked=typed.charts.links.link(base_page)
        # Only use modules the builder supplied for this project.
        new={name:(ROOT/linked['page']/name).read_text() for name in mods}
        point=svg.endpoint(root/f'linked-{iteration}',data,new,svg.ALL)
        observation=typed.charts.observe.observe(root,ROOT/point['page'],point['files'])
        return new,dict(point,public=observation)
    with patch.multiple(svg,OUT=root,ask=ask,MISSING=typed.MISSING),patch.object(typed.charts.links,'OUT',root/'linker'),patch.multiple(typed.base,OUT=OUT,END=typed.compact.END,template=template):
        try:
            if len(src)!=7:raise ValueError('Missing mandatory named renderer')
            src,fixed=draw(src,0)
            attempts.append(fixed['public'])
            if not svg.positive(fixed['public']):
                cmd=subprocess.run(['node',str(HERE/'inherited_fields.cjs'),str(ACORN)],input=json.dumps(src),text=True,capture_output=True,check=True)
                edits=json.loads(cmd.stdout)
                for name,changes in edits.items():
                    for item in sorted(changes,key=lambda v:v['start'],reverse=True):
                        # Acorn offsets are UTF-16 code units.
                        b=src[name].encode('utf-16-le')
                        src[name]=(b[:2*item['start']]+b[2*item['end']:]).decode('utf-16-le')
                src,fixed=draw(src,1)
                attempts.append(fixed['public'])
            if not svg.positive(fixed['public']):
                msg=core.messages('Fix the model-written chart modules so that public data draws real graphics. Read actual constructor contracts and field initialization. Return a JSON object containing files as an array of {path,content}, with complete sources for only the modules you change. Keep the registered mount code and chart names. Use no tests or external services.',dict(public=data,modules=src,observation=fixed['public']))
                raw=typed.base.request(ledger,(p,t,'a'),root/'repair',msg,'build',14000)
                updates=core.files_map(typed.base.parse_json(raw)['files'])
                if not updates or set(updates)-set(src):raise ValueError('Unexpected module path')
                src,fixed=draw(src|updates,2)
                attempts.append(fixed['public'])
            status='valid' if svg.positive(fixed['public']) else 'build_failed'
            if status=='valid':
                core.save(root/'A/modules.json',src)
                core.save(root/'admission.json',dict(public=fixed['public']))
                targets=case['deploy'][t]['targets']
                with ThreadPoolExecutor(max_workers=3) as pool:
                    plans=list(pool.map(lambda n:svg.choose(ledger,'A',n,data,{'status':'valid','selected':fixed},src),targets))
                for n,v in zip(targets,plans,strict=True):
                    for a,c in (('planned',v),('fixed',fixed)):
                        rows.append(dict(project=p,tag=t,task=n,arm=a,**{k:v for k,v in c.items() if k in ('status','reason','files','page')}))
        except typed.MISSING as exc:status='missing';attempts.append(str(exc))
        except typed.base.ERRORS as exc:status='build_failed';attempts.append(str(exc)[:450])
    core.save(root/'seal.json',dict(case=case,status=status,registration=sha(OUT/'registration.json'),rows=rows,reasons=attempts,recovered=locations,field_edits=edits))
    print(t,status,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        for c in reg['cases']:generate(c)
    if args.action=='score':
        import time
        from datetime import datetime,timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        with patch.object(typed,'OUT',OUT):
            for c in reg['cases']:
                while not (OUT/c['project']/c['builder']/'seal.json').exists():
                    if datetime.now(timezone.utc)>=typed.compact.END:raise SystemExit('deadline')
                    time.sleep(2)
                typed.score(c)
    if args.action=='publish':
        core.save(RESULT,dict(cost=ledger_read.totals(OUT/'budget.sqlite3'),registration_sha256=sha(OUT/'registration.json'),cases=[read(OUT/c['project']/c['builder']/'result.json') for c in reg['cases']]))
