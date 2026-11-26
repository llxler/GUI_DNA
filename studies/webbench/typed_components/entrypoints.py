"""Verify the compiler-owned survey entry and the table bootstrap against frozen module exports."""
import argparse
from pathlib import Path
from unittest.mock import patch
import os
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,now,sha
from . import run as typed,integration,svg_admission
from .unavailable import run as absent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/component-entrypoints-20261125'
CAP=.40
RESULT=HERE/'entrypoint-result.json'


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    cases=[]
    files=[Path(__file__),HERE/'entrypoints.md',Path(integration.__file__),integration.HERE/'integration-result.json',typed.form.COMPILER]
    for entry in integration.register()['cases']:
        c=entry['case'];root=integration.OUT/c['project']/c['builder']
        seal=read(root/'seal.json')
        if seal['status']!='build_failed':continue
        res=next(x for x in sorted((root/'repair').glob('transmission-*/response.json')) if read(x)['choices'][0]['finish_reason']!='error')
        files.extend([res,root/'seal.json'])
        cases.append(dict(**entry,repair=str(res.relative_to(ROOT)),error=seal['reasons'][-1]))
    assert {(e['case']['project'],e['case']['builder']) for e in cases}=={('form','gemma'),('table','qwen9')}
    bound=svg_admission.register()['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    core.save(path,dict(utc=now(),cap=CAP,deadline=typed.compact.END.isoformat(),combined_bound=bound,balance=balance,cases=cases,
                 sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def generate(e):
    c=e['case'];p,t=c['project'],c['builder'];folder=OUT/p/t
    if (folder/'seal.json').exists():return
    pub=read(ROOT/c['public']);targets=c['deploy'][t]['targets']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    changes=core.files_map(typed.base.parse_json(read(ROOT/e['repair'])['choices'][0]['message']['content'])['files'])
    orig=typed.base.template
    def template(project,tag,stage):
        config=orig(project,tag,stage)
        if tag=='qwen9':config['reasoning']={'enabled':False}
        return config
    rows=[]
    with patch.multiple(typed.base,OUT=OUT,END=typed.compact.END,template=template):
        try:
            if p=='form':
                with patch.object(typed.form,'OUT',ROOT/e['source']):modules=typed.form.module_files('build-a')
                assert set(changes)-set(modules)=={'index.js'}
                assert "'index.js':" in typed.form.COMPILER.read_text()
                del changes['index.js']
                mods,_=integration.corrected_imports(modules|changes)
                pkg=integration.check_form(pub,mods)
                core.save(folder/'library.json',pkg)
                fixed,plans=integration.form_plans(ledger,t,pub,pkg,targets,folder/'deployment')
            else:
                value=typed.base.parse_json(read(ROOT/e['source'])['choices'][0]['message']['content'])
                files,_=integration.corrected_imports({f['path']:f['content'] for f in value['files']})
                files.update(changes)
                msg=core.messages('Return only raw executable JavaScript for index.js. Wire this public table starter to these exact frozen modules. Read each real export and required arguments before calling it. Keep the observed module API. Implement the bootstrap only; compose the existing interactions. No tests, network or target dispatch.',
                                 dict(starter=pub['starter'],public_requirements=pub['requirements'],own_source=files,public_error=e['error']))
                raw=typed.base.request(ledger,(p,t,'a'),folder/'entry',msg,'build',8000)
                files['index.js']=typed.base.uncode(raw)
                value['files']=[dict(path=k,content=v) for k,v in files.items()]
                pkg=integration.check_table(pub,value,folder/'admission')
                core.save(folder/'library.json',pkg)
                fixed,plans=typed.table_deploy(ledger,t,targets,pub,pkg,folder/'deployment')
            status='valid';reasons=[]
            for n,v in zip(targets,plans,strict=True):
                for a,d in (('planned',v),('fixed',fixed)):rows.append(dict(project=p,tag=t,task=n,arm=a,**d))
        except typed.MISSING as exc:status='missing';reasons=[str(exc)]
        except typed.base.ERRORS as exc:status='build_failed';reasons=[str(exc)[:750]]
    core.save(folder/'seal.json',dict(case=c,registration=sha(OUT/'registration.json'),status=status,reasons=reasons,rows=rows))
    print(t,p,status,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        for e in reg['cases']:generate(e)
    elif args.action=='score':
        import time
        from datetime import datetime,timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        with patch.object(typed,'OUT',OUT):
            for e in reg['cases']:
                c=e['case']
                while not (OUT/c['project']/c['builder']/'seal.json').exists():
                    if datetime.now(timezone.utc)>=typed.compact.END:raise SystemExit('deadline')
                    time.sleep(2)
                typed.score(c)
    elif args.action=='publish':
        core.save(RESULT,dict(registration_sha256=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),cases=[read(OUT/e['case']['project']/e['case']['builder']/'result.json') for e in reg['cases']]))
