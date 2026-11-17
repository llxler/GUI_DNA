"""Separate budgeted construction and generation; hidden scores come afterward."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from gui_dna.budget import Ledger,BudgetStop
from gui_dna.provider import ProviderError,parse_json
from test.streaming_provider_v2 import StreamingOpenRouter
from test.review_stage import freeze
from test.ledger_read import calls
from .core import *


def now():return datetime.now(timezone.utc).isoformat()


def verify():
    frozen=json.loads((CALIBRATION/'frozen.json').read_text())
    for path,sha in frozen['sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    assert json.loads((CALIBRATION/'complete.json').read_text())['all_expectations_met']
    return frozen


def feedback_text(build,feedback):
    return ('Public development/compiler feedback:\n' if build else 'Public format/compiler/load feedback (no target behavior tests):\n')+'\n'.join(feedback)+'\nReturn the complete corrected JSON object.'


def attempt_loop(client,out,folder,record,initial,build,package=None,resume=False):
    target_path=folder/'record.json'
    if target_path.exists():
        record=json.loads(target_path.read_text())
        assert json.loads((folder/'messages.json').read_text())==initial
        if record['status'] in ('complete','frozen','frozen_development_failed','failed'):return record
        if not resume:return record
        messages=list(initial)
        for attempt in record['attempts']:
            raw=json.loads((folder/f'output-{attempt["attempt"]}.json').read_text())['text']
            messages += [{'role':'assistant','content':raw},{'role':'user','content':feedback_text(build,attempt['feedback'])}]
        lost=folder/f'call-{len(record["attempts"])}'
        if lost.exists():
            settled={r['id'] for r in calls(out/'budget.sqlite3') if r['actual'] is not None}
            for p in lost.rglob('request.json'):
                request=json.loads(p.read_text())
                assert request['call_id'] not in settled and request['body']['messages']==messages
            dest=out/'discarded-transport'/folder.relative_to(out)/now().replace(':','-')
            dest.mkdir(parents=True);shutil.copy2(target_path,dest/'record.json');shutil.move(str(lost),str(dest/lost.name))
    else:
        messages=list(initial);dump(folder/'messages.json',initial)
    record.update(status='in_progress');record.pop('error',None);dump(target_path,record)
    for attempt in range(len(record['attempts']),3):
        # A time ceiling is an admission rule; already in-flight calls retain their reservations.
        if datetime.now(timezone.utc)>=datetime.fromisoformat('2026-11-15T06:40:00+00:00'):
            record.update(status='time_incomplete');dump(target_path,record);return record
        try:
            raw=client.call(record['builder'] if build else record['model'],messages,folder/f'call-{attempt}',
                'interaction-transfer-build' if build else 'interaction-transfer-'+record['method'],seed=SEED)
        except BudgetStop as error:
            record.update(status='budget_incomplete',error=str(error));dump(target_path,record);raise
        except ProviderError as error:
            record.update(status='transport_incomplete',error=str(error));dump(target_path,record);return record
        dump(folder/f'output-{attempt}.json',{'text':raw})
        try:
            parsed=parse_json(raw)
            if build:
                feedback,reports=validate_package(record['project'],parsed,folder/f'validation-{attempt}')
                dump(folder/f'package-{attempt}.json',parsed);dump(folder/'package.json',parsed)
                record.update(selected_attempt=attempt,package_sha256=digest(parsed),development_passes=sum(r['all_passed'] for r in reports.values()),development_total=3)
                record.setdefault('compilable_attempts',[]).append(attempt)
            else:
                files=validate_files(output_files(record['method'],package,parsed))
                version=f'version-{attempt}';write_files(folder/version,files)
                record['versions'].append(version)
                dump(folder/version/'source-manifest.json',{'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()},'output_sha256':digest(files)})
                feedback=public_check(folder/version)
        except (ValueError,KeyError,TypeError,AttributeError,TimeoutError,subprocess.TimeoutExpired) as error:
            feedback=[f'{type(error).__name__}: {error}'[:2400]]
        record['attempts'].append({'attempt':attempt,'feedback':feedback});dump(target_path,record)
        if not feedback:break
        messages += [{'role':'assistant','content':raw},{'role':'user','content':feedback_text(build,feedback)}]
    record['status']=('frozen' if record.get('development_passes')==3 else 'frozen_development_failed') if build and 'selected_attempt' in record else ('failed' if build else 'complete')
    dump(target_path,record)
    print(record['project'],record.get('builder'),record['condition'],record.get('model',''),record.get('method','build'),record['status'],'attempts',len(record['attempts']),flush=True)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['build','run']);parser.add_argument('--resume',action='store_true');parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();build=args.phase=='build';out=BUILD if build else RUN
    verify();assert not (RUN/'grading-started.json').exists()
    cfg=config(build);allocation=json.loads((ROOT/'artifacts/review-20261115/budget-plan.json').read_text())['stages'][out.name]
    assert allocation=={'cap':cfg['budget_usd'],'stop':cfg['stop_new_requests_usd']}
    extras=[CALIBRATION/'frozen.json']
    if not build:
        barrier=json.loads((BUILD/'build-complete.json').read_text());extras.append(BUILD/'build-complete.json')
        extras+=list((BUILD/'libraries').rglob('package.json'))+list((BUILD/'libraries').rglob('record.json'))
        assert all(digest(json.loads((BUILD/path/'record.json').read_text()))==sha for path,sha in barrier['records_by_path_sha256'].items())
    freeze(out,cfg,[str(p.relative_to(ROOT)) for p in frozen_sources()+extras],{'kind':args.phase,'projects':PROJECTS,'conditions':CONDITIONS,'deadline_utc':'2026-11-15T07:20:03+00:00','scope':'New specification-derived interaction diagnostic, not official benchmark scores.'})
    client=StreamingOpenRouter(cfg,Ledger(out/'budget.sqlite3',cfg['budget_usd'],cfg['stop_new_requests_usd']))
    jobs=[]
    for project in PROJECTS:
        if build:
            for builder in BUILDERS:
                for condition in CONDITIONS:
                    folder=out/'libraries'/project/slug(builder)/condition
                    record={'project':project,'builder':builder,'condition':condition,'attempts':[],'status':'in_progress'}
                    jobs.append((folder,record,builder_messages(project,condition),True,None))
        else:
            for model in PLANNERS:
                options=[(None,'none','free',None)]
                for builder in BUILDERS:
                    for condition in CONDITIONS:
                        library=BUILD/'libraries'/project/slug(builder)/condition
                        rec=json.loads((library/'record.json').read_text())
                        package=json.loads((library/'package.json').read_text()) if rec['status']!='failed' else None
                        if package is not None:assert digest(package)==rec['package_sha256']
                        options += [(builder,condition,method,package) for method in ('plan','free_lib')]
                for builder,condition,method,package in options:
                    folder=out/'runs'/project/(slug(builder) if builder else 'no_library')/condition/slug(model)/method
                    rec={'project':project,'builder':builder,'condition':condition,'model':model,'method':method,'task':'full-application','package_sha256':digest(package) if package else None,'attempts':[],'versions':[],'status':'in_progress'}
                    if builder and package is None:
                        rec.update(status='complete',unavailable_library=True)
                        if not (folder/'record.json').exists():
                            dump(folder/'messages.json',messages_for(project,method,package));dump(folder/'record.json',rec)
                    jobs.append((folder,rec,messages_for(project,method,package),False,package))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results=list(pool.map(lambda j:attempt_loop(client,out,*j,resume=args.resume),jobs))
    valid={'frozen','frozen_development_failed','failed'} if build else {'complete'}
    assert all(r['status'] in valid for r in results),'Incomplete transport/budget/time: do not begin hidden grading'
    dump(out/('build-complete.json' if build else 'generation-complete.json'),{'finished_utc':now(),'candidates':len(results),'records_sha256':digest(results),
        'records_by_path_sha256':{str(j[0].relative_to(out)):digest(r) for j,r in zip(jobs,results)},'transport_incomplete':0})


if __name__=='__main__':main()
