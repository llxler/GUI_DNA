"""Public-only generation boundary for three previously shortlisted projects."""
from __future__ import annotations
import json
from pathlib import Path
from test.interface_blind.core import (ROOT, UPSTREAM, ENVIRONMENT, Server, browser_env,
    dump, digest, slug, validate_files, write_files, public_check, compile_plan as vm_compile)
from .schema import check_schema, validate

HERE = Path(__file__).resolve().parent
PROJECTS = ('calculator', 'table', 'bom')
BUILDERS = ('openai/gpt-5', 'anthropic/claude-sonnet-4.5')
PLANNERS = ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct')
SEED = 20261112


def requirements(project):
    if project not in PROJECTS:
        raise ValueError(project)
    return [{'id': row['id'], 'description': row['description']} for row in
            (json.loads(line) for line in (UPSTREAM / 'projects' / project / 'tasks.jsonl').read_text().splitlines())]


SCHEMA_RULES = '''plan_schema must be a machine-readable JSON object in this CLOSED dialect:
Every node has type and may have a textual description. No other keywords except:
- object: properties (<=64 fixed identifier keys), required (list of those keys),
  additionalProperties:false. The root MUST be an object.
- array: items (one schema), minItems (default 0), maxItems (required, <=64),
  optional uniqueItems boolean.
- string: enum of 1..128 distinct simple identifiers matching
  [A-Za-z][A-Za-z0-9_-]{0,63}. No arbitrary text, paths or code strings.
- integer: minimum and maximum, both required within -1000000..1000000.
- boolean: no further keywords.
No $schema, $ref, definitions, oneOf, anyOf, const, default, number, null, pattern,
dynamic keys or extra schema keywords. Nesting <=12. The generic validator runs
BEFORE your compiler. Use frozen labels/text/files for UI content; plans only
choose semantic options. You decide all property names and enum options.'''


def builder_messages(project):
    return [{'role': 'system', 'content': '''Design a reusable GUI component library and composition interface using only public requirements.
You choose components, shared state, event interfaces, semantic choices and all
implementation. No tests, reference solution or project-specific UI shell are
provided. Do not encode task numbers, milestone switches or a lookup table of
complete per-task solutions/plans. Use meaningful independently composable
options. Do not accept executable code as plan data. Return one JSON object.'''},
        {'role': 'user', 'content': ENVIRONMENT + '\nPublic requirement sequence:\n' +
         json.dumps(requirements(project), ensure_ascii=False) + '\n\n' + SCHEMA_RULES + '''

Return this exact package envelope:
{"design":"Components, state and limitations",
 "plan_documentation":"Explain your semantic options and how to compose them",
 "plan_schema":{}, "files":{"relative/path.js":"frozen source"},
 "compiler":"function compile(plan, files) { ...; return outputFiles; }",
 "examples":[{"description":"small default configuration", "plan":{}},
             {"description":"richer default configuration", "plan":{}}]}
The pure synchronous compile function receives a validated plan and your frozen
file map. It runs without DOM, require, process, imports, fetch or filesystem;
return a complete file map containing index.html. It may emit deterministic glue
and JSON configuration. Browser modules can use DOM APIs. Include dependencies.
Both documentation examples must validate, compile deterministically and load
without page or console errors. No behavioral tests are supplied. Implement the
full public behavior range; let a later planner select the desired composition.
Later models see the entire package. No markdown fences.'''}]


def compile_plan(package, plan):
    check_schema(package['plan_schema'])
    validate(package['plan_schema'], plan)
    return vm_compile(package, plan)


def validate_package(package, folder):
    if not isinstance(package, dict):
        raise ValueError('package must be an object')
    expected = {'design', 'plan_documentation', 'plan_schema', 'files', 'compiler', 'examples'}
    if set(package) != expected:
        raise ValueError('package keys must be exactly: ' + ', '.join(sorted(expected)))
    for key in ('design', 'plan_documentation', 'compiler'):
        if not isinstance(package[key], str) or not package[key].strip():
            raise ValueError(f'{key} must be nonempty text')
    check_schema(package['plan_schema'])
    if package['plan_schema']['type'] != 'object':
        raise ValueError('plan root schema must be object')
    validate_files(package['files'])
    if not isinstance(package['examples'], list) or len(package['examples']) != 2:
        raise ValueError('exactly two examples required')
    problems = []
    for i, example in enumerate(package['examples']):
        files = compile_plan(package, example['plan'])
        if files != compile_plan(package, example['plan']):
            raise ValueError('compiler must be deterministic')
        page = Path(folder) / f'example-{i}'
        write_files(page, files)
        problems.extend(f'example {i}: {error}' for error in public_check(page))
    return problems


def planner_messages(project, task, method, package=None):
    rows = requirements(project)
    index = next(i for i, row in enumerate(rows) if row['id'] == task)
    user = ENVIRONMENT + '\nImplement all requirements through the current task; later ones override earlier conflicts.\n'
    user += json.dumps(rows[:index + 1], ensure_ascii=False)
    if package is not None:
        user += '\nFrozen public-requirements-only library and interface (not behaviorally verified):\n' + json.dumps(package, ensure_ascii=False)
    if method == 'plan':
        system = ('Return only a JSON plan conforming to the supplied plan_schema. '
                  'A generic closed-schema validator runs before the frozen compiler. No source code or file maps.')
    elif method == 'free_lib':
        system = ('Implement the complete website using unrestricted JavaScript. All files in the library file map '
                  'are ALREADY PRESENT at their listed paths. You may import/call them, replace any file, or ignore '
                  'the library. Return only JSON: {"files":{"index.html":"...","new-or-modified/path.js":"..."}}. '
                  'Return ONLY new/changed files. Unspecified library files are inherited verbatim. You own the complete page.')
    else:
        system = 'Implement the complete website. Return JSON only: {"files":{"index.html":"...","relative/path.js":"..."}}. Include every required file.'
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def config(build=False):
    return {'models': list(BUILDERS if build else PLANNERS), 'temperature': .6,
        'max_tokens': 26000 if build else 12000, 'max_repairs': 2, 'seed': SEED,
        'budget_usd': 4.5 if build else 5, 'stop_new_requests_usd': 4.3 if build else 4.8,
        'price_caps_per_million': {'prompt': 3, 'completion': 15},
        'model_price_caps': {BUILDERS[0]: {'prompt': 1.25, 'completion': 10},
            BUILDERS[1]: {'prompt': 3, 'completion': 15},
            PLANNERS[0]: {'prompt': .2, 'completion': .7},
            PLANNERS[1]: {'prompt': .1, 'completion': .3}},
        'reasoning_effort': {BUILDERS[0]: 'medium', PLANNERS[0]: 'low'},
        'omit_params': {BUILDERS[0]: ['temperature', 'seed']},
        'provider_order': {PLANNERS[0]: ['Near AI'], PLANNERS[1]: ['DeepInfra']}}
