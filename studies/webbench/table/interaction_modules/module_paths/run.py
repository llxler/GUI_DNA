"""Replay only unambiguous names in the model's original module selections."""
import json
from pathlib import Path
import re

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..state_contract import run as source

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-module-paths-20261126pm'
prior=source.parent

def decode(raw, parts):
    value=json.loads(prior.BASE.uncode(raw).strip())
    if not isinstance(value,list):raise ValueError('Expected a list')
    chosen={'table'}
    for name in value:
        if name=='ctx':continue
        if not isinstance(name,str):raise ValueError('Expected a module name')
        token=re.fullmatch(r'(?:common/)?([a-z]+)(?:\.js)?',name)
        if not token or token[1] not in parts:raise ValueError('Unavailable module: '+name)
        chosen.add(token[1])
    return [k for k in parts if k in chosen]

def run():
    reg=OUT/'registration.json';old=read(source.HERE/'result.json')
    docs=[HERE/'PROTOCOL.md',Path(__file__),Path(source.__file__),source.HERE/'result.json',source.OUT/'seal.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in docs}
    if not reg.exists():core.save(reg,dict(utc=now(),sources=hashes,cost_usd=0))
    assert read(reg)['sources']==hashes
    entries=[];reasons={}
    pub=read(prior.PUBLIC)
    for rep,lib in old['libraries'].items():
        if lib['status']!='valid':continue
        data=read(source.OUT/rep/'library.json');parts=data['functions']
        for i in range(1,21):
            src=source.OUT/rep/'plans'/str(i)/'call'
            original=next(iter(sorted(src.glob('transmission-*/settled.json'))),None)
            if original:
                f=original.with_name('response.json');assert sha(f)==read(original)['response_sha256']
                try:
                    names=decode(read(f)['choices'][0]['message']['content'],parts)
                    candidate=source.emit(pub,{k:parts[k] for k in names},OUT/rep/str(i)/'page')
                    note={'modules':names}
                except (ValueError,TypeError) as exc:candidate=dict(status='invalid');note={'reason':str(exc)}
            else:candidate=dict(status='missing');note={'reason':'No settled response'}
            reasons[rep+'/'+str(i)]=note
            entries.append(dict(project='table',task=i,arm='self-'+rep,**candidate))
    seal=OUT/'seal.json';bundle=dict(registration=sha(reg),rows=entries,decoding=reasons)
    if not seal.exists():core.save(seal,bundle)
    assert read(seal)==bundle
    proto=browser.verify_contract('table');assert proto==read(prior.PUBLIC.with_name('browser.json'))
    results=browser.evaluate(entries,OUT,{'table':proto},3)
    rows=[{k:r.get(k) for k in ('task','arm','status','report_sha256')}|
          {'passed':False if r['status']=='invalid' else r.get('passed')} for r in results]
    rows.extend(r for r in old['rows'] if not r['arm'].startswith('self-'))
    core.save(HERE/'result.json',dict(registration=sha(reg),seal=sha(seal),libraries=old['libraries'],decoding=reasons,
                                    cost_usd=0,rows=rows,original=sha(source.HERE/'result.json')))
if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):run()
