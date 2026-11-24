"""Repair archived local controller code with public state-transition feedback."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.todomvc.event_modules import modules
from studies.public_library_transfer.self_refinement.todomvc.event_modules import run as base
from studies.study_io import ROOT,digest,read,sha,now

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todomvc-event-feedback-20261124'
REPORT=HERE/'result.json'
TASKS=base.TASKS
ARMS=('self','fixed_on','fixed_off')
REPS=('A','B')
save=browser.preserve_json


def verify_design():
    target=OUT/'public-design.json'
    if not target.exists():
        save(target,{'utc':now(),'sources':{k:sha(HERE/k) for k in ('PROTOCOL.md','probes.cjs')}})
    data=read(target)
    assert all(sha(HERE/k)==v for k,v in data['sources'].items())


def register():
    verify_design()
    parent=read(base.OUT/'seal.json')
    assert all(sha(base.OUT/k)==v for k,v in parent['sources'].items())
    paths=[HERE/'PROTOCOL.md',HERE/'probes.cjs',Path(__file__),Path(modules.__file__),Path(base.__file__),
           base.binding.HERE/'extract.cjs',base.binding.ACORN,modules.HERE/'function.cjs',Path(base.engine.__file__),
           base.OUT/'public.json',base.OUT/'seal.json',OUT/'public-design.json']
    desc={'files':{str(p.relative_to(ROOT)):sha(p) for p in paths},'seeds':base.SEEDS,'model':base.MODEL,'revision':base.REVISION}
    path=OUT/'registration.json'
    if path.exists():
        assert read(path)['contract']==desc
    else:
        save(path,{'utc':now(),'contract':desc})


def evaluate_public(source, features):
    payload=json.dumps({'source':source,'features':features})
    cmd=subprocess.run(['node',str(HERE/'probes.cjs')],input=payload,text=True,capture_output=True,check=True,timeout=15)
    return json.loads(cmd.stdout)


def passes(checks):
    return {k for k,v in checks.items() if v['passed']}


def diagnostic(checks):
    return {k:{'expected':v['expected'],'observed':v['actual']} for k,v in checks.items() if not v['passed']}


class Model(base.engine.Model):
    def __init__(self):
        import torch
        import transformers
        self.torch=torch
        self.tokenizer=transformers.AutoTokenizer.from_pretrained(str(base.SNAPSHOT),local_files_only=True)
        self.tokenizer.padding_side='left'
        self.tokenizer.pad_token=self.tokenizer.eos_token
        self.model=transformers.AutoModelForCausalLM.from_pretrained(
            str(base.SNAPSHOT),local_files_only=True,trust_remote_code=False,dtype=torch.float16,
            attn_implementation='sdpa').to('cuda').eval()
        save(OUT/'environment.json',{'torch':torch.__version__,'transformers':transformers.__version__,
             'gpu':torch.cuda.get_device_name(0),'model':base.MODEL,'revision':base.REVISION})


def classify(before, new, parsed):
    if not parsed:
        return 'invalid'
    if passes(before)-passes(new):
        return 'public_regression'
    return 'accepted' if passes(new)>passes(before) else 'no_public_gain'


def repair_library(lm, rep, features, public, config):
    folder=OUT/rep
    funcs=read(base.OUT/rep/'preparation/library.json')
    first=evaluate_public(modules.assemble(funcs,config),features)
    requests={}
    for name in modules.CONTRACTS:
        failing={k:v for k,v in first.items() if not v['passed'] and name in v['owners']}
        if failing:
            prompt=modules.messages(name,public)
            prompt.append({'role':'user','content':json.dumps({'original_function':funcs[name],
                'public_checks_failed':diagnostic(failing),
                'instruction':'Fix this function to follow the public state and event contract. Return just the complete JavaScript function, preserving its name and parameter count.'})})
            requests[name]=prompt
    names=list(requests)
    proposed={}
    for i in range(0,len(names),4):
        batch=names[i:i+4]
        raw=lm.generate(folder/'calls'/f'batch-{i}.json',[requests[n] for n in batch],512)
        for name,answer in zip(batch,raw,strict=True):
            proposed[name]=modules.extract(name,answer)
    current=first
    trials=[]
    for name,candidate in proposed.items():
        trial={**funcs,name:candidate} if candidate else None
        after=evaluate_public(modules.assemble(trial,config),features) if trial else None
        disposition=classify(current,after,candidate is not None)
        trials.append({'name':name,'outcome':disposition,'before':sorted(passes(current)),
                       'proposed':sorted(passes(after)) if after is not None else None,
                       'proposed_source_sha256':digest(candidate) if candidate else None})
        if disposition=='accepted':
            funcs,current=trial,after
    save(folder/'library.json',funcs)
    save(folder/'public.json',{'initial':first,'final':current,'attempts':trials})
    return funcs


def task_features(builder,target):
    requirement=target['requirement']
    return [k for k,lines in builder['spec'].items() if k=='core' or any(text in requirement for text in lines)]


def original_direct(task, row):
    n=TASKS.index(task)
    i=(n//4)*4
    record=read(base.OUT/'direct'/f'batch-{i}.json')
    raw=record['outputs'][n-i]
    if row['status']=='valid':
        path=base.OUT/'direct/direct'/task/'files.json'
        assert sha(path)==row['files_sha256']
        return raw,read(path)['candidate.js']
    return raw,None


def repair_direct(lm,target_map,public):
    plans={}
    result={}
    for task in TASKS:
        raw,code=original_direct(task,target_map['direct','direct',task])
        spec=public['targets'][task]
        features=task_features(public['builder'],spec)
        observed=evaluate_public(code,features)
        item=result[task]={'original':code,'initial':observed,'final_code':code,'final':observed,'outcome':'already_passed'}
        if passes(observed)==set(observed):
            continue
        prompt=core.messages('Repair one complete JavaScript controller. The supplied checks inspect only the public state contract. Return the entire browser JavaScript program assigning window.candidate, with init, reduce, select. No Markdown or explanation.',
            {'task':spec,'previous':code if code is not None else raw,
             'public_checks_failed':diagnostic(observed)})
        plans[task]=prompt
    scheduled=list(plans)
    for i in range(0,len(scheduled),4):
        batch=scheduled[i:i+4]
        outputs=lm.generate(OUT/'direct/calls'/f'batch-{i}.json',[plans[t] for t in batch],2048)
        for task,raw in zip(batch,outputs,strict=True):
            item=result[task]
            parsed=subprocess.run(['node',str(base.binding.HERE/'extract.cjs'),str(base.binding.ACORN)],
                input=modules.js_block(raw),text=True,capture_output=True,timeout=10)
            code=json.loads(parsed.stdout)['code'] if parsed.returncode==0 else None
            after=evaluate_public(code,task_features(public['builder'],public['targets'][task])) if code else None
            state=classify(item['initial'],after,code is not None)
            item['outcome']=state
            item['proposed']=sorted(passes(after)) if after is not None else None
            item['proposed_source_sha256']=digest(code) if code else None
            if state=='accepted':
                item.update(final=after,final_code=code)
    notes={task:{k:v for k,v in item.items() if k not in ('original','final_code')} for task,item in result.items()}
    save(OUT/'direct/public.json',notes)
    return result


def store_candidate(group, arm, task, code, plan=None):
    row={'group':group,'arm':arm,'task':task,'status':'valid' if code else 'invalid'}
    if plan is not None:
        row['plan']=plan
    if code:
        path=OUT/'candidates'/group/arm/task/'files.json'
        save(path,{'candidate.js':code})
        row['files_sha256']=sha(path)
    return row


def generate():
    register()
    if (OUT/'seal.json').exists():
        return
    public=read(base.OUT/'public.json')
    parent=read(base.OUT/'seal.json')
    before={(r['group'],r['arm'],r['task']):r for r in parent['rows']}
    model=Model()
    rows=[]
    for rep in REPS:
        config=before[rep,'fixed_on',TASKS[0]]['plan']
        features=list(public['builder']['spec'])
        updates=repair_library(model,rep,features,public['builder'],config)
        for task in TASKS:
            for arm in ARMS:
                old=before[rep,arm,task]
                plan=old['plan']
                path=base.OUT/rep/arm/task/'files.json'
                assert sha(path)==old['files_sha256']
                rows.append(store_candidate(rep,'before_'+arm,task,read(path)['candidate.js'],plan))
                rows.append(store_candidate(rep,'after_'+arm,task,modules.assemble(updates,plan),plan))
        print(rep,'public function checks complete',flush=True)
    changes=repair_direct(model,before,public)
    for task,item in changes.items():
        for arm,key in [('direct','original'),('feedback_direct','final_code')]:
            rows.append(store_candidate('direct',arm,task,item[key]))
    files={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*.json')) if p.name!='seal.json'}
    save(OUT/'seal.json',{'utc':now(),'registration_sha256':sha(OUT/'registration.json'),'files':files,'rows':rows})
    print('sealed',len(rows),flush=True)


def paired(rows):
    direct={a:{r['task']:r['passed'] for r in rows if r['group']=='direct' and r['arm']==a}
            for a in ('direct','feedback_direct')}
    pairs={}
    for rep in REPS:
        arms={a:{r['task']:r['passed'] for r in rows if r['group']==rep and r['arm']==a}
              for a in (phase+'_'+arm for phase in ('before','after') for arm in ARMS)}
        cols={**arms,**direct}
        assert all(set(v)==set(TASKS) for v in cols.values())
        pairs[rep]={a:[t for t in TASKS if v[t]] for a,v in cols.items()}
    return pairs


def score():
    record=read(OUT/'seal.json')
    assert all(sha(OUT/file)==h for file,h in record['files'].items())
    from studies.public_library_transfer.other_benchmarks import evaluate
    from studies.public_library_transfer.backbone_suites import run as suites
    targets,_=suites.inputs()
    server=evaluate.todo.Server(OUT)
    def one(row):
        if row['status']!='valid':
            return {**row,'passed':False}
        src=OUT/'candidates'/row['group']/row['arm']/row['task']/'files.json'
        assert sha(src)==row['files_sha256']
        path=OUT/'scores'/row['task']/row['files_sha256']
        with browser.lock(path/'.lock'):
            if not (path/'verdict.json').exists():
                with browser.browser_slot():
                    evaluate.score(('todomvc',targets[row['task']],read(src),path,server))
        return base.binding.official(path,targets[row['task']],row)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=list(pool.map(one,record['rows']))
    finally:
        server.close()
    usage={}
    for group in (*REPS,'direct'):
        calls=[read(p) for p in (OUT/group/'calls').glob('*.json')]
        usage[group]={'calls':sum(len(c['outputs']) for c in calls),
                      'input_tokens':sum(sum(c['input_tokens']) for c in calls),
                      'output_tokens':sum(sum(map(len,c['output_ids'])) for c in calls)}
    report={'model':base.MODEL,'revision':base.REVISION,'new_external_api_calls':0,'new_api_cost_usd':0,
            'public_design_utc':read(OUT/'public-design.json')['utc'],'registered_utc':read(OUT/'registration.json')['utc'],
            'sealed_utc':record['utc'],'seal_sha256':sha(OUT/'seal.json'),'parent_seal_sha256':sha(base.OUT/'seal.json'),
            'parent_repair_calls_included':False,'sources':read(OUT/'registration.json')['contract']['files'],
            'usage':usage,'public':{g:read(OUT/g/'public.json') for g in (*REPS,'direct')},'rows':rows,'paired':paired(rows)}
    browser.write_json(REPORT,report)
    check()


def check():
    data=read(REPORT)
    assert data['paired']==paired(data['rows'])
    assert len(data['rows'])==len({(r['group'],r['arm'],r['task']) for r in data['rows']})==112
    for p in (Path(__file__),HERE/'PROTOCOL.md',HERE/'probes.cjs'):
        assert sha(p)==data['sources'][str(p.relative_to(ROOT))]
    for tag in REPS:
        public=data['public'][tag]
        assert passes(public['final'])>=passes(public['initial'])
        for change in public['attempts']:
            if change['outcome']=='accepted':
                assert set(change['proposed'])>set(change['before'])
    for r in data['public']['direct'].values():
        assert passes(r['final'])>=passes(r['initial'])
    print({g:{a:len(t) for a,t in arms.items()} for g,arms in data['paired'].items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','generate','score','check'))
    args=parser.parse_args()
    {'register':register,'generate':generate,'score':score,'check':check}[args.action]()
