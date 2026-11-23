"""Construct isolated, schema-compatible table backends from the public brief."""
import concurrent.futures
import json
import os
import subprocess
import tempfile
from pathlib import Path

from studies.study_io import ROOT, dump, now, read, sha
from studies.table_library_sources import core
from studies.webbench_expand.core import validate_package

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/compatible-library-rebuild-20261123'
MODEL = 'gpt-6.2-astra'
ARMS = ('plain-1', 'contract-1', 'plain-2', 'contract-2')
COMMON = """Independently implement a reusable browser-native ES-module table behavior library behind the supplied, stable, closed configuration interface. All public requirements are listed below. Return only a JSON object with fields design (short string) and files (array of objects each having path and content, both strings). Deliver index.js and index.css (your additive CSS), plus reusable common/*.js modules. Do not output index.html. A supplied compiler preserves the exact public HTML and original CSS, appends your CSS, and imports a config module before loading your index.js; globalThis.APP_CONFIG is the raw plan, unspecified interaction flags default to enabled. Honor all schema choices, including explicitly false. Implementation must be project-generic across the listed targets: no target IDs, test access or test-specific dispatch. Do not use any tools or read any filesystem. Everything you may use is directly in this prompt. Provide complete code in your final response."""
PLAIN = "Implement the specified interaction behavior and make it configurable through the documented interface. Organize your implementation into reusable browser modules."
CONTRACT = """Start from the supplied live DOM and preserve its coordinates, contents and public roles. First derive one shared internal state contract (selection, anchor/focus, edit mode, gesture, model updates) and the ownership of mutations and rendering. Specify event precedence across independently wired controllers so one gesture cannot trigger competing behaviors. Work through the public precondition, input, observable postcondition and boundary for each capability before returning code. Implement the complete interaction paths in reusable modules. Reconcile interactions after DOM changes, including selection, header/body limits and control disablement."""
SCHEMA = {'type':'object','properties':{'design':{'type':'string'},'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}}},'required':['design','files'],'additionalProperties':False}
COMPILER = """function compile(plan, files) {
  const out = Object.assign({}, files);
  out['dna-plan.js'] = 'globalThis.APP_CONFIG = ' + JSON.stringify(plan) + ';';
  out['dna-library.js'] = out['index.js'];
  out['index.js'] = "import './dna-plan.js';\\nimport './dna-library.js';";
  return out;
}"""


def public_inputs():
    old = read(core.AI)
    return {'requirements': core.requirements('table'), 'starter': core.starter(),
            **{key: old[key] for key in ('plan_schema', 'plan_documentation', 'examples')}}


def build_package(response, public):
    files = {item['path']: item['content'] for item in response['files']}
    if len(files) != len(response['files']) or set(files) & {'index.html', 'dna-plan.js', 'dna-library.js'}:
        raise ValueError('Duplicate or reserved output path.')
    if not all(isinstance(files.get(k), str) for k in ('index.css','index.js')):
        raise ValueError('Missing library entry or stylesheet.')
    starter = public['starter']
    files = {**starter, **files, 'index.css': starter['index.css'] + '\n' + files['index.css']}
    return {**{key:public[key] for key in ('plan_schema','plan_documentation','examples')},
            'design':response['design'], 'compiler':COMPILER, 'files':files}


def generate(arm):
    folder = OUT / arm
    prompt = folder / 'prompt.txt'
    reply = folder / 'reply.json'
    status = {'status':'failed','started':now(), 'model':MODEL, 'effort':'medium'}
    env = os.environ.copy()
    # Use only local subscription authentication, with no API-key fallback.
    for k in ('OPENAI_API_KEY','OPENROUTER_API_KEY','OPENAI_BASE_URL'):
        env.pop(k, None)
    try:
        with tempfile.TemporaryDirectory(prefix='gui-library-blind-') as tmp, (folder/'events.jsonl').open('w') as log, (folder/'stderr.log').open('w') as err:
            cmd = ['codex','exec','--ephemeral','--ignore-user-config','--ignore-rules','--skip-git-repo-check','-C',tmp,'-s','read-only','-m',MODEL,'-c','model_reasoning_effort="medium"','--json','--output-schema',str(OUT/'response-schema.json'),'-o',str(reply),'-']
            proc = subprocess.run(cmd,input=prompt.read_text(),text=True,stdout=log,stderr=err,env=env,cwd=tmp,timeout=1100)
            if proc.returncode:
                raise ValueError(f'Codex exited {proc.returncode}')
        events = [json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines() if line.strip()]
        status['usage'] = [event.get('usage') for event in events if event['type']=='turn.completed']
        tools = [event['item']['type'] for event in events if isinstance(event.get('item'),dict) and event['item'].get('type') not in ('agent_message','reasoning','plan')]
        if tools or not status['usage']:
            raise ValueError(f'External item or missing usage: {tools}')
        package = build_package(read(reply),read(OUT/'public.json'))
        problems = validate_package(package,folder/'public-check')
        if problems:
            raise ValueError(str(problems))
        dump(folder/'package.json',package)
        status.update(status='accepted',package_sha256=sha(folder/'package.json'))
    except Exception as error:
        status['error']=f'{type(error).__name__}: {error}'
    status.update(finished=now(),prompt_sha256=sha(prompt))
    if reply.exists():
        status['reply_sha256']=sha(reply)
    dump(folder/'status.json',status)
    return arm,status


def main():
    if OUT.exists():
        raise SystemExit('This one-shot stage already exists.')
    auth = read(Path.home()/'.codex/auth.json')
    if auth.get('auth_mode') != 'chatgpt' or auth.get('OPENAI_API_KEY'):
        raise SystemExit('Subscription authentication required.')
    OUT.mkdir(parents=True)
    public=public_inputs()
    dump(OUT/'public.json',public)
    dump(OUT/'response-schema.json',SCHEMA)
    for arm in ARMS:
        folder=OUT/arm
        folder.mkdir()
        instruction = CONTRACT if arm.startswith('contract') else PLAIN
        (folder/'prompt.txt').write_text(COMMON+'\n'+instruction+'\n'+json.dumps(public,ensure_ascii=False))
    dump(OUT/'registered.json',{'registered':now(),'model':MODEL,'arms':list(ARMS),'public_sha256':sha(OUT/'public.json'),'response_schema_sha256':sha(OUT/'response-schema.json'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),'builder_sha256':sha(Path(__file__)),'prompt_sha256':{a:sha(OUT/a/'prompt.txt') for a in ARMS}})
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results=dict(executor.map(generate,ARMS))
    dump(OUT/'sealed.json',{'sealed':now(),'status':results,'registered_sha256':sha(OUT/'registered.json')})
    print({k:v['status'] for k,v in results.items()})


if __name__=='__main__':
    main()
