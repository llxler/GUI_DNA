"""Build candidate pages, run the public smoke check (feedback) and the official hidden Playwright spec (grading)."""
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import re
import subprocess
import sysconfig
import threading
from pathlib import Path

from .domain import HERE, ROOT, TEST_FEATURES, hidden_subset

HARNESS = HERE / 'harness'
SHELL = HERE / 'shell.html'
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def browser_env():
    """Same trick as the round-3 evaluator: unprivileged libnspr4/libnss3 unpacked under .browser-deps/."""
    env = dict(os.environ)
    libs = ROOT / '.browser-deps/usr/lib' / (sysconfig.get_config_var('MULTIARCH') or 'x86_64-linux-gnu')
    if libs.exists():
        env['LD_LIBRARY_PATH'] = str(libs) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env.pop('OPENROUTER_API_KEY', None)
    return env


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write_app(code, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    page = SHELL.read_text().replace('/*__CANDIDATE__*/', code.replace('</script', '<\\/script'))
    (folder / 'index.html').write_text(page)
    (folder / 'candidate.js').write_text(code)
    return folder / 'index.html'


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Server:
    """One static server for a run; candidate pages are addressed by their path below `root`."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        handler = functools.partial(_Quiet, directory=str(self.root))
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, page):
        return f'http://127.0.0.1:{self.port}/{Path(page).resolve().relative_to(self.root).as_posix()}'

    def close(self):
        self.httpd.shutdown()


def public_check(url, timeout_ms=5000):
    """Public feedback only: page errors and one add-a-todo smoke interaction. Never touches the hidden spec."""
    from playwright.sync_api import sync_playwright
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(env=browser_env())
        page = browser.new_page()
        page.on('pageerror', lambda err: problems.append(f'page error: {err}'))
        page.on('console', lambda msg: problems.append(f'console {msg.type}: {msg.text}') if msg.type == 'error' else None)
        try:
            page.goto(url, timeout=timeout_ms)
            page.wait_for_timeout(100)
            shown = page.locator('#error').text_content() or ''
            if shown.strip():
                problems.append('shell reported: ' + shown.strip()[:600])
            box = page.get_by_placeholder('What needs to be done?')
            box.fill('buy milk')
            box.press('Enter')
            page.wait_for_timeout(100)
            titles = page.get_by_test_id('todo-title').all_text_contents()
            if titles != ['buy milk']:
                problems.append(f'after adding "buy milk" the list shows {titles!r}; expected ["buy milk"]')
            stored = page.evaluate("() => localStorage.getItem('react-todos')")
            try:
                items = json.loads(stored) if stored else None
            except ValueError:
                items = None
            if not isinstance(items, list) or len(items) != 1:
                problems.append(f"localStorage['react-todos'] after one add is {stored!r}; expected a JSON array with one todo")
        except Exception as error:  # noqa: BLE001 - any failure is public feedback
            problems.append(f'smoke interaction failed: {type(error).__name__}: {str(error)[:300]}')
        finally:
            browser.close()
    seen, unique = set(), []
    for item in problems:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def run_official(url, report, timeout=300):
    """Run the official spec against `url`; return {(describe, title): 'passed'|'failed'|'timedOut'|'skipped'}."""
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    env = {**browser_env(), 'CANDIDATE_URL': url, 'REPORT_FILE': str(report), 'CI': '1'}
    try:
        done = subprocess.run(['npx', 'playwright', 'test', '--config', 'playwright.config.ts'], cwd=HARNESS, env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {key: 'timedOut' for key in TEST_FEATURES}, 'harness timeout'
    if not report.exists():
        return {key: 'failed' for key in TEST_FEATURES}, ANSI.sub('', (done.stderr or done.stdout)[-1500:])
    data = json.loads(report.read_text())
    results = {}

    def walk(suite, path):
        for spec in suite.get('specs', []):
            statuses = [r['status'] for t in spec.get('tests', []) for r in t.get('results', [])]
            status = 'passed' if statuses and all(s == 'passed' for s in statuses) else (statuses[-1] if statuses else 'failed')
            results[(path[-1] if path else '', spec['title'])] = status
        for child in suite.get('suites', []):
            walk(child, path + [child['title']])
    for suite in data.get('suites', []):
        walk(suite, [])
    return results, ''


def grade(url, report, features):
    """Hidden grade for one candidate: pass counts over the official tests the task enables."""
    results, note = run_official(url, report)
    subset = hidden_subset(features)
    rows = {f'{d} › {t}': results.get((d, t), 'missing') for d, t in subset}
    passed = sum(v == 'passed' for v in rows.values())
    return {'passed': passed, 'total': len(subset), 'all_passed': passed == len(subset) and len(subset) > 0, 'tests': rows,
            'all_official_passed': sum(v == 'passed' for v in results.values()), 'note': note}
