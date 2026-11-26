"""Assemble public GPT-5 components transferred from disjoint WebApp1K-Duo pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.duo_components import run as components
from studies.public_library_transfer.self_refinement.duo_components.compact import runtime
from studies.public_library_transfer.compact_todomvc.route_completion import run as route
from studies.study_io import ROOT,now,read,sha
from studies.webbench.table.action_library import run as action

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/duo-donors-20261126'
PARQUET = OUT/'donors.parquet'
DIGEST = 'e4470287edb0e5857e1ed9ac078301c59731d2cd0b9daa57c9108d6035b0fcac'
REVISION = 'fbda49ea521d9ddd22d2425d01237e17e3d6831c'
TAGS = ('gemma','qwen9','mistral','qwen','oss','deepseek-flash')
CAP = 1.0
original = components.original


def digest(x):
    return hashlib.sha256(x.encode()).hexdigest()


def register():
    f = OUT/'registration.json'
    paths = [HERE/'PROTOCOL.md',Path(__file__),original.HERE/'direct.cjs',Path(runtime.__file__),
             original.EXTRA/'targets.json', original.EXTRA/'build-inputs.json',Path(components.bundle.__code__.co_filename)]
    sources = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    if f.exists():
        assert read(f)['sources']==sources and sha(PARQUET)==DIGEST
        return read(f)
    assert sha(PARQUET)==DIGEST
    import duckdb
    db=duckdb.connect()
    targets=original.inputs()
    suites=read(original.EXTRA/'build-inputs.json')
    choices={}
    for domain in original.GROUPS:
        pairs = [p for p, in db.execute('select Scenario from read_parquet(?) where Category = ?',
                                        [str(PARQUET),domain]).fetchall() if p not in targets]
        assert len(pairs)==len(set(pairs))
        choices[domain]={}
        for name in sorted(suites[domain]):
            eligible=sorted((p for p in pairs if name in p.split('_')),
                    key=lambda p:digest(f'gui-dna-duo-donor-v1:{domain}/{name}/{p}'))
            selected=None
            for pair in eligible:
                assert pair not in targets
                source, = db.execute('select "gpt-5".code from read_parquet(?) where Category = ? and Scenario = ?',
                                     [str(PARQUET),domain,pair]).fetchone()
                if isinstance(source,str) and source.strip():
                    file=OUT/'raw'/domain/(pair+'.txt')
                    file.parent.mkdir(parents=True,exist_ok=True)
                    file.write_text(source)
                    selected=dict(pair=pair,sha256=sha(file))
                    break
            choices[domain][name]=selected
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(f,dict(utc=now(),cap=CAP,deadline=route.END.isoformat(),balance=balance,source_revision=REVISION,
                     parquet_sha256=DIGEST,sources=sources,choices=choices,targets=sorted(targets)))
    return read(f)


def build(reg):
    saved=OUT/'libraries.json'
    if saved.exists():
        return read(saved)
    libs={}
    for domain,choices in reg['choices'].items():
        donors={}
        for feature,v in choices.items():
            if v:donors.setdefault(v['pair'],[]).append(feature)
        modules={}
        singles={}
        for pair,names in donors.items():
            source=OUT/'raw'/domain/(pair+'.txt')
            assert all(choices[name]['sha256']==sha(source) for name in names)
            proc=subprocess.run(['node',str(original.HERE/'direct.cjs')],input=json.dumps({'original':None,'raw':source.read_text()}),
                                text=True,capture_output=True,check=True,timeout=15)
            entry=json.loads(proc.stdout)
            if entry:modules[pair]=entry['source']
        jobs=[(OUT/'public'/domain/name,domain,name,modules[pair]) for pair,names in donors.items()
              if pair in modules for name in names]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for name,verdict in pool.map(runtime.single,jobs):
                singles[name]={k:verdict[k] for k in ('passed','report_sha256','source_sha256','test_sha256')}
        libs[domain]=dict(status='valid' if any(v['passed'] for v in singles.values()) else 'build_failed',
                          owners={n:v['pair'] for n,v in choices.items() if v and v['pair'] in modules},
                          modules=modules,singles=singles)
    core.save(saved,libs)
    return libs


def generate(reg,libs):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    tasks=original.inputs()
    def one(job):
        tag,task=job
        row=tasks[task]
        folder=OUT/'candidates'/tag/task
        f=folder/'record.json'
        if f.exists():return
        lib=libs[row['group']]
        if lib['status']!='valid':
            core.save(f,{arm:dict(status=lib['status']) for arm in ('planned','fixed','names')})
            return
        ids=sorted(lib['modules'])
        modules={'components':[dict(id=i,source=lib['modules'][i]) for i in ids]}
        def assemble(arm,selected):
            setting=(selected+['NONE','NONE'])[:2]
            files=components.bundle(row['public']['module'],modules,dict(zip(('first','second'),setting,strict=True)))
            file=folder/(arm+'.json')
            core.save(file,files)
            return dict(status='valid',file=str(file.relative_to(OUT)),files_sha256=sha(file),ids=selected)
        features=task.split('_')
        entries=dict(fixed=assemble('fixed',ids[:2]),
                     names=assemble('names',list(dict.fromkeys(lib['owners'][n] for n in features if n in lib['owners']))))
        msg=core.messages('Select zero, one or two existing React modules to render. Each module implements the two listed public features. '
                          'Return only a JSON integer array of module indexes. Avoid unrelated features when possible.',
                          dict(required_features=features,available_modules={i:k.split('_') for i,k in enumerate(ids)}))
        try:
            raw=action.compact.base.request(ledger,('table',tag,'a'),folder/'call',msg,'plan',2400)
            text=action.compact.base.uncode(raw).strip()
            indices=json.loads(text)
            if not isinstance(indices,list) or len(indices)>2 or any(type(i) is not int or not 0<=i<len(ids) for i in indices):
                raise ValueError('Expected up to two module numbers')
            entries['planned']=assemble('planned',list(dict.fromkeys(ids[i] for i in indices)))
        except action.typed.MISSING as exc:entries['planned']=dict(status='missing',reason=str(exc))
        except ValueError as exc:entries['planned']=dict(status='invalid',reason=str(exc)[:160])
        core.save(f,entries)
    with patch.multiple(action.compact.base,OUT=OUT,END=route.END,template=action.settings),ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one,((tag,task) for tag in TAGS for task in reg['targets'])))
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),libraries=sha(OUT/'libraries.json'),
             candidates={str(f.relative_to(OUT)):sha(f) for f in sorted((OUT/'candidates').glob('*/*/record.json'))}))


def score(reg,libs):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and seal['libraries']==sha(OUT/'libraries.json')
    tasks=original.inputs()
    jobs={}
    results={}
    for file,stamp in seal['candidates'].items():
        path=OUT/file
        assert sha(path)==stamp
        tag,task=path.parts[-3:-1]
        model=action.settings('table',tag,'plan')['model']
        rows=results.setdefault(model,[])
        for arm,entry in read(path).items():
            record=dict(task=task,arm=arm,status=entry['status'],passed=False if entry['status']=='invalid' else None)
            rows.append(record)
            if entry['status']=='valid':
                src=OUT/entry['file']
                assert sha(src)==entry['files_sha256']
                key=(task,sha(src))
                jobs.setdefault(key,(src,[]))[1].append(record)
    def grade(item):
        (task,checksum),(src,entries)=item
        row=tasks[task]
        dest=OUT/'scores'/task/checksum
        verdict=runtime.score((row['group'],row,read(src),dest,None))
        assert sha(dest/'jest.json')==verdict['report_sha256']
        for record in entries:
            record.update(passed=verdict['passed'],report_sha256=verdict['report_sha256'],
                          official_cases_passed=verdict['assertion_statuses'].count('passed'))
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(grade,jobs.items()))
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),
        source_revision=REVISION,parquet_sha256=DIGEST,choices=reg['choices'],libraries={g:{k:v for k,v in d.items()
        if k!='modules'} for g,d in libs.items()},models=results,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','generate','score'))
    a=parser.parse_args().action
    with browser.lock(OUT/'.lock'):
        reg=register()
        libs=build(reg)
        if a=='generate':generate(reg,libs)
        if a=='score':score(reg,libs)
