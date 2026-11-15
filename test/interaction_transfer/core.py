"""Public-only prompts, package validation and equal-information candidate inputs."""
from pathlib import Path
import json
from .domain import PROJECTS, target
from .browser import evaluate
from test.interface_blind.core import ROOT,ENVIRONMENT,dump,digest,slug,validate_files,write_files,public_check
from test.webbench_expand.core import SCHEMA_RULES,compile_plan
from test.webbench_expand.schema import check_schema
from test.webbench_expand.generate import output_files,preloaded,COMPILER_PATH,FILES_PATH

HERE=Path(__file__).resolve().parent
BUILDERS=('openai/gpt-5','anthropic/claude-sonnet-4.5')
PLANNERS=('openai/gpt-5','openai/gpt-oss-120b')
CONDITIONS=('direct','contracts')
SEED=20261115
BUILD=ROOT/'artifacts/interaction-transfer-build-20261115'
RUN=ROOT/'artifacts/interaction-transfer-run-20261115'
CALIBRATION=ROOT/'artifacts/interaction-transfer-calibration-20261115'


def public_inputs(project):
    return json.loads((HERE/'public-development.json').read_text())[project]


def builder_messages(project,condition):
    process={
      'direct':'Design the package as a directly configurable complete page. Choose meaningful page options that let a future user combine the demonstrated capabilities; document how configurations change the page.',
      'contracts':'Design the package around composable operations over shared state. Explicitly document state ownership, operation preconditions/postconditions, identity invariants and derived-view consistency, and make the same operations reusable across combinations of the demonstrated capabilities. You choose the abstraction boundaries and plan language.'
    }[condition]
    return [{'role':'system','content':'Design a reusable full-page GUI library and a data-only composition interface from the supplied development requirements and observations. You choose every component, state representation, semantic option, schema field, implementation and compiler. Support combinations of known capabilities. Do not encode development IDs, task numbers or a lookup table of complete example solutions. No reference implementation or hidden tests are supplied. Return exactly one JSON object.'},
        {'role':'user','content':ENVIRONMENT+'\nConstruction approach:\n'+process+'\nDevelopment inputs (only these are available during construction):\n'+json.dumps(public_inputs(project),ensure_ascii=False)+'\n'+SCHEMA_RULES+'''
Return exactly {"design":"components, contracts and limitations", "plan_documentation":"how to configure and combine behavior", "plan_schema":{}, "files":{"relative/path":"source"}, "compiler":"function compile(plan, files) { ...; return outputFiles; }", "examples":[{"id":"dev-0","plan":{}},{"id":"dev-1","plan":{}},{"id":"dev-2","plan":{}}]}.
Each example must satisfy its development requirement and public observations. The compiler is pure, synchronous and deterministic; it receives your validated data plan and frozen file map, with no DOM, require, imports, process, fetch or filesystem. It must return a complete file map containing index.html. Browser code may use DOM/localStorage. No external dependencies or network. The package and three examples will be shown to future generators. No markdown fences.'''}]


def messages_for(project,method,package):
    user=ENVIRONMENT+'\nCommon development information:\n'+json.dumps(public_inputs(project),ensure_ascii=False)
    user+='\nComplete target requirement:\n'+json.dumps(target(project),ensure_ascii=False)
    if package is not None:
        user+='\nFrozen library and compiler (development success does not establish all interactions):\n'+json.dumps(package,ensure_ascii=False)
        user+=(f'\nFor unrestricted code, the exact compiler module /{COMPILER_PATH} and original file map /{FILES_PATH} are preloaded. '
            'Alternatively return {"program":"function build(files, compile) { ...; return outputFiles; }"}. '
            'The pure build-time JavaScript may directly call compile(anyData,files), modify its output or implement a complete page. '
            'Code is not restricted by plan_schema. No build-time DOM/require/process/fetch. Return a full file map including index.html. '
            'A one-line build program may reuse the exact compiler without copying it. Runtime code may use browser APIs. '
            'Alternatively return {"files":{"new-or-overridden/path":"source"}}; unchanged preloaded files remain available.')
    system={'plan':'Return only a data plan satisfying the frozen plan_schema. A generic closed-schema validator runs before compilation. No executable strings or file maps.',
        'free_lib':'Implement the complete target using unrestricted code. Return either the files or build(files,compile) program JSON form documented in the user message. You may call, modify or ignore the whole library/compiler.',
        'free':'Implement the complete target. Return JSON {"files":{"index.html":"source","relative/path":"source"}} with all needed HTML/CSS/JavaScript. No external dependencies.'}[method]
    return [{'role':'system','content':system},{'role':'user','content':user}]


def validate_package(project,package,folder):
    required={'design','plan_documentation','plan_schema','files','compiler','examples'}
    if not isinstance(package,dict) or set(package)!=required:raise ValueError('Package must have exactly the documented envelope keys')
    for key in ('design','plan_documentation','compiler'):
        if not isinstance(package[key],str) or not package[key].strip():raise ValueError(key+' must be nonempty text')
    check_schema(package['plan_schema'])
    if package['plan_schema']['type']!='object':raise ValueError('Root schema must be object')
    validate_files(package['files']);preloaded(package)
    examples=package['examples']
    if not isinstance(examples,list) or len(examples)!=3 or {x.get('id') for x in examples}!={f'dev-{i}' for i in range(3)}:
        raise ValueError('Exactly three distinct dev-0..dev-2 example plans required')
    compiled={}
    for ex in examples:
        files=compile_plan(package,ex['plan'])
        if files!=compile_plan(package,ex['plan']):raise ValueError('Compiler output must be deterministic')
        compiled[ex['id']]=files
    reports,feedback={},[]
    for task in public_inputs(project):
        page=Path(folder)/task['id'];write_files(page,compiled[task['id']])
        report=evaluate(page,project,task['public_cases']);dump(page/'public-report.json',report)
        reports[task['id']]=report
        if not report['all_passed']:feedback.append(task['id']+': '+json.dumps(report['failures'][:2],ensure_ascii=False))
    return feedback,reports


def config(build):
    return {'models':list(BUILDERS if build else PLANNERS),'temperature':.6,'max_tokens':20000 if build else 8000,'max_repairs':2,'seed':SEED,
       'budget_usd':12 if build else 6,'stop_new_requests_usd':11.5 if build else 5.7,
       'price_caps_per_million':{'prompt':3,'completion':15},
       'model_price_caps':{'openai/gpt-5':{'prompt':1.25,'completion':10},'anthropic/claude-sonnet-4.5':{'prompt':3,'completion':15},'openai/gpt-oss-120b':{'prompt':.2,'completion':.7}},
       'reasoning_effort':{'openai/gpt-5':'medium','openai/gpt-oss-120b':'low'},
       'omit_params':{'openai/gpt-5':['temperature','seed']},
       'provider_order':{'openai/gpt-5':['OpenAI'],'openai/gpt-oss-120b':['Near AI']}}


def frozen_sources():
    local=[HERE/name for name in ('__init__.py','domain.py','browser.py','core.py','run.py','controls.py','evaluate.py')]
    deps=['test/interface_blind/core.py','test/interface_blind/compile.cjs','test/webbench_expand/core.py',
      'test/webbench_expand/schema.py','test/webbench_expand/generate.py','test/webbench_expand/free_build.cjs',
      'test/provider_ext.py','test/streaming_provider_v2.py','src/gui_dna/provider.py','src/gui_dna/budget.py',
      'test/review_stage.py','test/webbench_expand/run.py','test/webbench_expand/resume.py',
      'test/ledger_read.py','pyproject.toml','uv.lock']
    return local+[ROOT/p for p in deps]
