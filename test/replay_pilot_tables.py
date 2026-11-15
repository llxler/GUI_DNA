"""Reconstruct the two historical pilot tables without a writable Ledger."""
from collections import defaultdict
import json
from pathlib import Path
from test.ledger_read import calls

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def checked_score(value):
    cases = value.get('cases', [])
    if not cases:
        assert not value.get('passed') and not value.get('behavior_passed')
        return
    field = 'behavior_passed' if 'behavior_passed' in value else 'passed'
    assert value[field] == all(c[field] for c in cases)
    base = [c for c in cases if c['kind'] == 'base']
    assert value['base_passed'] == sum(c[field] for c in base)
    assert value['base_total'] == len(base)


def score_from_file(folder, value, relative, alternate=None):
    path = folder / relative
    if not path.exists() and alternate is not None:
        path = folder / alternate
    if path.exists():
        assert json.loads(path.read_text()) == value, path
        checked_score(value)
        return str(path.resolve().relative_to(ROOT.resolve()))
    assert not value.get('cases') and not value.get('runnable'), path
    checked_score(value)
    return None


def reconstruct():
    reports, unavailable = set(), 0
    ledger = {r['id']: r for r in calls(ROOT / 'artifacts/budget.sqlite3')}
    original = read('artifacts/live/results.json')
    groups = defaultdict(list)
    for row in original['runs']:
        folder = ROOT / row['directory']
        record = read(folder / 'result.json')
        assert all(record[k] == row[k] for k in ('model', 'method', 'task_id', 'repetition', 'attempts'))
        path = score_from_file(folder, row['hidden'], 'hidden/evaluation.json')
        if path: reports.add(path)
        else: unavailable += 1
        groups[row['model'], row['method']].append(row)
    round1 = []
    for group in original['summary']:
        rows = groups[group['model'], group['method']]
        ids = {read(p)['call_id'] for r in rows for p in (ROOT / r['directory']).rglob('request.json')}
        assert ids.issubset(ledger)
        cost = sum(ledger[i]['actual'] or 0 for i in ids)
        metrics = {'n': len(rows), 'passed': sum(r['hidden']['passed'] for r in rows),
                   'base_passed': sum(r['hidden']['base_passed'] for r in rows),
                   'base_total': sum(r['hidden']['base_total'] for r in rows),
                   'repairs': sum(r['attempts'] - 1 for r in rows), 'generation_microusd': cost}
        assert all(group[k] == metrics[k] for k in ('n', 'passed', 'repairs'))
        assert round(group['generation_usd'] * 1e6) == cost
        assert abs(group['base_retention'] - metrics['base_passed'] / metrics['base_total']) < 1e-12
        round1.append({'model': group['model'], 'method': group['method'], **metrics})

    groups = defaultdict(list)
    n_round2 = 0
    for name in ('followup', 'linked-control', 'compact-pair'):
        for row in read(f'artifacts/{name}/results.json')['runs']:
            n_round2 += 1
            folder = ROOT / row['directory']
            record = read(folder / 'result.json')
            assert all(record[k] == row[k] for k in ('model', 'method', 'task_id', 'repetition', 'attempts'))
            for label in ('first_hidden', 'hidden'):
                same_page = bool(row['versions']) and row['versions'][0]['app_sha256'] == row['versions'][-1]['app_sha256']
                path = score_from_file(folder, row[label], label + '/evaluation.json',
                                       'first_hidden/evaluation.json' if same_page and label == 'hidden' else None)
                if path: reports.add(path)
                else: unavailable += 1
            groups[row['model'], row['method']].append(row)
    round2 = []
    for group in read('artifacts/followup/combined-results.json')['summary']:
        rows = groups[group['model'], group['method']]
        metrics = {'n': len(rows), 'first_passed': sum(r['first_hidden']['behavior_passed'] for r in rows),
                   'passed': sum(r['hidden']['behavior_passed'] for r in rows)}
        assert all(group[k] == v for k, v in metrics.items())
        round2.append({'model': group['model'], 'method': group['method'], **metrics})

    linked = read('artifacts/linked-plan-posthoc/results.json')
    groups = defaultdict(list)
    for row in linked['runs']:
        folder = ROOT / row['directory']
        for label in ('first', 'final'):
            versions = row['versions']
            same_page = bool(versions) and versions[0].get('app_sha256') == versions[-1].get('app_sha256')
            path = score_from_file(folder, row[label]['hidden'], label + '/hidden/evaluation.json',
                                   'first/hidden/evaluation.json' if label == 'final' and same_page else None)
            if path: reports.add(path)
            else: unavailable += 1
        groups[row['model'], row['method']].append(row)
    posthoc = []
    for group in linked['summary']:
        rows = groups[group['model'], group['source_method']]
        metrics = {label: sum(r[label]['hidden']['behavior_passed'] for r in rows) for label in ('first', 'final')}
        assert len(rows) == group['n']
        assert all(group[k]['behavior_passed'] == v for k, v in metrics.items())
        posthoc.append({'model': group['model'], 'source_method': group['source_method'], 'n': len(rows), **metrics})
    return {'all_passed': True, 'round1_candidates': len(original['runs']), 'round2_candidates': n_round2,
            'posthoc_replays': len(linked['runs']), 'raw_evaluation_files': len(reports),
            'nonexecutable_endpoint_records': unavailable, 'round1': round1, 'round2': round2, 'posthoc': posthoc,
            'scope': 'Historical pilot table counts from per-case saved evaluations and candidate records; round-1 generation fees from read-only ledger/request identities. Identical first/final pages reuse reports; absent executable outputs remain failures. No browser rerun or modification of frozen source, linker or main ledger. Surrounding prose and every token/timing claim are not all reconstructed here.'}


if __name__ == '__main__':
    result = reconstruct()
    (ROOT / 'test/results/pilot-tables-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print({k: result[k] for k in ('round1_candidates', 'round2_candidates', 'posthoc_replays', 'raw_evaluation_files', 'nonexecutable_endpoint_records')})
