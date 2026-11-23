"""Freeze and generate independent Web-Bench SVG Chart candidates."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.form_library_sources.run import MODEL
from studies.interface_blind.core import compile_plan, config
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, dump, now, read, sha, source_files
from studies.svg_chart_sources.run import files_under, inputs, materialize, message, reference

from .browser import OUT, SOURCE, TARGETS, score, use_harness

HERE = Path(__file__).resolve().parent
OLD = ROOT / 'artifacts/svg-chart-sources-20261121'
ARMS = ('direct', 'reference_typed', 'ai', 'reference_prose')
CAP = 1.30
DEADLINE = datetime(2026, 11, 23, 6, 16, tzinfo=timezone.utc)
SEED = 20261123


def inputs_for_run():
    starter = files_under(SOURCE / 'src-init')
    assets = files_under(SOURCE / 'assets')
    original = read(OLD / 'reference-package.json')
    assert original == reference()
    types = sorted(set(re.findall(r"\btype:\s*'([a-z]+)'", assets['data.js'])))
    classes = sorted(Path(k).stem for k in original['files'] if re.fullmatch(r'common/\w+Chart\.js', k))
    assert types and classes
    schema = (original['plan_schema'] + '\nThe keys of renderers are values of config.type in assets/data.js. '
              'The keys identifying individual samples in configs are a separate field. Allowed renderer keys: '
              + json.dumps(types) + '. Allowed renderer class values: ' + json.dumps(classes)
              + '. Select entries for the requested behavior.')
    return starter, assets, {'reference_prose': original, 'reference_typed': original | {'plan_schema': schema},
                             'ai': read(OLD / 'ai-package.json')}


def messages(arm, task, data):
    starter, assets, packages = data
    prefix = ('Vite serves index.html, JavaScript modules and SCSS. Public starter files: '
              + json.dumps(starter) + '\nShared read-only public assets: ' + json.dumps(assets)
              + '\nUse relative imports. No external packages or network requests. Public requirements so far:\n'
              + json.dumps(inputs()[:task]))
    if arm == 'direct':
        return message('Implement the requirements in the supplied public starter. Return only JSON '
                       '{"files":{relativePath:fullText,...}} for files you add or replace. Omitted starter files '
                       'are preserved. You may change any starter file.', prefix)
    return message('Implement the requirements. Return only a JSON plan matching the frozen interface.',
                   prefix + '\nFrozen package: ' + json.dumps(packages[arm]))


def check_freeze():
    for path, expected in read(OUT / 'freeze.json')['sha256'].items():
        assert sha(ROOT / path) == expected, path


def freeze():
    if (OUT / 'freeze.json').exists():
        check_freeze()
        return
    cal = read(OUT / 'calibration.json')
    assert {(a, n) for a, n, _ in cal} == {(a, n) for a in ('reference', 'blank') for n in TARGETS}
    assert all(ok == (name == 'reference' or n == 1) for name, n, ok in cal), 'Unexpected calibration outcome'
    starter, assets, packages = data = inputs_for_run()
    cfg = config(True)
    cfg.update(models=[MODEL], provider_order={}, budget_usd=CAP, stop_new_requests_usd=CAP)
    cfg['model_price_caps'][MODEL] = {'prompt': .2, 'completion': .8}
    credits = check_credits(CAP)
    assert credits['sufficient'] and CAP + .90 < 2.588189595
    for arm, pkg in packages.items():
        dump(OUT / 'packages' / (arm + '.json'), pkg)
    fixed = {Path(k).stem.removesuffix('Chart').lower(): Path(k).stem for k in packages['reference_prose']['files']
             if re.fullmatch(r'common/\w+Chart\.js', k)}
    controls = {'starter': starter, 'fixed-renderers': starter | compile_plan(packages['reference_prose'], {'renderers': fixed})}
    for name, files in controls.items():
        materialize(OUT / 'controls' / name, files)
    paths = [*HERE.glob('*.py'), HERE / 'PROTOCOL.md', OUT / 'calibration.json', SOURCE / 'tasks.yml',
             OLD / 'ai-package.json', OLD / 'reference-package.json', ROOT / 'studies/svg_chart_sources/compiler.js',
             ROOT / 'studies/svg_chart_sources/browser.py', ROOT / 'studies/svg_chart_sources/run.py',
             ROOT / 'studies/study_io.py', ROOT / 'studies/webbench_draw/browser.py', ROOT / 'studies/webbench_draw/server.mjs',
             ROOT / 'studies/interface_blind/core.py', ROOT / 'studies/interface_blind/compile.cjs',
             ROOT / 'studies/streaming_provider_v2.py', ROOT / 'studies/provider_ext.py', ROOT / 'src/gui_dna/budget.py',
             ROOT / 'src/gui_dna/provider.py', ROOT / 'studies/form_library_sources/run.py', SOURCE / 'src/index.scss',
             SOURCE / 'playwright.config.js', SOURCE / 'package.json', *list((OUT / 'packages').glob('*.json'))]
    for subdir in ['test', 'src-init', 'assets', 'src/common']:
        paths.extend(p for p in (SOURCE / subdir).rglob('*') if p.is_file())
    for task in TARGETS:
        for arm in ARMS:
            path = OUT / 'prompts' / arm / f'task-{task}.json'
            dump(path, messages(arm, task, data))
            paths.append(path)
    dump(OUT / 'freeze.json', {'frozen_utc': now(), 'config': cfg, 'credits': credits, 'targets': TARGETS, 'arms': ARMS,
         'seed': SEED, 'max_output_tokens': 8192, 'controls': {s: source_files(OUT / 'controls' / s) for s in controls},
         'sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def generate():
    freeze()
    check_freeze()
    if (OUT / 'generation-complete.json').exists():
        raise SystemExit('Generation already frozen')
    cfg = read(OUT / 'freeze.json')['config']
    client = StreamingOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', CAP, CAP))
    client.RATE_LIMIT_TRIES = 1
    starter, _, packages = inputs_for_run()

    def one(job):
        arm, task = job
        dest = OUT / 'runs' / arm / f'task-{task}'
        path = dest / 'record.json'
        if path.exists():
            return read(path)
        row = {'arm': arm, 'task': task, 'response': False}
        try:
            if datetime.now(timezone.utc) >= DEADLINE:
                raise BudgetStop('Deadline')
            raw = client.call(MODEL, read(OUT / 'prompts' / arm / f'task-{task}.json'), dest / 'call',
                              f'{arm}:task-{task}', max_tokens=8192, seed=SEED)
            row['response'] = True
            parsed = parse_json(raw)
            files = parsed['files'] if arm == 'direct' else compile_plan(packages[arm], parsed)
            if not isinstance(files, dict):
                raise ValueError('Expected a file map')
            row['files'] = materialize(dest / 'page', starter | files)
        except (ValueError, TypeError, KeyError, BudgetStop, ProviderError) as exc:
            row['error'] = str(exc)[:700]
        dump(path, row)
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(one, [(arm, n) for n in TARGETS for arm in ARMS]))
    dump(OUT / 'generation-complete.json', {'utc': now(), 'rows': rows})


def evaluate():
    check_freeze()
    complete = read(OUT / 'generation-complete.json')
    use_harness()
    def one(row):
        arm, n = row['arm'], row['task']
        passed = False if row['response'] else None
        if row.get('files'):
            page = OUT / 'runs' / arm / f'task-{n}' / 'page'
            assert source_files(page) == row['files']
            passed = score(arm, n, page)
        return {'arm': arm, 'task': n, 'passed': passed}

    def control(job):
        arm, n = job
        page = OUT / 'controls' / arm
        assert source_files(page) == read(OUT / 'freeze.json')['controls'][arm]
        return {'arm': arm, 'task': n, 'passed': score(arm, n, page)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(one, complete['rows']))
        controls = list(pool.map(control, [(a, n) for n in TARGETS for a in ('starter', 'fixed-renderers')]))
    dump(OUT / 'results.json', {'rows': rows, 'controls': controls, 'generated_sha256': sha(OUT / 'generation-complete.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('freeze', 'generate', 'evaluate'))
    args = parser.parse_args()
    {'freeze': freeze, 'generate': generate, 'evaluate': evaluate}[args.phase]()
