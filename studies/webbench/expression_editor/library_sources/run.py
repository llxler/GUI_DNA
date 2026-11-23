"""Freeze an independent three-workflow comparison with matched public preparation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import subprocess

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.interface_blind.core import write_files
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, UPSTREAM, digest, dump, now, read, sha, source_files
from studies.table_library_sources.run import file_hashes, verify
from studies.webbench_expand.core import config
from . import browser
from .core import (
    ARMS, BUILDER, CONTROLLERS, HERE, MODEL, MODULES, OUT, SOURCE, STARTED, TASKS, TOOLBAR,
    files, preparation, reference, render, requirements, starter, target_prompt, validate_preparation,
)

CAP = 1.20
END = datetime.fromisoformat('2026-11-23T05:48:00+00:00')
TARGETS = [(a,t) for t in TASKS for a in ARMS]
BASE_CONTROLS = ('starter','blank','upstream_final','reference_full')
EXAMPLES = ('ai_example2',)


def frozen(name):
    value = read(OUT / name)
    verify(value['inputs_sha256'])
    return value


def freeze():
    if OUT.exists():
        raise RuntimeError('Preserve prior stage directory')
    opening = check_credits(CAP)
    if not opening['sufficient']:
        raise BudgetStop('Insufficient available balance')
    revision = subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip()
    assert revision=='7b31ca2b786eef120dd49ce63dd03d0c0006046d'
    assert len(requirements())==20
    package = reference()
    dump(OUT/'reference.json',package)
    control_pages = {'starter':starter(),'blank':{'index.html':'<!doctype html><title>Blank</title>'},
                     'upstream_final':files(SOURCE/'src'),
                     'reference_full':render('reference',package,{'toolbar':list(TOOLBAR),'controllers':list(CONTROLLERS)})}
    for name,page in control_pages.items():
        write_files(OUT/'control-pages'/name,page)
    for arm in ('ai','direct'):
        dump(OUT/'prep-prompts'/(arm+'.json'),preparation(arm))
    assert read(OUT/'prep-prompts/ai.json')[1] == read(OUT/'prep-prompts/direct.json')[1]
    runtime = browser.harness()
    paths = [p for n in ('src','src-init','test') for p in (SOURCE/n).rglob('*') if p.is_file()]
    paths += [SOURCE/'tasks.yml',SOURCE/'package.json',SOURCE/'playwright.config.js',OUT/'reference.json',
              *sorted((OUT/'prep-prompts').glob('*.json'))]
    paths += [p for p in (OUT/'control-pages').rglob('*') if p.is_file()]
    paths += [HERE/f for f in ('core.py','browser.py','run.py','binding.js','compiler.js','runtime-lock.json',
                               'runtime-package.json','PROTOCOL.md')]
    paths += [ROOT/p for p in ('studies/table_library_sources/run.py','studies/browser_jobs.py','studies/study_io.py',
               'studies/ledger_read.py','studies/todomvc_dna/evaluate.py','studies/streaming_provider_v2.py',
               'studies/provider_ext.py','src/gui_dna/provider.py','src/gui_dna/budget.py','src/gui_dna/tasks.py',
               'studies/webbench_expand/core.py','studies/webbench_expand/schema.py','studies/interface_blind/core.py',
               'studies/interface_blind/compile.cjs')]
    finished = now()
    dump(OUT/'freeze.json',{'inputs_sha256':file_hashes(paths)|runtime,'opening_credit_check':opening,
         'opened_utc':STARTED,'frozen_utc':finished,'upstream_revision':revision,'budget_usd':CAP,
         'agent_preparation_elapsed_seconds':(datetime.fromisoformat(finished)-datetime.fromisoformat(STARTED)).total_seconds(),
         'planned_targets':TARGETS,'preparation_model':BUILDER,'target_model':MODEL})


def control_scores(names, marker):
    frozen('freeze.json')
    jobs = [(c,t) for t in TASKS for c in names]
    def one(pair):
        control,task = pair
        key = f'{control}/{task}'
        return key,browser.score(key,task,OUT/'control-pages'/control,True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        scored = dict(pool.map(one,jobs))
    dump(OUT/marker, {'completed_utc':now(),'rows':scored})


def client():
    cfg = config(True)
    cfg.update(models=[BUILDER,MODEL],provider_order={},budget_usd=CAP,stop_new_requests_usd=CAP)
    cfg['model_price_caps'][MODEL] = {'prompt':.2,'completion':.8}
    api = StreamingOpenRouter(cfg, Ledger(OUT/'budget.sqlite3',CAP,CAP))
    api.RATE_LIMIT_TRIES = 1
    return api


def request(api,model,messages,folder,purpose,limit):
    if datetime.now(timezone.utc)>=END and not (folder/'request.json').exists():
        raise BudgetStop('No new requests after the stage deadline')
    return api.call(model,messages,folder,purpose,max_tokens=limit,seed=20261123)


def with_error(prompt,response,error):
    return prompt + [{'role':'assistant','content':response},
                    {'role':'user','content':'Public format/compiler/validation feedback: '+error+
                     '\nReturn the complete corrected JSON output. No behavioral feedback is available.'}]


def prepare():
    frozen('freeze.json')
    if (OUT/'planning-freeze.json').exists():
        raise RuntimeError('Preparation already closed')
    calibrated = read(OUT/'controls-complete.json')['rows']
    discriminating = [t for t in TASKS if calibrated['upstream_final/'+t]['passed'] and
                     not calibrated['blank/'+t]['passed'] and not calibrated['starter/'+t]['passed']]
    if len(discriminating)<10:
        raise RuntimeError('The prespecified external calibration gate did not pass')
    credit = check_credits(CAP)
    if not credit['sufficient']:
        raise BudgetStop('Insufficient pre-call balance')
    api = client()
    def one(arm):
        prompt = read(OUT/'prep-prompts'/(arm+'.json'))
        dest = OUT/'preparation'/arm
        records = []
        for stage in ('first','repair'):
            current = dest/stage
            record = {'arm':arm,'stage':stage,'received':False,'valid':False,'prompt_sha256':digest(prompt)}
            try:
                raw = request(api,BUILDER,prompt,current/'call','prepare-'+arm+'-'+stage,16000)
                record['received'] = True
                obj = validate_preparation(arm,parse_json(raw),current/'validation')
                dump(dest/'artifact.json',obj)
                record.update(valid=True,artifact_sha256=sha(dest/'artifact.json'))
            except (ProviderError,BudgetStop,ValueError,KeyError,TypeError) as e:
                record['error'] = str(e)[:1100]
            dump(current/'record.json',record)
            records.append(record)
            if record['valid'] or not record['received']:
                break
            prompt = with_error(prompt,raw,record['error'])
        return arm,records
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = dict(pool.map(one,('ai','direct')))
    packages = {'reference':read(OUT/'reference.json')}
    for arm in ('ai','direct'):
        if records[arm][-1]['valid']:
            packages[arm]=read(OUT/'preparation'/arm/'artifact.json')
    for arm,task in TARGETS:
        if arm in packages:
            dump(OUT/'inputs'/arm/(task+'.json'),target_prompt(arm,task,packages[arm]))
    if 'ai' in packages:
        pkg=packages['ai']
        write_files(OUT/'control-pages/ai_example2', render('ai',pkg,pkg['examples'][1]['plan']))
    paths=[p for n in ('preparation','inputs','control-pages/ai_example2') for p in (OUT/n).rglob('*') if p.is_file()]
    dump(OUT/'planning-freeze.json',{'frozen_utc':now(),'freeze_sha256':sha(OUT/'freeze.json'),
         'preparation':records,'available_arms':sorted(packages),'inputs_sha256':file_hashes(paths),
         'pre_call_credit_check':credit,'controls_sha256':sha(OUT/'controls-complete.json')})


def generate():
    frozen('freeze.json')
    prep=frozen('planning-freeze.json')
    assert prep['freeze_sha256']==sha(OUT/'freeze.json') and prep['controls_sha256']==sha(OUT/'controls-complete.json')
    if (OUT/'generation-complete.json').exists():
        raise RuntimeError('Generation closed')
    api=client()
    packages={'reference':read(OUT/'reference.json')}
    for a in ('ai','direct'):
        if a in prep['available_arms']:
            packages[a]=read(OUT/'preparation'/a/'artifact.json')

    def attempt(arm,task,stage,prompt):
        dest=OUT/'candidates'/arm/task/stage
        row={'arm':arm,'task':task,'stage':stage,'generated':False,'valid':False}
        if (dest/'record.json').exists():
            record=read(dest/'record.json')
            assert record.get('prompt_sha256')==(digest(prompt) if prompt is not None else None)
            return record
        if prompt is None:
            row['error']='No valid frozen preparation artifact'
        else:
            row['prompt_sha256']=digest(prompt)
            try:
                raw=request(api,MODEL,prompt,dest/'call',arm+'-'+stage,8192)
                row['generated']=True
                rendered=render(arm,packages[arm],parse_json(raw))
                write_files(dest/'page',rendered)
                row.update(valid=True,files_sha256=source_files(dest/'page'))
            except (ProviderError,BudgetStop,ValueError,KeyError,TypeError) as e:
                row['error']=str(e)[:1100]
        dump(dest/'record.json',row)
        return row

    def first(pair):
        arm,task=pair
        prompt=read(OUT/'inputs'/arm/(task+'.json')) if arm in packages else None
        return attempt(arm,task,'first',prompt)

    def repair(row):
        arm,task=row['arm'],row['task']
        base=OUT/'candidates'/arm/task/'first/call'
        prompt=read(base/'request.json')['body']['messages']
        raw=read(base/'response.json')['choices'][0]['message']['content']
        return attempt(arm,task,'repair',with_error(prompt,raw,row['error']))

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(first,TARGETS[:3]))
        if not any(r['generated'] for r in rows):
            raise RuntimeError('None of the three probes returned a response')
        rows += list(pool.map(first,TARGETS[3:]))
        rows += list(pool.map(repair,[r for r in rows if r['generated'] and not r['valid']]))
    dump(OUT/'generation-complete.json',{'frozen_utc':now(),'freeze_sha256':sha(OUT/'freeze.json'),
         'planning_freeze_sha256':sha(OUT/'planning-freeze.json'),'rows':rows,
         'inputs_sha256':file_hashes(p for p in (OUT/'candidates').rglob('*') if p.is_file())})


def score():
    frozen('freeze.json')
    prep=frozen('planning-freeze.json')
    generation=frozen('generation-complete.json')
    assert generation['planning_freeze_sha256']==sha(OUT/'planning-freeze.json')
    def one(row):
        arm,task,stage=row['arm'],row['task'],row['stage']
        key=f'{arm}/{task}/{stage}'
        return key,browser.score(key,task,OUT/'candidates'/key/'page',False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        scored=dict(pool.map(one,[r for r in generation['rows'] if r['valid']]))
    dump(OUT/'scores-complete.json',{'completed_utc':now(),'rows':scored})
    control_scores(EXAMPLES if 'ai' in prep['available_arms'] else (), 'ai-control-complete.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','controls','prepare','generate','score'))
    args=parser.parse_args()
    if args.action=='controls':
        control_scores(BASE_CONTROLS,'controls-complete.json')
    else:
        {'freeze':freeze,'prepare':prepare,'generate':generate,'score':score}[args.action]()
