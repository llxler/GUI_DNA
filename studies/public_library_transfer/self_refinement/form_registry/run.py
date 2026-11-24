"""Probe model-authored public question constructors on an empty public form."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import mimetypes
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlparse

from studies.study_io import ROOT, dump, now, read, sha

HERE = Path(__file__).resolve().parent
SOURCE = ROOT/'artifacts/backbone-form-20261124'
OUT = ROOT/'artifacts/form-registry-20261124'
OLD = ROOT/'studies/results/backbone-form-20261124.json'
TYPES = ('Question','SingleSelectionQuestion','MultiSelectionQuestion','OpenQuestion','RatingQuestion',
         'RankingQuestion','NpsQuestion','LikertQuestion','DataQuestion')
MODES = ('native','exposed')
RESULT = HERE/'result.json'
REGISTRY = OUT/'seal.json'
PUBLIC = SOURCE/'inputs/form/public.json'


def checksum(text):
    return hashlib.sha256(text.encode()).hexdigest()


def last_response(tag):
    path = SOURCE/tag/'form/build'
    return max(path.glob('attempt-*/response.json'), key=lambda p: int(p.parent.name.split('-')[-1]))


def extract(text):
    values = []
    body = text.strip()
    for part in [body, *re.findall(r'```(?:json)?\s*\n([\s\S]*?)\n```',body)]:
        try:
            package = json.loads(part)
        except ValueError:
            continue
        if isinstance(package,dict) and isinstance(package.get('files'),list):
            return package['files'],package.get('script') or ''
    decoder = json.JSONDecoder()
    for m in re.finditer(r'\{\s*"path"\s*:',body):
        try:
            value,_=decoder.raw_decode(body[m.start():])
        except ValueError:
            continue
        if set(value) >= {'path','content'}:
            values.append(value)
    complete_script = re.search(r'"script"\s*:\s*("(?:[^"\\]|\\.)*")',body,re.S)
    script = ''
    if complete_script:
        try:
            script = json.loads(complete_script.group(1))
        except ValueError:
            pass
    return values,script


def valid_name(path):
    return (isinstance(path,str) and re.fullmatch(r'(?:\./)?(?:[\w.-]+/)*[\w.-]+\.js',path)
            and '..' not in PurePosixPath(path).parts)


def code_sources():
    return {str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),HERE/'PROTOCOL.md',HERE/'register.cjs',HERE/'probe.js',OLD)}


def register():
    models = read(SOURCE/'registered.json')['models']
    assert len(models) == 7
    snapshots = {}
    for tag,(model,*_) in models.items():
        raw = last_response(tag)
        result = read(raw)['choices'][0]
        text = result['message'].get('content') or ''
        files,script = extract(text)
        modules = {}
        for record in files:
            if isinstance(record,dict) and valid_name(record.get('path')) and isinstance(record.get('content'),str):
                name = str(PurePosixPath(record['path']))
                modules.setdefault(name,record['content'])
        if script:
            assert 'model-entry.js' not in modules
            modules['model-entry.js'] = script
        source_meta = {}
        for file, content in modules.items():
            payload = json.dumps({'file':file,'source':content,'classes':TYPES})
            process = subprocess.run(['node',str(HERE/'register.cjs')],input=payload,text=True,capture_output=True,check=True,cwd=ROOT)
            audit = json.loads(process.stdout)
            adapted = audit.pop('source')
            for mode,body in [('native',content),('exposed',adapted)]:
                where=OUT/'modules'/tag/mode/file
                where.parent.mkdir(parents=True,exist_ok=True)
                where.write_text(body)
            source_meta[file] = {**audit,'native':checksum(content),'exposed':checksum(adapted)}
        snapshots[model] = {'tag':tag, 'attempt':raw.parent.name,'receipt_sha256':sha(raw),
                            'visible_length':len(text),'finish_reason':result['finish_reason'],'files':source_meta}
    values = {'models':snapshots,'files':code_sources(),'public_sha256':sha(PUBLIC),
              'registration_sha256':sha(SOURCE/'registered.json'),'types':list(TYPES)}
    if REGISTRY.exists():
        recorded=read(REGISTRY)
        assert all(recorded[k]==v for k,v in values.items())
    else:
        dump(REGISTRY,dict(utc=now(),**values))


def one(job):
    from playwright.sync_api import sync_playwright
    model,entry,starter=job
    tag=entry['tag']
    rows={}
    with sync_playwright() as runtime:
        with runtime.chromium.launch() as browser:
            for mode in MODES:
                files=dict(starter)
                for name,hashes in entry['files'].items():
                    file=OUT/'modules'/tag/mode/name
                    assert sha(file)==hashes[mode]
                    files[name]=file.read_text()
                context=browser.new_context(service_workers='block')
                def route(request):
                    url=urlparse(request.request.url)
                    key=url.path.lstrip('/') or 'index.html'
                    if url.netloc!='form.local' or key not in files:
                        request.abort()
                    else:
                        mime=mimetypes.guess_type(key)[0] or 'text/plain'
                        request.fulfill(status=200,content_type=mime,body=files[key])
                context.route('**/*', route)
                context.add_init_script('globalThis.__diagnosticTypes=Object.create(null);')
                by_type=rows[mode]={}
                for name in TYPES:
                    filename='common/'+name+'.js'
                    params={'kind':mode,'type':name,'modulePath':'/'+filename if filename in entry['files'] else None,
                            'entry':'/model-entry.js' if 'model-entry.js' in entry['files'] else None}
                    page=context.new_page()
                    page.set_default_timeout(5000)
                    page.goto('http://form.local/',wait_until='load')
                    by_type[name]=page.evaluate((HERE/'probe.js').read_text(),params)
                    page.close()
                context.close()
    dump(OUT/'receipts'/(tag+'.json'),rows)
    return model,rows


def counts(rows):
    return {model:{mode:{key:sum(r[key] for r in by_type.values())
                         for key in ('exported','mounted','public_structure','control')}
                   for mode,by_type in modes.items()} for model,modes in rows.items()}


def run(workers):
    reg=read(REGISTRY)
    assert code_sources()==reg['files'] and sha(PUBLIC)==reg['public_sha256']
    assert sha(SOURCE/'registered.json')==reg['registration_sha256']==read(OLD)['registration_sha256']
    starter=read(PUBLIC)['starter']
    jobs=[(model,entry,starter) for model,entry in reg['models'].items()]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows=dict(pool.map(one,jobs))
    dump(RESULT,{**reg,'seal_sha256':sha(REGISTRY),'rows':rows,'counts':counts(rows),
                 'official_tasks_scored':0,'new_api_calls':0})


def check():
    data=read(RESULT)
    assert data['files']==code_sources() and data['counts']==counts(data['rows'])
    assert data['registration_sha256']==read(OLD)['registration_sha256']
    assert len(data['models'])==7 and set(data['models'])==set(data['rows'])
    assert data['official_tasks_scored']==data['new_api_calls']==0
    for model,modes in data['rows'].items():
        assert set(modes)==set(MODES)
        for by_type in modes.values():
            assert set(by_type)==set(TYPES)
            for r in by_type.values():
                assert not r['mounted'] or r['exported']
                assert not (r['public_structure'] or r['control']) or r['mounted']
        print(model, data['counts'][model])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','run','check'))
    parser.add_argument('--workers',default=2,type=int)
    args=parser.parse_args()
    if args.action=='run':
        run(args.workers)
    else:
        {'register':register,'check':check}[args.action]()
