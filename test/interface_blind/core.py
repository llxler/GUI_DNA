"""Public inputs and the generic file/JSON boundary; no benchmark solution imports."""
from __future__ import annotations

import hashlib
import functools
import http.server
import json
import os
import subprocess
import sysconfig
import threading
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'artifacts/web-bench'
PROJECTS = ('dom1', 'form')
BUILDERS = ('openai/gpt-5', 'anthropic/claude-sonnet-4.5')
PLANNERS = ('qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct')
SEED = 20261112


class Server:
    def __init__(self, root):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
            functools.partial(Quiet, directory=str(Path(root).resolve())))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def browser_env():
    env = dict(os.environ)
    env.pop('OPENROUTER_API_KEY', None)
    libs = ROOT / '.browser-deps/usr/lib' / (sysconfig.get_config_var('MULTIARCH') or 'x86_64-linux-gnu')
    if libs.exists():
        env['LD_LIBRARY_PATH'] = str(libs) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    return env


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def slug(model):
    return model.replace('/', '__')


def requirements(project):
    if project not in PROJECTS:
        raise ValueError(project)
    # This is the only upstream file the generation module reads.
    return [{'id': r['id'], 'description': r['description']} for r in
            (json.loads(line) for line in (UPSTREAM / 'projects' / project / 'tasks.jsonl').read_text().splitlines())]


ENVIRONMENT = '''The output is a complete static website served at /index.html in Chromium.
Use HTML, CSS, and browser JavaScript/ES modules. No npm build step, frameworks,
external network dependencies, or pre-existing UI shell are provided. Relative
files are served verbatim. Implement the public names and file paths when the
requirements specify them. The generic runtime gives no project-specific slots,
events, feature tags, component inventory, or reference implementation.'''


def builder_messages(project):
    return [{'role': 'system', 'content': '''Design a reusable GUI component library AND its composition interface from public requirements.
You decide component boundaries, state ownership, event interfaces, semantic
options, the JSON plan language, and all executable implementation. A separate
model will later use your library to implement prefixes of these requirements.
Do not encode task numbers, milestone switches, or a lookup table of complete
solutions/plans for the benchmark sequence. Use independently meaningful
components and semantic options. Do not accept executable code in a plan.
No tests or reference implementation are available to you. Do not claim that
your components have been verified. Return one JSON object only.'''} ,
            {'role': 'user', 'content': ENVIRONMENT + '\n\nPublic requirement sequence:\n' +
             json.dumps(requirements(project), ensure_ascii=False) + '''

Return exactly this package envelope (the envelope is generic, not a plan schema):
{
 "design": "Explain components, shared state, composition rules, and limitations",
 "plan_schema": "Complete documentation of YOUR JSON plan language and semantic choices",
 "files": {"relative/path.js": "frozen reusable implementation", "...": "..."},
 "compiler": "function compile(plan, files) { ...; return outputFiles; }",
 "examples": [{"description":"a small configuration", "plan": {}},
              {"description":"a richer configuration", "plan": {}}]
}
The compiler must be a pure synchronous JavaScript function named compile.
It receives only a JSON plan and your frozen file map, checks its own schema,
and returns a COMPLETE map of relative file paths to UTF-8 text, including
index.html. It runs without DOM, require, process, fetch, imports, or filesystem
access. It can copy frozen modules verbatim and emit deterministic glue and
JSON configuration. Runtime browser modules in files can use the DOM.
Plan values must be data, never JavaScript/HTML/CSS code. Include all dependencies.
Both examples must compile and load without page/console errors; examples are
documentation, not a per-task answer key. Later planners see this entire package.
Implement the full range of public behaviors, including their shared-state
interactions, but let the planner choose the needed configuration for its task.
Keep the library concise enough to fit in one response. No markdown fences.'''}]


def validate_files(files):
    if not isinstance(files, dict) or not files or len(files) > 100:
        raise ValueError('files must be a nonempty object with at most 100 files')
    for name, content in files.items():
        p = PurePosixPath(name)
        if (not name or name == '.' or p.is_absolute() or '..' in p.parts or '\\' in name or
                str(p) != name or not isinstance(content, str)):
            raise ValueError('files must have normalized relative paths and text contents')
    if sum(len(v.encode()) for v in files.values()) > 1_000_000:
        raise ValueError('file map exceeds 1 MB')
    return files


def write_files(folder, files):
    validate_files(files)
    if 'index.html' not in files:
        raise ValueError('output files must include index.html')
    for name, content in files.items():
        target = Path(folder) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def compile_plan(package, plan):
    result = subprocess.run(['node', str(HERE / 'compile.cjs')],
                            input=json.dumps({'package': package, 'plan': plan}),
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError('compiler: ' + result.stderr.strip()[:1200])
    files = validate_files(json.loads(result.stdout))
    if 'index.html' not in files:
        raise ValueError('compiler did not return index.html')
    return files


def public_check(folder):
    """Identical project-agnostic load feedback for builders and all planner methods."""
    from playwright.sync_api import sync_playwright
    problems = []
    server = Server(Path(folder).resolve())
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(env=browser_env())
            page = browser.new_page()
            page.on('pageerror', lambda error: problems.append(f'page error: {error}'))
            page.on('console', lambda msg: problems.append(f'console error: {msg.text}') if msg.type == 'error' else None)
            page.on('dialog', lambda dialog: dialog.dismiss())
            try:
                page.goto(f'http://127.0.0.1:{server.port}/index.html', timeout=10000)
                page.wait_for_timeout(300)
            except Exception as error:
                problems.append(f'load error: {type(error).__name__}: {str(error)[:300]}')
            finally:
                browser.close()
    finally:
        server.close()
    return list(dict.fromkeys(problems))[:8]


def validate_package(package, folder):
    if not isinstance(package, dict):
        raise ValueError('package must be an object')
    for key in ('design', 'plan_schema', 'compiler'):
        if not isinstance(package.get(key), str) or not package[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    validate_files(package.get('files'))
    examples = package.get('examples')
    if not isinstance(examples, list) or len(examples) != 2:
        raise ValueError('exactly two documentation examples are required')
    problems = []
    for i, example in enumerate(examples):
        if not isinstance(example, dict) or 'plan' not in example:
            raise ValueError('each example must contain plan')
        files = compile_plan(package, example['plan'])
        # Detect common nondeterministic compilers without evaluating task behavior.
        if files != compile_plan(package, example['plan']):
            raise ValueError('compiler output must be deterministic')
        page = Path(folder) / f'example-{i}'
        write_files(page, files)
        problems.extend(f'example {i}: {p}' for p in public_check(page))
    return problems


def planner_messages(project, task, method, package=None):
    rows = requirements(project)
    index = next(i for i, r in enumerate(rows) if r['id'] == task)
    user = ENVIRONMENT + '\n\nImplement all requirements through the current task. Later requirements override earlier ones where they conflict.\n'
    user += json.dumps(rows[:index + 1], ensure_ascii=False)
    if package is not None:
        user += '\n\nFrozen requirements-only library and interface (not behaviorally verified):\n' + json.dumps(package, ensure_ascii=False)
    if method == 'plan':
        system = 'Return only a JSON plan matching the supplied library plan_schema. No executable code. The frozen compiler creates the complete page.'
    else:
        system = 'Implement the complete website. Return JSON only: {"files": {"index.html": "...", "relative/path.js": "...", "...": "..."}}. Include every required file.'
        if method == 'free_lib':
            system += ' You may copy, adapt, call, or ignore any supplied library code, including its compiler; your output is unrestricted code.'
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def config(build=False):
    return {'models': list(BUILDERS if build else PLANNERS), 'temperature': 0.6,
            'max_tokens': 26000 if build else 12000, 'max_repairs': 2, 'seed': SEED,
            'budget_usd': 5.5 if build else 9.0, 'stop_new_requests_usd': 5.2 if build else 8.8,
            'price_caps_per_million': {'prompt': 3, 'completion': 15},
            'model_price_caps': {
                BUILDERS[0]: {'prompt': 1.25, 'completion': 10},
                BUILDERS[1]: {'prompt': 3, 'completion': 15},
                PLANNERS[0]: {'prompt': .2, 'completion': .8},
                PLANNERS[1]: {'prompt': .1, 'completion': .3}},
            'reasoning_effort': {BUILDERS[0]: 'medium'},
            'omit_params': {BUILDERS[0]: ['temperature', 'seed']},
            'provider_order': {PLANNERS[1]: ['Mistral']}}
