"""Use the pinned upstream browser adapter in a new output directory."""
import shutil
from concurrent.futures import ThreadPoolExecutor

from studies.svg_chart_sources import browser as upstream
from studies.study_io import dump, read

OUT = upstream.ROOT / 'artifacts/svg-chart-interfaces-20261123'
SOURCE = upstream.SOURCE
TARGETS = tuple(range(1, 21))


def use_harness():
    upstream.OUT = OUT
    upstream.HARNESS = OUT / 'harness'
    upstream.harness()


def score(name, task, page):
    saved = OUT / 'scores' / name / f'task-{task}' / 'score.json'
    if saved.exists():
        return read(saved)['passed']
    return upstream.grade(name, task, page)


def calibrate():
    use_harness()
    pages = OUT / 'calibration'
    for name, origin in [('reference', 'src'), ('blank', None)]:
        page = pages / name
        if not page.exists():
            if origin:
                shutil.copytree(SOURCE / origin, page)
            else:
                page.mkdir(parents=True)
                (page / 'index.html').write_text('<!doctype html><title>Blank</title>')
                shutil.copytree(SOURCE / 'assets', page / 'assets')
    def run(job):
        name, task = job
        return [name, task, score('calibration-' + name, task, pages / name)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run, [(name, n) for n in TARGETS for name in ('reference', 'blank')]))
    dump(OUT / 'calibration.json', rows)


if __name__ == '__main__':
    calibrate()
