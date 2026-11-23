"""Public inputs, model-facing prompts and deterministic page assembly."""
import html
import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

from studies.study_io import ROOT, UPSTREAM, now, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/public-library-transfer-20261123'
PROJECTS = ('dom1','form','calculator','table','bom','svg-chart','draw','canvas','flex','expression-editor')
BUILDERS = {'gpt5': 'openai/gpt-5', 'claude': 'anthropic/claude-sonnet-4.5',
            'codex-1': 'gpt-6.2-astra', 'codex-2': 'gpt-6.2-astra'}
MODEL = 'Qwen/Qwen2.5-0.5B-Instruct'
LIMIT = 2048


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if path.exists():
        if path.read_text() != raw:
            raise ValueError(f'Refusing to replace evidence: {path}')
        return
    tmp = path.with_suffix('.writing')
    tmp.write_text(raw)
    tmp.replace(path)


def public_input(project):
    source = UPSTREAM/'projects'/project
    if (source/'tasks.jsonl').exists():
        rows = [json.loads(line) for line in (source/'tasks.jsonl').read_text().splitlines() if line.strip()]
    else:
        raw = subprocess.check_output(['/usr/bin/python3','-c',
            'import sys,yaml,json;print(json.dumps(yaml.safe_load(sys.stdin),default=str))'],
            input=(source/'tasks.yml').read_bytes())
        rows = json.loads(raw)
    init = next((r['description'] for r in rows if r['id']=='init'), '')
    tasks = [{'id':r['id'],'description':r['description']} for r in rows if re.fullmatch(r'task-\d+',r['id'])]
    assert [r['id'] for r in tasks] == [f'task-{i}' for i in range(1,21)]
    starter = {p.relative_to(source/'src-init').as_posix():p.read_text() for p in sorted((source/'src-init').rglob('*')) if p.is_file()}
    assets = {}
    for p in sorted((source/'assets').rglob('*')):
        if p.is_file():
            record = {'sha256':sha(p),'bytes':p.stat().st_size}
            if p.suffix in ('.js','.svg','.json','.css','.txt'):
                record['text'] = p.read_text()
            assets[p.relative_to(source).as_posix()] = record
    return dict(project=project,starter=starter,assets=assets,init=init,requirements=tasks)


def obj(props):
    return dict(type='object',properties=props,required=list(props),additionalProperties=False)


def array(items):
    return {'type':'array','items':items}


S = {'type':'string'}
FILE = obj({'path':S,'content':S})
CONTROL = obj({'id':S,'behavior':S,'type':{'type':'string','enum':['boolean','enum']},
               'values':array(S),'default':S,'example':S})
SCHEMA = obj({'design':S,'controls':array(CONTROL),'anchor':S,'fragment':S,'css':S,'script':S,'files':array(FILE)})
BUILD = """Design a reusable GUI behavior library for this public Web-Bench project. Implement the public user interactions, observed DOM names, state and event transitions precisely. First check the provided starter markup and asset contracts. You choose one to six independent, semantic controls, especially incompatible states where requirements change. Each control id matches [a-z][a-z0-9-]*, describes its effect, has a boolean (empty values, default/example spelled true or false) or finite enum (2-8 distinct simple strings) domain. Both settings must work. Choose defaults and a first documented example in advance. No task-number switches, task dispatch, per-target page tables or executable plan payloads. Do not use tools or outside files.
Your package has design, controls, anchor, fragment, css, script, files. The deterministic assembler preserves the public starter HTML. It optionally inserts your static fragment immediately AFTER the unique exact literal anchor in the starter HTML (use empty strings for no fragment). It adds CSS to the head and classic script at body end. On the html element it sets data-dna-<id> attributes containing string values; before any module runs it also sets globalThis.APP_CONFIG (boolean or string fields), except on the CSS-only flex project. For example use html[data-dna-mode="compact"]. No backend, dependencies or network. Files is a list of {path,content} for new/updated local modules or styles (no index.html or mounted assets). Preserve starter dependencies. For a single-file brief put all code in the HTML fragment/style/script injection. For CSS-only flex use only markup and CSS. For draw and svg-chart the server supports Vite and SCSS. Implement real behavior for the received requirements. Return one JSON object matching the supplied schema with complete, concise code."""


def messages(system, user):
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(user,ensure_ascii=False)}]


def build_messages(data):
    return messages(BUILD, {'output_schema':SCHEMA,'public_project':data})


def prefix(data, task):
    if not 1 <= task <= len(data['requirements']):
        raise ValueError('Invalid target')
    return {**data,'requirements':data['requirements'][:task]}


def direct_messages(data, task):
    return messages('Build the working website for the final public request in this sequence, including its prerequisites. Start from the public starter. Use local browser code and mounted assets only. Return a single JSON object {"files":[{"path":"index.html","content":"complete file"}, ...]} with complete replacements/additions; untouched starter files remain. Do not use tools. For CSS-only flex use markup and CSS. Vite and SCSS are available for draw and svg-chart.', prefix(data,task))


def plan_messages(data, task, package):
    return messages('Select the semantic configuration that implements the final public request given its prerequisites. Return just one JSON configuration with all listed fields. Read the behavior of each option and resolve conflicts in favor of the current request. Use no tools.',{'public_project':prefix(data,task),'design':package['design'],'schema':package['plan_schema'],'documentation':package['plan_documentation'],'first_example':package['examples'][0]})


def files_map(entries):
    if not isinstance(entries,list) or len(entries)>128:
        raise ValueError('Expected a list of at most 128 files')
    result={}
    for entry in entries:
        name,content=entry['path'],entry['content']
        path=PurePosixPath(name)
        if (not isinstance(content,str) or not name or path.is_absolute() or path.as_posix()!=name or
            any(p.startswith('.') or p in ('assets','node_modules') for p in path.parts) or
            re.search(r'[^A-Za-z0-9_./-]',name) or name in result or path.suffix not in
            ('.html','.js','.mjs','.css','.scss','.svg','.json') or name.endswith('package.json')):
            raise ValueError(f'Unsupported website file: {name!r}')
        result[name]=content
    return result


def package(data, raw):
    controls=raw['controls']
    if not isinstance(controls,list) or not 1<=len(controls)<=6:
        raise ValueError('Expected 1-6 semantic controls')
    props,defaults,example={}, {}, {}
    for c in controls:
        key=c['id']
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}',key) or key in props or not c['behavior'].strip():
            raise ValueError('Expected a unique lowercase semantic id and behavior')
        if c['type']=='boolean' and c['values']==[]:
            vals={'true':True,'false':False}
            sch={'type':'boolean'}
        elif c['type']=='enum' and 2<=len(c['values'])<=8 and len(set(c['values']))==len(c['values']):
            vals={v:v for v in c['values'] if re.fullmatch('[A-Za-z0-9_-]{1,48}',v)}
            if len(vals)!=len(c['values']): raise ValueError('Invalid enum value')
            sch={'type':'string','enum':c['values']}
        else:
            raise ValueError('Invalid control type/domain')
        if c['default'] not in vals or c['example'] not in vals:
            raise ValueError('Default/example outside control domain')
        props[key],defaults[key],example[key]=sch,vals[c['default']],vals[c['example']]
    files=files_map(raw['files'])
    if 'index.html' in files: raise ValueError('index.html is assembled from the public starter')
    if raw['fragment'] and (not raw['anchor'] or data['starter']['index.html'].count(raw['anchor'])!=1):
        raise ValueError('Fragment anchor must occur exactly once in starter index.html')
    if data['project']=='flex' and (raw['script'].strip() or any(k.endswith(('.js','.mjs')) for k in files)):
        raise ValueError('CSS-only flex project')
    return {k:raw[k] for k in ('design','controls','anchor','fragment','css','script')} | {
        'files':files, 'plan_schema':obj(props), 'defaults':defaults,
        'plan_documentation':'\n'.join(f"{c['id']} (default {c['default']}): {c['behavior']}" for c in controls),
        'examples':[{'description':'First public configuration','plan':example}]}


def emit(project, source, target):
    target=Path(target)
    for name,content in source.items():
        p=target/name
        p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists() and p.read_text()!=content: raise ValueError('Candidate changed')
        p.write_text(content)
    assets=UPSTREAM/'projects'/project/'assets'
    if assets.is_dir(): shutil.copytree(assets,target/'assets',dirs_exist_ok=True)
    return {p.relative_to(target).as_posix():sha(p) for p in sorted(target.rglob('*')) if p.is_file()}


def materialize(project, pkg, plan, dest):
    props=pkg['plan_schema']['properties']
    if not isinstance(plan,dict) or set(plan)!=set(props): raise ValueError('Plan fields differ from schema')
    for k,sch in props.items():
        if (sch['type']=='boolean' and type(plan[k])!=bool) or (sch['type']=='string' and plan[k] not in sch['enum']):
            raise ValueError('Plan value outside domain')
    public=read(OUT/'inputs'/f'{project}.json')
    files=public['starter'] | pkg['files']
    index=files['index.html']
    if pkg['fragment']: index=index.replace(pkg['anchor'],pkg['anchor']+pkg['fragment'],1)
    attrs=''.join(' data-dna-'+k+'="'+html.escape(str(v).lower() if type(v)==bool else str(v),quote=True)+'"' for k,v in plan.items())
    index,n=re.subn(r'<html\b',lambda _: '<html'+attrs,index,1,flags=re.I)
    if not n: index='<html'+attrs+'>'+index+'</html>'
    config='' if project=='flex' else '<script>globalThis.APP_CONFIG='+json.dumps(plan)+';</script>'
    index,n=re.subn(r'(<head\b[^>]*>)',lambda m:m[0]+config,index,1,flags=re.I)
    if not n: index=index.replace('>','><head>'+config+'</head>',1)
    index=re.sub(r'</head\s*>',lambda _: '<style>'+pkg['css']+'</style></head>',index,1,flags=re.I)
    if pkg['script']:
        index=re.sub(r'</body\s*>',lambda _: '<script>'+pkg['script']+'</script></body>',index,1,flags=re.I)
    return emit(project,files | {'index.html':index},dest)


def materialize_direct(project, public, value, dest):
    changes=files_map(value['files'])
    if not changes: raise ValueError('Empty implementation')
    return emit(project,public['starter'] | changes,dest)


def parse(text):
    raw=text.strip()
    if raw.startswith('```'):
        raw=re.sub(r'^\x60{3}(?:json)?\s*','',raw,flags=re.I)
        raw=re.sub(r'\s*\x60{3}$','',raw)
    return json.loads(raw)


def register():
    for p in PROJECTS: save(OUT/'inputs'/f'{p}.json',public_input(p))


if __name__=='__main__':
    register()
