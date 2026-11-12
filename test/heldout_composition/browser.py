"""Generic browser action/observation runner; no hidden fixture imports."""
from pathlib import Path
import time

from playwright.sync_api import sync_playwright
from test.interface_blind.core import Server, browser_env


def observed(page, project):
    if project == 'calculator':
        return {'total': int(page.locator('#total').inner_text()),
                'memory': int(page.locator('#memory').inner_text()),
                'entry': page.locator('#entry').input_value(),
                'history': [int(x) for x in page.locator('[data-history-index]').all_text_contents()]}
    rows = page.locator('[data-row-id]').evaluate_all('nodes => nodes.map(n => [n.dataset.rowId, n.querySelector(".row-value").textContent.trim()])')
    selected = page.locator('[data-row-id][aria-selected="true"]').evaluate_all('nodes => nodes.map(n => n.dataset.rowId)')
    if len(selected) > 1:
        raise ValueError('Multiple selected rows')
    text = page.locator('#clipboard').inner_text().strip()
    return {'rows': [[key, int(value)] for key, value in rows],
            'selected': selected[0] if selected else None, 'clipboard': None if text == 'empty' else int(text)}


def perform(page, project, action):
    name, *args = action
    if name == 'enter':
        page.locator('#entry').fill(str(args[0]))
    elif name == 'history':
        target = page.locator(f'[data-history-index="{args[0]}"]')
        if target.count():
            target.click()
    elif name == 'select':
        target = page.locator(f'[data-row-id="{args[0]}"]')
        if target.count():
            target.locator('.row-value').click()
    elif name == 'edit':
        page.locator('#edit-value').fill(str(args[0]))
        page.locator('#apply').click()
    else:
        page.locator('#' + name).click()


def evaluate(folder, project, cases):
    server = Server(Path(folder).resolve())
    passed, total_steps, failures = 0, 0, []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(env=browser_env())
            browser_version = browser.version
            try:
                for i, case in enumerate(cases):
                    context = browser.new_context()
                    page = context.new_page()
                    page.set_default_timeout(1500)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    try:
                        page.goto(f'http://127.0.0.1:{server.port}/index.html', timeout=10000)
                        checks = [{'action': None, 'expected': case['initial']}, *case['steps']]
                        for j, check in enumerate(checks):
                            if check['action']:
                                perform(page, project, check['action'])
                            deadline = time.monotonic() + 1
                            while True:
                                actual = observed(page, project)
                                if actual == check['expected'] or time.monotonic() >= deadline:
                                    break
                                page.wait_for_timeout(20)
                            total_steps += 1
                            if actual != check['expected'] or errors:
                                failures.append({'case': i, 'step': j, 'action': check['action'],
                                                 'expected': check['expected'], 'actual': actual,
                                                 'page_errors': errors[:3]})
                                break
                        else:
                            passed += 1
                    except Exception as error:
                        failures.append({'case': i, 'error': type(error).__name__, 'message': str(error)[:900], 'page_errors': errors[:3]})
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        server.close()
    return {'all_passed': passed == len(cases), 'cases_passed': passed, 'cases_total': len(cases),
            'checked_steps': total_steps, 'failures': failures, 'browser_version': browser_version}
