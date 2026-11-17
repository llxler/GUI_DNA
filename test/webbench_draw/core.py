"""Public requirements and matched output interfaces; no hidden-test imports."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from test.interface_blind.core import ROOT, UPSTREAM, dump, slug, validate_files, write_files
from test.webbench_expand.core import SCHEMA_RULES, compile_plan, config as previous_config
from test.webbench_expand.schema import check_schema
from test.webbench_expand.generate import output_files
from test.history_replay.run import digest, sha
from .browser import public_check

HERE = Path(__file__).resolve().parent
BUILDERS = ('openai/gpt-5', 'anthropic/claude-sonnet-4.5')
PLANNERS = ('openai/gpt-oss-120b', 'openai/gpt-5')
MILESTONES = (4,8,12,16,20)
BUILD = ROOT / 'artifacts/webbench-draw-build-20261117'
STAGES = {PLANNERS[0]:ROOT / 'artifacts/webbench-draw-oss-20261117',
          PLANNERS[1]:ROOT / 'artifacts/webbench-draw-frontier-20261117'}
SEED = 20261117
ENVIRONMENT = '''Implement a standalone browser website in a complete file map including index.html.
The same fixed Vite 7.1.5 server with sass-embedded 1.83.1 serves every submission.
HTML, browser JavaScript ES modules, CSS and SCSS are supported. All required files
must be supplied; no npm packages, network services, remote fonts or assets.
No project-specific application shell is provided. Vite configuration is fixed;
custom package scripts, server plugins and backend code are not executed.'''


def requirements():
    path = UPSTREAM / 'projects/draw/tasks.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r['id'] for r in rows] == ['init', *[f'task-{i}' for i in range(1,21)]]
    return [{'id':r['id'], 'description':r['description']} for r in rows]


def builder_messages():
    return [{'role':'system', 'content':'''Design a reusable GUI library and composition interface from public requirements.
Choose components, shared state, events, all semantic options and implementation.
No tests, reference solution, hand-designed slots or application shell are given.
Do not encode task numbers, milestone switches or a lookup table of whole pages.
Use meaningful composable behavior options; no executable code in plan data.
Return one JSON object without markdown fences.'''}, {'role':'user', 'content':ENVIRONMENT +
        '\nPublic requirement sequence:\n' + json.dumps(requirements(), ensure_ascii=False) + '\n' + SCHEMA_RULES + '''
Return exactly:
{"design":"Components, state and limitations", "plan_documentation":"How to compose semantic options",
 "plan_schema":{}, "files":{"relative/path.js":"frozen source"},
 "compiler":"function compile(plan, files) { ...; return outputFiles; }",
 "examples":[{"description":"small default configuration","plan":{}},
             {"description":"richer default configuration","plan":{}}]}
The pure synchronous compile function receives the validated plan and frozen files.
It runs without DOM, require, process, imports, fetch or filesystem and returns
a complete file map including index.html. Browser modules can use DOM APIs.
Both examples must validate, compile deterministically and load without console
or page errors. No behavioral tests are supplied. Implement the full public
behavior range; later models see the entire frozen package.'''}]


def planner_messages(k, method, package):
    user = ENVIRONMENT + '\nImplement every public requirement through the current task; later requirements override earlier conflicts.\n'
    user += json.dumps(requirements()[:k+1], ensure_ascii=False)
    if package is not None:
        user += '\nFrozen library from public requirements only; behavior not verified:\n' + json.dumps(package, ensure_ascii=False)
        user += '''\nAll original library files are preloaded. The exact frozen compiler is also
preloaded as /__gui_dna_support/compiler.mjs (named export compile), and its
original file map as /__gui_dna_support/files.json. Unrestricted code may import
these, change files or ignore the library. Alternatively return exactly
{"program":"function build(files, compile) { ...; return outputFiles; }"}.
This pure synchronous build function receives the entire original file map and
compiler and may call compile(anyData, files), edit its output, or replace it.
There is NO plan-schema restriction on unrestricted code. Build-time code has no
DOM, require, process, fetch or filesystem; generated browser files have DOM APIs.
Plans use the same frozen compiler after closed-schema validation.'''
    system = {
        'plan':'Return only a JSON plan conforming to the supplied plan_schema. No code or file maps; the generic validator runs before the frozen compiler.',
        'free_lib':'Implement the complete website with unrestricted JavaScript. Return JSON {"files":{"index.html":"...","new-or-modified/file.js":"..."}} with only changed/new files; unspecified library files are inherited. Alternatively return the unrestricted program form documented below. You may use, modify or ignore the complete library.',
        'free':'Implement the complete website. Return JSON only: {"files":{"index.html":"...","relative/file.js":"..."}}. Include all required files.'}[method]
    return [{'role':'system','content':system}, {'role':'user','content':user}]


def config(kind):
    cfg = deepcopy(previous_config(kind == 'build'))
    allocation = json.loads((ROOT / 'artifacts/review-20261117/budget-plan.json').read_text())['stages']
    out = BUILD if kind == 'build' else STAGES[PLANNERS[0 if kind == 'oss' else 1]]
    cfg.update(models=list(BUILDERS) if kind == 'build' else [PLANNERS[0 if kind == 'oss' else 1]],
        max_tokens=26000 if kind == 'build' else 12000, seed=SEED,
        budget_usd=allocation[out.name]['cap'], stop_new_requests_usd=allocation[out.name]['stop'])
    cfg['provider_order'] = {PLANNERS[0]:['Near AI'], 'openai/gpt-5':['OpenAI']}
    return cfg


def write_source(folder, files):
    files = validate_files(files)
    if 'source-manifest.json' in files:
        raise ValueError('source-manifest.json is reserved for the evaluator')
    write_files(folder, files)
    dump(folder / 'source-manifest.json', {'files_sha256':{n:sha(folder / n) for n in files},
        'output_sha256':digest(files)})


def validate_package(package, folder):
    keys = {'design','plan_documentation','plan_schema','files','compiler','examples'}
    if not isinstance(package,dict) or set(package) != keys:
        raise ValueError('Package must have exactly ' + ', '.join(sorted(keys)))
    for key in ('design','plan_documentation','compiler'):
        if not isinstance(package[key], str) or not package[key].strip():
            raise ValueError(key + ' must be nonempty text')
    check_schema(package['plan_schema'])
    if package['plan_schema']['type'] != 'object':
        raise ValueError('Root schema must be object')
    validate_files(package['files'])
    if not isinstance(package['examples'], list) or len(package['examples']) != 2:
        raise ValueError('Exactly two documentation examples required')
    feedback = []
    for i, example in enumerate(package['examples']):
        files = compile_plan(package, example['plan'])
        if files != compile_plan(package, example['plan']):
            raise ValueError('Compiler is not deterministic')
        page = folder / f'example-{i}'
        write_source(page, files)
        feedback += [f'Example {i}: {error}' for error in public_check(page)]
    return feedback
