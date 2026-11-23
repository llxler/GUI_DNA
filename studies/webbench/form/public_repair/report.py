"""Read-only audit of the registered repair diagnostic and shared first responses."""
import argparse
from collections import Counter

from studies.form_library_sources.report import browser_result
from studies.form_public_repair.run import FIRST, OUT, ROOT
from studies.ledger_read import calls, totals
from studies.study_io import read, dump, sha

OUTPUT = ROOT / 'studies/results/form-public-repair-20261121.json'


def reconstruct():
    result = read(OUT / 'results.json')
    assert result['ledger'] == totals(OUT / 'budget.sqlite3')
    for path, digest in read(OUT / 'freeze.json')['inputs'].items():
        assert sha(ROOT / path) == digest
    originals = read(FIRST / 'results.json')['rows']
    first_records = read(FIRST / 'generation-complete.json')
    repairs = read(OUT / 'generation-complete.json')
    assert len(originals) == len(result['rows']) == len(repairs) == len(first_records) == 60
    rows = []
    accounting = {}
    for receipt in calls(OUT / 'budget.sqlite3'):
        data = accounting.setdefault(receipt['purpose'],Counter())
        data['calls'] += 1
        data['settled_micro_usd'] += receipt['actual'] or 0
        data['exposure_micro_usd'] += receipt['actual'] if receipt['actual'] is not None else receipt['reserved']
    for before, first, repair, after in zip(originals, first_records, repairs, result['rows'], strict=True):
        arm, task = before['arm'],before['task']
        assert all((r['arm'],r['task']) == (arm,task) for r in (first, repair, after))
        expected_reuse = not first['generated'] or 'files' in first
        assert after['reused'] == expected_reuse
        row = {'arm':arm,'task':task,'first':before['passed'],'after':after['passed'],'reused':expected_reuse}
        if expected_reuse:
            assert before['passed'] is after['passed']
        else:
            folder = OUT / arm / task
            messages = read(folder / 'call/request.json')['body']['messages']
            old = FIRST / arm / task / 'call'
            assert messages[:-2] == read(old / 'request.json')['body']['messages']
            assert messages[-2]['content'] == read(old / 'response.json')['choices'][0]['message']['content']
            assert messages[-1]['content'] == 'Public format/compiler feedback: '+first['error']+'\nReturn the complete corrected JSON output. No behavioral feedback is available.'
            if (folder / 'call/response.json').exists():
                usage = read(folder / 'call/response.json')['usage']
                for name in ('prompt_tokens','completion_tokens'):
                    accounting[arm][name] += usage[name]
            if 'files' in repair:
                assert all(sha(folder / 'page' / name) == h for name,h in repair['files'].items())
                report = folder / 'official/report.json'
                assert after['passed'] is browser_result(report, task)
                row.update(report=str(report.relative_to(ROOT)),sha256=sha(report))
            else:
                assert after['passed'] is (False if repair['generated'] else None)
        rows.append(row)
    return {'rows': rows, 'ledger':result['ledger'], 'by_arm':accounting,'freeze_sha256':sha(OUT / 'freeze.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args = parser.parse_args()
    result = reconstruct()
    if args.write:
        dump(OUTPUT,result)
    assert read(OUTPUT) == result
    print(result['ledger'])
