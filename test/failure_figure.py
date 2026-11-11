"""Reproduce the official task-4 setup on two saved Mistral pages and capture it.

uv run --with matplotlib python -m test.failure_figure
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from test.todomvc_dna.evaluate import Server, browser_env

ROOT = Path(__file__).resolve().parents[1]


def main():
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    out = ROOT / 'artifacts/failure-figure'
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'artifacts/webbench-dna-6/runs/mistralai__mistral-small-3.2-24b-instruct'
    evidence = {'model': 'mistralai/mistral-small-3.2-24b-instruct', 'task': 'task-4',
                'actions': ['click file', 'click dir', 'click file', 'click dir'],
                'viewport': {'width': 900, 'height': 520},
                'clip': {'x': 0, 'y': 0, 'width': 360, 'height': 210}, 'pages': {}}
    server = Server(source)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(env=browser_env())
            for arm in ['free', 'dna']:
                folder = source / arm / 'task-4'
                rec = json.loads((folder / 'record.json').read_text())
                html = folder / rec['versions'][-1] / 'index.html'
                page = browser.new_page(viewport=evidence['viewport'])
                page.goto(server.url(html))
                for name in ['file', 'dir', 'file', 'dir']:
                    page.locator('.tools').get_by_role('button', name=name, exact=True).click()
                page.wait_for_timeout(200)
                nested_files = page.locator('.entries > .dir:nth-child(2) > .dir-content > .file:nth-child(1)')
                nested_dirs = page.locator('.entries > .dir:nth-child(2) > .dir-content > .dir:nth-child(2)')
                passes = nested_files.count() == 1 and nested_dirs.count() == 1 and nested_files.is_visible() and nested_dirs.is_visible()
                page.screenshot(path=str(out / f'{arm}.png'), clip=evidence['clip'])
                evidence['pages'][arm] = {'source': str(html.relative_to(ROOT)), 'sha256': hashlib.sha256(html.read_bytes()).hexdigest(),
                                         'nested_file_and_dir_visible': passes, 'entries_text': page.locator('.entries').inner_text()}
                page.close()
            browser.close()
    finally:
        server.close()
    assert evidence['pages']['dna']['nested_file_and_dir_visible']
    assert not evidence['pages']['free']['nested_file_and_dir_visible']
    (out / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    figure, axes = plt.subplots(1, 2, figsize=(12, 3.8))
    for axis, arm, title in zip(axes, ['free', 'dna'], ['Free code: nesting fails', 'GUI-DNA: nesting passes']):
        axis.imshow(mpimg.imread(out / f'{arm}.png'))
        axis.set_title(title, fontsize=12)
        axis.axis('off')
    figure.tight_layout()
    target = ROOT / 'DNA_latex/figures/failure-case.pdf'
    figure.savefig(target, bbox_inches='tight')
    figure.savefig(out / 'preview.png', dpi=160, bbox_inches='tight')
    print(target)


if __name__ == '__main__':
    main()
