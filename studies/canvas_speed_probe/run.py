"""Intervene on frozen plans and measure the public keyboard acceleration response."""
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright
from studies.canvas_interface_probe.run import variants
from studies.interface_blind.core import Server, browser_env, write_files
from studies.matched_canvas.browser import OUT as BASE, PROJECT, add_assets
from studies.study_io import ROOT, digest, dump, read, sha
from studies.webbench_expand.core import compile_plan

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/canvas-speed-probe-20261118'
RESULT = ROOT/'studies/results/canvas-speed-probe-20261118.json'
STAGES = ('canvas-capacity-20261118','canvas-sonnet-20261118')
STATE = '''() => {
 const pipes=window.store?.pipes;
 return Array.isArray(pipes) && Number.isFinite(pipes[0]?.x) ? pipes[0].x : null;
}'''


def trace(browser,url,seed,key):
    page = browser.new_page(viewport={'width':800,'height':800})
    try:
        page.add_init_script(f'let state={seed}; Math.random=()=>((state=(Math.imul(1664525,state)+1013904223)>>>0)/4294967296);')
        page.clock.install(time=1700000000000)
        page.clock.pause_at(1700000001000)
        page.goto(url)
        page.clock.run_for(250)
        canvas = page.locator('canvas').first
        if not canvas.count():
            return [None,None]
        canvas.click(force=True,timeout=4000)
        page.clock.run_for(320)
        before = page.evaluate(STATE)
        page.keyboard.down(key)
        page.clock.run_for(96)
        after = page.evaluate(STATE)
        page.keyboard.up(key)
        return [before,after]
    finally:
        page.close()


def measure(browser,folder):
    server = Server(folder)
    try:
        observations = []
        for seed in (1,2,3):
            keys = {k:trace(browser,f'http://127.0.0.1:{server.port}/index.html',seed,k) for k in ('d','z')}
            response = None
            if all(isinstance(x,(int,float)) and isfinite(x) for pair in keys.values() for x in pair):
                d,z = keys['d'],keys['z']
                if d[0]==z[0] and all(before>=after for before,after in (d,z)):
                    response = (d[0]-d[1])-(z[0]-z[1])
            observations.append({'seed':seed,**keys,'acceleration_px':response})
        return observations
    finally:
        server.close()


def main():
    paths = (HERE/'run.py', HERE/'PROTOCOL.md', ROOT/'studies/canvas_interface_probe/run.py', PROJECT/'tasks.jsonl')
    frozen = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    freeze = OUT/'freeze.json'
    if freeze.exists():
        assert read(freeze)==frozen
    else:
        dump(freeze,frozen)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        controls = OUT/'controls.json'
        if not controls.exists():
            dump(controls,{k:measure(browser,BASE/'controls'/k) for k in ('reference','blank')})
        calibration = read(controls)
        calibrated = (all((r['acceleration_px'] or 0)>0 for r in calibration['reference']) and
                      all(r['acceleration_px'] is None for r in calibration['blank']))
        if not calibrated or not all((ROOT/'artifacts'/s/'generated.json').exists() for s in STAGES):
            print('Calibration',calibrated,calibration)
            return
        cache,libraries = {},{}
        for stage in STAGES:
            for rep in (1,2):
                key = f'{stage}/plan-{rep}'
                package_path = ROOT/'artifacts'/key/'prepare/frozen.json'
                if not package_path.exists():
                    libraries[key] = {'available':False}
                    continue
                package = read(package_path)
                rows = {}
                for label,plan in variants(package):
                    try:
                        files = compile_plan(package,plan)
                    except (TypeError,KeyError,ValueError) as exc:
                        rows[label] = {'invalid':str(exc)}
                        continue
                    identity = digest(files)
                    if identity not in cache:
                        with TemporaryDirectory() as tmp:
                            page = Path(tmp)
                            write_files(page,files)
                            add_assets(page)
                            cache[identity] = measure(browser,page)
                    rows[label] = {'source_digest':identity,'values':[r['acceleration_px'] for r in cache[identity]]}
                baseline = rows['example-0']['values']
                witnesses = {}
                for label,row in rows.items():
                    values = row.get('values',[])
                    if label.startswith('field/') and len(values)==3 and None not in baseline+values:
                        delta = [a-b for a,b in zip(values,baseline)]
                        if all(v>=2 for v in delta) or all(v<=-2 for v in delta):
                            witnesses[label] = delta
                libraries[key] = {'available':True,'package_sha256':sha(package_path),'rows':rows,'witnesses':witnesses}
        dump(OUT/'traces.json',cache)
        dump(RESULT,{'protocol_inputs_sha256':frozen,'calibration':calibration,'traces_sha256':sha(OUT/'traces.json'),
                     'libraries':libraries,'new_api_cost_usd':0})
        browser.close()


if __name__ == '__main__':
    main()
