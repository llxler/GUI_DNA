"""Receive entire HTML responses as documents and require composable extension installers."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from studies.public_library_transfer.compact_todomvc.syntax_reception import run as receipt
from ..dom_extensions import run as dom

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/file-explorer-documents-20261126'
SOURCE=dom.OUT
ORIG=dom.original
CAP=1.50
MODULES=dom.MODULES
BASE_REQUEST=ORIG.base.request
FENCE=re.compile(r'^`{3}(?:html|javascript|js)?[^\S\r\n]*\r?\n([\s\S]*?)^\s*`{3}',re.M|re.I)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.elements=[]
        self.scripts=[]
        self.styles=[]
        self.current=None
    def handle_starttag(self,name,attrs):
        self.elements.append(name)
        self.current=name if name in ('script','style') else None
        if self.current:getattr(self,self.current+'s').append('')
    def handle_endtag(self,name):
        if name==self.current:self.current=None
    def handle_data(self,value):
        if self.current:getattr(self,self.current+'s')[-1]+=value


def parse_document(raw):
    match=FENCE.search(raw.strip())
    text=(match[1] if match else raw).strip()
    doc=Document()
    doc.feed(text)
    if len(text)>800000 or not {'html','body'}.issubset(doc.elements) or not re.search(r'</body\s*>',text,re.I):
        raise ValueError('Expected a complete HTML document')
    return text


def installer(raw):
    match=FENCE.search(raw.strip())
    src=(match[1] if match else raw).strip()
    markup=Document()
    markup.feed(src)
    candidates=markup.scripts if re.match(r'\s*<(?:!doctype|html|script|style)',src,re.I) else [src]
    for js in candidates:
        check=subprocess.run(['node',str(dom.original.action.build.modules.HERE/'function.cjs'),str(dom.original.action.build.modules.ACORN)],
            input=json.dumps(dict(text=js,name='installFeature',arity=1)),capture_output=True,text=True,timeout=12)
        if not check.returncode and check.stdout.strip():return dict(script=check.stdout+'\ninstallFeature(document);',style='\n'.join(markup.styles))
    if candidates and 'html' not in markup.elements and set(markup.elements)<= {'script','style'} and markup.scripts:
        js='\n'.join(candidates)
        ok=subprocess.run(['node','--check'],input=js,text=True,capture_output=True,timeout=10)
        if not ok.returncode:return dict(script=js,style='\n'.join(markup.styles))
    raise ValueError('Extension must provide a complete installFeature(root); whole pages cannot be mounted as siblings.')


def register():
    f=OUT/'registration.json'
    parent=read(SOURCE/'registration.json')
    paths=[Path(__file__),HERE/'PROTOCOL.md',Path(dom.__file__),SOURCE/'registration.json',SOURCE/'seal.json',ORIG.OUT/'registration.json']
    paths+=list(SOURCE.glob('*/*/calls/core/*/transmission-*/settled.json'))
    sums={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not f.exists():
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=balance,deadline=dom.action.END.isoformat(),sources=sums,models=parent['models'],targets=parent['targets']))
    assert read(f)['sources']==sums
    return read(f)


def emit(pub,parts,dest):
    if not parts:return ORIG.emit(dest,core.emit('dom1',pub['starter'],dest))
    html=parts['core']
    files={}
    inject=[]
    for name,val in parts.items():
        if name=='core':continue
        files[name+'.js']='(function(){\n'+val['script']+'\n})();'
        inject.append('<script src="./'+name+'.js"></script>')
        if val['style']:
            files[name+'.css']=val['style']
            inject.append('<link rel="stylesheet" href="./'+name+'.css">')
    html=re.sub(r'</body\s*>',lambda m:''.join(inject)+m[0],html,count=1,flags=re.I)
    return ORIG.emit(dest,core.emit('dom1',{**pub['starter'],**files,'index.html':html},dest))


def library(tag,rep,pub,ledger):
    root=OUT/tag/rep
    f=root/'library.json'
    if f.exists():return read(f)
    parts={}
    public=[]
    for name,indices in MODULES.items():
        hint=None
        for attempt in range(2):
            context=dict(requested=dom.DESCRIPTION[name],requirements=[pub['requirements'][i-1] for i in indices],
                         existing_file=parts.get('core',pub['starter']['index.html'])[:10800],feedback=hint)
            try:
                if name=='core' and attempt==0:
                    raw,path=receipt.delivered([SOURCE/tag/rep/'calls/core/0'])
                    core.save(root/'reused.json',dict(response=str(path.relative_to(ROOT)),sha256=sha(path)))
                else:
                    system=('Return one complete working HTML document, including inline script and styles.' if name=='core' else
                        'Write ONE short complete function installFeature(root) where root is the live document. It runs AFTER the supplied file explorer. '
                        'Implement only the requested extension by DOM queries, listeners and standard browser calls. Add scoped styles inside the function. '
                        'Do not copy the existing app. Do not output an entire page or Markdown. Return only the function.')
                    raw=ORIG.base.request(ledger,('table',tag,rep),root/'calls'/name/str(attempt),core.messages(system,context),'build',6500)
                value=parse_document(raw) if name=='core' else installer(raw)
                trial={**parts,name:value}
                candidate=emit(pub,trial,root/'public'/name/str(attempt))
                obs=dom.exercise(candidate,[k for k in trial if k!='core'])
                # Each new option must cause a measurable effect relative to the core prefix.
                if name!='core' and obs['admitted']:
                    omitted=dom.exercise(emit(pub,parts,root/'public'/name/(str(attempt)+'-omitted')),[name])
                    if omitted['checks'].get(name):
                        obs=dict(obs,admitted=False,already_satisfied_without_extension=True)
                public.append(dict(name=name,attempt=attempt,**obs))
                if obs['admitted']:
                    parts=trial
                    break
                hint=obs
            except dom.action.typed.MISSING as exc:
                public.append(dict(name=name,attempt=attempt,missing=str(exc)));break
            except ValueError as exc:
                hint=str(exc);public.append(dict(name=name,attempt=attempt,invalid=hint))
        if name=='core' and name not in parts:break
    status='valid' if len(parts)>1 else ('missing' if not parts and any('missing' in h for h in public) else 'build_failed')
    core.save(f,dict(status=status,source=parts,public=public))
    print('document library',tag,rep,status,list(parts),flush=True)
    return read(f)


def recover_controls(reg):
    old=read(ORIG.OUT/'seal.json')
    assert old['registration']==sha(ORIG.OUT/'registration.json')
    results=[]
    pub=read(ORIG.OUT/'public.json')
    tasks={t['k']:t for t in ORIG.domain.tasks()}
    original_library=ORIG.domain.library()
    for tag in ORIG.TAGS:
        for n,t in tasks.items():
            for arm in ('direct','human','gpt5-library'):
                source=ORIG.OUT/tag/'deploy'/arm/str(n)/'record.json'
                assert sha(source)==old['sources'][str(source.relative_to(ORIG.OUT))]
                base=read(source)[0]
                if base['status']!='invalid':
                    results.append(dict(tag=tag,**base))
                    continue
                raw,path=receipt.delivered([source.parent/'call'])
                dest=OUT/tag/'controls'/arm/str(n)
                try:
                    if arm=='direct':
                        try:files={'index.html':parse_document(raw)}
                        except ValueError:
                            obj=receipt.first_object(raw)
                            files=core.files_map(obj['files']) if isinstance(obj['files'],list) else ORIG.blind.validate_files(obj['files'])
                        files=core.emit('dom1',{**pub['starter'],**files},dest)
                    else:
                        obj=receipt.first_object(raw)
                        if arm=='human':
                            js=ORIG.domain.compile_plan(obj,t['features'],original_library)
                            files=core.emit('dom1',{'index.html':ORIG.SHELL.read_text().replace('/*__CANDIDATE__*/',js)},dest)
                        else:files=core.emit('dom1',ORIG.blind.compile_plan(read(ORIG.GPT/'package.json'),obj),dest)
                    changed=ORIG.emit(dest,files)
                except ORIG.base.ERRORS as exc:changed=dict(status='invalid',reason=str(exc)[:160])
                results.append(dict(project='dom1',task=n,arm=arm,tag=tag,response_sha256=sha(path),**changed))
    f=OUT/'controls.json'
    core.save(f,dict(original=sha(ORIG.OUT/'seal.json'),rows=results))
    graded=browser.evaluate(results,OUT,{'dom1':read(ORIG.OUT/'browser.json')},4)
    core.save(HERE/'controls.json',dict(seal=sha(f),rows=[dict(tag=r['tag'],task=r['task'],arm=r['arm'],status=r['status'],
                  passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in graded]))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('generate','score','controls'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        if phase=='controls':recover_controls(reg)
        else:
            with patch.multiple(dom,OUT=OUT,HERE=HERE,CAP=CAP,register=register,emit=emit,library=library):dom.main(phase)
