"""Audit reference-prefix history without modifying the historical generator or scores."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from test.library_repair.run import now
from test.library_repair.core import ROOT, read, dump, digest
from test.webbench_dna import domain, evaluate
from test.webbench_dna.library import library
from test.webbench_dna.clean_prefix import clean_page

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/prefix-history-audit-20261114'


def prepare():
    assert not (OUT / 'inputs.json').exists()
    harness = OUT / 'harness'
    shutil.copytree(evaluate.HARNESS / 'dom1-tests', harness / 'dom1-tests')
    shutil.copy2(evaluate.HARNESS / 'playwright.config.js', harness / 'playwright.config.js')
    (harness / 'node_modules').symlink_to(evaluate.HARNESS / 'node_modules', target_is_directory=True)
    lib, rows = library(), []
    for task in domain.tasks():
        k = task['k'] - 1
        html = clean_page(task, lib)
        page = OUT / 'pages' / f'prefix-{k}'
        page.mkdir(parents=True)
        (page / 'index.html').write_text(html)
        specs = [f'task-{i}' for i in range(1, k + 1)] if k else ['init']
        rows.append({'prefix': k, 'next_task': task['id'], 'specs': specs,
                     'page': str(page.relative_to(ROOT)), 'page_sha256': hashlib.sha256(html.encode()).hexdigest()})
    assert sum(len(r['specs']) for r in rows) == 191
    dump(OUT / 'inputs.json', {'rows': rows, 'library_sha256': lib['sha256'],
        'playwright_version': read(evaluate.HARNESS / 'node_modules/@playwright/test/package.json')['version']})
    sources = [HERE / 'run.py', HERE / 'PROTOCOL.md', OUT / 'inputs.json', harness / 'playwright.config.js']
    sources += list((harness / 'dom1-tests').rglob('*.js'))
    sources += [ROOT / f'test/webbench_dna/{n}' for n in ('domain.py', 'library.py', 'clean_prefix.py', 'shell.html', 'evaluate.py', 'run.py')]
    sources += [ROOT / 'test/todomvc_dna/evaluate.py', evaluate.HARNESS / 'package-lock.json']
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}})
    print('Frozen 20 prefixes and 191 page/spec pairs', flush=True)


def verify():
    for name, sha in read(OUT / 'snapshot.json')['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    inputs = read(OUT / 'inputs.json')
    for row in inputs['rows']:
        assert hashlib.sha256((ROOT / row['page'] / 'index.html').read_bytes()).hexdigest() == row['page_sha256']
    return inputs


def score():
    inputs = verify()
    start = OUT / 'grading-started.json'
    if not start.exists():
        dump(start, {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    assert read(start)['inputs_sha256'] == digest(inputs)
    assert read(OUT / 'snapshot.json')['frozen_utc'] <= read(start)['started_utc']
    def one(row):
        target = OUT / 'scores' / f'prefix-{row["prefix"]}'
        if (target / 'receipt.json').exists():
            return
        target.mkdir(parents=True, exist_ok=True)
        report = target / 'report.json'
        assert not report.exists(), 'Preserve any interrupted report; do not silently rerun'
        server = evaluate.Server(ROOT / row['page'])
        try:
            env = {**evaluate.browser_env(), 'REPORT_FILE': str(report),
                   'CANDIDATE_URL': f'http://127.0.0.1:{server.port}', 'CI': '1', 'WORKERS': '1'}
            command = ['node', str(evaluate.HARNESS / 'node_modules/@playwright/test/cli.js'), 'test',
                '--config', 'playwright.config.js', '--workers=1', '--output', str(target / 'playwright-output')]
            command += [f'dom1-tests/{name}.spec.js' for name in row['specs']]
            done = subprocess.run(command, cwd=OUT / 'harness', env=env, capture_output=True, text=True, timeout=900)
        finally:
            server.close()
        (target / 'runner.txt').write_text(done.stdout + done.stderr)
        assert report.exists(), 'No browser report'
        payload = read(report)
        assert not payload.get('errors'), payload.get('errors')
        dump(target / 'receipt.json', {'exit_code': done.returncode,
             'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(), 'finished_utc': now()})
        print('prefix', row['prefix'], 'exit', done.returncode, flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, inputs['rows']))
    dump(OUT / 'evaluation-complete.json', {'finished_utc': now(), 'inputs_sha256': digest(inputs)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'score'])
    {'prepare': prepare, 'score': score}[parser.parse_args().phase]()
