"""Model input boundary and development-only package validation."""
from pathlib import Path
import json

from test.interface_blind.core import ROOT, ENVIRONMENT, dump, digest, slug, validate_files, write_files, public_check
from test.webbench_expand.core import SCHEMA_RULES, compile_plan
from test.webbench_expand.schema import check_schema
from test.webbench_expand.generate import output_files, preloaded, COMPILER_PATH, FILES_PATH
from .domain import public_task
from .browser import evaluate

HERE = Path(__file__).resolve().parent
BUILDERS = ('openai/gpt-5', 'anthropic/claude-sonnet-4.5')
PLANNERS = ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct')
STRONG = 'openai/gpt-5'
SEED = 20261112


def development_inputs(project):
    return json.loads((HERE / 'public-development.json').read_text())[project]


def builder_messages(project):
    return [{'role': 'system', 'content': 'Design a reusable full-page GUI library and its data-only composition interface from the supplied development requirements and public behavior examples. You choose component boundaries, state ownership, semantic options, schema properties, implementation and compiler. Support combinations of these known behaviors, not a lookup table of example IDs or whole solutions. Do not encode example numbers or a milestone/bit-mask switch. No existing UI shell, task-specific plan slots, reference implementation or hidden tests are provided. Return one JSON object.'},
            {'role': 'user', 'content': ENVIRONMENT + '\nDevelopment requirements and public observations only:\n' +
             json.dumps(development_inputs(project), ensure_ascii=False) + '\n' + SCHEMA_RULES + '''
Return exactly {"design":"explain components and limitations", "plan_documentation":"document semantic choices and composition", "plan_schema":{}, "files":{"relative/path.js":"frozen implementation"}, "compiler":"function compile(plan, files) { ...; return outputFiles; }", "examples":[{"id":"dev-0","plan":{}},{"id":"dev-1","plan":{}},{"id":"dev-2","plan":{}},{"id":"dev-3","plan":{}},{"id":"dev-4","plan":{}}]}.
Each example plan must implement its development requirement, including all public observations. The pure synchronous compiler receives a validated data plan and your original frozen file map; no DOM/require/process/imports/fetch/filesystem. Return a complete map including index.html. Runtime browser code may use DOM APIs. No external dependencies or network. The entire package and development examples will be provided to later generators. No markdown fences.'''}]


def messages_for(project, task, method, package):
    user = ENVIRONMENT + '\nDevelopment information available to all methods:\n' + json.dumps(development_inputs(project), ensure_ascii=False)
    user += '\nCurrent requirement (only this configuration should execute):\n' + json.dumps(public_task(task), ensure_ascii=False)
    if package is not None:
        user += '\nFrozen model-built library; development checks do not guarantee this new combination:\n' + json.dumps(package, ensure_ascii=False)
        user += (f'\nFor unrestricted code, original files are preloaded. Exact compiler ES module: /{COMPILER_PATH}, named export compile. Original files JSON: /{FILES_PATH}. '
                 'Alternatively return {"program":"function build(files, compile) { ...; return outputFiles; }"}. '
                 'This unrestricted build-time JavaScript receives the exact compiler and original file map in the same pure VM. '
                 'It may call compile(anyData, files), modify outputs, or implement a new page. No plan-schema check is applied to code. '
                 'Return the full map including index.html; no build-time DOM/require/process/fetch. This lets a one-line program reuse the compiler without copying it or building a browser-side loader.')
    if method == 'plan':
        system = 'Return only a JSON data plan conforming to the frozen plan_schema. The generic closed-schema validator runs before the frozen compiler. No code, file maps or executable strings.'
    elif method == 'free_lib':
        system = 'Implement the current complete page using unrestricted JavaScript. Return either {"files":{"new-or-overridden/path":"source"}} or the build(files,compile) program form documented below. Unchanged preloaded files remain available. You may call, modify or ignore the supplied library/compiler.'
    else:
        system = 'Implement the current complete page using unrestricted HTML/CSS/JavaScript. Return JSON {"files":{"index.html":"source", "relative/path.js":"source"}} containing every needed file.'
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def validate_package(project, package, folder):
    if not isinstance(package, dict) or set(package) != {'design', 'plan_documentation', 'plan_schema', 'files', 'compiler', 'examples'}:
        raise ValueError('Package must have exactly the documented envelope keys')
    for key in ('design', 'plan_documentation', 'compiler'):
        if not isinstance(package[key], str) or not package[key].strip():
            raise ValueError(key + ' must be nonempty text')
    check_schema(package['plan_schema'])
    if package['plan_schema']['type'] != 'object':
        raise ValueError('Plan schema root must be object')
    validate_files(package['files'])
    preloaded(package)
    examples = package['examples']
    if not isinstance(examples, list) or len(examples) != 5 or {e.get('id') for e in examples} != {f'dev-{i}' for i in range(5)}:
        raise ValueError('Provide exactly five distinct dev-0..dev-4 example plans')
    compiled = {}
    for example in examples:
        files = compile_plan(package, example['plan'])
        if files != compile_plan(package, example['plan']):
            raise ValueError('Compiler output must be deterministic')
        compiled[example['id']] = files
    # A syntactically valid package can still fail development behavior. Retain
    # every such attempt; choose first full pass or last compilable at the cap.
    reports, feedback = {}, []
    for task in development_inputs(project):
        page = Path(folder) / task['id']
        write_files(page, compiled[task['id']])
        report = evaluate(page, project, task['public_cases'])
        dump(page / 'public-report.json', report)
        reports[task['id']] = report
        if not report['all_passed']:
            feedback.append(task['id'] + ': ' + json.dumps(report['failures'][:1], ensure_ascii=False))
    return feedback, reports


def config(kind):
    build = kind == 'build'
    cap, stop = {'build': (3.0, 2.8), 'run': (1.2, 1.1), 'strong': (2.5, 2.35)}[kind]
    return {'models': list(BUILDERS if build else (STRONG,) if kind == 'strong' else PLANNERS),
            'temperature': .6, 'max_tokens': 20000 if build else 6000, 'max_repairs': 2, 'seed': SEED,
            'budget_usd': cap, 'stop_new_requests_usd': stop,
            'price_caps_per_million': {'prompt': 3, 'completion': 15},
            'model_price_caps': {BUILDERS[0]: {'prompt': 1.25, 'completion': 10}, BUILDERS[1]: {'prompt': 3, 'completion': 15},
                                 PLANNERS[0]: {'prompt': .2, 'completion': .7}, PLANNERS[1]: {'prompt': .1, 'completion': .3}},
            'reasoning_effort': {STRONG: 'medium', PLANNERS[0]: 'low'},
            'omit_params': {STRONG: ['temperature', 'seed']},
            'provider_order': {STRONG: ['OpenAI'], PLANNERS[0]: ['Near AI'], PLANNERS[1]: ['DeepInfra']}}
