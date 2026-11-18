"""Measure key-triggered game state across frozen canvas plan variants."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright
from studies.interface_blind.core import Server, browser_env, write_files
from studies.webbench_expand.core import compile_plan
from studies.webbench_expand.schema import validate
from studies.study_io import ROOT, digest, read, dump, sha
from studies.matched_canvas.browser import OUT as MAIN, add_assets

OUT = ROOT / 'artifacts/canvas-interface-probe-20261118'
HERE = Path(__file__).resolve().parent
COUNT = '() => Array.isArray(window.store?.bullets) ? window.store.bullets.length : null'


def observe(browser, url, seed, key):
    page = browser.new_page(viewport={'width':800, 'height':800})
    try:
        page.add_init_script(f'let state={seed}; Math.random=()=>((state=(Math.imul(1664525,state)+1013904223)>>>0)/4294967296);')
        page.clock.install(time=1700000000000)
        page.clock.pause_at(1700000001000)
        page.goto(url + '/index.html')
        page.clock.run_for(250)
        canvas = page.locator('canvas').first
        if not canvas.count():
            return {'before': None, 'after': None, 'canvas': False}
        canvas.click(force=True, timeout=4000)
        page.clock.run_for(320)
        before = page.evaluate(COUNT)
        page.keyboard.press(key)
        page.clock.run_for(32)
        return {'before':before, 'after':page.evaluate(COUNT), 'canvas':True}
    finally:
        page.close()


def probe(browser, directory):
    server = Server(directory)
    try:
        observations = []
        for seed in (1,2,3):
            keys = {key:observe(browser, f'http://127.0.0.1:{server.port}',seed,key) for key in ('k','z')}
            response = None
            if all(v[x] is not None for v in keys.values() for x in ('before','after')):
                response = keys['k']['after'] > keys['k']['before'] and keys['z']['after'] <= keys['z']['before']
            observations.append({'seed':seed, **keys, 'response':response})
        return observations
    finally:
        server.close()


def variants(package):
    first, last = [example['plan'] for example in package['examples']]
    yield 'example-0', first
    yield 'example-1', last
    for key in sorted(first.keys() | last.keys()):
        if (key in first) == (key in last) and first.get(key) == last.get(key):
            continue
        plan = deepcopy(first)
        if key in last:
            plan[key] = last[key]
        else:
            del plan[key]
        yield 'field/' + key, plan


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen = {p.name:sha(p) for p in (HERE/'run.py', HERE/'PROTOCOL.md')}
    if (OUT/'freeze.json').exists():
        assert read(OUT/'freeze.json') == frozen
    else:
        dump(OUT/'freeze.json',frozen)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        controls = OUT/'controls.json'
        if not controls.exists():
            dump(controls,{name:probe(browser,MAIN/'controls'/name) for name in ('reference','blank')})
        calibration = read(controls)
        assert all(v['response'] is True for v in calibration['reference'])
        assert all(v['response'] is None for v in calibration['blank'])
        if not (MAIN/'generated.json').exists():
            return
        libraries = {}
        cache = {}
        for rep in (1,2):
            package_file = MAIN/f'plan-{rep}/prepare/frozen.json'
            if not package_file.exists():
                libraries[rep] = {'status':'unavailable'}
                continue
            package = read(package_file)
            rows = []
            for label, plan in variants(package):
                try:
                    validate(package['plan_schema'], plan)
                    files = compile_plan(package,plan)
                except (ValueError, TypeError, KeyError) as exc:
                    rows.append({'label':label, 'plan':plan, 'invalid':str(exc)})
                    continue
                key = digest(files)
                if key not in cache:
                    with TemporaryDirectory() as tmp:
                        path = Path(tmp)
                        write_files(path,files)
                        add_assets(path)
                        cache[key] = probe(browser,path)
                rows.append({'label':label,'plan':plan,'source_digest':key,
                             'responses':[v['response'] for v in cache[key]]})
            libraries[rep] = {'package_sha256':sha(package_file), 'rows':rows}
        dump(OUT/'results.json', {'controls':calibration,'libraries':libraries,'observations':cache,'freeze':frozen})
        browser.close()


if __name__ == '__main__':
    main()
