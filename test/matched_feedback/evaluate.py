"""Score first/final response and immutable controls after all generation."""
from concurrent.futures import ThreadPoolExecutor
from .core import *
from .browser import grade
from test.history_replay.run import source_files


def main():
    verify()
    complete = read(OUT / 'generation-complete.json')
    assert complete['candidate_snapshot_sha256'] == sha(OUT / 'candidate-snapshot.json')
    for path, expected in read(OUT / 'candidate-snapshot.json')['sha256'].items():
        assert sha(ROOT / path) == expected, path
    assert not (OUT / 'grading-started.json').exists()
    specs = {'current': ['task-20'], 'withheld': read(OUT / 'inputs.json')['withheld'],
        'history': ['init', *[f'task-{i}' for i in range(1,21)]]}
    rows, unique = [], {}
    for job in jobs():
        folder = ROOT / job['folder']; record = read(folder / 'record.json')
        assert record['status'] == 'complete'
        for label, attempt in [('first', record['attempts'][0]), ('final', record['attempts'][-1])]:
            page = folder / attempt['version'] if attempt['version'] else None
            for endpoint, tests in specs.items():
                key = digest([job['project'], source_files(page), tests]) if page else None
                rows.append({**job, 'label': label, 'endpoint': endpoint, 'score_key': key})
                if key:
                    unique[key] = {'project': job['project'], 'page': str(page.relative_to(ROOT)), 'specs': tests,
                        'files': source_files(page)}
    for control in read(OUT / 'inputs.json')['controls']:
        page = ROOT / control['folder']
        for endpoint, tests in specs.items():
            key = digest([control['project'], source_files(page), tests])
            rows.append({**control, 'method': 'fixed_example', 'label': 'control', 'endpoint': endpoint, 'score_key': key})
            unique[key] = {'project': control['project'], 'page': str(page.relative_to(ROOT)), 'specs': tests, 'files': source_files(page)}
    dump(OUT / 'evaluation-inputs.json', {'rows': rows, 'jobs': unique})
    dump(OUT / 'grading-started.json', {'started_utc': now(), 'inputs_sha256': sha(OUT / 'evaluation-inputs.json'),
        'generation_sha256': sha(OUT / 'generation-complete.json')})
    def one(item):
        key, job = item
        assert source_files(ROOT / job['page']) == job['files']
        grade(job['project'], ROOT / job['page'], job['specs'], 'heldout/' + key)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i, _ in enumerate(pool.map(one, unique.items()), 1):
            if i % 10 == 0 or i == len(unique): print('scored', i, '/', len(unique), flush=True)
    dump(OUT / 'evaluation-complete.json', {'finished_utc': now(), 'inputs_sha256': sha(OUT / 'evaluation-inputs.json'),
        'comparisons': len(rows), 'reports': len(unique)})


if __name__ == '__main__':
    main()
