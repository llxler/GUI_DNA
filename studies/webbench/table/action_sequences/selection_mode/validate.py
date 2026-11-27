"""Evaluate sealed table pages on two new orders of public actions."""
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser


CASES = {
    'successive_edits': [
        ('click', 2, 1, False), ('Enter', 2, 1, True), ('Escape', 2, 1, False),
        ('click', 1, 2, False), ('Enter', 1, 2, True), ('Escape', 1, 2, False)],
    'arrow_cycle': [
        ('click', 2, 1, False), ('ArrowUp', 1, 1, False), ('ArrowLeft', 1, 0, False),
        ('ArrowDown', 2, 0, False), ('ArrowRight', 2, 1, False)],
}
STATE = """table => {
  const at = c => [c.parentElement.rowIndex, c.cellIndex];
  return {
    selected: [...table.querySelectorAll('.selected')].filter(c => c.matches('td,th')).map(at),
    editing: [...table.querySelectorAll('td,th')].filter(c => c.isContentEditable).map(at)
  };
}"""


def evaluate(directory: Path):
    result = {}
    with browser.serve('table', directory) as url, sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
        for name, actions in CASES.items():
            page = engine.new_page(service_workers='block')
            page.set_default_timeout(1600)
            page.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).netloc == urlsplit(url).netloc else route.abort())
            steps = []
            try:
                page.goto(url + '/index.html', wait_until='load', timeout=5500)
                table = page.locator('table').first
                for key, row, col, editing in actions:
                    if key == 'click':
                        table.locator('tr').nth(row).locator(':scope > :is(th,td)').nth(col).click()
                    else:
                        page.keyboard.press(key)
                    state = table.evaluate(STATE)
                    expected = {'selected': [[row, col]], 'editing': [[row, col]] if editing else []}
                    steps.append(dict(action=key, expected=expected, observed=state, passed=state == expected))
            except Exception as error:
                steps.append(dict(action='browser', error=str(error).splitlines()[0][:180], passed=False))
            finally:
                page.close()
            result[name] = dict(passed=len(steps) == len(actions) and all(s['passed'] for s in steps), steps=steps)
    return result
