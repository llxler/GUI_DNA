"""Probe two public table operations under one-field plan interventions."""
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright
from studies.canvas_interface_probe.run import variants
from studies.interface_blind.core import Server, browser_env, write_files
from studies.study_io import ROOT, UPSTREAM, digest, dump, read, sha, source_files
from studies.webbench_expand.core import BUILDERS, compile_plan, slug

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-behavior-probe-20261118'
RESULT = ROOT / 'studies/results/table-behavior-probe-20261118.json'
PROJECT = UPSTREAM / 'projects/table'
OPERATIONS = ('delete_row', 'clear_cell')


def snapshot(page):
    return page.locator('.table tbody tr').evaluate_all(
        '(rows) => rows.map(r => Array.from(r.cells, c => c.textContent.trim()))')


def observe(browser, url, operation, active):
    page = browser.new_page()
    try:
        page.goto(url)
        before = snapshot(page)
        if not before or not before[0] or not before[0][0]:
            return {'before': before, 'after': None, 'response': None}
        cell = page.locator('.table tbody td').first
        if operation == 'clear_cell':
            cell.click()
            page.keyboard.press('Delete' if active else 'Shift')
            expected = [['', *before[0][1:]], *before[1:]]
        else:
            cell.click(button='right')
            item = page.locator('.menu-item-delete-row').first
            if active:
                if item.is_visible() and item.is_enabled():
                    item.click()
            else:
                page.keyboard.press('Escape')
            expected = before[1:]
        after = snapshot(page)
        return {'before': before, 'after': after, 'response': after == (expected if active else before)}
    finally:
        page.close()


def measure(browser, path):
    server = Server(path)
    try:
        url = f'http://127.0.0.1:{server.port}/index.html'
        records = {}
        for op in OPERATIONS:
            samples = []
            for _ in range(2):
                action, sham = [observe(browser, url, op, active) for active in (True, False)]
                values = [action['response'], sham['response']]
                matched_start = action['before'] == sham['before']
                samples.append({'action': action, 'sham': sham,
                    'response': all(values) if None not in values and matched_start else None})
            records[op] = samples
        return records
    finally:
        server.close()


def main():
    packages = {b: ROOT/'artifacts/webbench-expand-build/libraries/table'/slug(b)/'package.json' for b in BUILDERS}
    frozen = {str(p.relative_to(ROOT)): sha(p) for p in [
        HERE/'PROTOCOL.md', HERE/'run.py', PROJECT/'tasks.jsonl', *packages.values(),
        ROOT/'studies/canvas_interface_probe/run.py', ROOT/'studies/webbench_expand/core.py',
        ROOT/'studies/webbench_expand/schema.py', ROOT/'studies/interface_blind/core.py',
        ROOT/'studies/interface_blind/compile.cjs']}
    freeze = OUT/'freeze.json'
    if freeze.exists():
        assert read(freeze) == frozen
    else:
        dump(freeze, frozen)
    blank = OUT/'blank'
    write_files(blank, {'index.html':'<!doctype html><title>Blank</title>'})
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        controls = {k:measure(browser,p) for k,p in [('reference', PROJECT/'src'), ('blank', blank)]}
        for op in OPERATIONS:
            assert [r['response'] for r in controls['reference'][op]] == [True,True], (op,controls)
            assert [r['response'] for r in controls['blank'][op]] == [None,None]
        observations = {}
        libraries = {}
        for builder, package_path in packages.items():
            package = read(package_path)
            rows = {}
            for label, plan in variants(package):
                try:
                    files = compile_plan(package,plan)
                except (ValueError,TypeError,KeyError) as err:
                    rows[label] = {'plan':plan,'invalid':str(err)}
                    continue
                key = digest(files)
                if key not in observations:
                    with TemporaryDirectory() as tmp:
                        write_files(Path(tmp),files)
                        observations[key] = measure(browser,Path(tmp))
                rows[label] = {'plan':plan,'source_digest':key,'responses':{
                    op:[r['response'] for r in observations[key][op]] for op in OPERATIONS}}
            baseline = rows['example-0']['responses']
            witnesses = {op:[] for op in OPERATIONS}
            for label,row in rows.items():
                if not label.startswith('field/') or 'responses' not in row:
                    continue
                for op, values in row['responses'].items():
                    if (baseline[op],values) in [([True,True],[False,False]),([False,False],[True,True])]:
                        witnesses[op].append(label)
            libraries[builder] = {'package_sha256':sha(package_path),'variants':rows,'witnesses':witnesses}
        raw = OUT/'observations.json'
        dump(raw, {'controls':controls,'pages':observations})
        dump(RESULT, {'project':'table','official_scores_used':False,'new_api_cost_usd':0,
            'protocol_and_inputs':frozen, 'reference_files':source_files(PROJECT/'src'),
            'browser_version':browser.version,'observations_sha256':sha(raw),
            'controls':{k:{op:[r['response'] for r in rows] for op,rows in v.items()} for k,v in controls.items()},
            'libraries':libraries})
        browser.close()


if __name__ == '__main__':
    main()
