"""Verify saved outcomes against raw Playwright reports, without rerunning tests."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from .core import ROOT, dump


def verify_report(outcome, path):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == outcome['report_sha256'], path
    report = json.loads(raw)
    errors = [e for e in report.get('errors', [])
              if 'maximum allowed failures' not in e.get('message', '')]
    assert not errors, (path, errors)
    statuses = []

    def visit(suite):
        for spec in suite.get('specs', []):
            for case in spec.get('tests', []):
                attempts = [item['status'] for item in case.get('results', [])]
                statuses.append('passed' if attempts and all(s == 'passed' for s in attempts)
                                else attempts[-1] if attempts else 'missing')
        for child in suite.get('suites', []):
            visit(child)

    for suite in report.get('suites', []):
        visit(suite)
    complete = bool(statuses) and all(s == 'passed' for s in statuses)
    assert complete or any(s in ('failed', 'timedOut') for s in statuses), path
    assert complete == outcome['all_passed'], path
    assert sum(s == 'passed' for s in statuses) == outcome['passed'], path
    assert len(statuses) == outcome['total_listed'], path
    return hashlib.sha256(raw).hexdigest()


def main():
    main_stage = ROOT / 'artifacts/webbench-expand-run'
    frontier = ROOT / 'artifacts/webbench-expand-frontier-2'
    controls = ROOT / 'artifacts/webbench-expand-controls'
    checked, reports = Counter(), {}
    for stage, expected in ((main_stage, 600), (frontier, 60)):
        paths = sorted((stage / 'runs').rglob('record.json'))
        assert len(paths) == expected
        for path in paths:
            record = json.loads(path.read_text())
            assert record['status'] == 'complete'
            hidden = json.loads(path.with_name('hidden.json').read_text())
            versions = record['versions']
            if not versions:
                assert hidden['first'] == hidden['final']
                assert hidden['final']['all_passed'] is False
                assert hidden['final']['reason'] == 'no executable version'
                checked['candidate_without_page'] += 1
            else:
                for label, version in (('first', versions[0]), ('final', versions[-1])):
                    report = path.parent / version / 'official-report.json'
                    reports[str(report.relative_to(ROOT))] = verify_report(hidden[label], report)
                checked['candidate_with_page'] += 1
            checked[stage.name + '/candidates'] += 1
    for folder, expected, name in ((controls / 'scores', 480, 'main_fixed_controls'),
                                   (frontier / 'fixed-final', 30, 'gpt5_fixed_final')):
        paths = sorted(folder.rglob('hidden.json'))
        assert len(paths) == expected, (folder, len(paths))
        for path in paths:
            outcome = json.loads(path.read_text())
            if 'report_sha256' in outcome:
                report = path.with_name('report.json')
                reports[str(report.relative_to(ROOT))] = verify_report(outcome, report)
            else:
                assert outcome['all_passed'] is False
                assert outcome['reason'] == 'No executable final plan'
                checked['control_without_page'] += 1
            checked[name] += 1
    summary = {'all_passed': True, 'counts': dict(checked),
               'distinct_raw_reports': len(reports), 'reports_sha256': reports,
               'scope': 'Read-only reconciliation of saved candidate/control outcomes with raw official reports. No browser reruns, model calls, or selective changes.'}
    dump(ROOT / 'test/results/webbench-expand-score-audit.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'reports_sha256'}, indent=2))


if __name__ == '__main__':
    main()
