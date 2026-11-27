"""Check the four frozen HTML fragments locally without grading any benchmark operation."""
from argparse import ArgumentParser

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT, dump, read, sha
from ...functional_pilot import pages
from .run import HERE, PAGES

INSPECT = """() => ({
    visible_text_characters: document.body.innerText.length,
    visible_buttons: [...document.querySelectorAll('button')].filter(x => x.getClientRects().length).length,
    inline_classic_scripts: [...document.scripts].filter(s => !s.src && (!s.type || s.type === 'text/javascript'))
        .map(s => { try { new Function(s.textContent); return 'parses' } catch (e) { return e.name } })
})"""


def inspect():
    results = {}
    with browser.browser_slot(), sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
        version = engine.version
        for batch, record in read(PAGES)['records'].items():
            results[batch] = []
            for attempt in record['attempts']:
                path = ROOT/attempt['html']
                assert sha(path) == attempt['sha256']
                with pages.local_tab(engine, path.read_text()) as page:
                    results[batch].append(dict(attempt=attempt['attempt'], **page.evaluate(INSPECT)))
    return dict(candidates=sha(PAGES), chromium=version, observations=results)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = inspect()
    output = HERE/'browser.json'
    if args.write:
        dump(output, result)
    assert read(output) == result
    print('Verified visible DOM and inline JavaScript syntax in all four original replies.')
