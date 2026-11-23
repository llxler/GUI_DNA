"""Freeze, build, generate and score the five prespecified chart milestones."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.form_library_sources.run import END, MODEL, OUT as FORM
from studies.interface_blind.core import compile_plan, config, dump, validate_files, write_files
from studies.ledger_read import totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import sha, source_files
from studies.webbench_draw.browser import public_check
from .browser import HARNESS, OUT, ROOT, RUNTIME, SOURCE, TARGETS, grade

HERE = Path(__file__).resolve().parent
BUILDER = 'openai/gpt-5'
ARMS = ('reference', 'ai', 'direct')
SEED = 20261121


def files_under(base):
    return {str(p.relative_to(base)): p.read_text() for p in sorted(base.rglob('*')) if p.is_file()}


def inputs():
    # The system PyYAML is available on this workstation; requirements are public.
    result = subprocess.check_output(['/usr/bin/python3', '-c',
        'import json,sys,yaml;print(json.dumps(yaml.safe_load(sys.stdin), default=str))'],
        input=(SOURCE / 'tasks.yml').read_text(), text=True)
    rows = [{'id': r['id'], 'description': r['description']} for r in json.loads(result)]
    assert [r['id'] for r in rows] == [f'task-{i}' for i in range(1, 21)]
    return rows


def reference():
    files = {'common/' + k: v for k, v in files_under(SOURCE / 'src/common').items()}
    files.update({'index.html': (SOURCE / 'src-init/index.html').read_text(),
                  'index.scss': (SOURCE / 'src/index.scss').read_text()})
    return {'files': files, 'compiler': (HERE / 'compiler.js').read_text(),
            'plan_schema': 'Return {"renderers":{type:className,...}}. Choose the chart types to render from the requirements. Use the exact exported class name for each value. Unknown types are skipped. Source components implement config options including interaction.'}


def materialize(folder, files):
    assets = {'assets/' + k: v for k, v in files_under(SOURCE / 'assets').items()}
    validate_files(files)
    for name in files:
        if name.startswith('.') or name.split('/')[0] in {'node_modules','package.json'} or Path(name).suffix not in {'.js','.mjs','.html','.css','.scss','.json','.svg'}:
            raise ValueError(f'Unsupported website file: {name}')
    write_files(folder, files | assets)
    return source_files(folder)


def message(system, statement):
    return [{'role':'system','content':system}, {'role':'user','content':statement}]


def main():
    if datetime.now(timezone.utc) >= END or (OUT / 'freeze.json').exists():
        raise SystemExit('Stage closed or already initialized')
    if not (FORM / 'generation-complete.json').exists():
        raise SystemExit('Wait for form generation to finish')
    other = totals(FORM / 'budget.sqlite3')
    if (FORM / 'continuation/budget.sqlite3').exists():
        extra = totals(FORM / 'continuation/budget.sqlite3')
        other = {key:round(other[key] + extra[key], 6) for key in ('calls', 'settled_usd', 'exposure_usd', 'unsettled_calls')}
    credits = check_credits(2)
    if not credits['sufficient'] or other['exposure_usd'] + 2 > 3.138999695:
        raise SystemExit('Insufficient authorized and funded exposure')
    calibration = json.loads((OUT / 'calibration.json').read_text())
    assert len(calibration) == 10 and all(ok == (kind == 'reference') for kind, _, ok in calibration)
    rows = inputs()
    init = files_under(SOURCE / 'src-init')
    assets = files_under(SOURCE / 'assets')
    context = ('Vite serves index.html, JS modules and SCSS. Start from these public initial files: ' +
               json.dumps(init) + '\nThese assets are mounted unchanged under assets/ on every candidate: ' +
               json.dumps(assets) + '\nUse public DOM and relative imports. No external packages or network requests.\n')
    supplied = reference()
    cfg = config(True)
    cfg.update(models=[BUILDER, MODEL], provider_order={BUILDER:['OpenAI']}, budget_usd=2, stop_new_requests_usd=2)
    cfg['model_price_caps'][MODEL] = {'prompt': .2, 'completion': .8}
    sources = [*HERE.glob('*.py'), HERE / 'compiler.js', HERE / 'PROTOCOL.md', SOURCE / 'tasks.yml',
               OUT / 'calibration.json', RUNTIME / 'package-lock.json', *HARNESS.glob('*.js'),
               *(p for p in (HARNESS / 'test').rglob('*') if p.is_file())]
    for directory in ('assets','src-init','src/common'):
        sources += [p for p in (SOURCE / directory).rglob('*') if p.is_file()]
    sources += [SOURCE / 'src/index.scss', ROOT / 'studies/form_library_sources/run.py',
                ROOT / 'studies/streaming_provider_v2.py', ROOT / 'studies/webbench_draw/browser.py',
                ROOT / 'studies/webbench_draw/server.mjs', ROOT / 'studies/interface_blind/compile.cjs']
    dump(OUT / 'freeze.json', {'cfg':cfg,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in sources},
                               'credits':credits, 'other_stage':other, 'targets':TARGETS})
    dump(OUT / 'reference-package.json', supplied)
    client = StreamingOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', 2, 2))
    client.RATE_LIMIT_TRIES = 1

    def call(model, messages, folder, purpose, limit):
        if datetime.now(timezone.utc) >= END:
            raise BudgetStop('deadline')
        return client.call(model, messages, folder, purpose, max_tokens=limit, seed=SEED)

    messages = message('Design an executable reusable chart library and a data-only composition interface. Choose semantic components and switches. No task IDs, tables of completed pages or executable code in plans. Return JSON.',
        context + json.dumps(rows) + '\nReturn {design,plan_schema,files,compiler,examples}. plan_schema is text documenting the JSON plan. compiler is pure synchronous JavaScript source defining function compile(plan,files) returning a complete file map with index.html. No Node or DOM in compiler. examples is two {description,plan} entries; both should compile and load.')
    ai = None
    build_missing = False
    build_log = []
    for attempt in range(2):
        folder = OUT / 'builder' / str(attempt)
        try:
            raw = call(BUILDER, messages, folder, 'library:svg-chart', 26000)
        except (BudgetStop, ProviderError) as error:
            build_missing = True
            build_log.append({'transport':str(error)})
            break
        try:
            pkg = parse_json(raw)
            if not isinstance(pkg['plan_schema'], str) or len(pkg['examples']) != 2:
                raise ValueError('Need documented schema and two examples')
            for i, ex in enumerate(pkg['examples']):
                files = compile_plan(pkg, ex['plan'])
                if files != compile_plan(pkg, ex['plan']):
                    raise ValueError('Nondeterministic compiler')
                page = folder / f'example-{i}'
                materialize(page, files)
                issues = public_check(page)
                if issues:
                    raise ValueError(str(issues)[:1200])
            ai = pkg
            dump(OUT / 'ai-package.json', ai)
            build_log.append({'frozen':True})
            break
        except (KeyError, TypeError, ValueError) as exc:
            build_log.append({'feedback':str(exc)})
            messages.extend([{'role':'assistant','content':raw}, {'role':'user','content':'Public format/compile/load feedback: '+str(exc)[:1200]+'. Return complete corrected package.'}])
    dump(OUT / 'build-log.json', build_log)

    def candidate(job):
        arm, n = job
        package = {'reference':supplied,'ai':ai,'direct':None}[arm]
        folder = OUT / 'runs' / arm / f'task-{n}'
        record = {'arm':arm, 'task':n, 'generated':False}
        if arm == 'ai' and ai is None:
            return record | {'builder_failed':not build_missing}
        prompt = context + json.dumps(rows[:n])
        if package:
            prompt += '\nFrozen package: ' + json.dumps(package)
        messages = message('Implement all requirements so far. Return only a JSON plan matching the frozen interface.' if package else
                           'Implement all requirements so far. Return only JSON {"files":{relativePath:source,...}} for the complete page.', prompt)
        try:
            raw = call(MODEL, messages, folder / 'call', arm, 8192)
            record['generated'] = True
            parsed = parse_json(raw)
            files = compile_plan(package, parsed) if package else parsed['files']
            record['files'] = materialize(folder / 'page', files)
        except (ValueError, KeyError, TypeError, ProviderError, BudgetStop) as exc:
            record['error'] = str(exc)[:1200]
        dump(folder / 'record.json', record)
        return record

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(candidate, [(arm, n) for n in TARGETS for arm in ARMS]))
    fixed = {Path(k).stem.removesuffix('Chart').lower():Path(k).stem for k in supplied['files'] if k.endswith('Chart.js') and Path(k).stem != 'Chart'}
    page = OUT / 'fixed-reference'
    materialize(page, compile_plan(supplied, {'renderers':fixed}))
    dump(OUT / 'generation-complete.json', records)
    def evaluate(record):
        arm, n = record['arm'], record['task']
        passed = False if record['generated'] or record.get('builder_failed') else None
        if record.get('files'):
            page = OUT / 'runs' / arm / f'task-{n}' / 'page'
            assert record['files'] == source_files(page)
            passed = grade(arm, n, page)
        return {'arm':arm,'task':n,'passed':passed}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(evaluate, records))
        control = list(pool.map(lambda n:grade('fixed-reference', n, page), TARGETS))
    dump(OUT / 'results.json', {'rows':results,'fixed_reference':control,'ledger':totals(OUT / 'budget.sqlite3')})


if __name__ == '__main__':
    main()
