"""Reconstruct both November 21 comparisons from frozen records and official reports."""
import argparse
from collections import Counter
from pathlib import Path

from studies.ledger_read import calls, totals
from studies.study_io import ROOT, cases_by_file, dump, read, sha

OUTPUT = ROOT / 'studies/results/library-sources-20261121.json'
ARMS = ('reference', 'ai', 'direct')


def browser_result(report, target):
    raw = read(report)
    assert not [error for error in raw.get('errors', []) if 'maximum allowed failures' not in error.get('message', '')]
    cases = cases_by_file(raw)
    assert set(cases) == {target} and cases[target]
    statuses = [s for case in cases[target] for s in case['statuses']]
    if 'failed' in statuses or 'timedOut' in statuses:
        return False
    assert all(case['passed'] for case in cases[target])
    return True


def reconstruct(project):
    form = project == 'form'
    stage = ROOT / 'artifacts' / ('form-library-sources-20261121' if form else 'svg-chart-sources-20261121')
    freeze = read(stage / 'freeze.json')
    for name, checksum in (freeze if form else freeze['inputs']).items():
        assert sha(ROOT / name) == checksum, name
    result = read(stage / 'results.json')
    ledger = totals(stage / 'budget.sqlite3')
    assert result['ledger'] == ledger
    ledgers = [stage / 'budget.sqlite3']
    if (stage / 'continuation/budget.sqlite3').exists():
        ledgers.append(stage / 'continuation/budget.sqlite3')
        extra = totals(ledgers[-1])
        ledger = {key:round(ledger[key] + extra[key], 6) for key in ('calls', 'settled_usd', 'exposure_usd', 'unsettled_calls')}
        assert ledger['exposure_usd'] <= 2.95
        assert read(stage / 'continuation/freeze.json')['source'] == sha(Path(__file__).with_name('resume.py'))

    records = read(stage / 'generation-complete.json')
    targets = list(range(1, 21)) if form else [4, 8, 12, 16, 20]
    assert len(records) == len(result['rows']) == len(ARMS) * len(targets)
    cells = {arm:{} for arm in ARMS}
    for record, row in zip(records, result['rows'], strict=True):
        arm, task = row['arm'], row['task']
        assert (record['arm'], record['task']) == (arm, task)
        n = int(str(task).removeprefix('task-'))
        assert n in targets and str(n) not in cells[arm]
        target = f'task-{n}'
        folder = (stage if form else stage / 'runs') / arm / target
        entry = {'passed': row['passed'], 'generated': record['generated']}
        if record.get('files'):
            assert all(sha(folder / 'page' / name) == h for name, h in record['files'].items())
            report = folder / 'official/report.json' if form else stage / 'scores' / arm / target / 'report.json'
            assert browser_result(report, target) is row['passed']
            entry.update(status='browser', report=str(report.relative_to(ROOT)), sha256=sha(report))
        else:
            is_failure = record['generated'] or record.get('builder_failed', False)
            assert row['passed'] is (False if is_failure else None)
            entry['status'] = 'invalid_output' if record['generated'] else ('failed_build' if is_failure else 'missing')
        cells[arm][str(n)] = entry
    accounting = {}
    receipts = {c['id']:c for path in ledgers for c in calls(path)}
    for call in receipts.values():
        arm = call['purpose']
        summary = accounting.setdefault(arm, Counter())
        summary['calls'] += 1
        summary['settled_micro_usd'] += call['actual'] or 0
        summary['exposure_micro_usd'] += call['actual'] if call['actual'] is not None else call['reserved']
    for response in stage.rglob('response.json'):
        if 'node_modules' in response.parts:
            continue
        request = read(response.with_name('request.json'))
        arm = receipts[request['call_id']]['purpose']
        usage = read(response)['usage']
        for name in ('prompt_tokens','completion_tokens'):
            accounting[arm][name] += usage[name]
    data = {'targets':targets,'generator':'mistralai/mistral-small-3.2-24b-instruct','ai_builder':'openai/gpt-5',
            'cells':cells,'ledger':ledger,'by_purpose':accounting, 'freeze_sha256':sha(stage / 'freeze.json'),
            'generation_sha256':sha(stage / 'generation-complete.json')}
    if form:
        data['ai_library_origin'] = 'artifacts/interface-blind-build-2/libraries/form/openai__gpt-5'
        data['historical_successful_build_receipt_usd'] = read(ROOT / data['ai_library_origin'] / 'call-0/response.json')['usage']['cost']
        history = []
        for stage_name in ('interface-blind-build', 'interface-blind-build-2'):
            old = ROOT / 'artifacts' / stage_name
            receipts = {c['id']:c for c in calls(old / 'budget.sqlite3')}
            for request in (old / 'libraries/form/openai__gpt-5').glob('call-*/request.json'):
                history.append(receipts[read(request)['call_id']])
        data['historical_form_build'] = {
            'calls':len(history),
            'settled_micro_usd':sum(c['actual'] or 0 for c in history),
            'exposure_micro_usd':sum(c['actual'] if c['actual'] is not None else c['reserved'] for c in history),
            'unknown_calls':sum(c['actual'] is None for c in history),
        }
    else:
        data['fixed_reference'] = {str(n):browser_result(stage / 'scores/fixed-reference' / f'task-{n}/report.json', f'task-{n}') for n in targets}
        assert list(data['fixed_reference'].values()) == result['fixed_reference']
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = {p:reconstruct(p) for p in ('form','svg-chart')}
    if args.write:
        dump(OUTPUT, report)
    assert report == read(OUTPUT)
    for project, stage in report.items():
        print(project, {arm:sum(cell['passed'] is True for cell in cells.values()) for arm,cells in stage['cells'].items()}, stage['ledger'])
