"""Public preparation and independent target prompts for the expression editor."""
import json
from pathlib import Path
import subprocess

from studies.interface_blind.core import validate_files
from studies.study_io import ROOT, UPSTREAM
from studies.webbench_expand.core import SCHEMA_RULES, compile_plan, validate_package

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/expression-editor-sources-20261123'
RUNTIME = ROOT / 'artifacts/expression-editor-runtime-20261123'
PROJECT = 'expression-editor'
SOURCE = UPSTREAM / 'projects' / PROJECT
ARMS = ('reference', 'ai', 'direct')
TASKS = tuple(f'task-{n}' for n in range(1, 21))
BUILDER = 'openai/gpt-5'
MODEL = 'mistralai/mistral-small-3.2-24b-instruct'
MODULES = ('parser', 'evaluate', 'editor', 'highlight', 'lint', 'autocomplete')
TOOLBAR = ('documentation', 'uppercase', 'snippet', 'run')
CONTROLLERS = ('pairParentheses', 'highlight', 'diagnosticTooltip', 'syntaxErrors', 'completion', 'history')
STARTED = '2026-11-23T03:23:02+00:00'


def files(base):
    return {str(p.relative_to(base)):p.read_text() for p in sorted(base.rglob('*')) if p.is_file()}


def starter():
    return files(SOURCE / 'src-init')


def requirements():
    raw = subprocess.check_output(['/usr/bin/python3','-c',
         'import json,sys,yaml;print(json.dumps(yaml.safe_load(sys.stdin),default=str))'],
         input=(SOURCE / 'tasks.yml').read_bytes())
    rows = [{'id':r['id'],'description':r['description']} for r in json.loads(raw)]
    assert [r['id'] for r in rows] == list(TASKS)
    return rows


def reference():
    def options(values):
        return {'type':'array','items':{'type':'string','enum':list(values)},
                'maxItems':len(values),'uniqueItems':True}
    schema = {'type':'object','properties':{'toolbar':options(TOOLBAR),'controllers':options(CONTROLLERS)},
              'required':['toolbar','controllers'],'additionalProperties':False}
    library = starter() | {m+'.js':(SOURCE / 'src' / (m+'.js')).read_text() for m in MODULES}
    library['binding.js'] = (HERE / 'binding.js').read_text()
    return {'files':library, 'plan_schema':schema,'compiler':(HERE/'compiler.js').read_text(),
            'plan_documentation': 'The editable region and language modules always exist. Select toolbar commands '
            'and event controllers using the documented enums. The highlight controller includes diagnostic decorations. '
            'The diagnostic tooltip consumes decorations. Completion handles mouse and keyboard interaction.'}


def prompt(system, public):
    return [{'role':'system','content':system},{'role':'user','content':public}]


def common_inputs(rows):
    return ('Public starter files (the page uses static ES modules, no external packages):\n'
            + json.dumps(starter(),ensure_ascii=False) + '\nPublic requirements in order:\n'
            + json.dumps(rows,ensure_ascii=False))


def preparation(arm):
    public = common_inputs(requirements())
    if arm == 'direct':
        return prompt('Prepare a reusable technical design memo for a later engineer implementing this expression editor. '
            'You receive the complete public brief and starter once. Work out algorithms, module APIs, DOM behavior, '
            'edge cases and integration. You may include pseudocode and code fragments. Your memo will be visible as '
            'text only; the engineer writes the website freely and may use, modify or ignore the memo. Its text never '
            'runs as supplied files. Respond with precisely one JSON object {"notes":"..."} and no surrounding prose.', public)
    return prompt('Build a reusable web GUI implementation package from the public brief and starter for a later '
            'planner to assemble. Design independently composable semantic choices; no task-number switches or stored '
            'per-task answers. Use static ES modules, with all their dependencies locally supplied. No external network. '
            'Return a single JSON object with exactly design (text), plan_documentation (text), plan_schema, '
            'files (map relative path -> UTF-8 text), compiler (source declaring function compile(plan,files)), and '
            'examples (two documentation objects with description and plan, first basic, second richer). '
            'Your pure synchronous compiler runs in an isolated JS VM without DOM, process or filesystem; '
            'it must return a complete file map including index.html and must compile both examples deterministically. '
            'The examples must load in a browser with no page or console errors. A later model receives this entire package. '
            'Use simple types and concise components. ' + SCHEMA_RULES, public)


def target_prompt(arm, task, artifact):
    rows = requirements()
    public = common_inputs(rows[:TASKS.index(task)+1]) + '\nImplement all requirements so far.'
    if arm=='direct':
        return prompt('Create or replace any files freely to implement the required page. Public starter files not '
            'overridden are inherited. Return only {"files":{relativePath:completeText,...}}. Your preparation memo '
            'is advisory; its text is never executed or supplied as code.',
            public + '\nYour project preparation memo:\n' + artifact['notes'])
    return prompt('Respond with a JSON data plan satisfying the frozen plan_schema. Only the frozen compiler may '
            'supply page files. Do not write executable code or a file map.',public + '\nYour frozen implementation '
            'package and its documentation:\n' + json.dumps(artifact,ensure_ascii=False))


def validate_preparation(arm, obj, path):
    if arm == 'ai':
        issues = validate_package(obj, path)
        if issues:
            raise ValueError('\n'.join(issues))
    elif (not isinstance(obj,dict) or set(obj)!={'notes'} or not isinstance(obj['notes'],str)
          or not obj['notes'].strip()):
        raise ValueError('Return exactly one nonempty notes string in a JSON object.')
    return obj


def render(arm, artifact, obj):
    if arm == 'direct':
        if not isinstance(obj, dict) or set(obj)!={'files'} or not isinstance(obj['files'],dict):
            raise ValueError('Return exactly one files object mapping relative file paths to contents.')
        changed = obj['files']
        if changed:
            validate_files(changed)
    else:
        changed = compile_plan(artifact,obj)
    return validate_files(starter() | changed)
