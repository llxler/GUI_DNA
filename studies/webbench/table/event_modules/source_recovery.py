"""Receive file-shaped self-built table installers without writing their behavior."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import time
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,read,sha,now
from studies.webbench.typed_components.svg_admission import ACORN
from . import run as parent

OUT=ROOT/'artifacts/table-installer-recovery-20261125'
HERE=parent.HERE
RESULT=HERE/'source-recovery-result.json'
CAP=.85
ORIGINAL=parent.OUT


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==h for p,h in reg['sources'].items())
        return reg
    previous=parent.register()
    bound=previous['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    files=[Path(__file__),HERE/'source-recovery.md',HERE/'installer.cjs',Path(parent.__file__),ORIGINAL/'registration.json',ACORN]
    core.save(path,dict(utc=now(),balance=balance,cap=CAP,combined_bound=bound,deadline=previous['deadline'],targets=previous['targets'],
        models=previous['models'],eligibility='Every failed public build, independent of official outcomes.',
        sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def recover(raw):
    stripped=raw.strip()
    blocks=re.findall(r'^```(json|js|javascript|javascript:|css)?[ \t]*\n([\s\S]*?)^```[ \t]*$',stripped,re.M|re.I)
    css=''
    code=[(lang.lower(),v.strip()) for lang,v in blocks if lang.lower()!='css']
    styles=[v for lang,v in blocks if lang.lower()=='css']
    if blocks:
        if len(code)!=1 or len(styles)>1:raise ValueError('Ambiguous source blocks')
        stripped=code[0][1]
        if styles:css=styles[0]
    if stripped.startswith('{'):
        obj=json.loads(stripped)
        if set(obj)!= {'js','css'}:raise ValueError('Invalid JSON fields')
        stripped,css=obj['js'],obj['css']
    if re.search(r'\bexport\s+default\b',stripped):
        cmd=subprocess.run(['node',str(HERE/'installer.cjs'),str(ACORN)],input=stripped,text=True,capture_output=True)
        if cmd.returncode:raise ValueError('Invalid default installer')
        stripped=cmd.stdout
    return parent.contract.component_ok(dict(js=stripped,css=css))


def component(tag,k,pub,parts,folder,ledger,hint=None):
    if k=='table' and not hint:
        for p in sorted((ORIGINAL/tag/'build/table').glob('*/transmission-*/response.json')):
            msg=read(p)['choices'][0]
            if msg['finish_reason']!='stop':continue
            try:part=recover(msg['message']['content'])
            except parent.compact.base.ERRORS:continue
            core.save(folder/'from-source.json',dict(source=str(p.relative_to(ROOT)),sha256=sha(p)))
            return part
    sys=('Return ONLY one short ES module: export default function install(ctx){ ... }. No JSON, no Markdown, no imports. '
         'Put CSS in a locally installed style element if needed. Implement only the assigned role. Aim for at most 220 lines. '
         'The host has already initialized ctx.table, ctx.selected, ctx.anchor and ctx.active. Core provides ctx.select,ctx.startEdit,ctx.stopEdit. '
         'ctx.select(cells,active,anchor) updates the selected Set and classes; ctx.active/ctx.anchor are table cell elements. '
         'All roles share the same ctx. Use the exact public labels, DOM classes, and original starter rows. No target-number dispatch.')
    data=dict(role=parent.PARTS[k],filename=f'common/{k}.js',starter=pub['starter'],requirements=pub['requirements'])
    if k!='table':data['installed_core']=parts['table']['js']
    if hint:data.update(previous=parts[k],public_observation=hint)
    messages=core.messages(sys,data)
    for attempt in range(1 if hint else 2):
        raw=parent.compact.base.request(ledger,('table',tag,'a'),folder/str(attempt),messages,'build',8192)
        try:return recover(raw)
        except parent.compact.base.ERRORS as exc:
            messages+= [dict(role='user',content='Return one complete concise default install function; previous source was invalid: '+str(exc)[:140])]
    raise ValueError('Invalid module '+k)


def wait_for(path):
    while not path.exists():
        if datetime.now(timezone.utc)>=parent.compact.END:raise SystemExit('deadline')
        time.sleep(2)


def main(action):
    reg=register()
    if action=='generate':
        original_compile=parent.compile_page
        def compile_page(pub,parts,enabled,dest):
            starter=dict(pub['starter'])
            # Initialize state at the module boundary before the first installer receives it.
            prefix="\nObject.assign(ctx,{table:document.querySelector('.table'),selected:new Set(),active:null,anchor:null});\n"
            adjusted=dict(parts,table=dict(parts['table'],js=prefix+parts['table']['js']))
            return original_compile(pub,adjusted,enabled,dest)
        orig=parent.compact.base.template
        def settings(p,t,s):
            cfg=orig(p,t,s)
            if t=='qwen9':cfg['reasoning']={'enabled':False}
            return cfg
        def one(t):
            prev=ORIGINAL/t/'seal.json'
            wait_for(prev)
            if read(prev)['status']=='build_failed':
                parent.generate(t,reg)
            elif not (OUT/t/'seal.json').exists():
                core.save(OUT/t/'parts.json',{})
                core.save(OUT/t/'seal.json',dict(tag=t,model=reg['models'][t],registration=sha(OUT/'registration.json'),
                    parts_sha256=sha(OUT/t/'parts.json'),status='ineligible',reasons=['Earlier preparation '+read(prev)['status']],public=[],rows=[]))
        with patch.multiple(parent,OUT=OUT,CAP=CAP,build_part=component,compile_page=compile_page),patch.multiple(parent.compact.base,OUT=OUT,END=parent.compact.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(one,parent.TAGS))
    if action=='score':
        for t in parent.TAGS:wait_for(OUT/t/'seal.json')
        with patch.multiple(parent,OUT=OUT,RESULT=RESULT,register=lambda:reg):parent.main('score')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
