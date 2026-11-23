"""Cross the official chart data with presence of the reference rendering code."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sys

from studies.study_io import ROOT, cases_by_file, dump, now, read, sha, source_files
from studies.svg_chart_sources import browser

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/svg-chart-fixture-20261123'
OUTPUT = ROOT / 'studies/results/svg-chart-fixture-20261123.json'
PAGE = ('reference', 'blank')
DATA = ('upstream', 'single-line')
TARGETS = (1, 2)


def freeze():
    if (OUT / 'freeze.json').exists():
        return
    pages = {}
    for page in PAGE:
        for fixture in DATA:
            arm = page + '-' + fixture
            folder = OUT / 'pages' / arm
            if page == 'reference':
                shutil.copytree(browser.SOURCE / 'src', folder)
            else:
                folder.mkdir(parents=True)
                (folder / 'index.html').write_text('<!doctype html><title>Blank</title>')
                shutil.copytree(browser.SOURCE / 'assets', folder / 'assets')
            file = folder / 'assets/data.js'
            assert sha(file) == sha(browser.SOURCE / 'assets/data.js')
            if fixture == 'single-line':
                with file.open('a') as stream:
                    stream.write("\nfor (const id of Object.keys(configs)) if (id !== 'line') delete configs[id];\n")
            pages[arm] = source_files(folder)
    files = [HERE / 'audit.py', HERE / 'README.md', ROOT / 'studies/svg_chart_sources/browser.py',
             browser.SOURCE / 'test/util/util.js', *(browser.SOURCE / f'test/task-{n}.spec.js' for n in TARGETS),
             browser.SOURCE / 'playwright.config.js', browser.RUNTIME / 'package-lock.json']
    dump(OUT / 'freeze.json', {'utc': now(), 'targets': TARGETS, 'pages': pages,
                               'sha256': {str(p.relative_to(ROOT)): sha(p) for p in files}})


def run():
    freeze()
    browser.OUT = OUT
    browser.HARNESS = OUT / 'harness'
    browser.harness()
    frozen = read(OUT / 'freeze.json')
    def grade(job):
        arm, n = job
        page = OUT / 'pages' / arm
        assert source_files(page) == frozen['pages'][arm]
        if not (OUT / 'scores' / arm / f'task-{n}' / 'score.json').exists():
            browser.grade(arm, n, page)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(grade, [(a, n) for a in frozen['pages'] for n in TARGETS]))


def report():
    frozen = read(OUT / 'freeze.json')
    assert all(sha(ROOT / k) == v for k, v in frozen['sha256'].items())
    rows = []
    for arm, files in frozen['pages'].items():
        assert source_files(OUT / 'pages' / arm) == files
        for n in TARGETS:
            path = OUT / 'scores' / arm / f'task-{n}'
            sc = read(path / 'score.json')
            assert sha(path / 'report.json') == sc['report_sha256']
            tests = cases_by_file(read(path / 'report.json'))[f'task-{n}']
            assert tests and all(t['passed'] for t in tests) == sc['passed']
            rows.append({'page_and_data': arm, 'task': n, **sc})
    return {'project': 'svg-chart', 'phase': 'post-calibration fixture diagnostic', 'api_calls': 0,
            'rows': rows, 'freeze_sha256': sha(OUT / 'freeze.json')}


if __name__ == '__main__':
    if sys.argv[1:] == ['--write']:
        run()
        dump(OUTPUT, report())
    elif sys.argv[1:]:
        raise SystemExit('Use --write to run the controls')
    else:
        assert read(OUTPUT) == report()
    print([(r['page_and_data'], r['task'], r['passed']) for r in report()['rows']])
