"""Preregister and run two independent subscription builds and target-matched controls."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from experiments.webapp1k_probe import REPO
from studies.todomvc_dna import domain

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'artifacts/public-library-transfer-extra-20261123'
DUO_MANIFEST = ROOT / 'artifacts/webapp1k-dna/manifest.json'
MODEL = 'gpt-6.2-astra'
ATTEMPTS = ('a', 'b')
GENERATOR_SETTINGS = {'model': MODEL, 'effort': 'medium', 'auth': 'chatgpt', 'sample': 1}
STRING = {'type': 'string'}
BOOL = {'type': 'boolean'}
DIRECT = 'Write a complete self-contained implementation for this current request. Follow the public interface. Output only a JSON object with a source string. '
PREFIX = 'Work only with this text. Do not use any tools or access files. Return a single JSON object conforming to the supplied schema.\n'
TODO_BUILD = """Build a reusable configurable TodoMVC state controller from the whole public specification. Do not assume a target task number. Expose one to six independent semantic Boolean controls. Give each a unique JavaScript identifier, a default, and a precise description explaining which interactions and views it controls. The host declares const DNA_CONFIG containing explicit booleans before your code in the same scope. Implement real candidate state, persistence, event and view transitions behind the fixed shell. Keep common behavior working across modes and feature interactions composable. Choose a first working example and return its enabled switch IDs (all others false). Source is plain browser JavaScript assigning window.candidate exactly as specified. No HTML or script tags, no tooling.\n"""
DUO_BUILD = """Build a reusable finite-menu library of independent self-contained React component implementations for this category. The input lists all public SINGLE-feature specifications available to this library. Future clients will select components by meaning. Choose your own unique simple JavaScript identifier for each component, state its behavior precisely, and provide each complete React module source (default export; imports may be react or react-router-dom). Preserve expected interaction, labels, fetch endpoints, state and failures. Name/describe actual user-facing functionality. Components must compose as siblings, receive forwarded props, and avoid unrelated text or controls that collide with siblings. The final host selects up to two component IDs in order. Provide a first working example containing one or two IDs. Do not write a target-combination lookup.\n"""
PLAN = 'Select one configuration to satisfy the current public request using the frozen library interface below. Output only the parameter object.\n'


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def array(items):
    return {'type': 'array', 'items': items}


TODO_SCHEMA = obj({'controls': array(obj({'id': STRING, 'behavior': STRING, 'default': BOOL})), 'source': STRING, 'example': array(STRING)})
DUO_SCHEMA = obj({'components': array(obj({'id': STRING, 'behavior': STRING, 'source': STRING})), 'example': array(STRING)})
DIRECT_SCHEMA = obj({'source': STRING})


def request(path, instruction, public, schema):
    if path.exists():
        raise FileExistsError(path)
    path.mkdir(parents=True)
    (path/'prompt.txt').write_text(PREFIX + instruction + json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    dump(path/'schema.json', schema)
    return dict(prompt_sha256=sha(path/'prompt.txt'), schema_sha256=sha(path/'schema.json'))


def register():
    if OUT.exists():
        raise FileExistsError(OUT)
    tasks = read(DUO_MANIFEST)['tasks']
    targets = {}
    builders = {}
    requests = {}
    builders['todomvc'] = {'spec': domain.SPEC, 'contract': domain.INTERFACE}
    for item in domain.tasks():
        targets[item['id']] = dict(group='todomvc', public={'contract': domain.INTERFACE, 'requirement': item['requirement']}, features=item['features'])
    for item in tasks:
        group = item['category']
        tier = 'tests' if item['kind'] == 'single' else 'duo_tests'
        path = REPO/tier/'react'/group/(item['name']+'.test.js')
        if item['kind'] == 'single':
            builders.setdefault(group, {})[item['name']] = path.read_text()
        else:
            targets[item['name']] = dict(group=group, public={'module': item['module'], 'jest': path.read_text()}, test=str(path.relative_to(ROOT)), test_sha256=sha(path))
    dump(OUT/'targets.json', targets)
    dump(OUT/'build-inputs.json', builders)
    for group, public in builders.items():
        todo = group == 'todomvc'
        for rep in ATTEMPTS:
            name = f'build/{group}/{rep}'
            requests[name] = request(OUT/name, TODO_BUILD if todo else DUO_BUILD, public, TODO_SCHEMA if todo else DUO_SCHEMA)
    for task, row in targets.items():
        suffix = 'Provide plain browser JavaScript assigning window.candidate. ' if row['group'] == 'todomvc' else 'Provide a single complete React default-export module. Only import react or react-router-dom. '
        name = f'direct/{task}'
        requests[name] = request(OUT/name, DIRECT+suffix, row['public'], DIRECT_SCHEMA)
    dump(OUT/'registered.json', {'registered': now(), 'settings': GENERATOR_SETTINGS, 'repetitions': list(ATTEMPTS), 'requests': requests,
                                 'target_sha256': sha(OUT/'targets.json'), 'input_sha256': sha(OUT/'build-inputs.json'), 'protocol_sha256': sha(HERE/'PROTOCOL.md'), 'generator_sha256': sha(Path(__file__)),
                                 'todo_shell_sha256': sha(domain.HERE/'shell.html'), 'todo_spec_sha256': sha(domain.HERE/'harness/demo-todo-app.spec.ts'), 'duo_manifest_sha256': sha(DUO_MANIFEST)})


def invoke(name):
    path = OUT/name
    if (path/'status.json').is_file():
        return read(path/'status.json')['status']
    if (path/'events.jsonl').exists():
        raise RuntimeError(f'Unresolved prior request {name}')
    auth = read(Path.home()/'.codex/auth.json')
    if auth.get('auth_mode') != 'chatgpt' or auth.get('OPENAI_API_KEY'):
        raise RuntimeError('Subscription authentication required')
    status = {'started': now(), 'status': 'failed', 'settings': GENERATOR_SETTINGS, 'prompt_sha256': sha(path/'prompt.txt'), 'schema_sha256': sha(path/'schema.json')}
    env = {k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_BASE_URL')}
    try:
        with tempfile.TemporaryDirectory(prefix='transfer-isolated-') as tmp, (path/'events.jsonl').open('x') as log, (path/'stderr.log').open('x') as err:
            cmd = ['codex','exec','--ephemeral','--ignore-user-config','--ignore-rules','--skip-git-repo-check','-C',tmp,'-s','read-only','-m',MODEL,'-c','model_reasoning_effort="medium"','--json','--output-schema',str(path/'schema.json'),'-o',str(path/'reply.json'),'-']
            subprocess.run(cmd, input=(path/'prompt.txt').read_text(), text=True, env=env, cwd=tmp, stdout=log, stderr=err, timeout=690, check=True)
        events = [json.loads(line) for line in (path/'events.jsonl').read_text().splitlines() if line]
        sessions = [e['thread_id'] for e in events if e['type']=='thread.started']
        usage = [e['usage'] for e in events if e['type']=='turn.completed']
        tools = [e['item']['type'] for e in events if isinstance(e.get('item'),dict) and e['item']['type'] not in ('agent_message','reasoning','plan')]
        if len(sessions)!=1 or len(usage)!=1 or tools:
            raise ValueError('Unexpected session, usage or tool events')
        read(path/'reply.json')
        status.update(status='returned', session=sessions[0], usage=usage[0], reply_sha256=sha(path/'reply.json'))
    except Exception as err:
        status['error'] = f'{type(err).__name__}: {err}'
    status['finished'] = now()
    dump(path/'status.json',status)
    print(name,status['status'],flush=True)
    return status['status']


def interface(group, value):
    todo = group == 'todomvc'
    entries = value['controls' if todo else 'components']
    keys = [e['id'] for e in entries]
    first = value['example']
    if len(keys) != len(set(keys)) or not keys or (todo and len(keys)>6) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', k) or k=='NONE' for k in keys):
        raise ValueError('Invalid library interface')
    if (not todo and not 1<=len(first)<=2) or len(first)!=len(set(first)) or set(first)-set(keys):
        raise ValueError('Invalid first example')
    if any(not e['behavior'].strip() for e in entries):
        raise ValueError('Empty documentation')
    if todo:
        if any(type(e['default']) is not bool for e in entries) or not value['source'].strip():
            raise ValueError('Missing TodoMVC defaults or implementation')
        schema = obj({k: BOOL for k in keys})
        example = {k: k in first for k in keys}
    else:
        if any(not e['source'].strip() for e in entries):
            raise ValueError('Empty component')
        choice = {'type':'string','enum':['NONE',*keys]}
        schema = obj({'first':choice,'second':choice})
        example = dict(first=first[0],second=first[1] if len(first)==2 else 'NONE')
    docs = [{k:v for k,v in e.items() if k!='source'} for e in entries]
    return dict(schema=schema, menu=docs, first=example)


def plan_prompts():
    if (OUT/'plans-registered.json').exists():
        return
    requests = {}
    targets = read(OUT/'targets.json')
    interfaces = {}
    for group in read(OUT/'build-inputs.json'):
        for rep in ATTEMPTS:
            path = OUT/'build'/group/rep
            status = read(path/'status.json')
            try:
                if status['status']!='returned':
                    raise ValueError('No library reply')
                menu = interface(group,read(path/'reply.json'))
                for task, row in targets.items():
                    if row['group']==group:
                        name=f'plan/{rep}/{task}'
                        requests[name]=request(OUT/name,PLAN,dict(current=row['public'], library=menu),menu['schema'])
                interfaces[f'{group}/{rep}']=dict(status='accepted', menu=menu, reply_sha256=status['reply_sha256'])
            except ValueError as err:
                interfaces[f'{group}/{rep}']=dict(status='invalid', reason=str(err))
    dump(OUT/'plans-registered.json',dict(registered=now(), requests=requests, interfaces=interfaces, initial_sha256=sha(OUT/'registered.json')))


def generate(workers):
    initial=read(OUT/'registered.json')['requests']
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(invoke,[n for n in initial if n.startswith('build/')]))
        plan_prompts()
        names=[n for n in initial if n.startswith('direct/')]
        names.extend(read(OUT/'plans-registered.json')['requests'])
        list(pool.map(invoke,names))
    if not (OUT/'sealed.json').exists():
        calls={str(p.parent.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('status.json'))}
        dump(OUT/'sealed.json',dict(sealed=now(), registered_sha256=sha(OUT/'registered.json'), plan_sha256=sha(OUT/'plans-registered.json'), calls=calls))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['register','generate'])
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    register() if args.phase=='register' else generate(args.workers)
