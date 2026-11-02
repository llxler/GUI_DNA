"""Candidate pages, public smoke feedback and official per-task grading for the Web-Bench dom1 stage."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from test.todomvc_dna.evaluate import Server, browser_env  # same static server + browser libs trick

from .domain import HERE, ROOT

HARNESS = HERE / 'harness'
SHELL = HERE / 'shell.html'
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write_candidate(folder, html=None, script=None):
    """Either a complete index.html (free arm) or the shell with the compiled script injected (rule / dna)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if html is None:
        html = SHELL.read_text().replace('/*__CANDIDATE__*/', script.replace('</script', '<\\/script'))
        (folder / 'candidate.js').write_text(script)
    (folder / 'index.html').write_text(html)
    return folder


def public_check(folder, timeout_ms=5000):
    """Public feedback only: page / console errors on load and after clicking each tool button once."""
    from playwright.sync_api import sync_playwright
    problems = []
    server = Server(Path(folder).resolve())
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(env=browser_env())
            page = browser.new_page()
            page.on('pageerror', lambda err: problems.append(f'page error: {err}'))
            page.on('console', lambda msg: problems.append(f'console error: {msg.text}') if msg.type == 'error' else None)
            page.on('dialog', lambda d: d.dismiss())
            try:
                page.goto(f'http://127.0.0.1:{server.port}/index.html', timeout=timeout_ms)
                page.wait_for_timeout(100)
                buttons = page.locator('.tools button')
                for i in range(buttons.count()):
                    try:
                        buttons.nth(i).click(timeout=1000)
                        page.wait_for_timeout(50)
                    except Exception as error:  # noqa: BLE001
                        problems.append(f'tool button #{i + 1} could not be clicked: {str(error).splitlines()[0][:200]}')
            except Exception as error:  # noqa: BLE001
                problems.append(f'page failed to load: {type(error).__name__}: {str(error)[:300]}')
            finally:
                browser.close()
    finally:
        server.close()
    seen, unique = set(), []
    for item in problems:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:8]


def run_spec(folder, spec, report, timeout=600):
    """Run one official spec file against the candidate directory; return {title: status} and a note."""
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    server = Server(Path(folder).resolve())
    try:
        env = {**browser_env(), 'CANDIDATE_URL': f'http://127.0.0.1:{server.port}', 'REPORT_FILE': str(report), 'CI': '1'}
        try:
            done = subprocess.run(['npx', 'playwright', 'test', '--config', 'playwright.config.js', f'dom1-tests/{spec}'],
                                  cwd=HARNESS, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {}, 'harness timeout'
    finally:
        server.close()
    if not report.exists():
        return {}, ANSI.sub('', (done.stderr or done.stdout)[-1200:])
    data = json.loads(report.read_text())
    results = {}

    def walk(suite):
        for sp in suite.get('specs', []):
            statuses = [r['status'] for t in sp.get('tests', []) for r in t.get('results', [])]
            results[sp['title']] = 'passed' if statuses and all(s == 'passed' for s in statuses) else (statuses[-1] if statuses else 'failed')
        for child in suite.get('suites', []):
            walk(child)
    for suite in data.get('suites', []):
        walk(suite)
    return results, ''


def grade(folder, task, report):
    results, note = run_spec(folder, task['spec'], report)
    passed = sum(v == 'passed' for v in results.values())
    return {'passed': passed, 'total': len(results), 'all_passed': bool(results) and passed == len(results), 'tests': results, 'note': note}
