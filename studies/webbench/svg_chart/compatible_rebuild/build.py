"""Independently build two schema-compatible SVG libraries from the same public brief."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import tempfile

from studies.compatible_library_rebuild.build import MODEL, SCHEMA
from studies.interface_blind.core import compile_plan, validate_files
from studies.library_refinement_chart import adapter
from studies.library_refinement_chart.environment import setup
from studies.study_io import ROOT, dump, now, read, sha
from studies.webbench_draw.browser import public_check

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/compatible-chart-rebuild-20261123'
RUNTIME = adapter.OUT / 'replays/compatible-chart-rebuild-20261123'
NAMES = ('old_gpt5', 'contract_1', 'contract_2')
PROMPT = '''Design and implement a reusable native SVG chart behavior library for the supplied public project. Work only from this input. Do not use any tools, filesystem or network. Two independent artifacts are supplied: the public starter/assets/requirements, and a previously published data-only configuration interface with two examples. Implement the complete public behavior range behind this exact interface. Preserve semantic public module contracts and browser-observable geometry, delegation, event and update semantics. Derive a shared configuration/geometry/state contract for chart subtypes; track axis, grid, legend, label and series visibility, coordinate boundaries and legend/input transitions with correct event ownership. Resolve later public requirements when they supersede earlier ones and expose the documented configuration choices. The original starter index.html is immutable. A pure compiler inserts globalThis.__chartPlan into its head, then the original index.js module entry runs. The starter files otherwise persist unless you supply replacements. All public assets are mounted unchanged under assets/. Vite supports ES modules and SCSS. Use no external packages, no test-specific logic or target IDs. Provide a real complete implementation with reusable components: output only JSON {"design":string,"files":[{"path":string,"content":string},...]}. Return index.js, index.scss and the component source files. Do not return index.html or assets/.'''
COMPILER = '''function compile(plan, files) {
  const out = { ...files };
  const json = JSON.stringify(plan).replace(/</g, '\\\\u003c');
  out['index.html'] = out['index.html'].replace(/<head>/i, () => '<head><script>globalThis.__chartPlan = ' + json + ';</script>');
  return out;
}'''


def package(response, public):
    files = {f['path']: f['content'] for f in response['files']}
    if len(files) != len(response['files']) or 'index.html' in files or any(n.startswith('assets/') for n in files):
        raise ValueError('Duplicate or reserved output path')
    if not {'index.js', 'index.scss'} <= files.keys():
        raise ValueError('Missing library entry point or stylesheet')
    validate_files(files)
    return {'design': response['design'], 'compiler': COMPILER, 'files': public['starter'] | files,
            'plan_schema': public['plan_schema'], 'examples': public['examples']}


def generate(name):
    folder = OUT / name
    env = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_BASE_URL'):
        env.pop(key, None)
    state = {'started': now(), 'status': 'failed', 'model': MODEL, 'effort': 'medium'}
    try:
        with tempfile.TemporaryDirectory(prefix='gui-chart-blind-') as tmp, (folder/'events.jsonl').open('w') as log, (folder/'stderr.log').open('w') as err:
            cmd = ['codex','exec','--ephemeral','--ignore-user-config','--ignore-rules','--skip-git-repo-check','-C',tmp,'-s','read-only','-m',MODEL,'-c','model_reasoning_effort="medium"','--json','--output-schema',str(OUT/'response-schema.json'),'-o',str(folder/'reply.json'),'-']
            proc = subprocess.run(cmd, input=(OUT/'prompt.txt').read_text(), text=True, stdout=log, stderr=err, env=env, cwd=tmp, timeout=1000)
            if proc.returncode:
                raise ValueError(f'Codex exited {proc.returncode}')
        events = [json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines() if line.strip()]
        attempts = [e for e in events if e['type'] == 'turn.completed']
        state['usage'] = [e['usage'] for e in attempts]
        actions = [e['item']['type'] for e in events if isinstance(e.get('item'), dict) and e['item']['type'] not in ('reasoning','agent_message','plan')]
        if actions or len(attempts) != 1:
            raise ValueError(f'External tool items or unexpected turn count: {actions}')
        pkg = package(read(folder/'reply.json'), read(OUT/'public.json'))
        for i, ex in enumerate(pkg['examples']):
            data = compile_plan(pkg, ex['plan'])
            assert data == compile_plan(pkg, ex['plan'])
            dest = RUNTIME/'public-validation'/name/f'example-{i+1}'
            adapter.materialize(dest, data)
            issues = public_check(dest)
            if issues:
                raise ValueError(str(issues)[:900])
        dump(folder/'package.json', pkg)
        state.update(status='accepted', package_sha256=sha(folder/'package.json'))
    except Exception as exc:
        state['error'] = f'{type(exc).__name__}: {exc}'
    state['finished'] = now()
    state['evidence'] = {f: sha(folder/f) for f in ('events.jsonl','stderr.log','reply.json') if (folder/f).exists()}
    dump(folder/'status.json', state)
    return name, state


def main():
    if OUT.exists():
        raise SystemExit('One-shot build has already started')
    auth = read(Path.home()/'.codex/auth.json')
    if auth.get('auth_mode') != 'chatgpt' or auth.get('OPENAI_API_KEY'):
        raise ValueError('ChatGPT subscription authentication required')
    setup(RUNTIME)
    OUT.mkdir(parents=True)
    old = adapter.old_package()
    rows, starter, assets = adapter.public_inputs()
    public = {'requirements': rows, 'assets': assets, 'starter': starter,
              'plan_schema': old['plan_schema'], 'examples': old['examples']}
    dump(OUT/'public.json', public)
    dump(OUT/'response-schema.json', SCHEMA)
    (OUT/'prompt.txt').write_text(PROMPT+'\n'+json.dumps(public, ensure_ascii=False))
    for name in NAMES:
        (OUT/name).mkdir()
    dump(OUT/NAMES[0]/'package.json', old)
    sources = [HERE/'PROTOCOL.md', Path(__file__), OUT/'public.json', OUT/'prompt.txt', OUT/'response-schema.json', OUT/NAMES[0]/'package.json',
               ROOT/'studies/svg_chart_compact_local/run.py', ROOT/'artifacts/svg-chart-compact-local-20261123/freeze.json', Path(adapter.__file__)]
    registered = {'utc': now(), 'model': MODEL, 'arms': list(NAMES), 'effort': 'medium', 'prompt_files': {n:'prompt.txt' for n in NAMES[1:]},
                  'sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources}}
    dump(OUT/'registered.json', registered)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        states = dict(pool.map(generate, NAMES[1:]))
    dump(OUT/'sealed.json', {'utc': now(), 'registered_sha256': sha(OUT/'registered.json'), 'states': states})
    print({n:s['status'] for n,s in states.items()})


if __name__ == '__main__':
    main()
