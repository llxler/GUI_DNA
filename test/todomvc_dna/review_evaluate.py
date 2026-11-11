"""Evaluate a task's unchanged official tests; stop after a counterexample for pass/fail only.

This evaluator is for the review-stage enumeration, not for the frozen main study.
Timeouts and assertions are unchanged. Skipped tests after a failure do not count as
passes, and partial test counts must not be interpreted as a test-level score.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import domain, evaluate


def grade(url, report, features):
    subset = domain.hidden_subset(features)
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    pattern = '|'.join(re.escape(title) + '$' for _, title in subset)
    env = {**evaluate.browser_env(), 'CANDIDATE_URL': url, 'REPORT_FILE': str(report), 'CI': '1'}
    command = ['node', str(evaluate.HARNESS / 'node_modules/@playwright/test/cli.js'), 'test',
               '--config', 'playwright.config.ts', '--workers=1', '--max-failures=1', '--grep', pattern,
               '--output', str(report.parent / 'playwright-output')]
    try:
        done = subprocess.run(command, cwd=evaluate.HARNESS, env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise RuntimeError('review harness timeout') from None
    if not report.exists():
        raise RuntimeError('review harness produced no report: ' + evaluate.ANSI.sub('', done.stderr[-1000:]))
    raw = json.loads(report.read_text())
    errors = [e for e in raw.get('errors', [])
              if e.get('message') != 'Testing stopped early after 1 maximum allowed failures.']
    if errors:
        raise RuntimeError('review harness global error: ' + str(errors)[:500])
    results = {}

    def walk(suite, path):
        for spec in suite.get('specs', []):
            runs = [r for test in spec.get('tests', []) for r in test.get('results', [])]
            status = runs[-1]['status'] if runs else 'skipped'
            results[(path[-1] if path else '', spec['title'])] = status
        for child in suite.get('suites', []):
            walk(child, path + [child['title']])

    for suite in raw.get('suites', []):
        walk(suite, [])
    selected = {f'{d} › {t}': results.get((d, t), 'missing') for d, t in subset}
    passed = sum(s == 'passed' for s in selected.values())
    failed = any(s in ('failed', 'timedOut') for s in selected.values())
    if not failed and passed != len(subset):
        raise RuntimeError('review harness has neither a counterexample nor a complete pass')
    return {'passed': passed, 'total': len(subset), 'all_passed': passed == len(subset), 'tests': selected,
            'note': '', 'short_circuit': True, 'test_counts_complete': all(s in ('passed', 'failed', 'timedOut') for s in selected.values())}
