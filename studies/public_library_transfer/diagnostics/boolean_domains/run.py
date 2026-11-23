"""Losslessly canonicalize a redundant Boolean domain; keep earlier trial outcomes."""
import argparse
import copy
from pathlib import Path
import time
from studies.public_library_transfer import core as c,browser
from studies.public_library_transfer.report import comparison
from studies.public_library_transfer_open import run as upstream
from studies.schema_constrained_table.generate import SNAPSHOT,REVISION,infer

HERE=Path(__file__).resolve().parent
OUT=c.ROOT/'artifacts/public-library-transfer-boolean-20261123'


def register():
    path=OUT/'registered.json'
    inputs=[Path(__file__),HERE/'PROTOCOL.md',Path(upstream.__file__),Path(c.__file__),
            c.ROOT/'studies/schema_constrained_table/generate.py',upstream.OUT/'registered.json',c.OUT/'generation-sealed.json']
    src={str(p.relative_to(c.ROOT)):c.sha(p) for p in inputs}
    if path.exists():
        if c.read(path)['sources']!=src: raise ValueError('Registered source changed')
    else: c.save(path,{'registered':c.now(),'sources':src,'planner':c.MODEL,'revision':REVISION,'new_api_requests':0})


def normalize(raw):
    changed=[]
    normalized=copy.deepcopy(raw)
    for control in normalized['controls']:
        vals=control['values']
        if control['type']=='boolean' and isinstance(vals,list) and len(vals)==2 and set(vals)=={'true','false'}:
            control['values']=[]
            changed.append(control['id'])
    return normalized,changed


def admit(p,tag,public):
    dest=OUT/'builds'/p/tag
    if (dest/'status.json').exists(): return
    src=upstream.OUT/'builds'/p/tag
    while not (src/'status.json').is_file(): time.sleep(4)
    old=c.read(src/'status.json')
    attempts=[]
    status='missing' if old['status']=='missing' else 'build_failed'
    for reply in sorted(src.glob('attempt-*/response.json')):
        try:
            raw=c.parse(c.read(reply)['choices'][0]['message']['content'] or '')
            normalized,changed=normalize(raw)
            pkg=c.package(public,normalized)
            for key,v in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=dest/reply.parent.name/key
                c.materialize(p,pkg,v,page)
                errors=browser.public_load(p,page)
                c.save(dest/reply.parent.name/(key+'-load.json'),errors)
                if errors: raise ValueError(str(errors)[:1600])
            c.save(dest/'package.json',pkg)
            attempts.append({'response':str(reply.relative_to(c.ROOT)),'sha256':c.sha(reply),'canonicalized':changed,'admitted':True})
            status='valid';break
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            attempts.append({'response':str(reply.relative_to(c.ROOT)),'sha256':c.sha(reply),'admitted':False,'reason':str(exc)[:600]})
    c.save(dest/'status.json',{'status':status,'old_status':old['status'],'attempts':attempts})


def generate():
    import torch
    import transformers
    tokenizer=transformers.AutoTokenizer.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False)
    model=transformers.AutoModelForCausalLM.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False,
                dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
    for p in upstream.ORDER:
        seal=OUT/'seals'/f'{p}.json'
        if seal.exists(): continue
        public=c.read(c.OUT/'inputs'/f'{p}.json')
        rows=[r for r in c.read(c.OUT/'project-seals'/f'{p}.json')['rows'] if r['arm']=='direct' and r['task'] in upstream.tasks(p)]
        for tag in (('oss','mistral') if p in upstream.SPECIAL else ('oss',)):
            admit(p,tag,public)
            d=OUT/'builds'/p/tag
            status=c.read(d/'status.json')['status']
            pkg=c.read(d/'package.json') if status=='valid' else None
            if pkg:
                fixed=d/'fixed'
                fixed_files=c.materialize(p,pkg,pkg['examples'][0]['plan'],fixed)
            for n in upstream.tasks(p):
                base={'project':p,'task':n,'builder':upstream.remote.MODELS[tag],'rep':1,'status':status,'files':None,'page':None}
                plan=dict(base,arm='plan',planner=c.MODEL)
                first=dict(base,arm='fixed',planner=None)
                if pkg:
                    dest=OUT/'plans'/p/tag/f'task-{n}'
                    msg=c.plan_messages(public,n,pkg)
                    c.save(dest/'messages.json',msg)
                    if not (dest/'response.json').exists():
                        c.save(dest/'response.json',infer(torch,tokenizer,model,msg,pkg['plan_schema']))
                    files=c.materialize(p,pkg,c.read(dest/'response.json')['plan'],dest/'page')
                    plan.update(files=files,page=str((dest/'page').relative_to(c.ROOT)))
                    first.update(files=fixed_files,page=str(fixed.relative_to(c.ROOT)))
                rows.extend([plan,first])
        c.save(seal,{'rows':rows,'registered_sha256':c.sha(OUT/'registered.json')})
        print(p,'sealed',flush=True)


def score():
    for p in upstream.ORDER:
        seal=OUT/'seals'/f'{p}.json'
        while not seal.exists(): time.sleep(5)
        dest=OUT/'scores'/f'{p}.json'
        if dest.exists(): continue
        rows=browser.evaluate(c.read(seal)['rows'],OUT,{p:browser.verify_contract(p)},2)
        direct={r['task']:r for r in rows if r['arm']=='direct'}
        groups=[]
        for tag in ('oss','mistral') if p in upstream.SPECIAL else ('oss',):
            a,b=[{r['task']:r for r in rows if r['builder']==upstream.remote.MODELS[tag] and r['arm']==kind}
                 for kind in ('plan','fixed')]
            status=c.read(OUT/'builds'/p/tag/'status.json')
            groups.append({'builder':upstream.remote.MODELS[tag],'public_admission':status,
                           'plan_vs_direct':comparison(a,direct,upstream.tasks(p)),
                           'plan_vs_fixed':comparison(a,b,upstream.tasks(p))})
        c.save(dest,{'project':p,'groups':groups,'targets':upstream.tasks(p),'seal_sha256':c.sha(seal),
                    'rows':[{k:r[k] for k in ('task','arm','builder','status','passed','report_sha256')} for r in rows]})
    c.save(c.ROOT/'studies/results/public-library-transfer-boolean-20261123.json',{'planner':c.MODEL,
        'registered_sha256':c.sha(OUT/'registered.json'),'new_api_calls':0,
        'projects':[c.read(OUT/'scores'/f'{p}.json') for p in upstream.ORDER]})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('generate','score'));arg=ap.parse_args()
    register()
    if arg.action=='generate': generate()
    else: score()
