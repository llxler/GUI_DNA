"""Verify the generation boundary and score each saved final canvas candidate."""
from concurrent.futures import ThreadPoolExecutor
from .browser import OUT, TASKS, score
from .run import GROUPS
from studies.study_io import ROOT, read, dump, sha, now


def verify(manifest):
    for path, expected in read(manifest)['sha256'].items():
        assert sha(ROOT / path) == expected, path


def evaluate():
    verify(OUT/'protocol-freeze.json')
    verify(OUT/'generated.json')
    jobs = [(f'{arm}-{rep}', task) for arm, rep in GROUPS for task in TASKS]
    def one(item):
        group, task = item
        record = read(OUT/group/task/'result.json')
        key = group + '/' + task
        value = {'status': record['status'], 'passed': None, 'page': record.get('page')}
        if value['page']:
            value.update(score(ROOT/value['page'], task, key))
        elif record['status'] != 'missing':
            value['passed'] = False
        return key, value
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(one, jobs))
    dump(OUT/'evaluation.json', {'utc':now(), 'generated_sha256':sha(OUT/'generated.json'), 'results':results})


if __name__ == '__main__':
    evaluate()
