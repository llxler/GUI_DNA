"""Repeat a frozen schema and an empty example at the end of each human-library prompt."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil

from gui_dna.budget import BudgetStop,Ledger
from gui_dna.provider import ProviderError,parse_json
from scripts.check_openrouter_credits import check_credits
from studies import browser_jobs
from studies.expression_editor_sources.browser import HARNESS,RUNTIME_KEY
from studies.expression_editor_sources.core import MODEL,OUT as TRIAL,RUNTIME,TASKS,render
from studies.interface_blind.core import write_files
from studies.ledger_read import totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT,digest,dump,now,read,sha,source_files
from studies.table_library_sources.report import paired
from studies.table_library_sources.run import file_hashes,verify
from studies.webbench_expand.core import config

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/expression-editor-interface-examples-20261123'
BASELINE=ROOT/'studies/results/expression-editor-sources-20261123.json'
CONTROL=ROOT/'studies/results/expression-editor-empty-plan-20261123.json'
DEST=ROOT/'studies/results/expression-editor-interface-examples-20261123.json'
EXAMPLE={'toolbar':[],'controllers':[]}
MAX_CAP=.15
END=datetime.fromisoformat('2026-11-23T05:55:00+00:00')


def intervention(original,schema):
    assert len(original)==2 and original[0]['role']=='system' and original[1]['role']=='user'
    suffix=('\n\nOutput plan_schema (repeated from the frozen package):\n'+json.dumps(schema,ensure_ascii=False)
            +'\nA schema-valid example showing the output format:\n'+json.dumps(EXAMPLE,ensure_ascii=False))
    return [dict(original[0]),{'role':'user','content':original[1]['content']+suffix}]


def freeze():
    if OUT.exists() or (TRIAL/'scores').exists() or (TRIAL/'scores-complete.json').exists():
        raise RuntimeError('Freeze this study before official candidate scoring; preserve existing stages')
    manifest=read(TRIAL/'planning-freeze.json')
    verify(manifest['inputs_sha256'])
    schema=read(TRIAL/'reference.json')['plan_schema']
    inputs=[HERE/'PROTOCOL.md',HERE/'run.py',TRIAL/'freeze.json',TRIAL/'planning-freeze.json',TRIAL/'reference.json',CONTROL,
            ROOT/'studies/expression_editor_sources/core.py',ROOT/'studies/expression_editor_sources/run.py',
            ROOT/'studies/streaming_provider_v2.py',ROOT/'studies/provider_ext.py',ROOT/'src/gui_dna/budget.py',
            ROOT/'studies/interface_blind/core.py',ROOT/'studies/interface_blind/compile.cjs',
            ROOT/'studies/webbench_expand/schema.py',ROOT/'studies/webbench_expand/core.py',ROOT/'studies/browser_jobs.py']
    for task in TASKS:
        old=TRIAL/'inputs/reference'/(task+'.json')
        new=OUT/'prompts'/(task+'.json')
        dump(new,intervention(read(old),schema))
        inputs.extend((old,new))
    harness=OUT/'harness'/HARNESS
    prior=TRIAL/'harness'/HARNESS
    shutil.copytree(prior,harness,symlinks=True)
    assert (harness/'node_modules').resolve()==(prior/'node_modules').resolve()
    for p in [harness/'playwright.config.cjs',harness/'package.json',*(harness/'test').glob('*.js')]:
        assert sha(p)==sha(prior/p.relative_to(harness))
        inputs.append(p)
    dump(OUT/'freeze.json',{'frozen_utc':now(),'inputs_sha256':file_hashes(inputs),'task_ids':TASKS,'model':MODEL,
         'max_output_tokens':8192,'conditioned_on_seen_format_difficulties':True,'initial_candidate_scores_seen':False,
         'optional_stage_cap_max_usd':MAX_CAP,'empty_example':EXAMPLE})


def generate(cap):
    if cap is None or not 0<cap<=MAX_CAP:
        raise RuntimeError('Set the separately authorized exposure limit within the registered maximum')
    if (OUT/'generation-complete.json').exists() or datetime.now(timezone.utc)>=END:
        raise RuntimeError('Closed stage')
    frozen=read(OUT/'freeze.json')
    verify(frozen['inputs_sha256'])
    credit=check_credits(cap)
    if not credit['sufficient']:
        raise BudgetStop('Insufficient available balance')
    if not (OUT/'opening-credits.json').exists():
        dump(OUT/'opening-credits.json',credit)
    cfg=config(True)
    cfg.update(models=[MODEL],provider_order={},budget_usd=cap,stop_new_requests_usd=cap)
    cfg['model_price_caps'][MODEL]={'prompt':.2,'completion':.8}
    api=StreamingOpenRouter(cfg,Ledger(OUT/'budget.sqlite3',cap,cap))
    api.RATE_LIMIT_TRIES=1
    pkg=read(TRIAL/'reference.json')
    def one(task):
        folder=OUT/'candidates/reference'/task/'first'
        if (folder/'record.json').exists():
            return read(folder/'record.json')
        rec={'task':task,'response':False,'valid':False}
        prompt=read(OUT/'prompts'/(task+'.json'))
        try:
            if datetime.now(timezone.utc)>=END:
                raise BudgetStop('Deadline')
            raw=api.call(MODEL,prompt,folder/'call','reference-first',max_tokens=8192,seed=20261123)
            rec['response']=True
            obj=parse_json(raw)
            rendered=render('reference',pkg,obj)
            write_files(folder/'page',rendered)
            rec.update(valid=True,equals_empty_example=obj==EXAMPLE,files_sha256=source_files(folder/'page'))
        except (ProviderError,BudgetStop,ValueError,KeyError,TypeError) as e:
            rec['error']=str(e)[:1200]
        dump(folder/'record.json',rec)
        return rec
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(one,TASKS))
    dump(OUT/'generation-complete.json',{'frozen_utc':now(),'freeze_sha256':sha(OUT/'freeze.json'),
                 'rows':rows,'files_sha256':file_hashes(p for p in (OUT/'candidates').rglob('*') if p.is_file())})


def score():
    frozen=read(OUT/'freeze.json')
    verify(frozen['inputs_sha256'])
    gen=read(OUT/'generation-complete.json')
    verify(gen['files_sha256'])
    assert gen['freeze_sha256']==sha(OUT/'freeze.json')
    browser_jobs.OUT=OUT
    browser_jobs.RUNTIME[RUNTIME_KEY]=RUNTIME/'node_modules'
    def one(rec):
        task=rec['task']
        base=OUT/'candidates/reference'/task/'first'
        result={'response':rec['response'],'valid':rec['valid'],
                'equals_empty_example':rec.get('equals_empty_example'),
                'passed':False if rec['response'] else None,'official_report_sha256':None}
        if (base/'call/request.json').exists():
            req=read(base/'call/request.json')
            assert req['body']['messages']==read(OUT/'prompts'/(task+'.json')) and req['body']['model']==MODEL
        if rec['valid']:
            grade=browser_jobs.grade(task,{'harness':HARNESS,'runtime':RUNTIME_KEY,'specs':browser_jobs.current_task_specs(task),
                           'files':rec['files_sha256'],'page':str((base/'page').relative_to(ROOT))})
            assert set(grade['tests'])=={task} and grade['report_sha256']==sha(OUT/'scores'/task/'report.json')
            result.update(passed=grade['all_passed'],official_report_sha256=grade['report_sha256'])
        return task,result
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=dict(pool.map(one,gen['rows']))
    dump(OUT/'scores-complete.json',{'completed_utc':now(),'rows':rows})


def summary(targets):
    vals={tag:{t:targets[t][tag]['passed'] for t in TASKS} for tag in ('original','appended','empty_plan','reference_full')}
    observed=[t for t in TASKS if all(vals[k][t] is not None for k in vals)]
    return {'shared_observed_targets':observed,'common_count':len(observed),
            'valid_pages':{k:sum(targets[t][k]['valid'] for t in observed) for k in ('original','appended')},
            'current_passes':{k:sum(vals[k][t] for t in observed) for k in vals},
            'appended_equals_empty_example':sum(targets[t]['appended']['equals_empty_example'] is True for t in observed),
            'paired_appended_vs':{k:paired(vals['appended'],vals[k],TASKS) for k in ('original','empty_plan','reference_full')}}


def report(check):
    if check:
        value=read(DEST)
    else:
        original=read(BASELINE)
        control=read(CONTROL)
        rows=read(OUT/'scores-complete.json')['rows']
        targets={t:{'original':original['targets'][t]['reference']['first'],'appended':rows[t],
                    'empty_plan':control['targets'][t]['empty_plan'],'reference_full':control['targets'][t]['reference_full']} for t in TASKS}
        value={'study':'expression-editor-interface-examples-20261123','exploratory':True,'project':'expression-editor',
               'model':MODEL,'frozen_utc':read(OUT/'freeze.json')['frozen_utc'],'prepared_after_format_failures':True,
               'source_selection':'same reference library','intervention':'Append unchanged schema and one valid empty plan example.',
               'planned_targets':len(TASKS),'targets':targets,'summary':summary(targets),'ledger':totals(OUT/'budget.sqlite3'),
               'audit_sha256':{'freeze':sha(OUT/'freeze.json'),'generated':sha(OUT/'generation-complete.json'),
                      'scores':sha(OUT/'scores-complete.json'),'primary':sha(BASELINE),'fixed_control':sha(CONTROL)}}
    assert tuple(value['targets'])==TASKS and summary(value['targets'])==value['summary']
    assert value['ledger']['exposure_usd']<=value['ledger']['cap_usd']<=MAX_CAP
    if not check:
        if DEST.exists() and read(DEST)!=value:
            raise SystemExit('Preserve prior result')
        dump(DEST,value)
    print(value['summary'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('freeze','generate','score','report','check-public'))
    parser.add_argument('--cap-usd',type=float)
    args=parser.parse_args()
    if args.phase=='generate':
        generate(args.cap_usd)
    elif args.phase in ('report','check-public'):
        report(args.phase=='check-public')
    else:
        (freeze if args.phase=='freeze' else score)()
