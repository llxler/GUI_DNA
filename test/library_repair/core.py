"""Public inputs for a single-response implementation intervention."""
from copy import deepcopy
from pathlib import Path
import json

from test.interface_blind.core import ROOT, dump, digest, slug, validate_files
from test.webbench_expand.core import BUILDERS, PROJECTS, requirements, compile_plan
from gui_dna.provider import parse_json

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/library-repair-20261113'
ORIGINAL = ROOT / 'artifacts/webbench-expand-build'
MAIN = ROOT / 'artifacts/webbench-expand-run'
STRONG = ROOT / 'artifacts/webbench-expand-frontier-2'
PUBLIC_TASKS = (2, 6, 10, 14, 18)
TEST_TASKS = (4, 8, 12, 16, 20)
CONDITIONS = ('review', 'feedback')
MODELS = ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct', 'openai/gpt-5')


def read(path):
    return json.loads(Path(path).read_text())


def original_package(project, builder):
    return read(ORIGINAL / 'libraries' / project / slug(builder) / 'package.json')


def source_folder(project, builder, model, method, task):
    stage = STRONG if model == 'openai/gpt-5' else MAIN
    return stage / 'runs' / project / slug(builder) / slug(model) / method / f'task-{task}'


def source_output(folder):
    record = read(folder / 'record.json')
    assert record['status'] == 'complete'
    if not record['versions']:
        return None
    index = record['versions'][-1].removeprefix('version-')
    return parse_json(read(folder / f'output-{index}.json')['text'])


def messages_for(project, builder, condition, public):
    assert condition in CONDITIONS
    assert set(public) == {f'task-{k}' for k in PUBLIC_TASKS}
    material = {'requirements': requirements(project), 'original_package': original_package(project, builder),
                'fixed_development_plans': {k: public[k]['plan'] for k in public}}
    if condition == 'feedback':
        material['development_observations'] = {k: public[k]['feedback'] for k in public}
    return [{'role': 'system', 'content': '''Review and improve the implementation of an existing static-browser GUI library.
Keep the exact existing data interface and the documented meaning of every option. Only implementation files and the compiler may change. Preserve the original design, plan_documentation, plan_schema and examples; the harness will copy those unchanged. Do not ignore configuration choices just to pass a supplied observation. No reference implementation is supplied. Return JSON only with exactly {"files": {"relative/path": "complete source", ...}, "compiler": "function compile(plan, files) { ... }"}. files is a full replacement map, not a patch; include unchanged required files. The compiler stays pure, synchronous and deterministic. Browser code may use the DOM but no external dependencies/network. Do not put benchmark task IDs, test detection, fixed observation traces or per-task lookup tables into the implementation.'''},
            {'role': 'user', 'content': 'All public requirements, the original package, and fixed development configurations follow. '
             + ('Use the provided development observations to diagnose implementation defects. ' if condition == 'feedback' else
                'Independently review the implementation against the requirements; no test outcomes are supplied. ')
             + 'This is your single revision opportunity. Preserve valid behavior and option semantics. Return only the replacement files/compiler.\n'
             + json.dumps(material, ensure_ascii=False)}]


def repaired_package(original, patch):
    if not isinstance(patch, dict) or set(patch) != {'files', 'compiler'}:
        raise ValueError('Return exactly files and compiler')
    validate_files(patch['files'])
    if not isinstance(patch['compiler'], str) or not patch['compiler'].strip():
        raise ValueError('compiler must be nonempty source')
    package = {**deepcopy(original), **patch}
    for example in original['examples']:
        files = compile_plan(package, example['plan'])
        assert files == compile_plan(package, example['plan']), 'Nondeterministic compiler'
    assert all(package[k] == original[k] for k in original if k not in ('files', 'compiler'))
    return package


def config():
    return {'models': list(BUILDERS), 'temperature': .6, 'max_tokens': 26000, 'max_repairs': 0, 'seed': 20261113,
            'budget_usd': 9.0, 'stop_new_requests_usd': 8.6,
            'price_caps_per_million': {'prompt': 3, 'completion': 15},
            'model_price_caps': {BUILDERS[0]: {'prompt': 1.25, 'completion': 10}, BUILDERS[1]: {'prompt': 3, 'completion': 15}},
            'reasoning_effort': {BUILDERS[0]: 'medium'}, 'omit_params': {BUILDERS[0]: ['temperature', 'seed']},
            'provider_order': {BUILDERS[0]: ['OpenAI']}}
