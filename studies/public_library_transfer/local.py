"""Generate matched free code and closed plans with one frozen local model."""
import hashlib
import json
from pathlib import Path
import time

from studies.schema_constrained_table.generate import REVISION, SNAPSHOT, infer
from . import core as c


def base(project,task,arm,tag=None):
    return {'project':project,'task':task,'arm':arm,'rep':0 if tag is None else 2 if tag=='codex-2' else 1,
            'builder':c.BUILDERS.get(tag),'planner':None if arm=='fixed' else c.MODEL,
            'page':None,'files':None}


def valid(row,page,files):
    return {**row,'status':'valid','page':str(page.relative_to(c.ROOT)),'files':files}


def direct_batch(model,tokenizer,torch,data,tasks):
    project=data['project']
    folders=[c.OUT/'direct'/project/f'task-{task}' for task in tasks]
    prompts=[c.direct_messages(data,n) for n in tasks]
    for d,prompt in zip(folders,prompts): c.save(d/'messages.json',prompt)
    texts=[tokenizer.apply_chat_template(m,add_generation_prompt=True,tokenize=False) for m in prompts]
    inputs=tokenizer(texts,padding=True,return_tensors='pt',add_special_tokens=False).to(model.device)
    with torch.inference_mode():
        tokens=model.generate(**inputs,max_new_tokens=c.LIMIT,do_sample=False,pad_token_id=tokenizer.eos_token_id)
    for task,d,seq in zip(tasks,folders,tokens[:,inputs['input_ids'].shape[1]:]):
        ids=seq.tolist()
        if tokenizer.eos_token_id in ids: ids=ids[:ids.index(tokenizer.eos_token_id)+1]
        raw=tokenizer.decode(ids,skip_special_tokens=True)
        c.save(d/'response.json',{'text':raw,'tokens':ids,'prompt_sha256':c.sha(d/'messages.json')})
        row=base(project,task,'direct')
        try:
            files=c.materialize_direct(project,data,c.parse(raw),d/'page')
            row=valid(row,d/'page',files)
        except (ValueError,KeyError,TypeError) as e:
            row.update(status='invalid',error=str(e)[:450])
        c.save(d/'row.json',row)


def plans(model,tokenizer,torch,data,tag):
    project=data['project']
    b=c.OUT/'builds'/project/tag
    status=c.read(b/'status.json')
    pkg=c.read(b/'package.json') if status['status']=='valid' else None
    if pkg:
        page=b/'first-page'
        fixed=c.materialize(project,pkg,pkg['examples'][0]['plan'],page)
    for task in range(1,21):
        d=c.OUT/'plans'/project/tag/f'task-{task}'
        if (d/'rows.json').is_file(): continue
        plan_row=base(project,task,'plan',tag)
        fixed_row=base(project,task,'fixed',tag)
        if pkg:
            msg=c.plan_messages(data,task,pkg)
            c.save(d/'messages.json',msg)
            resp=infer(torch,tokenizer,model,msg,pkg['plan_schema'])
            if len(resp['generated_token_ids'])>c.LIMIT: raise RuntimeError('Plan over registered output limit')
            c.save(d/'response.json',{**resp,'prompt_sha256':c.sha(d/'messages.json'),'package_sha256':status['package_sha256']})
            files=c.materialize(project,pkg,resp['plan'],d/'page')
            plan_row=valid(plan_row,d/'page',files)
            fixed_row=valid(fixed_row,page,fixed)
        else:
            plan_row['status']=fixed_row['status']=status['status']
        c.save(d/'rows.json',[plan_row,fixed_row])


def seal(project):
    direct=[c.read(c.OUT/'direct'/project/f'task-{t}/row.json') for t in range(1,21)]
    matched=[r for tag in c.BUILDERS for t in range(1,21) for r in c.read(c.OUT/'plans'/project/tag/f'task-{t}/rows.json')]
    c.save(c.OUT/'project-seals'/f'{project}.json',{'project':project,'rows':direct+matched})
    print('sealed',project,flush=True)


def main():
    reg=c.read(c.OUT/'registered.json')['contract']['sources']
    for p,h in reg.items():
        if c.sha(c.ROOT/p)!=h: raise ValueError(f'Registered source changed: {p}')
    import torch
    import transformers
    tokenizer=transformers.AutoTokenizer.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False)
    tokenizer.padding_side='left'
    tokenizer.pad_token=tokenizer.eos_token
    model=transformers.AutoModelForCausalLM.from_pretrained(str(SNAPSHOT),local_files_only=True,trust_remote_code=False,
                                     dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
    c.save(c.OUT/'local-environment.json',{'model':c.MODEL,'revision':REVISION,'transformers':transformers.__version__,
        'torch':torch.__version__,'dtype':'float16','gpu':torch.cuda.get_device_name(0),'max_output_tokens':c.LIMIT})
    while True:
        for project in c.PROJECTS:
            if (c.OUT/'project-seals'/f'{project}.json').is_file(): continue
            data=c.read(c.OUT/'inputs'/f'{project}.json')
            for tag in c.BUILDERS:
                if (c.OUT/'builds'/project/tag/'status.json').is_file():
                    plans(model,tokenizer,torch,data,tag)
            needed=[n for n in range(1,21) if not (c.OUT/'direct'/project/f'task-{n}/row.json').exists()]
            for i in range(0,len(needed),5):
                direct_batch(model,tokenizer,torch,data,needed[i:i+5])
            if all((c.OUT/'plans'/project/tag/'task-20/rows.json').exists() for tag in c.BUILDERS):
                seal(project)
        if all((c.OUT/'project-seals'/f'{p}.json').is_file() for p in c.PROJECTS): break
        time.sleep(4)
    files=[c.OUT/'project-seals'/f'{p}.json' for p in c.PROJECTS]
    c.save(c.OUT/'generation-sealed.json',{'sealed':c.now(),'project_seals':{p.stem:c.sha(p) for p in files},
                                          'rows':[r for p in files for r in c.read(p)['rows']]})


if __name__=='__main__': main()
