"""Read the same free-code responses using a format-tolerant, non-generative decoder."""
from pathlib import Path
import json
import re
import sys
import time
from studies.public_library_transfer import core as c, browser
from studies.public_library_transfer.report import counts,comparison
from studies.study_io import digest

HERE=Path(__file__).resolve().parent
OUT=c.ROOT/'artifacts/public-library-transfer-delivery-20261123'


def unique(items):
    obj={}
    for key,value in items:
        if key in obj: raise ValueError('Duplicate JSON key')
        obj[key]=value
    return obj


def delivery(raw):
    raw=raw.strip().lstrip('\ufeff')
    fence=re.search(r'^`{3}(?:json)?[^\S\n]*\n(.*?)\n`{3}[^\S\n]*$',raw,re.I|re.M|re.S)
    if fence:
        if raw.count('```')!=2 or re.search(r'[{}\[\]<>]',raw[:fence.start()]+raw[fence.end():]):
            raise ValueError('Ambiguous text surrounding fence')
        raw=fence[1].strip()
    decoder=json.JSONDecoder(strict=False,object_pairs_hook=unique)
    value,offset=decoder.raw_decode(raw)
    if re.search(r'[{}\[\]<>`]',raw[offset:]): raise ValueError('Trailing code after JSON document')
    if not isinstance(value,dict) or set(value)!={'files'}: raise ValueError('Expected one files object')
    return value


def register():
    reg=OUT/'registered.json'
    sources={str(p.relative_to(c.ROOT)):c.sha(p) for p in (Path(__file__),HERE/'PROTOCOL.md',Path(c.__file__))}
    if reg.exists():
        if c.read(reg)['sources']!=sources: raise ValueError('Registered sources changed')
    else: c.save(reg,{'registered':c.now(),'sources':sources,'projects':c.PROJECTS,'main_registered':c.sha(c.OUT/'registered.json')})


def prepare(project):
    public=c.read(c.OUT/'inputs'/f'{project}.json')
    rows=[]
    for task in range(1,21):
        d=c.OUT/'direct'/project/f'task-{task}'
        original=c.read(d/'row.json')
        result=dict(original,original_status=original['status'],response_sha256=c.sha(d/'response.json'))
        if original['status']=='invalid':
            page=OUT/'pages'/project/f'task-{task}'
            try:
                files=c.materialize_direct(project,public,delivery(c.read(d/'response.json')['text']),page)
                result.update(status='valid',page=str(page.relative_to(c.ROOT)),files=files)
            except (ValueError,TypeError,KeyError) as exc:
                result['delivery_error']=str(exc)[:300]
        rows.append(result)
    c.save(OUT/'seals'/f'{project}.json',{'rows':rows,'registered_sha256':c.sha(OUT/'registered.json')})


def score(project):
    path=OUT/'scores'/f'{project}.json'
    if path.exists(): return
    original=c.read(c.OUT/'browser/project-scores'/f'{project}.json')['rows']
    seal=OUT/'seals'/f'{project}.json'
    rows=browser.evaluate(c.read(seal)['rows'],OUT,{project:browser.verify_contract(project)},2)
    before={r['task']:r for r in original if r['arm']=='direct'}
    after={r['task']:r for r in rows}
    for n in before:
        if before[n]['status']=='valid':
            assert before[n]['files']==after[n]['files'] and before[n]['passed']==after[n]['passed']
    against=[]
    for tag,model in c.BUILDERS.items():
        rep=2 if tag=='codex-2' else 1
        plans={r['task']:r for r in original if r['arm']=='plan' and r['builder']==model and r['rep']==rep}
        against.append({'tag':tag,**comparison(plans,after,range(1,21))})
    c.save(path,{'project':project,'before':counts(before.values()),'after':counts(rows),
        'pairs':against,'seal_sha256':c.sha(seal),
        'rows':[{k:r[k] for k in ('task','original_status','status','passed','response_sha256','report_sha256')} for r in rows]})


if __name__=='__main__':
    register()
    if sys.argv[1]=='run':
        while True:
            for p in c.PROJECTS:
                if not (OUT/'seals'/f'{p}.json').exists() and (c.OUT/'direct'/p/'task-20/row.json').is_file(): prepare(p)
                if (OUT/'seals'/f'{p}.json').is_file() and (c.OUT/'browser/project-scores'/f'{p}.json').is_file(): score(p)
            if all((OUT/'scores'/f'{p}.json').exists() for p in c.PROJECTS): break
            time.sleep(8)
        c.save(c.ROOT/'studies/results/public-library-transfer-delivery-20261123.json',
               {'study':'format-only sensitivity of the same local no-library outputs',
                'registered_sha256':c.sha(OUT/'registered.json'),'projects':[c.read(OUT/'scores'/f'{p}.json') for p in c.PROJECTS]})
