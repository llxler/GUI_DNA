"""Evaluate a shared semantic survey plan and publicly repaired GPT-OSS form modules."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
from unittest.mock import patch

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.interface_blind.core import validate_files
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.compact_todomvc.syntax_reception import run as receiver
from studies.public_library_transfer.self_refinement.form_components import run as form
from studies.study_io import ROOT,read,sha,now
from studies.webbench.file_explorer.document_library import run as document
from studies.webbench.typed_components import entrypoints,integration
from studies.webbench.table.action_library import run as action
from ..flash_self_build.visible_targets import run as visible

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/survey-workflow-20261126'
CAP=1.50
TAGS=('gemma','mistral','oss')
BASE=visible.OLD/'inputs/form'
FROZEN={'gemma':{'a':entrypoints.OUT/'form/gemma/deployment/build-a/fixed/20/page'},
        'mistral':{'a':integration.OUT/'form/mistral/deployment/build-a/fixed/20/page'},
        'oss':{r:form.OUT/('build-'+r)/'fixed/20/page' for r in ('a','b')}}
KINDS={'question':('Question',()),'single':('SingleSelectionQuestion',('options',)),'multi':('MultiSelectionQuestion',('options',)),
       'open':('OpenQuestion',('isMultilines',)),'rating':('RatingQuestion',('starCount',)),'ranking':('RankingQuestion',('options',)),
       'nps':('NpsQuestion',()),'likert':('LikertQuestion',('options','statements')),'data':('DataQuestion',('dataType',))}
SPEC=('Return JSON with surveyTitle (string or null before a survey is requested), exportData (boolean), questions (ordered array). '
    'Each question has kind, title, name, position (prepend or append), and the applicable fields. '
    'Kinds and their additional fields: question; single(options); multi(options); open(isMultilines); rating(starCount); ranking(options); '
    'nps; likert(options,statements); data(dataType). options and statements are arrays of literal strings. Support required, minLength, '
    'isSelectMode and isShuffleMode when requested. Preserve the exact quoted titles, names, option order and latest changes. '
    'Include every instance needed at this point. Return one data object, no source code.')
EXAMPLE={'surveyTitle':'Public preference survey','exportData':True,'questions':[
    dict(kind='single',title='Choose a day',name='trip-day',position='append',options=['Monday','Friday']),
    dict(kind='open',title='Your note',name='trip-note',position='append',isMultilines=False),
    dict(kind='rating',title='Rate the plan',name='trip-rating',position='append',starCount=3)]}


def register():
    f=OUT/'registration.json'
    files=[HERE/'PROTOCOL.md',Path(__file__),form.COMPILER,BASE/'public.json',BASE/'browser.json',BASE/'human.json',BASE/'gpt5-library.json',
           Path(document.__file__),Path(receiver.__file__),entrypoints.RESULT,integration.HERE/"integration-result.json",form.HERE/'result.json']
    for reps in FROZEN.values():
        for folder in reps.values():files.extend(p for p in folder.rglob('*') if p.is_file())
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=b,deadline=action.END.isoformat(),models={t:action.settings('table',t,'plan')['model'] for t in TAGS},
                         sources=sums,targets=list(range(1,21))))
    assert read(f)['sources']==sums
    return read(f)


def semantic(raw):
    p=receiver.first_object(raw)
    if not isinstance(p,dict) or not isinstance(p.get('questions'),list) or len(p['questions'])>60:raise ValueError('Expected question list')
    if 'surveyTitle' not in p or (p['surveyTitle'] is not None and not isinstance(p['surveyTitle'],str)) or type(p.get('exportData'))!=bool:raise ValueError('Invalid survey fields')
    for q in p['questions']:
        if not isinstance(q,dict) or q.get('kind') not in KINDS or not all(isinstance(q.get(k),str) for k in ('name','title')):raise ValueError('Question name, class or title is absent')
        if q.get('position','append') not in ('append','prepend'):raise ValueError('Unknown insertion direction')
    return p


def compile_page(pkg,plan,gpt,dest):
    if gpt:
        config=dict(questions=plan['questions'])
        if plan['surveyTitle'] is not None:config['title']=plan['surveyTitle']
    else:
        items=[]
        for q in plan['questions']:
            name,fields=KINDS[q['kind']]
            args=[q['title'],q['name']]
            for key in fields:
                if key in q:args.append(q[key])
                elif key=='starCount':pass  # Use the documented constructor default.
                elif key=='isMultilines':args.append(False)
                else:raise ValueError('Missing constructor field '+key)
            items.append(dict(type=name,args=args,position=q.get('position','append')))
        config=dict(surveyTitle=plan['surveyTitle'],exportData=plan['exportData'],questions=items)
    files=form.compile_plan(pkg,config)
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=core.emit('form',files,dest))


def public(pkg,gpt,dest):
    names=('load','radio','text','export','retained')
    values=dict.fromkeys(names,False)
    errors=[]
    try:
        candidate=compile_page(pkg,EXAMPLE,gpt,dest)
        serve=browser.served_page(OUT,'form',dest,candidate['files'])
        with browser.browser_slot(),browser.serve('form',serve) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
            tab=eng.new_page(service_workers='block')
            tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
            tab.set_default_timeout(1200)
            tab.on('pageerror',lambda e:errors.append(str(e.stack or e).splitlines()[:3]))
            tab.goto(url+'/index.html')
            values['load']=tab.locator('form').count()==1 and not errors
            for key,selector in [('radio','input[type=radio]'),('text','input[type=text],textarea,input:not([type])')]:
                try:
                    el=tab.locator('form '+selector.replace(',',',form ')).first
                    if key=='radio':el.check();values[key]=el.is_checked()
                    else:el.fill('Public note');values[key]=el.input_value()=='Public note'
                except Exception as e:errors.append([key,str(e).splitlines()[0][:200]])
            try:
                tab.locator('.export').first.click()
                snapshot=tab.evaluate("localStorage.getItem('data')")
                payload=json.loads(snapshot or 'null')
                values['export']=isinstance(payload,dict) and payload.get('title')==EXAMPLE['surveyTitle'] and isinstance(payload.get('questions'),list) and len(payload['questions'])==3
                tab.reload()
                values['retained']=values['export'] and tab.evaluate("localStorage.getItem('data')")==snapshot
            except Exception as e:errors.append(['export',str(e).splitlines()[0][:200]])
    except Exception as e:errors.append([str(e).splitlines()[0][:200]])
    return dict(checks=values,errors=errors)


def prepare(tag,rep,pub,ledger):
    folder=OUT/tag/rep
    f=folder/'library.json'
    if f.exists():return read(f)
    archive=FROZEN[tag][rep]
    files={p.relative_to(archive).as_posix():p.read_text() for p in archive.rglob('*') if p.is_file() and not p.is_relative_to(archive/'assets') and p.name!='index.js'}
    pkg=dict(files=files,compiler=form.COMPILER.read_text())
    first=public(pkg,False,folder/'public/first')
    checks=first
    history=[]
    if tag=='oss':
        tried=set()
        for i in range(2):
            if all(checks['checks'].values()) and not checks['errors']:break
            fallback=['Survey','Contents','Question']
            if not checks['checks']['radio']:fallback.insert(0,'SingleSelectionQuestion')
            if not checks['checks']['text']:fallback.insert(0,'OpenQuestion')
            trace=str(checks['errors'])
            names=[k.split('/')[-1][:-3] for k in pkg['files'] if k.startswith('common/') and k.endswith('.js')]
            name=next((k for k in names if k+'.js' in trace and k not in tried),None) or next((k for k in fallback if k in names and k not in tried),None)
            if not name:break
            tried.add(name);key='common/'+name+'.js'
            prompt=core.messages('Correct one model-written JavaScript ES module in your survey library. Return its complete source. '
                    'Preserve named exports, paths, existing public class methods and other working behaviors. No compiler edits or test cases.',
                    dict(file=key,old=pkg['files'][key],available_modules=names,public_workflow=EXAMPLE,
                         observations=checks,original_project=pub['requirements']))
            try:
                raw=action.compact.base.request(ledger,('table',tag,rep),folder/'repairs'/name,prompt,'build',5600)
                src=action.build.modules.js_block(raw)
                form.syntax({key:src})
                trial_pkg=dict(pkg,files={**pkg['files'],key:src})
                obs=public(trial_pkg,False,folder/'public'/name)
                before={k for k,v in checks['checks'].items() if v};after={k for k,v in obs['checks'].items() if v}
                keep=before<after and len(obs['errors'])<=len(checks['errors'])
                history.append(dict(module=name,kept=keep,observation=obs))
                if keep:pkg,checks=trial_pkg,obs
            except (ValueError,*action.typed.MISSING) as e:history.append(dict(module=name,reason=str(e)))
    core.save(f,dict(package=pkg,before=first,after=checks,repairs=history))
    return read(f)


def main(phase):
    reg=register()
    targets=reg['targets']
    pub=read(BASE/'public.json')
    if phase=='generate':
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        packages={a:read(BASE/(a+'.json')) for a in ('human','gpt5-library')}
        with patch.multiple(action.compact.base,OUT=OUT,END=action.END,template=action.settings):
            libs={(t,r):prepare(t,r,pub,ledger) for t in TAGS for r in FROZEN[t]}
            public_examples={a:public(p,a=='gpt5-library',OUT/'public'/a) for a,p in packages.items()}
            def one(job):
                tag,n=job
                folder=OUT/tag/'targets'/str(n)
                f=folder/'rows.json'
                if f.exists():return
                rows=[]
                def emit(arm,call):
                    try:value=call()
                    except action.typed.MISSING as e:value=dict(status='missing',reason=str(e))
                    except action.compact.base.ERRORS as e:value=dict(status='invalid',reason=str(e)[:200])
                    rows.append(dict(project='form',task=n,tag=tag,arm=arm,**value))
                def direct():
                    raw=action.compact.base.request(ledger,('table',tag,'a'),folder/'direct-call',core.direct_messages(pub,n),'plan',8192)
                    try:
                        val=receiver.first_object(raw)
                        files=core.files_map(val['files']) if isinstance(val['files'],list) else validate_files(val['files'])
                    except (ValueError,KeyError,TypeError,AttributeError):
                        files={'index.html':document.parse_document(raw)}
                    dest=folder/'direct'
                    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=core.emit('form',{**pub['starter'],**files},dest))
                emit('direct',direct)
                msg=core.messages(SPEC,dict(public=core.prefix(pub,n)))
                try:
                    raw=action.compact.base.request(ledger,('table',tag,'a'),folder/'shared-call',msg,'plan',8192)
                    plan=semantic(raw);failed=None
                except action.typed.MISSING as e:failed=dict(status='missing',reason=str(e))
                except action.compact.base.ERRORS as e:failed=dict(status='invalid',reason=str(e)[:200])
                pool={**packages,**{'self-'+r:libs[tag,r]['package'] for r in FROZEN[tag]}}
                for arm,pkg in pool.items():
                    emit(arm,lambda:failed or compile_page(pkg,plan,arm=='gpt5-library',folder/arm))
                core.save(f,rows)
            with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(one,((t,n) for n in targets for t in TAGS)))
        # Each frozen default here is the common public three-question scenario, independently of any target.
        fixed={}
        for t in TAGS:
            fixed[t]={}
            for arm,pkg in {**packages,**{'self-'+r:libs[t,r]['package'] for r in FROZEN[t]}}.items():
                try:fixed[t][arm]=compile_page(pkg,EXAMPLE,arm=='gpt5-library',OUT/t/'fixed'/arm)
                except (ValueError,TypeError,KeyError) as e:fixed[t][arm]=dict(status='invalid',reason=str(e))
        src=[*OUT.glob('*/*/library.json'),*OUT.glob('*/targets/*/rows.json')]
        core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),sources={str(f.relative_to(OUT)):sha(f) for f in src},public=public_examples,fixed=fixed))
        return
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/f)==v for f,v in seal['sources'].items())
    rows=[r for f in OUT.glob('*/targets/*/rows.json') for r in read(f)]
    for t,arms in seal['fixed'].items():
        rows.extend(dict(project='form',task=n,tag=t,arm='fixed-'+a,**v) for a,v in arms.items() for n in targets)
    proto=browser.verify_contract('form')
    assert proto==read(BASE/'browser.json')
    graded=browser.evaluate(rows,OUT,{'form':proto},4)
    results={reg['models'][t]:[dict(task=r['task'],arm=r['arm'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],
                    report_sha256=r.get('report_sha256')) for r in graded if r['tag']==t] for t in TAGS}
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),models=results,
        public=seal['public'],libraries={t:{r:{k:v for k,v in read(OUT/t/r/'library.json').items() if k!='package'} for r in FROZEN[t]} for t in TAGS},
        cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('generate','score'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
