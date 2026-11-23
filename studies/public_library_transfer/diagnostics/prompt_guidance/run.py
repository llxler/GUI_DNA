"""Matched generic versus behavior-focused preparation on the two historical 3/20 projects."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from studies.public_library_transfer import core as c, browser, build
from studies.public_library_transfer.report import comparison
from studies.study_io import digest

HERE=Path(__file__).resolve().parent
OUT=c.ROOT/'artifacts/public-library-transfer-prompt-20261123'
PROJECTS=('table','svg-chart')
TAGS=('codex-1','codex-2')
GENERIC="""Build a reusable website behavior library implementing the given public project. Choose one to six independently selectable semantic controls. No task-number switches, per-target pages, executable plans, outside files, network, dependencies or tools. Return complete code matching the JSON schema. Each id matches [a-z][a-z0-9-]*. Use boolean with empty values and default/example strings true or false, or enum with 2-8 distinct simple strings, default and first example. Supply the design, controls, an optional static HTML fragment inserted AFTER a unique exact anchor in the starter (empty strings for no fragment), additive CSS, optional classic script at body end, and files as path/content pairs for browser modules or styles. The compiler preserves the starter HTML and assets; it sets data-dna-<id> attributes on html and globalThis.APP_CONFIG before modules load. You cannot replace index.html or mounted assets. Vite and SCSS are available on svg-chart."""


def register():
    path=OUT/'registered.json'
    source=[Path(__file__),HERE/'PROTOCOL.md',Path(c.__file__),Path(build.__file__)]+[c.OUT/'inputs'/f'{p}.json' for p in PROJECTS]
    hashes={str(p.relative_to(c.ROOT)):c.sha(p) for p in source}
    if path.exists():
        if c.read(path)['hashes']!=hashes: raise ValueError('Registered dependencies changed')
    else:
        c.save(path,{'registered':c.now(),'projects':PROJECTS,'tags':TAGS,'hashes':hashes,
                     'main_registration_sha256':c.sha(c.OUT/'registered.json')})


def prepare(job):
    p,tag=job
    d=OUT/p/tag
    if (d/'status.json').exists(): return
    data=c.read(c.OUT/'inputs'/f'{p}.json')
    base=c.messages(GENERIC,{'output_schema':c.SCHEMA,'public_project':data})
    msg=base
    attempts=[]
    status='missing'
    for n in range(2):
        attempt=d/f'attempt-{n+1}'
        c.save(attempt/'messages.json',msg)
        try: raw=build.subscribe(msg,attempt)
        except Exception as exc:
            attempts.append({'error':str(exc),'received':False}); break
        try:
            pkg=c.package(data,c.parse(raw))
            for key,plan in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=attempt/key
                c.materialize(p,pkg,plan,page)
                errors=browser.public_load(p,page)
                c.save(attempt/f'{key}.json',errors)
                if errors: raise ValueError(str(errors)[:1600])
            c.save(d/'package.json',pkg)
            attempts.append({'received':True,'public_valid':True})
            status='valid'
            break
        except (ValueError,TypeError,KeyError) as e:
            attempts.append({'received':True,'public_valid':False,'error':str(e)[:1600]})
            msg=base+[{'role':'assistant','content':raw[:65000]},{'role':'user','content':'The public load/format check reported '+str(e)[:1600]+'. Return a complete replacement JSON package.'}]
            status='build_failed'
    c.save(d/'status.json',{'status':status,'attempts':attempts})


def freeze():
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(prepare,[(p,t) for p in PROJECTS for t in TAGS]))
    rows=[]
    for p in PROJECTS:
        for tag in TAGS:
            for condition,folder in [('generic',OUT/p/tag),('focused',c.OUT/'builds'/p/tag)]:
                status=c.read(folder/'status.json')['status']
                files=page=None
                if status=='valid':
                    pkg=c.read(folder/'package.json')
                    page=OUT/'pages'/p/tag/condition
                    files=c.materialize(p,pkg,pkg['examples'][0]['plan'],page)
                for n in range(1,21):
                    rows.append({'project':p,'task':n,'arm':'fixed','builder':c.BUILDERS[tag],'planner':None,
                        'rep':int(tag[-1]),'condition':condition,'status':status,'files':files,
                        'page':str(page.relative_to(c.ROOT)) if page else None})
    c.save(OUT/'sealed.json',{'rows':rows,'registration_sha256':c.sha(OUT/'registered.json')})


def score():
    raw=c.read(OUT/'sealed.json')
    rows=browser.evaluate(raw['rows'],OUT,{p:browser.verify_contract(p) for p in PROJECTS},2)
    summary=[]
    for p in PROJECTS:
        for tag in TAGS:
            src=[r for r in rows if r['project']==p and r['rep']==int(tag[-1])]
            a,b=[{r['task']:r for r in src if r['condition']==cond} for cond in ('focused','generic')]
            summary.append({'project':p,'rep':int(tag[-1]),**comparison(a,b,range(1,21))})
    c.save(c.ROOT/'studies/results/public-library-transfer-prompt-20261123.json',{'builder':'gpt-6.2-astra',
        'registered_sha256':raw['registration_sha256'],'seal_sha256':c.sha(OUT/'sealed.json'),
        'comparison_order':['focused first example','generic first example'],'groups':summary,
        'rows':[{k:r[k] for k in ('project','task','rep','condition','status','passed','report_sha256')} for r in rows]})


if __name__=='__main__':
    register()
    if sys.argv[1]=='generate': freeze()
    elif sys.argv[1]=='score': score()
    else: raise SystemExit('Expected generate or score')
