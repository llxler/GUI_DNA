"""Reconcile every completed recovery observation with the fixed prior cohort."""
from test.history_replay.run import ROOT, read, dump, sha, cases_by_file
from .run import OUT, PARENT, verify


def main():
    verify()
    inputs = read(OUT / 'inputs/inputs.json'); done = read(OUT / 'outputs/complete.json')
    assert done['jobs'] == len(inputs['jobs']) == 19
    assert done['inputs_sha256'] == sha(OUT / 'inputs/inputs.json')
    rows = []
    for job in inputs['jobs']:
        folder = OUT / 'outputs/scores' / job['id']; raw = read(folder / 'report.json')
        assert read(folder / 'receipt.json')['report_sha256'] == sha(folder / 'report.json')
        assert not [e for e in raw.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
        cases = cases_by_file(raw)
        passed = set(cases) == set(job['specs']) and all(cases.values()) and all(c['passed'] for group in cases.values() for c in group)
        assert passed or any(s in ('failed', 'timedOut') for group in cases.values() for c in group for s in c['statuses'])
        expected = read(ROOT / 'artifacts/history-replay-20261115/scores' / job['history_key'] / 'score.json')['all_passed'] if job['comparison'] == 'history' else job['expected']
        rows.append({**job, 'passed': passed, 'expected_observation': expected, 'matches': passed == expected, 'tests': cases})
    result = {'stage': str(OUT.relative_to(ROOT)), 'preserved_infrastructure_stage': str(PARENT.relative_to(ROOT)),
              'scope': '19 fixed original saved pages, fresh container userspace/browser/npm; same host kernel. Original launch failed before any page score; same image/inputs recovered with owner UID/GID. Not cross-machine, all-history, or an anonymous-zip browser reinstall.',
              'rows': rows, 'matched': sum(r['matches'] for r in rows), 'total': len(rows),
              'environment': read(OUT / 'outputs/environment.json'), 'image_id': read(OUT / 'image.json')['Id'],
              'base_image_digest': read(PARENT / 'snapshot.json')['base_image_digest'], 'recovery': read(OUT / 'recovery.json')}
    dump(ROOT / 'test/results/container-replay.json', result)
    print('Matched', result['matched'], '/', result['total'], flush=True)


if __name__ == '__main__': main()
