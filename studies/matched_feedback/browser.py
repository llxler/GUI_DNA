"""Unchanged official assertions with separate public and withheld file sets."""
import re
import threading
from studies import browser_jobs
from .core import OUT, ROOT, read, dump

BOM_LOCK = threading.Lock()


def grade(project, page, specs, key, calibration=False):
    browser_jobs.OUT = OUT
    job = {'project': project, 'harness': '157-' + project, 'runtime': '157',
        'page': str(page.relative_to(ROOT)), 'files': browser_jobs.source_files(page),
        'specs': list(specs), 'all_tests': False}
    if project == 'bom':
        with BOM_LOCK:
            return browser_jobs.grade(key, job, calibration)
    return browser_jobs.grade(key, job, calibration)


def public_feedback(project, page, key):
    from .core import PUBLIC
    feedback, reports = [], {}
    for spec in PUBLIC:
        result = grade(project, page, [spec], key + '/' + spec)
        reports[spec] = result
        if result['all_passed']:
            continue
        raw = read(OUT / 'scores' / key / spec / 'report.json')
        stack = list(raw.get('suites', [])); failures = []
        while stack:
            suite = stack.pop(); stack += suite.get('suites', [])
            for item in suite.get('specs', []):
                for test in item.get('tests', []):
                    for attempt in test.get('results', []):
                        if attempt['status'] in ('failed', 'timedOut'):
                            message = re.sub(r'\x1b\[[0-9;]*m', '', attempt.get('error', {}).get('message', ''))
                            failures.append({'title': item['title'], 'error': message[:1800]})
        assert failures, 'No decisive public failure'
        feedback.append({'file': spec, 'failures': failures[:1]})
    return feedback, reports
