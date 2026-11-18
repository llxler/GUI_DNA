"""Test official current files against selective loss of a documented input behavior."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import shutil
from playwright.sync_api import sync_playwright
from studies import browser_jobs
from studies.canvas_interface_probe.run import probe as shoot
from studies.interface_blind.core import Server, browser_env
from studies.study_io import ROOT, UPSTREAM, digest, dump, read, sha, source_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/input-controls-20261118'
RESULT = ROOT / 'studies/results/input-controls-20261118.json'
TARGETS = {'canvas':'task-17','flex':'task-20'}
EVENTS = {'canvas':(['keydown','keypress','keyup'], "event.key.toLowerCase() === 'k'"),
          'flex':(['mousemove','pointermove'], 'event.buttons !== 0')}


def make_page(project, kind):
    upstream = UPSTREAM/'projects'/project
    path = OUT/'pages'/project/kind
    if path.exists():
        return path
    shutil.copytree(upstream/'src',path)
    if (upstream/'assets').exists():
        shutil.copytree(upstream/'assets',path/'assets')
    if kind != 'reference':
        events,condition = EVENTS[project]
        body = '' if kind == 'sham' else 'event.preventDefault(); event.stopImmediatePropagation();'
        handler = f"<script>for(const name of {events!r}) window.addEventListener(name,event=>{{if({condition}){{{body}}}}},true);</script>"
        entry = path/'index.html'
        source,n = re.subn(r'(<head\b[^>]*>)',lambda m:m[1]+handler,entry.read_text(),count=1,flags=re.I)
        assert n == 1
        entry.write_text(source)
    return path


def drag(browser, path):
    server = Server(path)
    results = []
    try:
        for _ in range(2):
            trial = []
            for dy in (-40,40):
                page = browser.new_page(viewport={'width':360,'height':720})
                try:
                    page.goto(f'http://127.0.0.1:{server.port}/index.html')
                    handle = page.locator('.right-drag').first
                    content = page.locator('.content').first
                    box = handle.bounding_box()
                    start = content.bounding_box()['height']
                    x,y = box['x']+box['width']/2,box['y']+box['height']/2
                    page.mouse.move(x,y)
                    page.mouse.down()
                    page.mouse.move(x,y+dy,steps=8)
                    page.mouse.up()
                    page.evaluate('() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))')
                    trial.append({'dy':dy,'before':start,'after':content.bounding_box()['height']})
                finally:
                    page.close()
            results.append({'trials':trial,'response':any(abs(t['after']-t['before']) >= 2 for t in trial)})
        return results
    finally:
        server.close()


def main():
    files = [HERE/'PROTOCOL.md',HERE/'run.py',ROOT/'studies/canvas_interface_probe/run.py',ROOT/'studies/browser_jobs.py']
    for name,target in TARGETS.items():
        project = UPSTREAM/'projects'/name
        files.extend([project/'tasks.jsonl',project/'test/task-4.spec.js',project/'test'/f'{target}.spec.js'])
        files.extend(p for p in (project/'src').rglob('*') if p.is_file())
    frozen = {str(p.relative_to(ROOT)):sha(p) for p in files}
    freeze = OUT/'freeze.json'
    if freeze.exists():
        assert read(freeze) == frozen
    else:
        dump(freeze,frozen)
    browser_jobs.OUT = OUT
    observations = {}
    jobs = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        for project, target in TARGETS.items():
            harness = browser_jobs.prepare_harness('expansion',project)
            for kind in ('reference','sham','blocked'):
                page = make_page(project,kind)
                key = project+'/'+kind
                manifest = source_files(page)
                observations[key] = {'source_digest':digest(manifest),
                    'public_probe':(shoot if project=='canvas' else drag)(browser,page)}
                for task in ('task-4',target):
                    jobs.append((key+'/'+task,{'harness':harness,'runtime':'157','page':str(page.relative_to(ROOT)),
                                               'files':manifest,'specs':[task]}))
        browser.close()
    def grade(job):
        key,data = job
        result = browser_jobs.grade(key,data)
        return key,{'passed':result['all_passed'],'report_sha256':result['report_sha256']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = dict(pool.map(grade,jobs))
    dump(RESULT,{'protocol_sha256':sha(freeze),'new_api_cost_usd':0,'observations':observations,'official':reports})


if __name__ == '__main__':
    main()
