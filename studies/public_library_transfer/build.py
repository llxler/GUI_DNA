"""Admit the first public-valid package; retain every raw build response."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

from gui_dna.budget import Ledger
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.webbench_expand.core import config
from . import core as c

CAPS={'gpt5':6,'claude':7}
END=datetime.fromisoformat('2026-11-23T09:24:00+00:00')


def subscribe(messages, folder):
    env={k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY','OPENROUTER_API_KEY','OPENAI_BASE_URL')}
    with tempfile.TemporaryDirectory(prefix='dna-public-build-') as cwd:
        cmd=['codex','exec','--ephemeral','--ignore-user-config','--ignore-rules','--skip-git-repo-check',
             '-C',cwd,'-s','read-only','-m',c.BUILDERS['codex-1'],'-c','model_reasoning_effort="medium"',
             '--json','--output-schema',str(c.OUT/'response-schema.json'),'-o',str(folder/'reply.json'),'-']
        with (folder/'events.jsonl').open('w') as out,(folder/'stderr.log').open('w') as err:
            subprocess.run(cmd,cwd=cwd,env=env,input=json.dumps(messages,ensure_ascii=False),text=True,
                           stdout=out,stderr=err,timeout=1200,check=True)
    events=[json.loads(s) for s in (folder/'events.jsonl').read_text().splitlines()]
    calls=[e['item']['type'] for e in events if isinstance(e.get('item'),dict) and e['item']['type'] not in ('agent_message','reasoning','plan')]
    if calls or sum(e['type']=='turn.completed' for e in events)!=1: raise RuntimeError('Unexpected tool event or missing terminal usage')
    return (folder/'reply.json').read_text()


def registration():
    c.register()
    c.save(c.OUT/'response-schema.json',c.SCHEMA)
    validate_sources=[c.HERE/name for name in ('core.py','build.py','local.py','PROTOCOL.md')]
    validate_sources.extend([c.ROOT/'studies/schema_constrained_table/generate.py',c.ROOT/'studies/streaming_provider_v2.py'])
    inputs=[c.OUT/'inputs'/f'{p}.json' for p in c.PROJECTS]
    contract={'projects':list(c.PROJECTS),'builders':c.BUILDERS,'budget':CAPS,'deadline':END.isoformat(),
              'sources':{str(p.relative_to(c.ROOT)):c.sha(p) for p in validate_sources+inputs}}
    path=c.OUT/'registered.json'
    if path.exists():
        if c.read(path)['contract']!=contract: raise RuntimeError('Registered source changed')
    else: c.save(path,{'created':c.now(),'contract':contract})


def execute(job,clients):
    project,tag=job
    from .browser import public_load
    folder=c.OUT/'builds'/project/tag
    if (folder/'status.json').exists(): return
    data=c.read(c.OUT/'inputs'/f'{project}.json')
    messages=c.build_messages(data)
    status={'project':project,'builder':c.BUILDERS[tag],'rep':2 if tag=='codex-2' else 1,'attempts':[]}
    for n in range(2):
        d=folder/f'attempt-{n+1}'
        c.save(d/'messages.json',messages)
        try:
            if (d/'raw.json').exists(): raw=c.read(d/'raw.json')['text']
            elif tag in CAPS:
                if datetime.now(timezone.utc)>=END: raise RuntimeError('Submission deadline')
                raw=clients[tag].call(c.BUILDERS[tag],messages,d/'provider',f'{project}/{tag}/{n+1}',max_tokens=21000,seed=20261123+n)
            else: raw=subscribe(messages,d)
            c.save(d/'raw.json',{'text':raw})
        except Exception as e:
            status.update(status='missing',reason=f'{type(e).__name__}: {e}')
            break
        try:
            pkg=c.package(data,c.parse(raw))
            for key,plan in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=d/'check'/key
                c.materialize(project,pkg,plan,page)
                errors=public_load(project,page)
                c.save(d/(key+'-load.json'),errors)
                if errors: raise ValueError(str(errors)[:1600])
            c.save(folder/'package.json',pkg)
            status['attempts'].append({'attempt':n+1,'valid':True})
            status.update(status='valid',package_sha256=c.sha(folder/'package.json'))
            break
        except (ValueError,KeyError,TypeError,IndexError) as e:
            reason=f'{type(e).__name__}: {e}'
            status['attempts'].append({'attempt':n+1,'valid':False,'public_error':reason[:1600]})
            status.update(status='build_failed')
            messages=c.build_messages(data)+[{'role':'assistant','content':raw[:65000]},
                {'role':'user','content':'The public load/format check reported '+reason[:1600]+'. Return a complete replacement JSON package.'}]
    c.save(folder/'status.json',dict(status,finished=c.now()))
    print(project,tag,status['status'],flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',choices=['api','subscription','register'])
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    registration()
    if args.source=='register': return
    clients={}
    if args.source=='api':
        for tag,cap in CAPS.items():
            model=c.BUILDERS[tag]
            cfg=config(True)
            cfg.update(models=[model],provider_order={},budget_usd=cap,stop_new_requests_usd=cap)
            cfg['reasoning_effort']['openai/gpt-5']='low'
            engine=StreamingOpenRouter(cfg,Ledger(c.OUT/f'{tag}-budget.sqlite3',cap,cap))
            engine.RATE_LIMIT_TRIES=1
            clients[tag]=engine
        tags=list(CAPS)
    else:
        auth=c.read(Path.home()/'.codex/auth.json')
        if auth.get('auth_mode')!='chatgpt' or auth.get('OPENAI_API_KEY'): raise RuntimeError('Subscription authentication required')
        tags=['codex-1','codex-2']
    from .browser import lock
    with lock(c.OUT/f'{args.source}.lock'),ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[(p,tag) for p in c.PROJECTS for tag in tags]
        list(pool.map(lambda job:execute(job,clients),jobs))


if __name__=='__main__': main()
