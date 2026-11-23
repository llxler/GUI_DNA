"""Frozen public input boundary and typed table controller selection."""
import json
from pathlib import Path

from studies.interface_blind.core import validate_files
from studies.study_io import ROOT, UPSTREAM, read
from studies.webbench_expand.core import compile_plan, requirements

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-library-sources-20261123'
SOURCE = UPSTREAM / 'projects/table'
AI = ROOT / 'artifacts/webbench-expand-build/libraries/table/openai__gpt-5/package.json'
MODEL = 'mistralai/mistral-small-3.2-24b-instruct'
ARMS = ('reference', 'ai', 'direct')
TASKS = tuple(f'task-{n}' for n in range(1, 21))
MODULES = ('table', 'menu', 'key', 'mouse', 'layout', 'drag', 'util')
CONTROLLERS = ('contextMenu', 'keyboard', 'rowResize', 'columnResize', 'mouseSelection', 'dragReorder')
STARTED = '2026-11-23T03:16:52+00:00'


def starter():
    return {p.name: p.read_text() for p in sorted((SOURCE / 'src-init').iterdir()) if p.is_file()}


def reference_package():
    files = starter()
    for name in MODULES:
        path = f'common/{name}.js'
        files[path] = (SOURCE / 'src' / path).read_text()
    files['index.css'] = (SOURCE / 'src/index.css').read_text()
    schema = {'type': 'object', 'properties': {
        'controllers': {'type': 'array', 'minItems': 0, 'maxItems': len(CONTROLLERS), 'uniqueItems': True,
                        'items': {'type': 'string', 'enum': list(CONTROLLERS)}}},
        'required': ['controllers'], 'additionalProperties': False}
    return {'plan_schema': schema, 'files': files, 'compiler': (HERE / 'compiler.js').read_text(),
            'plan_documentation': 'The table state, click selection and editing are always present. Select the controllers needed for the requested behavior. Controller names identify native reference-module entry points. Controllers are initialized in a fixed dependency order.'}


def packages():
    return {'reference': reference_package(), 'ai': read(AI), 'direct': None}


def messages(arm, task, package):
    rows = requirements('table')
    end = next(i for i, row in enumerate(rows) if row['id'] == task)
    public = ('Implement all public requirements through the current task. Later requirements override earlier conflicts. '
              'The browser serves ES modules and static files from index.html.\nRequirements:\n'
              + json.dumps(rows[:end + 1], ensure_ascii=False)
              + '\nPublic starting files (all inherited verbatim unless replaced):\n' + json.dumps(starter()))
    if arm == 'direct':
        system = ('Implement the page freely. Return only a JSON object {"files":{...}} with new or changed '
                  'files keyed by normalized relative path, including all code needed beyond the public starter. '
                  'You may replace any starting file. Output no commentary.')
    else:
        system = ('Return only a JSON plan matching plan_schema. The frozen compiler takes a closed, typed '
                  'data plan and generates the page. No code, file maps or commentary in your response.')
        label = 'reference-derived' if arm == 'reference' else 'public-requirements-only'
        public += f'\nFrozen {label} package (including its compiler and files):\n' + json.dumps(package, ensure_ascii=False)
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': public}]


def render(arm, package, parsed):
    if arm == 'direct':
        if not isinstance(parsed, dict) or set(parsed) != {'files'} or not isinstance(parsed['files'], dict):
            raise ValueError('Return exactly one files object mapping relative paths to text.')
        if parsed['files']:
            validate_files(parsed['files'])
        page = parsed['files']
    else:
        page = compile_plan(package, parsed)
    return validate_files({**starter(), **page})
