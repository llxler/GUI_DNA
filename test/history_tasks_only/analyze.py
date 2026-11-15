"""Summarize the posthoc task-file history endpoint from retained reports."""
from collections import defaultdict
from .run import ROOT, ORIGINAL, OUT, read, dump, sha, digest, cases_by_file, observed, verify


def main():
    inputs = verify()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    original = read(ROOT / 'test/results/history-replay.json')
    outcomes = {}
    for key, decision in inputs['decisions'].items():
        path = ROOT / decision['old_report']
        assert sha(path) == decision['old_report_sha256']
        passed, reason = observed(cases_by_file(read(path)), decision['specs'])
        assert passed == decision['observed'] and reason == decision['reason']
        if passed is None:
            path = OUT / 'scores' / key / 'report.json'
            score = read(path.with_name('score.json'))
            assert sha(path) == score['report_sha256']
            passed, _ = observed(cases_by_file(read(path)), decision['specs'])
            assert passed is not None and passed == score['all_passed']
        outcomes[key] = bool(passed)
    rows = []
    for row in original['rows']:
        passed = outcomes[row['score_key']] if row['score_key'] else False
        assert not row['history_passed'] or passed
        rows.append({**row, 'task_history_passed': passed,
                     'new_report_used': row['score_key'] in inputs['jobs']})
    groups = []
    for dimensions in (('cohort', 'method', 'label'), ('cohort', 'project', 'method', 'label')):
        buckets = defaultdict(list)
        for row in rows:
            buckets[tuple(row[k] for k in dimensions)].append(row)
        for key, selected in buckets.items():
            groups.append({**dict(zip(dimensions, key)), 'n': len(selected),
                           'level': 'overall' if len(dimensions) == 3 else 'project',
                           'old_current_available': sum(r['old_current_passed'] is not None for r in selected),
                           'old_current_passed': sum(bool(r['old_current_passed']) for r in selected),
                           'history_passed': sum(r['history_passed'] for r in selected),
                           'task_history_passed': sum(r['task_history_passed'] for r in selected),
                           'old_current_pass_task_history_fail': sum(r['old_current_passed'] is True and not r['task_history_passed'] for r in selected),
                           'old_current_fail_task_history_pass': sum(r['old_current_passed'] is False and r['task_history_passed'] for r in selected),
                           'new_report_endpoints': sum(r['new_report_used'] for r in selected)})
    result = {'posthoc': True, 'scope': inputs['scope'], 'comparisons': len(rows),
              'new_reports': len(inputs['jobs']), 'reused_decisive_reports': len(inputs['decisions']) - len(inputs['jobs']),
              'groups': groups, 'rows': rows}
    dump(ROOT / 'test/results/history-tasks-only.json', result)
    print('Task-file history:', len(rows), 'endpoints;', result['new_reports'], 'new reports.')
    for g in groups:
        if g['level'] == 'overall' and g['label'] == 'final':
            print(g['cohort'], g['method'], g['n'], g['old_current_passed'], g['history_passed'], g['task_history_passed'])


if __name__ == '__main__':
    main()
